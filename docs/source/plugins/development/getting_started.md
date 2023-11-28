# Getting Started

:::{index} Plugins Getting Started
:::

## Entry Point

There are two primary ways to create an Arelle plugin: via a standalone script or a module (directory).

If using the script approach, your plugin's *entry point* is the script itself (`myplugin.py`)

If using the module approach, your plugin's *entry point* is the `__init__.py` script in your plugin module's root directory. (`myplugin/__init__.py`)

Once your entry point is created, it will need to be properly configured as an Arelle plugin.
To do this, your plugin's entry point must define a `__pluginInfo__` property
as a map with the following properties (some optional):

| Property     | Description                                                                   |
|--------------|-------------------------------------------------------------------------------|
| **name**     | (Required) Name of plugin for display purposes.                               |
| **version**  | (Required) Version of plugin for display purposes.                            |
| description  | Description displayed in the GUI.                                             |
| aliases      | Collection of names (in addition to "name") that match this plug-in.          |
| localeURL    | L10N internationalization for this module (subdirectory if relative).         |
| localeDomain | Domain for L10N internationalization (e.g., 'arelle').                        |
| license      | License information to display with plugin.                                   |
| author       | Author to be listed in the GUI.                                               |
| copyright    | Copyright information to be listed in the GUI.                                |
| import       | `str`, `list` or `tuple` of plug-in URLs, relative paths, names, or aliases.  |
| (hook)       | See Plugin Functionality below.                                               |

Here is an example of what this might look like in Python code:
```python
from optparse import OptionParser
from typing import Any

from arelle.utils.PluginHooks import PluginHooks


class MyPlugin(PluginHooks):
    @staticmethod
    def cntlrCmdLineOptions(
        parser: OptionParser,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        # This will be called when Arelle searches for `CntlrCmdLine.Options` usages from plugins.
        parser.add_option(
            '--my-plugin-command-line-option',
            action='store',
            dest='myPluginCommandLineOption',
            help='Adds an option to the Arelle command line for my plugin.',
        )


__pluginInfo__ = {
    'name': 'My Plugin',
    'version': '1.0.0',
    'license': 'MIT',
    'author': 'John Smith',
    'copyright': '(c) Copyright 2023 Example Inc., All rights reserved.',
    'import': ['../otherPlugin.py', '../otherPlugin2.py'],
    'CntlrCmdLine.Options': MyPlugin.cntlrCmdLineOptions,
}
```

## Plugin Functionality

Arelle is configured to search for and run plugin code at predetermined places.
These predetermined places are referred to as *hooks*.

In the example above, when the plugin is enabled and Arelle calls for the hook named `CntlrCmdLine.Options`, it will call the `MyPlugin.cntlrCmdLineOptions` method which will add
`--my-plugin-command-line-option` as an option to the Arelle command line.

Hooks may or may not expect a value to be returned by your plugin's method,
which may or may not prevent other plugins from running or cause Arelle's default behavior to be circumvented.

See [Plugin Hooks][hooks] to find documentation on expected arguments, expected return values, and other behavior associated with specific hooks as well as documentation for the [PluginHooks](#arelle.utils.PluginHooks.PluginHooks) class that can help with writing plugins.

[hooks]: project:hooks.md
