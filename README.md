# Arelle

[![PyPI](https://img.shields.io/pypi/v/arelle-release)](https://pypi.org/project/arelle-release/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/arelle-release)](https://pypi.org/project/arelle-release/)
[![Read the Docs](https://img.shields.io/readthedocs/arelle)](https://arelle.readthedocs.io/)

[![Arelle Banner](https://arelle.org/arelle/wp-content/themes/platform/images/logo-platform.png)](https://arelle.org/)

## Table of Contents

- [Arelle](#arelle)
  - [Table of Contents](#table-of-contents)
  - [Description](#description)
  - [Documentation](#documentation)
  - [Features](#features)
  - [Need Support?](#need-support)
    - [Arelle Within Other Products](#arelle-within-other-products)
    - [EdgarRenderer or EFM Validations](#edgarrenderer-or-efm-validations)
    - [Installing or Running Arelle](#installing-or-running-arelle)
    - [Bug Report or Feature Request](#bug-report-or-feature-request)
    - [Security Vulnerabilities](#security-vulnerabilities)
    - [How-To and General XBRL Questions](#how-to-and-general-xbrl-questions)
    - [Email](#email)
  - [How To Contribute](#how-to-contribute)
  - [License](#license)

## Description

Arelle is an end-to-end open source XBRL platform, which provides the XBRL community
with an easy to use set of tools. It supports XBRL and its extension features in
an extensible manner. It does this in a compact yet robust framework that can be
used as a desktop application and can be integrated with other applications and
languages utilizing its web service, command line interface, and Python API.

## Documentation

Need help with Arelle? Go check out [our documentation][read-the-docs].

[read-the-docs]: https://arelle.readthedocs.io/

## Features

- Fully-featured XBRL processor with GUI, CLI, Python API and Web Service API.
- Support for the XBRL Standard, including:
    - XBRL v2.1 and XBRL Dimensions v1.0
    - XBRL Formula v1.0
    - Taxonomy Packages v1.0
    - xBRL-JSON v1.0 and xBRL-CSV v1.0
    - Inline XBRL v1.1
    - Units Registry v1.0
- Certified by XBRL International as a [Validating Processor][certification].
- Support for filing programme validation rules:
    - Edgar Filer Manual validation (US SEC)
    - ESEF Reporting Manual (EU)
    - HMRC (UK)
    - CIPC (South Africa)
    - FERC (US Federal Energy Regulatory Commission)
- Integrated support for [Arelle Inline XBRL Viewer][viewer].
- Extensible plugin architecture.
- Support for XF text-based Formula and XULE validation rules.
- The Web Service API allows XBRL integration with applications, such as those in
  Excel, Java or Oracle.
- Instance creation is supported using forms defined by the table linkbase.
- Support for reading/monitoring US SEC XBRL RSS feeds (RSS Watch).

[viewer]: https://github.com/Arelle/ixbrl-viewer
[certification]: https://software.xbrl.org/processor/arelle-arelle

## Need Support?

Whether you've found a bug, need help with installation, have a feature request,
or want to know how to use Arelle, we can help! Here's a quick guide:

When reporting issues it's important to include as much information as possible:

- what version of Arelle are you using?
- how are you using Arelle (GUI, command line, web server, or the Python API?)
- what operating system (Windows, macOS, Ubuntu, etc.) are you using?
- what plugins if any do you have enabled?
- can you provide an XBRL report that recreates the issue?
- what's the diagnostics output (`arelleCmdLine.exe --diagnostics`) on your system?

### Arelle Within Other Products

A number of service providers embed Arelle within their XBRL products and tools.
If you're having an issue with Arelle within one of these offerings please
contact the developer of that tool for support or first verify that you have the
same issue when using Arelle directly. Most issues in these situations are caused
by the tool using an old version of Arelle or not running a valid command.

### EdgarRenderer or EFM Validations

The SEC develops and maintains the EdgarRenderer and EFM validation plugins. Please
report issues with these plugins directly to the SEC (<StructuredData@sec.gov>).

### Installing or Running Arelle

Most installation and startup issues can be resolved by downloading the latest version
of Arelle and performing a [clean install][clean-install]. If that doesn't resolve
the problem for you, please [report a bug](#bug-report-or-feature-request).

[clean-install]: https://arelle.readthedocs.io/en/latest/install.html#clean-install

### Bug Report or Feature Request

Please use the GitHub [issue tracker][github-issue-tracker] if you'd like to suggest
a new feature or report a bug.

Before opening a new issue, please:

- Check that the issue has not already been reported.
- Check that the issue has not already been fixed in the latest release.
- Be clear and precise (do not prose, but name functions and commands exactly).
- For bug reports include the version of Arelle you're using.

[github-issue-tracker]: https://github.com/Arelle/Arelle/issues

### Security Vulnerabilities

Identified a security concern? Email the Arelle team (<Support@arelle.org>) so we
can resolve the issue and make sure service providers and authorities who use Arelle
in production are prepared to update and apply security patches before notifying
the general public.

### How-To and General XBRL Questions

Have a question that isn't covered by the [documentation](#documentation)?
Join our [Arelle Google Group][google-group] and start a conversation with the Arelle
team and community of experts.

### Email

The Arelle team can also be reached by email (<Support@arelle.org>) for issues that
aren't a good fit for the other support channels. However, please note that you will
likely receive a faster response if you [open a GitHub issue][new-github-issue]
or start a new conversation in the [Arelle Google Group][google-group] where the
Arelle team is active and other people within the community can also see and respond
to your message.

[google-group]: https://groups.google.com/g/arelle-users
[new-github-issue]: https://github.com/Arelle/Arelle/issues/new/choose

## How To Contribute

Interested in contributing to Arelle? Awesome! Make sure to review our
[contribution guidelines][contribution guidelines].

[contribution guidelines]: https://arelle.readthedocs.io/en/latest/contributing.html



## 👥 Contributors

<div align="center">
  <a href="https://github.com/Arelle/Arelle/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=Arelle/Arelle&max=100&columns=10" style="margin: 5px;" />
  </a>
  <p>Join our community and become a contributor today! 🚀 </p>
</div>



## License

[Apache License 2.0][license]

[license]: https://arelle.readthedocs.io/en/latest/license.html
