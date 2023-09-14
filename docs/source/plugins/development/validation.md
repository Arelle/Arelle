# Create a Validation Plugin

:::{index} Create a Validation Plugin
:::

One of the more common reasons to build a plugin is to add support for taxonomy or jurisdiction specific validation rules.
To help accelerate the process of creating new validation plugins there's a [ValidationPlugin][validation-plugin] class
and [@validation][validation-decorator] decorator for writing validation rule functions along with an [example template validation plugin][example-plugin]
that demonstrates how to use them together and can be copied as a starting point.

## Steps to Create a New Validation Plugin

1. Copy the [XYZ validation plugin][example-plugin] from the examples directory into the [Arelle/plugins/validate directory][validations-directory].
2. Rename the plugin module from `XYZ` to the name of the taxonomy or jurisdiction you're implementing validation rules for.
3. Update the resources/config.xml disclosure system file with details for your plugin.
4. Update the `__init__.py` module:
   1. If there's a filer manual or other documentation for the rules you're implementing available online,
      update the comment at the top of the `__init__.py` module with a link.
   2. Update the `__pluginInfo__` details with the name and description of your plugin.
   3. Update the `DISCLOSURE_SYSTEM_VALIDATION_TYPE` variable to match the validation type you used in resources/config.xml.
   4. Remove any of the plugin hooks you don't need, including the functions defined in the `ValidationPluginExtension` class.
5. Implement the plugin specific validation rules in the rules directory using functions and the [@validation][validation-decorator] decorator.
6. [Open a PR][contributing-code] to have your plugin merged into Arelle.

## Example of a validation rule

:::{literalinclude} ../../../../arelle/examples/plugin/validate/XYZ/rules/rules01.py
:start-after: "# rule 01.01 (2022)"
:end-before: "# rule 01.01 (2023)"
:::

[validation-plugin]: #arelle.utils.validate.ValidationPlugin.ValidationPlugin
[validation-decorator]: #arelle.utils.validate.Decorator.validation
[example-plugin]: https://github.com/Arelle/Arelle/tree/master/arelle/examples/plugin/validate/XYZ
[validations-directory]: https://github.com/Arelle/Arelle/tree/master/arelle/plugin/validate
[contributing-code]: project:../../contributing.md#contributing-code
