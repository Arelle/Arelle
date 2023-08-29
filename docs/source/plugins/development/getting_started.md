# Getting Started

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
| localeURL    | L10N internationalization for this module (subdirectory if relative).         |
| localeDomain | Domain for L10N internationalization (e.g., 'arelle').                        |
| license      | License information to display with plugin.                                   |
| author       | Author to be listed in the GUI.                                               |
| copyright    | Copyright information to be listed in the GUI.                                |
| import       | `str`, `list` or `tuple` of URLs or relative file names of imported plug-ins. |
| (hook)       | See Plugin Functionality below.                                               |

Here is an example of what this might look like in Python code:
```python
def exampleHook(arg):
  # This will be called when Arelle searches for `Example.Hook` usages from plugins.
  pass

__pluginInfo__ = {
    'name': 'My Plugin',
    'version': '1.0.0',
    'license': 'MIT',
    'author': 'John Smith',
    'copyright': '(c) Copyright 2023 Example Inc., All rights reserved.',
    'import': ['../otherPlugin.py', '../otherPlugin2.py'],
    'Example.Hook': exampleHook
}
```

## Plugin Functionality
Arelle is configured to search for and run plugin code at predetermined places.
These predetermined places are referred to as *hooks*.

In the example above, when Arelle calls for the hypothetical hook named `Example.Hook`, it will call the `exampleHook` method.

Hooks may or may not expect a value to be returned by your plugin's method,
which may or may not prevent other plugins from running or cause Arelle's default behavior to be circumvented.

See [Plugin Hooks][hooks] to find documentation on expected arguments, expected return values, and other behavior associated with specific hooks.

[hooks]: project:hooks.md