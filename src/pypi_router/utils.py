from packaging.utils import parse_wheel_filename
from pathlib import Path
import re
import subprocess
import sys

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
