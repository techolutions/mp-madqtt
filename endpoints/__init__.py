from aiohttp import web

import importlib
importlib.import_module("plugins.mp-madqtt.endpoints.ExampleEndpoint").ExampleEndpoint
importlib.import_module("plugins.mp-madqtt.endpoints.PluginfaqEndpoint").PluginfaqEndpoint
importlib.import_module("plugins.mp-madqtt.endpoints.ReadmeEndpoint").ReadmeEndpoint


def register_custom_plugin_endpoints(app: web.Application):
    # Simply register any endpoints here. If you do not intend to add any views (which is discouraged) simply "pass"
    app.router.add_view('/example', ExampleEndpoint, name='example')
    app.router.add_view('/pluginfaq', PluginfaqEndpoint, name='pluginfaq')
    app.router.add_view('/readme', ReadmeEndpoint, name='readme')
