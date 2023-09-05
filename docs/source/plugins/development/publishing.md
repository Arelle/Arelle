# Publishing a Plugin

:::{index} Publishing a Plugin
:::

## Packaging Tutorial
The best way to make your plugin available for others is by publishing it to a package manager registry.

Use the [Python Packaging User Guide](https://packaging.python.org/en/latest/) to learn how to package and publish a package to PyPI.
Specifically, the [Packaging Python Projects](https://packaging.python.org/en/latest/tutorials/packaging-projects/) details this process.

## Configuring Entry Point
Publishing the package will make it installable by package managers, 
but an extra step is necessary to make the package discoverable as a plugin by Arelle.

Arelle uses [`setuptools`](https://pypi.org/project/setuptools/) to discover packages that define entry points for Arelle.
Entry points can be defined in `pyproject.toml` as described [here](https://setuptools.pypa.io/en/latest/userguide/entry_point.html#entry-points-for-plugins).
For `ixbrl-viewer`, that looks like [this](https://github.com/Arelle/ixbrl-viewer/blob/fa547995873662328ce761cafd8c7dbf40fc5ae4/pyproject.toml#L41-L43C1):
```toml
[project.entry-points."arelle.plugin"]
ixbrl-viewer = "iXBRLViewerPlugin:load_plugin_url"
```

For your project, swap out `ixbrl-viewer` with your plugin name, and swap 
`iXBRLViewerPlugin:load_plugin_url` with a reference to a method that returns a path
to the Python script that defines `__pluginInfo__`.

> Consider including 'arelle' and 'plugin' [keywords](https://github.com/Arelle/ixbrl-viewer/blob/903ef1a5656ebcb2eb682fcb0261b109550fc602/pyproject.toml#L14) in your package to make it more discoverable!
