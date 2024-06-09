import hashlib
from packaging.utils import parse_wheel_filename
from pathlib import Path
import re
import shutil
import subprocess
import sys

import toml

DEFAULT_CACHE_DIR = str(Path.home().joinpath('.cache', 'pypi-router'))
DEFAULT_OUT_DIR = str(Path().cwd())

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

def make_index(index_dir: Union[str, Path], package_list: Union[str, Path],
               cache_dir: Union[str, Path] = DEFAULT_CACHE_DIR,
               rebuild: bool = False):
    index_dir = Path(index_dir)
    cache_dir = Path(cache_dir)

    with open(package_list) as f:
        git_repos = [l.strip(' \n') for l in f.readlines()]

    package_names: list[str] = [None] * len(git_repos)
    for i, repo in enumerate(git_repos):
        repo_dir = _git_clone(repo, cache_dir)

        with open(repo_dir / 'pyproject.toml', 'r', encoding='utf-8') as f:
            pyproject = toml.load(f)
        package_name: str = pyproject['project']['name']
        package_names[i] = package_name
        print(f"Copy of package {package_name} at " + str(repo_dir))

        pkg_index_dir = index_dir / package_name
        pkg_index_dir.mkdir(parents=True, exist_ok=True)

        versions = _build_all_version_tags(
            repo_dir, metadata_dst_dir=pkg_index_dir, rebuild=rebuild
        )
        wheel_names, metadata_hashes = tuple(zip(*versions))

        pkg_index = pkg_index_dir / 'index.html'
        html = _build_index_html(wheel_names, metadata_hashes=metadata_hashes,
                                 git_repo=repo)
        with open(pkg_index, 'w', encoding='utf-8') as f:
            f.write(html)

    html = _build_index_html([f"/{n}/" for n in package_names])
    with open(index_dir / 'index.html', 'w', encoding='utf-8') as f:
        f.write(html)

_GIT_CLONE_OK_PATTERN = re.compile(r"^Cloning into '(.+)'...$")
_GIT_CLONE_EXIST_PATTERN = re.compile(
    r"^fatal: destination path '(.+)' already exists and is not an empty "
    r"directory.$"
)

def _git_clone(repo: str, working_dir: Path):
    working_dir.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(['git', 'clone', repo], cwd=working_dir,
                       capture_output=True, text=True)
    if p.returncode == 0:
        repo_reldir = _GIT_CLONE_OK_PATTERN.match(p.stderr).group(1)
    elif p.returncode == 128:
        repo_reldir = _GIT_CLONE_EXIST_PATTERN.match(p.stderr).group(1)
    else:
        p.check_returncode()
    return working_dir.joinpath(repo_reldir)

def _build_all_version_tags(
    repo: Path,
    metadata_dst_dir: Union[Path, None] = None,
    rebuild: bool = False
):
    versions: dict[str, list[tuple[str, str]]] = {}

    if metadata_dst_dir is not None:
        index_path = metadata_dst_dir / 'index.html'
        if index_path.is_file() and not rebuild:
            versions_info = _parse_index_html(index_path)
            pattern = f"{metadata_dst_dir.name}-([^-]+)-.+\.whl"
            for info in versions_info:
                wheel_name = info[0]
                vtag = 'v' + re.match(pattern, wheel_name).group(1)
                versions.setdefault(vtag, [])
                versions[vtag].append((wheel_name, info[2]))

            tmp = [b[0] for builds in versions.values() for b in builds]
            print(f"Found existing package versions in index.html:\n"
                  + '\n'.join(tmp) + '\n')

    p = subprocess.run(['git', 'tag'], cwd=repo, capture_output=True,
                       text=True, check=True)
    vtags = [tag for tag in p.stdout.split('\n') if tag.startswith('v')]
    print('Found the following version tags:\n' + '\n'.join(vtags) + '\n')

    vtags_to_build = [t for t in vtags if t not in versions]
    for vtag in vtags_to_build:
        wheel_name, metadata_src = _build_package(repo, vtag) # TODO multiple builds for same tag
        hash = get_hash_name_value(metadata_src)
        if metadata_dst_dir is not None:
            metadata_dst = metadata_dst_dir / (wheel_name + '.metadata')
            shutil.copy2(metadata_src, metadata_dst)
            assert get_hash_name_value(metadata_dst) == hash
        versions[vtag] = [(wheel_name, hash)]

    return [b for t in vtags for b in versions[t]]

_METADATA_PATH_PATTERN = re.compile(r"^writing (.+\.egg-info\\PKG-INFO)$",
                                    flags=re.MULTILINE)
_WHEEL_NAME_PATTERN = re.compile(r"^Successfully built (.+\.whl)$",
                                 flags=re.MULTILINE)

def _build_package(repo: Path, tag: str):
    # # Get commit hash from tag
    # p = subprocess.run(['git', 'rev-list', '-n', '1', tag], cwd=repo,
    #                    capture_output=True, text=True, check=True)
    # commit = p.stdout

    subprocess.run(['git', 'checkout', tag], cwd=repo, check=True)
    p = subprocess.run([sys.executable, '-m', 'build', '-w'], cwd=repo,
                       capture_output=True, text=True, check=True)
    metadata_src = _METADATA_PATH_PATTERN.search(p.stdout).group(1)
    metadata_src = repo.joinpath(metadata_src)
    wheel_name = _WHEEL_NAME_PATTERN.search(p.stdout).group(1)
    print(f"Built {wheel_name}\n")

    return wheel_name, metadata_src

_BUF_SIZE = 65536

def get_hash_name_value(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while True:
            data = f.read(_BUF_SIZE)
            if not data:
                break
            sha256.update(data)
    return f"sha256={sha256.hexdigest()}"

_INDEX_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
  <body>
{anchors}
  </body>
</html>
"""

def _create_anchor(name, href=None, hash=None, metadata_hash=None):
    if href is None: href = name
    a = f"href=\"{href}"
    if hash is not None:
        a += f"#{hash}"
    a += '"'
    if metadata_hash is not None:
        a += f" data-core-metadata=\"{metadata_hash}\""
    a = f"<a {a}>{name}</a><br>"
    return a

_ANCHOR_INDENT = ' ' * 4

def _build_index_html(names, hrefs=None, hashes=None, metadata_hashes=None,
                      git_repo=None):
    def none_iter():
        while True:
            yield None

    if hrefs is None: hrefs = none_iter()
    if hashes is None: hashes = none_iter()
    if metadata_hashes is None: metadata_hashes = none_iter()

    anchors = []
    if git_repo is not None:
        anchors.append(_create_anchor('git-repo', href=git_repo))
    anchors.extend([_create_anchor(*args)
                    for args in zip(names, hrefs, hashes, metadata_hashes)])

    anchors = _ANCHOR_INDENT + f"\n{_ANCHOR_INDENT}".join(anchors)
    return _INDEX_HTML_TEMPLATE.format(anchors=anchors)

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
