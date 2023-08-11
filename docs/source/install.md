# Install

:::{index} Install
:::

The implementation is in Python >= 3.8 and is intended for Windows, macOS, or
Linux (tested against Ubuntu). The standard desktop installation includes a GUI,
a RESTful web server, and CLI. We try to support all operating system versions
that still receive security updates from their development teams.

## Install PyPI package

The Arelle python package defines optional extra dependencies for various
plugins and use cases.

- Crypto (security plugin dependencies)
- DB (database plugin dependencies)
- EFM (EdgarRenderer plugin dependencies - does not include the EdgarRenderer,
  just the dependencies required to run it)
- ObjectMaker (ObjectMaker plugin dependencies)
- WebServer (dependencies for running the Arelle web server)

```shell
pip install arelle-release
# or for all extra dependencies
pip install arelle-release[Crypto,DB,EFM,ObjectMaker,WebServer]
```

## Install development version from GitHub

```shell
pip install git+https://git@github.com/arelle/arelle.git@master
```

## Install distributions

Distributions are self contained builds that come bundled with their own Python
runtime and resources needed to run Arelle.

Distributions are provided for the following operating systems:

- Windows
- macOS (Intel)
- Linux (Ubuntu)

Distributions can be downloaded from:

- [Arelle website](https://arelle.org/arelle/pub/)
- [GitHub releases](https://github.com/Arelle/Arelle/releases)
