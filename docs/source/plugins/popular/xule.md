# XULE

:::{index} XULE
:::

## Overview

The [XULE][github] plugin, developed and maintained by XBRL US, enhances XBRL data manipulation and querying. Inquiries
can be directed to [info@xbrl.us][xbrl-us-email]. XULE is instrumental in validating SEC and FERC filings, with both DQC
rules for SEC filings and FERC rules available in XULE format. It also allows for the creation of new XBRL reports and
facts. Utilize the `DQC Rules Validator` and `ESEF DQC Rules Validator` plugins for specific XULE validation rules. For
more details on XULE and its usage, visit the [XULE plugin readme][readme].

## Installation

XULE is included in Arelle's [prepackaged distributions][prepackaged], so no additional
installation steps are needed if you are using one of those.

If you installed Arelle [from source][from-source] or via [pip][python-package],
the XULE plugin is **not** included and must be installed separately.
See the [XULE plugin README][readme] for installation instructions.

Additionally, XULE requires some extra Python dependencies. You can install them by running:

```shell
pip install arelle-release[XULE]
```

Or if running from source:

```shell
pip install -r requirements-plugins.txt
```

[prepackaged]: project:../../install.md#prepackaged-distributions
[from-source]: project:../../install.md#from-python-source
[python-package]: project:../../install.md#python-package

## Key Features

- **XBRL Data Querying and Manipulation**: Provides a user-friendly syntax for interacting with XBRL data.
- **Validation Capabilities**: Data quality rule sets provided for SEC and FERC filings.
- **Creation of XBRL Reports**: Enables the definition and creation of new XBRL reports.

## Example Command Line Usage

For all available options, refer to the [project repo](https://github.com/xbrlus/xule).

- **Run XULE SEC DQC validations**:

  ```bash
  python arelleCmdLine.py --plugins "validate/DQC|EDGAR/transforms" --validate --file filing-documents.zip
  ```

- **Run XULE ESEF DQC validations**:

  ```bash
  python arelleCmdLine.py --plugins validate/ESEF-DQC --validate --file filing-documents.zip
  ```

- **Compile Your Own XULE Validation Rules to a Rule Set**:

  ```bash
  python arelleCmdLine.py --plugins xule --xule-compile xule-source-files/v1 --xule-rule-set xule-rule-set-v1.zip
  ```

## Example GUI Usage

Configure the XULE processor and DQC validation plugins in Arelle via:

- `Tools` > `Xule`
- `Tools` > `DQC`
- `Tools` > `ESEF-dqc`
- `Tools` > `Validation` > `DQC Rules`
- `Tools` > `Validation` > `ESEF-dqc Rules`

[github]: https://github.com/xbrlus/xule
[readme]: https://github.com/xbrlus/xule/blob/main/plugin/xule/README.md
[xbrl-us-email]: mailto:info@xbrl.us
