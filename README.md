<div align="center">
  <img src="http://arelle.org/arelle/wp-content/themes/platform/images/logo-platform.png">
</div>

- [Arelle](#arelle)
  - [Features](#features)
- [Installation](#installation)
  - [Install PyPi package](#install-pypi-package)
  - [Install development version from github](#install-development-version-from-github)
  - [Install distributions](#install-distributions)
- [Reporting Issues](#reporting-issues)
- [Contribution guidelines](#contribution-guidelines)
- [License](#license)

# Arelle
[Arelle](https://arelle.org/arelle/) is an end-to-end open source XBRL platform,
which provides the XBRL community with an easy to use set of tools.  It supports
XBRL and its extension features in an extensible manner.  It does this in a
compact yet robust framework that can be used as a desktop application and can
be integrated with other applications and languages utilizing its web service.

## Features
* Support for XBRL versioning. Validation tool for versioning reports and a
  production tool to generate the basics of a versioning report that can be
  inferred by diffing two DTSs.
* Edgar and Global Filer Manual validation
* Base Specification, Dimensions, Generic linkbase validation
* Formula validation including support for extension modules
* Instance creation is supported using forms defined by the table linkbase (Eurofiling version).
* RSS Watch facility
* Users can explore the functionality and features from an interactive GUI,
  command line interface, or web services, and can develop their own controller
  interfaces as needed.
* The Web Service API allows XBRL integration with applications, such as those in
  Excel, Java or Oracle.
* QuickBooks is supported by XBRL-GL.


# Installation

The implementation is in Python 3.10, and is intended for Windows (any recent),
Mac OS-X 10.9+, Unix or Linux. The standard installation includes both desktop GUI,
a localhost RESTful web server and CLI.

## Install PyPi package
```shell
pip install arelle-release
```

## Install development version from github
```shell
pip install git+https://git@github.com/arelle/arelle.git@master#egg=arelle-release
```

## Install distributions
Distributions include Python version and resources needed to run Arelle.

Arelle provides distributions for the following operating systems:
* Windows (x64 and x32 architecture)
* Mac OS
* Linux (Ubuntu)
* Red Hat

Distributions can be downloaded from:
* [Arelle website](https://arelle.org/arelle/pub/)
* [github releases](https://github.com/Arelle/Arelle/releases)

# Reporting Issues
Please report issues to the [issue tracker](https://github.com/arelle/arelle/issues).

* Check that the issue has not already been reported.
* Check that the issue has not already been fixed in the latest code.
* Be clear and precise (do not prose, but name functions and commands exactly).
* Include the version of Arelle.

# Contribution guidelines

If you want to contribute to Arelle, be sure to review the
[contribution guidelines](https://github.com/Arelle/Arelle/blob/master/CONTRIBUTING.md).

# License

[Apache License 2.0](https://github.com/Arelle/Arelle/blob/master/LICENSE.md)
