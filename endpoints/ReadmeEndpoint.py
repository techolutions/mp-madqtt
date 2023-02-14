from mapadroid.plugins.endpoints.AbstractPluginEndpoint import AbstractPluginEndpoint
import aiohttp_jinja2


class ReadmeEndpoint(AbstractPluginEndpoint):
    """
    "/readme"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('madqtt_readme.html')
    async def get(self):
        return {"header": "MADqtt Header",
                "title": "MADqtt Title"}
