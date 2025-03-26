# ESEF (European Single Electronic Format)

:::{index} ESEF
:::

## Overview

The European Single Electronic Format (ESEF) is a digital reporting requirement mandated by the European Securities and Markets Authority (ESMA) for publicly listed companies in the European Union. It requires annual financial reports to be prepared in XHTML format with XBRL tags embedded within the document using the Inline XBRL (iXBRL) format for consolidated financial statements.

## Validation in Arelle

### XBRL Core Validation

Arelle automatically validates that all XBRL reports meet the standards defined in the XBRL specifications and executes any validation rules implemented using the XBRL Formula specification.

### ESEF-Specific Validation

ESMA defines additional validation rules and requirements in their Regulatory Technical Standards (RTS) and ESEF Reporting Manual. Since these rules are published as plain text and cannot be automatically derived from the specifications, Arelle provides a dedicated plugin called `Validate ESMA ESEF` that implements these additional validation rules.

## ESEF Disclosure Systems

Arelle's validation plugins can provide multiple collections of validation rules. Each of these collections is called a disclosure system. The ESEF disclosure systems in Arelle correspond to the year of the reporting manual that the plugin validates against:

### Types of ESEF Disclosure Systems

- **Annual consolidated systems**:
  - Format: `esef-YYYY` (e.g., `esef-2023`)
  - Purpose: Validates against rules published in that year's reporting manual
  - Use for: XHTML reports with Inline XBRL tagging of consolidated statements

- **Unconsolidated systems**:
  - Format: `esef-unconsolidated-YYYY` (e.g., `esef-unconsolidated-2023`)
  - Purpose: Validates XHTML reports without XBRL tagging
  - Use for: Annual reports without consolidated IFRS statements

> **Important**: Always select the appropriate disclosure system version that matches your reporting period requirements, as validation rules evolve between reporting years.

## GUI Validation

To enable ESEF validation in the Arelle graphical user interface:

1. **Enable the ESEF Plugin**:
   - Use the plugin manager to [select][select-esef-gui-plugin] the `Validate ESMA ESEF` plugin to enable it
   - Restart Arelle if required

2. **Select the ESEF Disclosure System**:
   - Navigate to `Tools` > `Validation` > `Select disclosure system...`
   - Choose the appropriate ESEF disclosure system:
     - For reports with Inline XBRL: Select year-specific system matching your requirements (e.g., `ESMA RTS on ESEF-2023`)
     - For reports without XBRL tagging: Select `ESMA RTS on ESEF-2023 Unconsolidated` or equivalent for your reporting year

3. **Set Formula Parameters (Optional)**:
   - Navigate to `Tools` > `Formula` > `Parameters...`
   - Set parameters as needed:
     - `authority`: For country-specific validations (e.g., `DK` for Denmark or `UK` for UKSEF)
     - `eps_threshold`: Custom calculation tolerance for numeric accuracy checks

4. **Open the ESEF Report**:
   - Use `File` > `Open File...` to open the ESEF report (can be .zip package, or .xbri report package.)

5. **Trigger Validation**:
   - Select `Tools` > `Validation` > `Validate`
   - Validation results will appear in the messages window at the bottom of the screen

[select-esef-gui-plugin]: project:/plugins/using_with_gui.md#select

## CLI Validation

Arelle's command-line interface provides flexible options for validating ESEF reports in automated workflows or batch processing.

### Basic CLI Usage Patterns

#### Basic Validation (Latest Supported Reporting Manual)

```bash
python arelleCmdLine.py --plugin validate/ESEF --disclosureSystem esef --validate --file report.xbri
```

#### Year-Specific Validation

```bash
python arelleCmdLine.py --plugin validate/ESEF --disclosureSystem esef-2023 --validate --file report.zip
```

#### Country-Specific Validation Rules

For authority-specific validations (e.g., Denmark or United Kingdom):

```bash
python arelleCmdLine.py --plugin validate/ESEF --disclosureSystem esef-2023 --parameters "authority=DK" --validate --file report.zip
```

### Including ESEF Taxonomy Packages

If you need to include ESEF taxonomy packages:

```bash
python arelleCmdLine.py --plugin validate/ESEF --package path/to/esef_taxonomy.zip --disclosureSystem esef-2023 --validate --file report.zip
```

### Output Formats

Control the validation output format:

```bash
python arelleCmdLine.py --plugin validate/ESEF --disclosureSystem esef-2023 --validate --file report.zip --logFile results.xml
```

Available log file formats:

- `xml`: Structured XML output for automated processing
- `json`: JSON-formatted results
- `text`: Plain text (default)

## Reference Documentation

- [ESMA ESEF Reporting Manual](https://www.esma.europa.eu/document/esef-reporting-manual) - Latest guidelines and best practices
- [ESMA RTS on ESEF](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32019R0815) - Regulatory Technical Standards
