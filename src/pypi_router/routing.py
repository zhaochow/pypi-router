import itertools
from pathlib import Path

from simpleindex.configs import Configuration
from simpleindex.routes import Response, Route, Params
from starlette import routing
from starlette.applications import Starlette
from starlette.requests import Request
from uvicorn import run as run_uvicorn

import pypi_router.utils as ut

class LocalIndexRoute(Route):
    async def get_page(self, params: Params) -> Response:
        path = self.root.joinpath(self.to.format(**params))
        if path.is_file():
            return Response(content=path.read_bytes(), media_type='text/html')
        if path.is_dir():
            html = (path / 'index.html').read_bytes()
            return Response(content=html, media_type='text/html')
        return Response(status_code=404, content='Not Found')

    async def get_file(
        self, params: Params, filename: str, cache_dir: Path
    ) -> Response:
        path = self.root.joinpath(self.to.format(**params), filename)
        if path.suffix not in ('.whl', '.metadata'):
            return await super().get_file(params, filename)

        if path.suffix == '.whl':
            index_dir = path.parent
            path = cache_dir.joinpath(index_dir.name, 'dist', path.name)
            if not path.is_file():
                ut.build_wheel(path, index_dir)
            media_type = 'application/zip'
        else:
            media_type = 'application/octet-stream'

        if not path.is_file():
            return await super().get_file(params, filename)

        data = path.read_bytes()
        return Response(status_code=200, content=data, media_type=media_type)

# simpleindex.__main__.py
def _build_routes(key: str, route: Route, cache_dir: Path):
    async def page(request: Request):
        response = await route.get_page(request.path_params)
        return response.to_http_response()

    async def dist(request: Request):
        params = request.path_params
        filename = params.pop(filename_param)
        if isinstance(route, LocalIndexRoute):
            response = await route.get_file(params, filename, cache_dir)
        else:
            response = await route.get_file(params, filename)
        return response.to_http_response()

    filename_param = "__simpleindex_match_filename__"
    return [
        routing.Route(f"/{key}/", page),
        routing.Route(f"/{key}/{{{filename_param}}}", dist),
    ]

def run_simpleindex(config: str, cache_dir: Path):
    config_path, configuration = Configuration.parse_arg(config)

    routes = itertools.chain.from_iterable(
        _build_routes(key, route.derive(config_path.parent), cache_dir)
        for key, route in configuration.routes.items()
    )
    app = Starlette(routes=list(routes))

    options = {k.replace("-", "_"): v for k, v in configuration.server.items()}
    run_uvicorn(app, **options)
