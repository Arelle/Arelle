---
# Compatibility-only SEC-linked page; see _index.md before moving or removing.
title: Applications
url: /arelle/pub/applications/
build:
  list: never
sitemap:
  disable: true
---

## Arelle Applications

Arelle provides an application programming interface that is used to develop XBRL applications.

---

### EDGAR® Renderer

EDGAR Renderer enables investors to view the interactive data filings submitted under the US Security and Exchange Commission (SEC) rules that require the submission of information in XBRL format to the EDGAR system. Previewing locally with the Renderer provides the capability to test how an interactive data submission will appear on the SEC's website when submitted via EDGAR.

EDGAR Renderer was created by staff of the U.S. Securities and Exchange Commission. Data and content created by government employees within the scope of their employment are not subject to domestic copyright protection. 17 U.S.C. 105.

There are two distributions of the version currently in production at the SEC:

- Pre-built application with EDGAR renderer and local viewer (based on Arelle), for Windows, macOS and Linux, from the [Arelle download page][download-page]:
  - Download and install.
  - Enable EDGAR Renderer plugin (help→manage plugins→select→EDGAR Renderer→ok→close).
  - Open an SEC filing (inline or traditional XBRL).
- [Documentation of EDGAR Renderer installation][edgar-installation]
- EDGAR Renderer source code for developers: [Arelle/EDGAR on GitHub][edgar-source]

We suggest installing and testing the app before the source.

End user support is by e-mail direct to SEC at: <StructuredData@sec.gov>

[download-page]: /download
[edgar-installation]: /legacy/edgar/edgar-renderer-installation
[edgar-source]: https://github.com/Arelle/EDGAR
