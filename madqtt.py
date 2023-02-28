import os
import asyncio
import datetime
import json
from typing import Dict
from aiohttp import web
import asyncio_mqtt as aiomqtt
import paho.mqtt as mqtt

import mapadroid.plugins.pluginBase
from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper

import importlib
register_custom_plugin_endpoints = importlib.import_module("plugins.mp-madqtt.endpoints").register_custom_plugin_endpoints

class MADqtt(mapadroid.plugins.pluginBase.Plugin):

    def _file_path(self) -> str:
        return os.path.dirname(os.path.abspath(__file__))

    def __init__(self, subapp_to_register_to: web.Application, mad_parts: Dict):
        super().__init__(subapp_to_register_to, mad_parts)

        self._rootdir = os.path.dirname(os.path.abspath(__file__))

        self.author = self._versionconfig.get("plugin", "author", fallback="ExXtReMe")
        self.url = self._versionconfig.get("plugin", "url", fallback="https://github.com/techolutions/mp-madqtt")
        self.description = self._versionconfig.get("plugin", "description", fallback="Plugin to restart not responding devices via MQTT")
        self.version = self._versionconfig.get("plugin", "version", fallback="0.2")
        self.pluginname = self._versionconfig.get("plugin", "pluginname", fallback="MADqtt")

        self._hotlink = [
            ("Plugin faq", "pluginfaq", "Create own plugin"),
            ("Plugin Example", "example", "Testpage"),
            ("Readme", "readme", "Readme Page"),
        ]

        if self._pluginconfig.getboolean("plugin", "active", fallback=False):
            register_custom_plugin_endpoints(self._plugin_subapp)

            for name, link, description in self._hotlink:
                self._mad_parts['madmin'].add_plugin_hotlink(name, link.replace("/", ""),
                                                       self.pluginname, self.description, self.author, self.url,
                                                       description, self.version)

    async def _perform_operation(self):
        if self._mad_parts['args'].config_mode:
            return False

        self._instance = self._mad_parts["db_wrapper"].get_instance_id()
        self._mad_parts['logger'].info('plugin is running on instance {0}'.format(self._instance))

        await self.search_devices()
        await self.load_config()

        self.event_loop()

        return True

    async def load_config(self):
        self._mad_parts['logger'].info('load_plugin_config')
        self._config = {
            'timeouts': {
                'mitm': int(self._pluginconfig.get('timeouts', 'mitm', fallback=600)),
                'proto': int(self._pluginconfig.get('timeouts', 'proto', fallback=600)),
                'restart': int(self._pluginconfig.get('timeouts', 'restart', fallback=900)),
                'check': int(self._pluginconfig.get('timeouts', 'check', fallback=60))
            },
            'mqtt': {
                'host': self._pluginconfig.get('mqtt', 'host', fallback='localhost'),
                'port': int(self._pluginconfig.get('mqtt', 'port', fallback=1883)),
                'user': self._pluginconfig.get('mqtt', 'user', fallback=None),
                'pass': self._pluginconfig.get('mqtt', 'pass', fallback=None),
                'ssl': self._pluginconfig.getboolean("mqtt", "ssl", fallback=False),
                'client-id': self._pluginconfig.get('mqtt', 'client-id', fallback='madqtt-client')
            },
            'devices': {}
        }

        # load device config if present
        for device in self._devices:
            section = 'device.{0}'.format(device['origin'])
            self._mad_parts['logger'].info('read device config from section {0}'.format(section))

            self._config['devices'][device['origin']] = {
                'active': self._pluginconfig.getboolean(section, "active", fallback=False),
                'mode': self._pluginconfig.get(section, "mode", fallback=None)
            }

            ## load mqtt specific settings
            if (self._config['devices'][device['origin']]['mode'] == 'mqtt'):
                self._config['devices'][device['origin']] = {
                    'topic-pub': self._pluginconfig.get(section, "topic-pub", fallback=None),
                    'topic-sub': self._pluginconfig.get(section, "topic-sub", fallback=None),
                    'payload-on': self._pluginconfig.get(section, "payload-on", fallback='ON'),
                    'payload-off': self._pluginconfig.get(section, "payload-off", fallback='OFF'),
                }

        self._mad_parts['logger'].info(self._config)

    # async def save_plugin_config(self):
    #     self._mad_parts['logger'].info('save_plugin_config')
    #     self._pluginconfig.set('timeouts', 'check', '30')
    #
    #     with open(self._rootdir + "/plugin.ini", "w") as configfile:
    #         self._pluginconfig.write(configfile)
    #
    #     self.load_plugin_config()

    async def search_devices(self):
        self._mad_parts['logger'].info('search_devices')

        self._devices = []
        async with self._mad_parts["db_wrapper"] as session, session:
            for settingsDevice in await SettingsDeviceHelper.get_all(session, self._instance):
                device = {}
                device['id'] = settingsDevice.device_id
                device['origin'] = settingsDevice.name
                self._devices.append(device)

        self._mad_parts['logger'].info(self._devices)

    # async def refresh_devices(self):
    #     self._mad_parts['logger'].info('refresh_devices')
    #
    #     for device in self._devices:
    #         device['injected'] = await self._mad_parts['mitm_mapper'].get_injection_status(device['origin'])
    #
    #         async with self._mad_parts["db_wrapper"] as session, session:
    #             trsStatus: Optional[TrsStatus] = await TrsStatusHelper.get(session, device['id'])
    #             if trsStatus:
    #                 device['idle'] = trsStatus.idle
    #                 device['proto-time'] = trsStatus.lastProtoDateTime
    #                 device['sleep-time'] = trsStatus.currentSleepTime
    #                 device['softban-time'] = trsStatus.last_softban_action
    #             else:
    #                 device['idle'] = None
    #                 device['proto-time'] = None
    #                 device['sleep-time'] = None
    #                 device['softban-time'] = None
    #
    #     self._mad_parts['logger'].info(self._devices)

    async def madqtt_runner(self):
        while True:
            self._mad_parts['logger'].info('searching for devices that need a reboot')

            await self._client.publish(self._config['device.ATV06']['topic-pub'], payload=self._config['device.ATV06']['payload-off'])
            await asyncio.sleep(1)
            await self._client.publish(self._config['device.ATV06']['topic-pub'], payload=self._config['device.ATV06']['payload-on'])
            # await self.refresh_devices()
            # for device in self._devices:
            #     if device['state'] == 'off':
            #         # turned off devices should be skipped
            #         self._mad_parts['logger'].info('{0} has been skipped, because it\'s off'.format(device['origin']))
            #     elif device['idle'] == 1:
            #         # paused devices should be skipped
            #         self._mad_parts['logger'].info('{0} has been skipped, because it\'s paused'.format(device['origin']))
            #
            #     elif (datetime.datetime.now(datetime.timezone.utc) - device['power-time']) < datetime.timedelta(seconds=self._config['timeouts']['restart']):
            #         # recently restarted devices sholud be skipped
            #         self._mad_parts['logger'].info('{0} has been skipped, because it\'s recently (re)started'.format(device['origin']))
            #     elif (device['injected'] == False and self.elapsed_seconds(device['data-time']) > self._config['timeouts']['mitm']) or (self.elapsed_seconds(device['proto-time'] + device['sleep-time']) > self._config['timeouts']['proto']):
            #         self._logger.info('device {0} will be restarted'.format(device['origin']))
            #         self.device_command(device['origin'], 'restart')
            #         time.sleep(1)

            await asyncio.sleep(self._config['timeouts']['check'])

    async def mqtt_listener(self):
        reconnect_interval = 10
        while True:
            try:
                async with aiomqtt.Client(self._config['mqtt']['host'],port=self._config['mqtt']['port'],username=self._config['mqtt']['user'],password=self._config['mqtt']['pass']) as client:
                    self._client = client
                    async with client.messages() as messages:
                        await client.subscribe('#')
                        async for message in messages:
                            self._mad_parts['logger'].info(message.payload.decode())
            except aiomqtt.MqttError as error:
                self._mad_parts['logger'].info('mqtt error {0}, trying to reconnect in {1} seconds.'.format(error, reconnect_interval))
                await asyncio.sleep(reconnect_interval)

    def event_loop(self):
        #loop = asyncio.get_event_loop()
        #loop.create_task(self.madqtt())
        asyncio.create_task(self.mqtt_listener())
        asyncio.create_task(self.madqtt_runner())
