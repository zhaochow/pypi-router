from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pathlib import Path
from typing import Sequence, Union

import simpleindex
from simpleindex.routes import Response, Route, Params

import pypi_router.utils as ut

_cache_dir = Path(ut.DEFAULT_CACHE_DIR)

class LocalIndexRoute(Route):
    async def get_page(self, params: Params) -> Response:
        path = self.root.joinpath(self.to.format(**params))
        if path.is_file():
            return Response(content=path.read_bytes(), media_type='text/html')
        if path.is_dir():
            html = (path / 'index.html').read_bytes()
            return Response(content=html, media_type='text/html')
        return Response(status_code=404, content='Not Found')

    async def get_file(self, params: Params, filename: str) -> Response:
        path = self.root.joinpath(self.to.format(**params), filename)
        if path.suffix not in ('.whl', '.metadata'):
            return await super().get_file(params, filename)

        if path.suffix == '.whl':
            index_dir = path.parent
            path = _cache_dir.joinpath(index_dir.name, 'dist', path.name)
            if not path.is_file():
                ut.build_wheel(path, index_dir)
            media_type = 'application/zip'
        else:
            media_type = 'application/octet-stream'

        if not path.is_file():
            return await super().get_file(params, filename)

        data = path.read_bytes()
        return Response(status_code=200, content=data, media_type=media_type)

def main(args: Union[Sequence[str], None] = None):
    global _cache_dir
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-l', '--package-list',
                        help='Path to package list file')
    parser.add_argument('-i', '--pypi-index', help='Path to custom index')
    parser.add_argument('-c', '--config', help='simpleindex configuration')
    parser.add_argument('--cache-dir', default=str(_cache_dir),
                        help='Cache directory')
    parser.add_argument('--port', type=int, help='simpleindex port')
    args = parser.parse_args(args)

    _cache_dir = Path(args.cache_dir).resolve()

    if args.config is None:
        if args.pypi_index is None:
            if args.package_list is None:
                raise ValueError('At least one of (--package-list | '
                                 '--pypi-index | --config) should be given')
            pypi_index = ut.create_index(args.package_list,
                                         cache_dir=_cache_dir)
        else:
            pypi_index = Path(args.pypi_index).resolve()
            if not pypi_index.is_dir():
                if args.package_list is None:
                    raise FileExistsError(f"{str(pypi_index)} does not exist")
                ut.create_index(args.package_list, index_dir=pypi_index,
                                cache_dir=_cache_dir)
        cfg_path = ut.create_config(pypi_index, port=args.port,
                                    cache_dir=_cache_dir)
    else:
        cfg_path = Path(args.config).resolve()

    simpleindex.run([str(cfg_path)])

if __name__ == '__main__':
    main()
