from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pathlib import Path
import subprocess
import sys

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
            html = (path / 'index.html').read_text()
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

def main(*args):
    global _cache_dir
    if len(args) < 1: args = None
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    # group.add_argument('--pypi-repo') # TODO
    group.add_argument('--pypi-path', help='Path to custom index')
    parser.add_argument('--source', choices=['http', 'path'], default='http',
                        help='simpleindex source')
    parser.add_argument('--pypi-port', type=int, default=8001,
                        help='http.server port')
    parser.add_argument('--cache-dir', default=str(_cache_dir),
                        help='Cache directory')
    parser.add_argument('--config', help='simpleindex configuration')
    parser.add_argument('--port', type=int, help='simpleindex port')
    args = parser.parse_args(args)

    _cache_dir = Path(args.cache_dir).resolve()

    if args.pypi_path is None:
        raise NotImplementedError()
        p = subprocess.run(['git', 'clone', args.pypi_repo, str(cache_dir)],
                           check=True)
        pypi_root
    else:
        pypi_root = Path(args.pypi_path).resolve()

    if args.config is None:
        packages = [p for p in pypi_root.glob('*') if p.is_dir()]

        with open(Path(__file__).with_name('config_template.toml')) as f:
            cfg = f.readlines()

        source_str = f"source = \"{args.source}\"\n"
        custom_lines = []
        for package in packages:
            custom_lines.extend([
                f"[routes.\"{package.name}\"]\n",
                source_str,
                f"to = \"http://127.0.0.1:{args.pypi_port}/{package.name}/\"\n",
                '\n',
            ])
        cfg = cfg[:1] + custom_lines + cfg[2:]

        if args.port is not None:
            cfg[-1] = f"port = {args.port}\n"

        _cache_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = _cache_dir.joinpath('config.toml')
        with open(cfg_path, 'w', encoding='utf-8') as f:
            f.writelines(cfg)
    else:
        cfg_path = Path(args.config).resolve()

    pypi_server = subprocess.Popen(
        [sys.executable, '-m', 'http.server', '--directory', str(pypi_root),
         str(args.pypi_port)]
    )

    simpleindex_server = subprocess.Popen(
        [sys.executable, '-m', 'simpleindex', str(cfg_path)]
    )
    pass

if __name__ == '__main__':
    main()
