# Plugin Installation

:::{index} Plugin Installation
:::

## Preinstalled Plugins
Some plugins are built into and packaged with Arelle.
These plugins are located in the [source code][plugins-source] under `/arelle/plugins`.
No additional installation steps are necessary for these plugins.
Activate pre-installed plugins [via the GUI using Select][gui-select] or [via CLI by name][cli-name].

## Installing Plugins via Package Manager
If you installed Arelle [from source][install-from-source],
published plugins can be installed by your Python package manager of choice.

Example:
```bash
pip install ixbrl-viewer
```
Activate plugins installed with this method [via the GUI using Select][gui-select] or [via CLI by name][cli-name].

## Installing Plugins Manually
If the plugin you are using is not available via package manager, 
or you would like to run a plugin you are developing locally,
plugins can also be installed anywhere Arelle can access on your local file system.
You can then activate manually installed plugins [via the GUI using Browse][gui-browse] or [via CLI by path][cli-path].

Alternatively, if you are running Arelle [from source][install-from-source], 
you can place your plugin in the preinstalled plugins directory (`arelle/plugins`)
to allow your plugin to be treated as a [preinstalled plugin][preinstalled-plugins] and activated by name.

___
Next, see [Using Plugins with GUI](project:using_with_gui.md) or [Using Plugins with CLI](project:using_with_cli.md) to learn how to use the plugins. 


[preinstalled-plugins]: installation.md#preinstalled-plugins
[plugins-source]: https://github.com/Arelle/Arelle/tree/master/arelle/plugin
[install-from-source]: project:../install.md#from-python-source
[cli-name]: using_with_cli.md#by-name
[cli-path]: using_with_cli.md#by-path
[gui-select]: using_with_gui.md#select
[gui-browse]: using_with_gui.md#browse
[gui-web]: using_with_gui.md#web
