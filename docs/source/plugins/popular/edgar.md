# EDGAR

:::{index} EDGAR
:::

## Overview

The [EDGAR Renderer][github-edgar-renderer] plugin, developed and maintained by the staff of the U.S. Securities and Exchange
Commission (SEC), is designed to provide traditional and inline XBRL viewers for SEC filings. It also integrates with
and extends the [EFM Validation plugin][github-validate-efm], offering EFM validation for SEC filings. For end-user support,
please contact the SEC directly at: [StructuredData@sec.gov][sec-email].

## Key Features

- **XBRL Viewers**: Offers both traditional and inline XBRL viewers for SEC filings.
- **EFM Validation**: Integrates with the EFM Validation plugin for comprehensive SEC filing validation.

## Example Command Line Usage

For a complete list of options, visit the [EDGAR plugins repository][github-edgar-renderer].

To create traditional and inline XBRL viewers in the `out` directory, use the following command:

```bash
python arelleCmdLine.py --plugins EDGAR/render --httpUserAgent "Arelle via <your-email-address>" --disclosureSystem efm --reports out --file filing-documents.zip
```

To validate an SEC filing:

```bash
python arelleCmdLine.py --plugins EDGAR/render --httpUserAgent "Arelle via <your-email-address>" --disclosureSystem efm --validate --file filing-documents.zip
```

## Example GUI Usage

The Edgar Renderer can be easily configured through the graphical user interface:

- To identify yourself with the SEC go to `Tools` > `Internet` > `HTTP User Agent` and enter your email address.
- To access the Renderer, go to `View` > `Edgar Renderer`.
- To select an EFM disclosure system, navigate to `Tools` > `Validation` > `Disclosure system checks`.

[github-edgar-renderer]: https://github.com/Arelle/EDGAR/tree/master/render
[github-validate-efm]: https://github.com/Arelle/EDGAR/tree/master/validate
[sec-email]: mailto:StructuredData@sec.gov
