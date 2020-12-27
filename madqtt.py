import mapadroid.utils.pluginBase
from flask import render_template, Blueprint, request, jsonify
from mapadroid.madmin.functions import auth_required
import os

from mapadroid.utils.logging import get_logger, LoggerEnums
from threading import Thread
import json
import paho.mqtt.client as mqtt
import time
import re
import sys


class Madqtt(mapadroid.utils.pluginBase.Plugin):

    def __init__(self, mad):
        super().__init__(mad)

        self._rootdir = os.path.dirname(os.path.abspath(__file__))

        self._mad = mad

        self._pluginconfig.read(self._rootdir + "/plugin.ini")
        self._versionconfig.read(self._rootdir + "/version.mpl")
        self.author = self._versionconfig.get("plugin", "author", fallback="unknown")
        self.url = self._versionconfig.get("plugin", "url", fallback="https://www.maddev.eu")
        self.description = self._versionconfig.get("plugin", "description", fallback="unknown")
        self.version = self._versionconfig.get("plugin", "version", fallback="unknown")
        self.pluginname = self._versionconfig.get("plugin", "pluginname", fallback="https://www.maddev.eu")
        self.staticpath = self._rootdir + "/static/"
        self.templatepath = self._rootdir + "/template/"

        self._routes = [
            ("/madqtt", self.ui_overview, ['GET']),
            ("/madqtt/readme", self.ui_readme, ['GET']),
            ("/madqtt/api/state", self.api_state, ['GET']),
            ("/madqtt/api/devices/<device>", self.api_devices, ['POST']),
        ]

        self._hotlink = [
            ("Overview", "/madqtt", "MADqtt Overview"),
            ("Readme", "/madqtt/readme", "Readme Page"),
        ]

        if self._pluginconfig.getboolean("plugin", "active", fallback=False):
            self._plugin = Blueprint(str(self.pluginname), __name__, static_folder=self.staticpath,
                                     template_folder=self.templatepath)

            for route, view_func, methods in self._routes:
                self._plugin.add_url_rule(route, route.replace("/", ""), view_func=view_func, methods=methods)

            for name, link, description in self._hotlink:
                self._mad['madmin'].add_plugin_hotlink(name, self._plugin.name+"."+link.replace("/", ""),
                                                       self.pluginname, self.description, self.author, self.url,
                                                       description, self.version)

    def perform_operation(self):

        # do not change this part ▽▽▽▽▽▽▽▽▽▽▽▽▽▽▽
        if not self._pluginconfig.getboolean("plugin", "active", fallback=False):
            return False
        self._mad['madmin'].register_plugin(self._plugin)
        # do not change this part △△△△△△△△△△△△△△△

        # load your stuff now
        self._logger = get_logger(LoggerEnums.plugin, 'madqtt')

        # do not start plugin when in config mode
        if self._mad['args'].config_mode == True:
            self._logger.warning('not active while in configmode')
            return False

        self._logger.info('plugin is running')
        self._logger.debug('loading pluginconfig')
        self._config = {
            'topic': self._pluginconfig.get('mqtt', 'topic', fallback='madqtt'),
            'broker': {
                'host': self._pluginconfig.get('broker', 'host', fallback='localhost'),
                'port': int(self._pluginconfig.get('broker', 'port', fallback=1883)),
                'user': self._pluginconfig.get('broker', 'user', fallback=None),
                'pass': self._pluginconfig.get('broker', 'pass', fallback=None)
            },
            'timeouts': {
                'mitm': int(self._pluginconfig.get('timeouts', 'mitm', fallback=600)),
                'proto': int(self._pluginconfig.get('timeouts', 'proto', fallback=600)),
                'restart': int(self._pluginconfig.get('timeouts', 'restart', fallback=900)),
                'check': int(self._pluginconfig.get('timeouts', 'check', fallback=60))
            }
        }

        self._devices = []
        for item in self._mad['db_wrapper'].download_status():
            device = {}
            device['origin'] = item['name']
            device['state'] = None
            device['restart-time'] = int(time.time())
            self._devices.append(device)
        self.refresh_devices()

        mqttListener = Thread(name='MqttListener', target=self.mqttListener)
        mqttListener.daemon = True
        mqttListener.start()

        madqttRunner = Thread(name='MadqttRunner', target=self.madqttRunner)
        madqttRunner.daemon = True
        madqttRunner.start()

        return True

    def madqttRunner(self):
        while True:
            self._logger.info('searching for devices that need a reboot')
            self.refresh_devices()

            for device in self._devices:
                if device['state'] == 'off':
                    # turned off devices should be skipped
                    self._logger.debug('device {0} has been skipped, because it\'s off'.format(device['origin']))
                elif device['mode'] == 'Idle':
                    # paused devices should be skipped
                    self._logger.debug('device {0} has been skipped, because it\'s paused'.format(device['origin']))
                elif self.elapsed_seconds(device['restart-time']) < self._config['timeouts']['restart']:
                    # recently restarted devices sholud be skipped
                    self._logger.debug('device {0} has been skipped, because it\'s recently (re)started'.format(device['origin']))
                elif (device['injected'] == False and self.elapsed_seconds(device['data-time']) > self._config['timeouts']['mitm']) or (self.elapsed_seconds(device['proto-time'] + device['sleep-time']) > self._config['timeouts']['proto']):
                    self._logger.info('device {0} will be restarted'.format(device['origin']))
                    self.device_command(device['origin'], 'restart')
                    time.sleep(1)

            time.sleep(self._config['timeouts']['check'])

    def mqttListener(self):
        self._client = mqtt.Client()
        self._client.on_connect = self.on_connect
        self._client.on_disconnect = self.on_disconnect
        self._client.on_message = self.on_message

        if self._config['broker']['user'] != None:
            self._client.username_pw_set(self._config['broker']['user'], self._config['broker']['pass'])

        self._client.connect(self._config['broker']['host'], self._config['broker']['port'], 30)
        self._client.loop_forever(retry_first_connection=True)

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._logger.success('connection to mqtt-broker "{0}:{1}" was successful'.format(self._config['broker']['host'], self._config['broker']['port']))
            self._logger.debug('subscribing to topic "{0}/#"'.format(self._config['topic']))
            client.subscribe('{0}/#'.format(self._config['topic']))
            client.message_callback_add('{0}/+'.format(self._config['topic']), self.on_device)
            client.publish('{0}/command'.format(self._config['topic']), 'update')
        else:
            raise ConnectionError('connection to mqtt-broker "{0}:{1}" failed with rc {2}'.format(self._config['broker']['host'], self._config['broker']['port'], rc))

    def on_disconnect(self, client, userdata, rc):
        self._logger.warning('connection to mqtt-broker "{0}:{1}" was lost'.format(self._config['broker']['host'], self._config['broker']['port']))

    def on_message(self, client, userdata, message):
        pass

    def on_device(self, client, userdata, message):
        state = message.payload.decode('UTF-8')
        match = re.match(r'^{0}\/(.*)$'.format(self._config['topic']), message.topic).group(1)

        for device in self._devices:
            if device['origin'] == match:
                self._logger.debug('device {0} reported new state "{1}"'.format(device['origin'], state))
                device['state'] = state
                if state == 'on':
                    device['restart-time'] = int(time.time())
                break

    def device_command(self, device, command):
        self._logger.debug('publishing message "{2}" to topic "{0}/{1}/command"'.format(self._config['topic'], device, command))
        self._client.publish('{0}/{1}/command'.format(self._config['topic'], device), command)

    def refresh_devices(self):
        self._logger.debug('refreshing device informations')

        madmin_stats = self._mad['db_wrapper'].download_status()
        mitm_stats = json.loads(self._mad['mitm_receiver_process'].status(None, None))['origin_status']

        for device in self._devices:
            for item in madmin_stats:
                if item['name'] == device['origin']:
                    device['route'] = item['rmname']
                    device['mode'] = item['mode']
                    device['proto-time'] = item['lastProtoDateTime']
                    device['sleep-time'] = item['currentSleepTime']
                    break
            device['injected'] = mitm_stats[device['origin']]['injection_status']
            device['data-time'] = mitm_stats[device['origin']]['latest_data']

    def elapsed_seconds(self, timestamp):
        if isinstance(timestamp, int):
            return int(time.time()) - timestamp
        return sys.maxsize

    @auth_required
    def ui_overview(self):
        return render_template("overview.html", header="MADqtt Overview", title="MADqtt Overview")

    @auth_required
    def ui_readme(self):
        return render_template("readme.html", header="MADqtt Readme", title="MADqtt Readme")

    @auth_required
    def api_state(self):
        return jsonify(self._devices)

    @auth_required
    def api_devices(self, device):
        if not request.json:
            abort(400)
        else:
            if 'command' in request.json:
                self.device_command(device, request.json['command'])
                return '', 204
        abort(400)
