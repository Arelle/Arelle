# Install

:::{index} Install
:::

There are a few different ways to install Arelle depending on your requirements.

## Prepackaged Distributions

The Arelle distribution builds are self contained bundles that provide an executable
and include the Arelle source code along with its dependencies and a Python runtime
ready to run out of the box. These distributions include all of the [plugins in the
Arelle repo][arelle-plugins], along with the [Arelle ixbrl-viewer][arelle-ixbrl-viewer],
the [SEC EdgarRenderer][edgarrenderer], and [XULE][xule].

Distributions are provided for Windows, macOS, and Linux and can be downloaded from
the [Arelle website][arelle-download-page] and [GitHub release page][github-latest-release].

[arelle-download-page]: https://arelle.org/arelle/pub/
[arelle-ixbrl-viewer]: https://github.com/Arelle/ixbrl-viewer
[arelle-plugins]: https://github.com/Arelle/Arelle/tree/master/arelle/plugin
[edgarrenderer]: https://github.com/Arelle/EdgarRenderer
[github-latest-release]: https://github.com/Arelle/Arelle/releases/latest
[xule]: https://github.com/xbrlus/xule

### Clean Install

Arelle stores configuration data and comes with a number of installation files.
If your installation of Arelle isn't behaving as expected it can be beneficial to
try deleting (or moving) these files and performing a fresh installation.

### Linux

1. Delete the directory where you extracted the Arelle download.
2. If the `~/.config/arelle/` configuration directory exists, delete it.
3. Reinstall Arelle using the [latest release](#prepackaged-distributions).

### macOS

1. If the `/Applications/Arelle.app` application exists, delete it.
2. If the `~/Library/Application Support/Arelle` configuration directory exists,
   delete it.
3. If the `~/Library/Caches/Arelle` cache directory exists, delete it.
4. Reinstall Arelle using the [latest release](#prepackaged-distributions).

### Windows

1. If the file `C:\Program Files\Arelle\Uninstall.exe` exists, run it.
2. If the `C:\Program Files\Arelle` application directory exists, delete it.
3. If the `%LOCALAPPDATA%\Arelle` configuration directory exists, delete it.
4. Reinstall Arelle using the [latest release](#prepackaged-distributions).

## From Python Source

See the contributing documentation for [setting up your environment][setting-up-your-environment]
if you're comfortable setting up your own Python environment and would like to run
Arelle from source.

[setting-up-your-environment]: project:contributing.md#setting-up-your-environment

## Python Package

If you would like to use Arelle as a Python library or you want to use your own
Python runtime, but would rather not clone the repo, you can use pip to install Arelle.

The Arelle Python package defines optional extra dependencies for various plugins
and use cases.

- Crypto (security plugin dependencies)
- DB (database plugin dependencies)
- EFM (EdgarRenderer plugin dependencies - does not include the EdgarRenderer,
  just the dependencies required to run it)
- ObjectMaker (ObjectMaker plugin dependencies)
- WebServer (dependencies for running the Arelle web server)

```shell
# to install Arelle and its base dependencies
pip install arelle-release
# to install Arelle with all optional dependencies
pip install arelle-release[Crypto,DB,EFM,ObjectMaker,WebServer]
```

The Arelle command line and GUI applications should then be available on your path.

```shell
# To run the command line
arelleCmdLine --help

# To launch the GUI
arelleGUI
```
