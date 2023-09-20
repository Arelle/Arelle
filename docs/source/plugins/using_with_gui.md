# Using Plugins with GUI

:::{index} Using Plugins with GUI
:::

(plug-in-manager)=
## Plug-in Manager
:::{image} /images/gui_plugin_manager.png
:::
Plugin configuration for the GUI is primarily done through the 'Plug-in Manager' dialog.
With the GUI running, navigate to `Help > Manage plug-ins` in the toolbar to open the 'Plug-in Manager'.

:::{image} /images/gui_manage_plugins.png
:width: 400
:::

___
## Configuring Plugins for the GUI
After a plugin is installed, it needs to be 'configured' via [Plug-in Manager](#plug-in-manager) before it can be used by the GUI.

Plugin configurations persist between GUI sessions, so the following steps are only necessary once,
and not needed on subsequent uses of the GUI.

* Open the [Plug-in Manager](#plug-in-manager)
* If your plugin does not appear in the list, you will need to add it via one of these options:
    * If your plugin is preinstalled or installed via package manager, go to [GUI - Select](#select).
    * If your plugin is manually installed, go to [GUI - Browse](#browse)
    * If your plugin is hosted online, go to [GUI - Web](#web)

___
### Select
With the [Plug-in Manager](#plug-in-manager) dialog open, click the 'Select' button.
:::{image} /images/gui_plugin_manager_select_button.png
:::
Find your plugin in the list that opens, then click 'OK'.
:::{image} /images/gui_plugin_manager_select.png
:::

___
### Browse
With the [Plug-in Manager](#plug-in-manager) dialog open, click the 'Browse' button.
:::{image} /images/gui_plugin_manager_browse_button.png
:::
Navigate to and select your plugin entry point (an individual script or `__init__.py`) and click 'Open'.
:::{image} /images/gui_plugin_manager_browse.png
:::

___
### Web
With the [Plug-in Manager](#plug-in-manager) dialog open, click the 'On Web' button.
:::{image} /images/gui_plugin_manager_web_button.png
:::
Provide a URL to load your plugin from, then click 'OK'.
:::{image} /images/gui_plugin_manager_web.png
:::

___
## Enabling/Disabling Plugins for the GUI
Plugins are 'enabled' for the GUI by default when they are initially configured.
To enable/disable a plugin, open [Plug-in Manager](#plug-in-manager) and click on the plugin row, 
then click the 'Enable' or 'Disable' button.
