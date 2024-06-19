# PyPI router

Simple repository for routing Python packages to specific indexes.

Routing is handled using [simpleindex](https://github.com/uranusjr/simpleindex).

A new [simpleindex](https://github.com/uranusjr/simpleindex) route `local_index` is also provided for serving a local
index storing only metadata files. The necessary wheel files will be built from the git repository after all
dependencies have been solved. A `git-repo` anchor pointing to the git repository is therefore required when using this
route type.

## Install

```sh
git clone https://github.com/zhaochow/pypi-router.git
python -m pip install pypi-router
```
