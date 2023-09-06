# Plugin Hooks

:::{index} Plugin Hooks
:::

:::{important}
It's not considered a breaking change if additional parameters are passed to these hooks in a future version of Arelle.
To ensure your plugin continues to work with future versions of Arelle it's important to include `*args, **kwargs`
in the function signature so an exception isn't thrown if a new argument is passed.
:::

It's recommended to implement plugin hooks by extending the `PluginHooks` abstract class and overriding the static methods
that refer to the hooks you need and assigning them to `__pluginInfo__`.

```python
from typing import Any

from arelle.utils.PluginHooks import PluginHooks
from arelle.ValidateXbrl import ValidateXbrl


class MyPlugin(PluginHooks):
    @staticmethod
    def validateFinally(val: ValidateXbrl, *args: Any, **kwargs: Any) -> None:
        if "Cash" not in val.modelXbrl.factsByLocalName:
            val.modelXbrl.error(codes="01.01", msg="Cash must be reported.")


__pluginInfo__ = {
    "name": "My Plugin",
    "version": "0.0.1",
    "Validate.Finally": MyPlugin.validateFinally,
}
```

:::{autodoc2-object} arelle.utils.PluginHooks.PluginHooks
:::
