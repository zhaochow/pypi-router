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

