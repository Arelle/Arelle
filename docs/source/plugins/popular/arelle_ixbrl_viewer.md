# Arelle iXBRL Viewer

:::{index} Arelle iXBRL Viewer
:::

## Overview

The [Arelle iXBRL Viewer][github] is an interactive tool developed by the Arelle team for viewing Inline XBRL (iXBRL)
reports in web browsers. It enables users to access and interact with XBRL data embedded in iXBRL reports. This viewer
is designed with extensibility in mind, allowing users to adapt it to their needs.

## Key Features

- **Interactive Viewing**: Experience interactive viewing of iXBRL reports in any web browser.
- **Data Accessibility**: Easily access the XBRL data embedded within iXBRL reports.
- **Global Usage**: Adapted and customized by various service providers and regulators.

## Example Command Line Usage

For a comprehensive list of options, please refer to the [project readme][readme].

To create an `ixbrl-viewer.htm` viewer file, use the following command:

```bash
python arelleCmdLine.py --plugins iXBRLViewerPlugin --file filing-documents.zip --save-viewer ixbrl-viewer.htm
```

## Example GUI Usage

The Arelle iXBRL Viewer can also be configured and utilized via the graphical user interface (GUI).
Simply navigate to `Tools` > `iXBRL Viewer` in the menu to get started.

[github]: https://github.com/Arelle/ixbrl-viewer
[readme]: https://github.com/Arelle/ixbrl-viewer/blob/master/README.md
