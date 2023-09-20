# Create a Validation Plugin

:::{index} Create a Validation Plugin
:::

One of the more common reasons to build a plugin is to add support for taxonomy- or jurisdiction-specific validation rules.
To accelerate the process of creating new validation plugins, there's an [example template validation plugin][example-plugin]
that can serve as a starting point.

The example plugin demonstrates how to use the [ValidationPlugin][validation-plugin] class, the [@validation][validation-decorator]
decorator, and the [PluginValidationData][plugin-validation-data] to write validation rules.

The [@validation][validation-decorator] decorator is used to register functions as validation rules and specify which
disclosure systems they should run with.

The [ValidationPlugin][validation-plugin] class is responsible for collecting and running the decorated validation rules.

The [PluginValidationData][plugin-validation-data] data class is used for caching plugin data that's expensive to compute.
It is passed between rule functions by the [ValidationPlugin][validation-plugin] class. The default implementation only
contains a name field. To include your own fields, you should extend the data class and define the fields you need.
Also, extend the ValidationPlugin class and override the [newPluginData][validation-new-plugin-data]
method to return your data class.

:::{note}
Validation rules for the same [ValidationHook][validation-hook] are not guaranteed to run in a specific order. If you
need a rule to run before another you can either implement them with different hooks, such as `Validate.XBRL.Start` and
`Validate.XBRL.Finally` or implement them within the same [@validation][validation-decorator] decorated function.
:::

## Steps to Create a New Validation Plugin

1. Copy the [XYZ validation plugin][example-plugin] from the examples directory into the [Arelle/plugins/validate directory][validations-directory].
2. Rename the plugin module from `XYZ` to the name of the taxonomy or jurisdiction you're implementing validation rules for.
3. Update the `resources/config.xml` disclosure system file with details for your plugin.
4. Update `DisclosureSystems.py` with the names of your disclosure systems.
5. Update the `__init__.py` module:
   1. If there's a filer manual or other documentation for the rules you're implementing available online,
      update the comment at the top of the `__init__.py` module with a link.
   2. Update the `__pluginInfo__` details with the name and description of your plugin.
   3. Update the `DISCLOSURE_SYSTEM_VALIDATION_TYPE` variable to match the validation type you used in resources/config.xml.
   4. Remove any of the plugin hooks you don't need, including the functions defined in the `ValidationPluginExtension` class.
6. Update the `PluginValidationDataExtension` dataclass with any fields you need. This is passed between rules and is how
   you should cache data. Note, you should'
7. Implement the plugin specific validation rules in the rules directory using functions and the
   [@validation][validation-decorator] decorator.
8. [Open a PR][contributing-code] to have your plugin merged into Arelle.

## Example of a validation rule

:::{literalinclude} ../../../../arelle/examples/plugin/validate/XYZ/rules/rules01.py
:start-after: "# rule 01.01 (2022)"
:end-before: "# rule 01.01 (2023)"
:::

[validation-plugin]: #arelle.utils.validate.ValidationPlugin.ValidationPlugin
[validation-new-plugin-data]: #arelle.utils.validate.ValidationPlugin.ValidationPlugin.newPluginData
[validation-hook]: #arelle.utils.PluginHooks.ValidationHook
[validation-decorator]: #arelle.utils.validate.Decorator.validation
[plugin-validation-data]: #arelle.utils.validate.PluginValidationData.PluginValidationData
[example-plugin]: https://github.com/Arelle/Arelle/tree/master/arelle/examples/plugin/validate/XYZ
[validations-directory]: https://github.com/Arelle/Arelle/tree/master/arelle/plugin/validate
[contributing-code]: project:../../contributing.md#contributing-code
