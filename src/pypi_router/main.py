from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pathlib import Path
from typing import Sequence, Union

from pypi_router.routing import run_simpleindex
import pypi_router.utils as ut

def main(args: Union[Sequence[str], None] = None):
    cache_dir = Path(ut.DEFAULT_CACHE_DIR)
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-l', '--package-list',
                        help='Path to package list file')
    parser.add_argument('-i', '--pypi-index', help='Path to custom index')
    parser.add_argument('-c', '--config', help='simpleindex configuration')
    parser.add_argument('--cache-dir', default=str(cache_dir),
                        help='Cache directory')
    parser.add_argument('--port', type=int, help='simpleindex port')
    parser.add_argument('--rebuild', action='store_true',
                        help='Rebuild the entire custom index')
    args = parser.parse_args(args)

    cwd = Path().cwd()
    cache_dir = Path(args.cache_dir).resolve()

    pypi_index = args.pypi_index
    if args.package_list is not None:
        if pypi_index is None:
            pypi_index = cwd / 'pypi_index'
        ut.make_index(pypi_index, args.package_list, cache_dir=cache_dir,
                      rebuild=args.rebuild)

    cfg_path = args.config
    if pypi_index is not None:
        if cfg_path is None:
            cfg_path = cwd / 'config.toml'
        ut.make_config(cfg_path, pypi_index, port=args.port)

    if cfg_path is None:
        raise ValueError('At least one of (--package-list | --pypi-index | '
                         '--config) should be given')
    else:
        run_simpleindex(str(cfg_path), cache_dir)

if __name__ == '__main__':
    main()
