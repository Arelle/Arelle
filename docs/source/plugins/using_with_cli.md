# Using Plugins with CLI

:::{index} Using Plugins with CLI
:::

## Enabling Plugins for the CLI
Plugin enablement does not persist between CLI runs, 
so every CLI execution needs any used plugins to be specified each time.

[//]: # (TODO: link below --plugins mentions to CLI documentation once it's implemented)

___
### By Name
The plugin's name can be passed to the `--plugins` CLI option. Multiple names can be passed by separating with a vertical bar `|` character.

Example:
```bash
python arelleCmdLine.py --plugins=myplugin ...
```
```bash
python arelleCmdLine.py --plugins="myplugin|myplugin2" ...
```

___
### By Path
A relative or absolute path to the plugin can be passed to the `--plugins` CLI option.

Examples:
```bash
python arelleCmdLine.py --plugins=../myplugin ...
```
```bash
python arelleCmdLine.py --plugins=/Users/me/myplugin ...
```