from aiohttp import web

from plugins.mp-madqtt.endpoints.ExampleEndpoint import ExampleEndpoint
from plugins.mp-madqtt.endpoints.PluginfaqEndpoint import PluginfaqEndpoint
from plugins.mp-madqtt.endpoints.ReadmeEndpoint import ReadmeEndpoint


def register_custom_plugin_endpoints(app: web.Application):
    # Simply register any endpoints here. If you do not intend to add any views (which is discouraged) simply "pass"
    app.router.add_view('/example', ExampleEndpoint, name='example')
    app.router.add_view('/pluginfaq', PluginfaqEndpoint, name='pluginfaq')
    app.router.add_view('/readme', ReadmeEndpoint, name='readme')
