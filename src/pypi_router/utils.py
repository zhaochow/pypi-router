from packaging.utils import parse_wheel_filename
from pathlib import Path
import re
import subprocess
import sys

DEFAULT_CACHE_DIR = str(Path.home().joinpath('.cache', 'pypi-router'))

_GIT_REPO_PATTERN = re.compile(r'<a href="(.+)">git-repo</a>')

def build_wheel(wheel_path: Path, index_dir: Path):
    # A wheel is a zip file thus the checksum will be different every time
    repo_dir = wheel_path.parents[1]
    name, ver, build, tags = parse_wheel_filename(wheel_path.name)
    with open(index_dir / 'index.html') as f:
        for line in f:
            m = _GIT_REPO_PATTERN.search(line)
            if m is not None:
                git_repo = m.group(1)
                break

    if not repo_dir.is_dir():
        repo_dir.mkdir(parents=True)
        subprocess.run(['git', 'clone', git_repo, str(repo_dir)], check=True)

    subprocess.run(['git', 'checkout', f"v{ver}"], cwd=repo_dir, check=True)
    subprocess.run([sys.executable, '-m', 'build', '-w'], cwd=repo_dir,
                   check=True)

    if not wheel_path.is_file():
        raise ValueError(str(wheel_path))

def create_config(pypi_index: Path, port: int = 8000,
                  cache_dir=DEFAULT_CACHE_DIR) -> Path:
    packages = [p for p in pypi_index.glob('*') if p.is_dir()]

    with open(Path(__file__).with_name('config_template.toml')) as f:
        cfg = f.readlines()

    source_str = 'source = "local_index"\n'
    custom_lines = []
    for package in packages:
        custom_lines.extend([
            f"[routes.\"{package.name}\"]\n",
            source_str,
            f"to = '{str(pypi_index / package.name)}'\n",
            '\n',
        ])
    cfg = cfg[:1] + custom_lines + cfg[2:]

    if port is not None:
        cfg[-1] = f"port = {port}\n"

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cache_dir.joinpath('config.toml')
    with open(cfg_path, 'w', encoding='utf-8') as f:
        f.writelines(cfg)

    return cfg_path
