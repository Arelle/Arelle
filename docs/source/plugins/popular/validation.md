# Validation Plugins

:::{index} Validation Plugins
:::

## Overview of Validation Plugins

Arelle offers a range of validation plugins designed for taxonomy and jurisdiction-specific validations. These plugins
ensure that filings adhere to the required standards and rules of different disclosure systems. To effectively utilize
these plugins, follow a three-step validation process:

1. **Enable the Plugin**: Activate the desired validation plugin in Arelle.
2. **Select a Disclosure System**: Choose the appropriate disclosure system that matches your validation needs.
3. **Provide Formula Parameters**: Set formula parameters if applicable to the taxonomy being validated.
4. **Perform Validation**: Execute the validation process to check your document.

### Discovering Available Disclosure Systems

To identify which disclosure systems are supported by a specific validation plugin, you can use the following methods:

#### Command Line Interface (CLI)

Run this command to list the disclosure systems provided by a plugin:

```bash
python arelleCmdLine.py --plugins validate/PluginName --disclosureSystem help
```

#### Graphical User Interface (GUI)

In the GUI, follow these steps to view available disclosure systems:

- Navigate to the `Tools` menu.
- Go to `Validation`.
- Select `Select disclosure system...`.

## Validate CIPC

:::{index} Validate CIPC
:::

:::{autodoc2-docstring} arelle.plugin.validate.CIPC
:::

## Validate EBA, EIOPA

:::{index} Validate EBA, EIOPA
:::

:::{autodoc2-docstring} arelle.plugin.validate.EBA
:::

## Validate EFM

:::{index} Validate EFM
:::

The Validate EFM plugin, developed and maintained by the staff of the U.S. Securities and Exchange Commission (SEC), is
a crucial tool for ensuring compliance with the EDGAR Filer Manual (EFM) specifications. For direct end-user support,
contact the SEC at [StructuredData@sec.gov](mailto:StructuredData@sec.gov).

While the Validate EFM plugin is integral for EFM validations, it does not encompass all the validations required by the
EDGAR Filer Manual. To achieve comprehensive validation, it's essential to also enable the
[EDGAR Renderer plugin][edgar-renderer]. This additional plugin covers specific validations that are not included in the
Validate EFM plugin, ensuring thorough compliance with EFM standards.

[edgar-renderer]: project:edgar_renderer.md

## Validate EFM non-XBRL HTM

:::{index} Validate EFM non-XBRL HTM
:::

The Validate EFM non-XBRL HTM plugin, developed and maintained by the staff of the U.S. Securities and Exchange
Commission (SEC), is used to ensure EFM compliance for non-XBRL HTM documents. For direct end-user support, contact the
SEC at [StructuredData@sec.gov](mailto:StructuredData@sec.gov).

## Validate ESMA ESEF

:::{index} Validate ESMA ESEF
:::

:::{autodoc2-docstring} arelle.plugin.validate.ESEF
:::

## Validate FERC

:::{index} Validate FERC
:::

:::{autodoc2-docstring} arelle.plugin.validate.FERC
:::

## Validate HMRC

:::{index} Validate HMRC
:::

:::{autodoc2-docstring} arelle.plugin.validate.HMRC
:::

## Validate NL

:::{index} Validate NL
:::

:::{autodoc2-docstring} arelle.plugin.validate.NL
:::

## Validate ROS

:::{index} Validate ROS
:::

:::{autodoc2-docstring} arelle.plugin.validate.ROS
:::
