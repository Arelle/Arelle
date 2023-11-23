# EDGAR Renderer

:::{index} EDGAR Renderer
:::

## Overview

The [EDGAR Renderer][github] plugin, developed and maintained by the staff of the U.S. Securities and Exchange
Commission (SEC), is designed to provide traditional and inline XBRL viewers for SEC filings. It also integrates with
and extends the [EFM Validation plugin][validate-efm], offering EFM validation for SEC filings. For end-user support,
please contact the SEC directly at: [StructuredData@sec.gov][sec-email].

## Key Features

- **XBRL Viewers**: Offers both traditional and inline XBRL viewers for SEC filings.
- **EFM Validation**: Integrates with the EFM Validation plugin for comprehensive SEC filing validation.

## Example Command Line Usage

For a complete list of options, visit the [EDGAR Renderer plugin repository][github].

To create traditional and inline XBRL viewers in the `out` directory, use the following command:

```bash
python arelleCmdLine.py --plugins EdgarRenderer --disclosureSystem efm --reports out --file filing-documents.zip
```

To validate an SEC filing:

```bash
python arelleCmdLine.py --plugins EdgarRenderer --disclosureSystem efm --validate --file filing-documents.zip
```

## Example GUI Usage

The Edgar Renderer can be easily configured through the graphical user interface:

- To access the Renderer, go to `View` > `Edgar Renderer`.
- To select an EFM disclosure system, navigate to `Tools` > `Validation` > `Disclosure system checks`.

[github]: https://github.com/Arelle/EdgarRenderer
[sec-email]: mailto:StructuredData@sec.gov
[validate-efm]: project:validation.md#validate-efm
