import os
import asyncio
import time
from typing import Dict
from aiohttp import web

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

        self.load_plugin_config()
        await self.search_devices()

        self.event_loop()

        return True

    def load_plugin_config(self):
        self._mad_parts['logger'].info('load_plugin_config')
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
        self._mad_parts['logger'].info(self._config)

    async def search_devices(self):
        self._mad_parts['logger'].info('search_devices')

        self._devices = []
        async with self._mad_parts["db_wrapper"] as session, session:
            for settingsDevice in await SettingsDeviceHelper.get_all(session, self._instance):
                device = {}
                device['id'] = settingsDevice.device_id
                device['name'] = settingsDevice.name
                device['power-toggle'] = 0
                self._devices.append(device)

        self._mad_parts['logger'].info(self._devices)

    async def refresh_devices(self):
        self._logger.debug('refresh_devices')

        self._logger.debug(self._mad_parts['mitm_mapper'].get_injection_status('ATV06'))
        #mitm_stats = json.loads(self._mad_parts['mitm_receiver_process'].status(None, None))['origin_status']


    async def madqtt(self):
        while True:
            self._mad_parts['logger'].info('doing MADqtt things')

            await refresh_devices()
            await asyncio.sleep(self._config['timeouts']['check'])


    def event_loop(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.madqtt())
