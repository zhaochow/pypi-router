from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pathlib import Path
import subprocess
import sys

def main():
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    # group.add_argument('--pypi-repo') # TODO
    group.add_argument('--pypi-path', help='Path to custom index')
    parser.add_argument('--source', choices=['http', 'path'], default='http',
                        help='simpleindex source')
    parser.add_argument('--pypi-port', type=int, default=8001,
                        help='http.server port')
    parser.add_argument(
        '--cache-dir',
        default=str(Path.home().joinpath('.cache', 'pypi-router')),
        help='Cache directory',
    )
    parser.add_argument('--config', help='simpleindex configuration')
    parser.add_argument('--port', type=int, help='simpleindex port')
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir).resolve()

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

        cache_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = cache_dir.joinpath('config.toml')
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
