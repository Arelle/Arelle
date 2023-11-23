# SEC Inline Transforms

:::{index} SEC Inline Transforms
:::

## Overview

The [SEC Inline Transforms][github] plugin, developed and maintained by the U.S. Securities and Exchange Commission
(SEC), facilitates specific iXBRL value transformations for SEC filings. For end-user support, direct inquiries to
[StructuredData@sec.gov][sec-email]. The plugin is automatically activated when either the
[EDGAR Renderer][edgar-renderer] or [EFM validation][validate-efm] plugins are selected.

## Key Features

- **iXBRL Transformations**: Tailored for transforming values in iXBRL used in SEC filings.
- **Integration with Other Plugins**: Works seamlessly with the `Edgar Renderer` and `validate/EFM` plugins.

## Example Command Line Usage

To load a filing with SEC iXBRL transforms, use the following command:

```bash
python arelleCmdLine.py --plugins transforms/SEC --file filing-documents.zip
```

## Example GUI Usage

To enable SEC transforms in the GUI:

1. Go to `Help` > `Manage plug-ins`.
2. Select the `SEC Inline Transforms` plugin to activate it.

[github]: https://github.com/Arelle/Arelle/blob/master/arelle/plugin/transforms/SEC/__init__.py
[sec-email]: mailto:StructuredData@sec.gov
[edgar-renderer]: project:edgar_renderer.md
[validate-efm]: project:validation.md#validate-efm
