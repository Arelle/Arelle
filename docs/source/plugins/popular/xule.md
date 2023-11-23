# XULE

:::{index} XULE
:::

## Overview

The [XULE][github] plugin, developed and maintained by XBRL US, enhances XBRL data manipulation and querying. Inquiries
can be directed to [info@xbrl.us][xbrl-us-email]. XULE is instrumental in validating SEC and FERC filings, with both DQC
rules for SEC filings and FERC rules available in XULE format. It also allows for the creation of new XBRL reports and
facts. Utilize the `DQC Rules Validator` and `ESEF DQC Rules Validator` plugins for specific XULE validation rules. For
more details on XULE and its usage, visit the [XULE plugin readme][readme].

## Key Features

- **XBRL Data Querying and Manipulation**: Provides a user-friendly syntax for interacting with XBRL data.
- **Validation Capabilities**: Data quality rule sets provided for SEC and FERC filings.
- **Creation of XBRL Reports**: Enables the definition and creation of new XBRL reports.

## Example Command Line Usage

For all available options, refer to the [project repo](https://github.com/xbrlus/xule).

- **Run XULE SEC DQC validations**:

  ```bash
  python arelleCmdLine.py --plugins "validate/DQC|transforms/SEC" --validate --file filing-documents.zip
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
