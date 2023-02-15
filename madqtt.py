import os
from typing import Dict
from aiohttp import web

import mapadroid.plugins.pluginBase
import importlib
register_custom_plugin_endpoints = importlib.import_module("plugins.mp-madqtt.endpoints").register_custom_plugin_endpoints

class MADqtt(mapadroid.plugins.pluginBase.Plugin):

    def _file_path(self) -> str:
        return os.path.dirname(os.path.abspath(__file__))

    def __init__(self, subapp_to_register_to: web.Application, mad: Dict):
        super().__init__(subapp_to_register_to, mad)

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

        if self._mad['args'].config_mode:
            return False

        self._mad['logger'].info('plugin is running')

        return True
