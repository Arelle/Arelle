from pathlib import Path, PurePath

from tests.integration_tests.validation.assets import ESEF_PACKAGES, UKFRC_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteConfig,
    ConformanceSuiteAssetConfig,
)

_CORRUPTED_TEST_CASES = {
    "FRC_09": (
        # Test case references TC2_valid.zip, but actual file in suite has .xbri extension.
        ("TC2_valid.zip", "TC2_valid.xbri"),
        # Test case references TC3_valid.zip, but actual file in suite has .xbri extension.
        ("TC3_valid.zip", "TC3_valid.xbri"),
    ),
    "FRC_02": (
        # In test case TC3_invalid reference to TC2_invalid.zip, but the actual file in the suite is TC3_invalid.zip
        ("TC2_invalid.zip", "TC3_invalid.zip"),
    )
}

# Test packages built to exercise other rules do not carry the Companies House mandatory facts.
_MISSING_MANDATORY_ITEM_COUNTS = {
    "FRC_01/index.xml:TC1_valid": 1,
    "FRC_01/index.xml:TC8_invalid": 1,
    "FRC_04/index.xml:TC1_valid": 1,
    "FRC_05/index.xml:TC2_valid": 1,
    "FRC_05/index.xml:TC5_invalid": 1,
    "FRC_09/index.xml:TC3_valid": 1,
    "FRC_09/index.xml:TC5_valid": 1,
    "FRC_10/index.xml:TC1_valid": 1,
    "FRC_11/index.xml:TC1_valid": 1,
    "FRC_13/index.xml:TC1_valid": 1,
    "FRC_01/index.xml:TC2_valid": 1,
    "FRC_01/index.xml:TC3_valid": 1,
    "FRC_01/index.xml:TC4_valid": 1,
    "FRC_01/index.xml:TC5_valid": 1,
    "FRC_01/index.xml:TC6_invalid": 1,
    "FRC_01/index.xml:TC9_invalid": 1,
    "FRC_02/index.xml:TC1_valid": 1,
    "FRC_02/index.xml:TC2_valid": 1,
    "FRC_02/index.xml:TC3_invalid": 1,
    "FRC_03/index.xml:TC1_valid": 1,
    "FRC_04/index.xml:TC2_invalid": 1,
    "FRC_05/index.xml:TC1_valid": 1,
    "FRC_05/index.xml:TC3_valid": 1,
    "FRC_05/index.xml:TC6_invalid": 1,
    "FRC_06/index.xml:TC1_valid": 1,
    "FRC_06/index.xml:TC2_invalid": 1,
    "FRC_06/index.xml:TC3_invalid": 1,
    "FRC_07/index.xml:TC1_valid": 1,
    "FRC_07/index.xml:TC2_invalid": 1,
    "FRC_07/index.xml:TC3_invalid": 1,
    "FRC_07/index.xml:TC4_invalid": 1,
    "FRC_08/index.xml:TC1_valid": 1,
    "FRC_08/index.xml:TC2_invalid": 1,
    "FRC_08/index.xml:TC3_invalid": 1,
    "FRC_09/index.xml:TC1_valid": 1,
    "FRC_10/index.xml:TC2_valid": 1,
    "FRC_12/index.xml:TC1_valid": 1,
    "FRC_12/index.xml:TC2_valid": 1,
    "FRC_14/index.xml:TC1_valid": 1,
    "FRC_14/index.xml:TC2_valid": 1,
    "FRC_14/index.xml:TC3_valid": 1,
    "FRC_15/index.xml:TC1_valid": 1,
    "FRC_16/index.xml:TC1_valid": 1,
    "FRC_17/index.xml:TC1_valid": 1,
    "FRC_18/index.xml:TC1_valid": 1,
    "FRC_18/index.xml:TC2_valid": 1,
    "FRC_19/index.xml:TC1_valid": 1,
    "FRC_20/index.xml:TC1_valid": 1,
    "FRC_20/index.xml:TC2_valid": 1,
    "FRC_21/index.xml:TC1_valid": 1,
    "FRC_10/index.xml:TC3_invalid": 2,
    "FRC_11/index.xml:TC3_invalid": 2,
    "FRC_13/index.xml:TC2_invalid": 1,
    "FRC_13/index.xml:TC3_invalid": 1,
    "FRC_14/index.xml:TC4_invalid": 1,
    "FRC_14/index.xml:TC5_invalid": 1,
    "FRC_14/index.xml:TC6_invalid": 1,
    "FRC_14/index.xml:TC7_invalid": 1,
    "FRC_15/index.xml:TC2_invalid": 1,
    "FRC_15/index.xml:TC3_invalid": 1,
    "FRC_15/index.xml:TC4_invalid": 1,
    "FRC_16/index.xml:TC2_invalid": 1,
    "FRC_17/index.xml:TC2_invalid": 1,
    "FRC_17/index.xml:TC3_invalid": 1,
    "FRC_18/index.xml:TC3_invalid": 1,
    "FRC_18/index.xml:TC4_invalid": 1,
    "FRC_19/index.xml:TC2_invalid": 1,
    "FRC_20/index.xml:TC3_invalid": 1,
    "FRC_21/index.xml:TC2_invalid": 1,
    "FRC_21/index.xml:TC3_invalid": 1,
}

# Test packages built to exercise other rules are not named after the issuer LEI.
_PACKAGE_NAME_COUNTS = {
    "FRC_12/index.xml:TC2_valid": 1,
    "FRC_01/index.xml:TC1_valid": 1,
    "FRC_01/index.xml:TC2_valid": 1,
    "FRC_01/index.xml:TC3_valid": 1,
    "FRC_01/index.xml:TC4_valid": 1,
    "FRC_01/index.xml:TC5_valid": 1,
    "FRC_01/index.xml:TC6_invalid": 1,
    "FRC_01/index.xml:TC7_invalid": 1,
    "FRC_01/index.xml:TC8_invalid": 1,
    "FRC_01/index.xml:TC9_invalid": 1,
    "FRC_02/index.xml:TC1_valid": 1,
    "FRC_02/index.xml:TC2_valid": 1,
    "FRC_02/index.xml:TC3_invalid": 1,
    "FRC_03/index.xml:TC1_valid": 1,
    "FRC_03/index.xml:TC2_invalid": 1,
    "FRC_03/index.xml:TC3_invalid": 1,
    "FRC_03/index.xml:TC4_invalid": 1,
    "FRC_04/index.xml:TC1_valid": 1,
    "FRC_05/index.xml:TC1_valid": 1,
    "FRC_05/index.xml:TC2_valid": 1,
    "FRC_05/index.xml:TC3_valid": 1,
    "FRC_05/index.xml:TC4_invalid": 1,
    "FRC_05/index.xml:TC6_invalid": 1,
    "FRC_06/index.xml:TC1_valid": 1,
    "FRC_06/index.xml:TC2_invalid": 1,
    "FRC_06/index.xml:TC3_invalid": 1,
    "FRC_07/index.xml:TC1_valid": 1,
    "FRC_07/index.xml:TC2_invalid": 1,
    "FRC_07/index.xml:TC3_invalid": 1,
    "FRC_07/index.xml:TC4_invalid": 1,
    "FRC_08/index.xml:TC1_valid": 1,
    "FRC_08/index.xml:TC2_invalid": 1,
    "FRC_08/index.xml:TC3_invalid": 1,
    "FRC_09/index.xml:TC1_valid": 1,
    "FRC_09/index.xml:TC3_valid": 1,
    "FRC_09/index.xml:TC5_valid": 1,
    "FRC_10/index.xml:TC1_valid": 1,
    "FRC_10/index.xml:TC2_valid": 1,
    "FRC_10/index.xml:TC3_invalid": 2,
    "FRC_11/index.xml:TC1_valid": 1,
    "FRC_11/index.xml:TC2_invalid": 1,
    "FRC_11/index.xml:TC3_invalid": 2,
    "FRC_12/index.xml:TC1_valid": 1,
    "FRC_13/index.xml:TC1_valid": 1,
    "FRC_13/index.xml:TC2_invalid": 1,
    "FRC_13/index.xml:TC3_invalid": 1,
    "FRC_14/index.xml:TC1_valid": 1,
    "FRC_14/index.xml:TC2_valid": 1,
    "FRC_14/index.xml:TC3_valid": 1,
    "FRC_14/index.xml:TC4_invalid": 1,
    "FRC_14/index.xml:TC5_invalid": 1,
    "FRC_14/index.xml:TC6_invalid": 1,
    "FRC_14/index.xml:TC7_invalid": 1,
    "FRC_15/index.xml:TC1_valid": 1,
    "FRC_15/index.xml:TC2_invalid": 1,
    "FRC_15/index.xml:TC3_invalid": 1,
    "FRC_15/index.xml:TC4_invalid": 1,
    "FRC_16/index.xml:TC1_valid": 1,
    "FRC_16/index.xml:TC2_invalid": 1,
    "FRC_18/index.xml:TC1_valid": 1,
    "FRC_18/index.xml:TC2_valid": 1,
    "FRC_18/index.xml:TC3_invalid": 1,
    "FRC_18/index.xml:TC4_invalid": 1,
    "FRC_19/index.xml:TC1_valid": 1,
    "FRC_19/index.xml:TC2_invalid": 1,
    "FRC_20/index.xml:TC1_valid": 1,
    "FRC_20/index.xml:TC2_valid": 1,
    "FRC_20/index.xml:TC3_invalid": 1,
    "FRC_21/index.xml:TC1_valid": 1,
    "FRC_21/index.xml:TC2_invalid": 1,
    "FRC_21/index.xml:TC3_invalid": 1,
}

# Expected additional errors that are specific to individual test cases.
_OTHER_ERRORS: dict[str, dict[str, int]] = {
    "FRC_01/index.xml:TC7_invalid": {
        # UKFRC6 fire invalidIdentifier error because `FRC_01:TC7` doesn't have a second `ix:references` element with a target attribute,
        # and we can't separate schemas iso17442 and ENTITY_IDENTIFIER_SCHEME_CRN
        "invalidIdentifier": 1,
        # UKFRC1 and UKFRC5 have the same conditions for the test case, but have different checks and fire different errors
        "noUKFRSData": 1,
        # same explanation as invalidIdentifier error above
        "multipleIdentifiers": 1,
        "segmentUsed": 1,
    },
    "FRC_02/index.xml:TC3_invalid": {
        "info:duplicatedSchema": 1,
        "xbrl:multipleTopLevelSchemasForNamespace": 1,
    },
    "FRC_03/index.xml:TC2_invalid": {
        # rule_incorrectTarget covers the UKFRC1 and UKFRC3 incorrectTarget conditions.
        # UKFRC1 and UKFRC5 have the same conditions for the test case, but have different checks and fire different errors
        "noUKFRSData": 1,
        # UKFRC6 fire invalidIdentifier error because `FRC_03:TC2` doesn't have a target attribute,
        # and we can't separate schemas iso17442 and ENTITY_IDENTIFIER_SCHEME_CRN
        "invalidIdentifier": 1,
        # same explanation as invalidIdentifier error above
        "multipleIdentifiers": 1,
        "segmentUsed": 1,
    },
    "FRC_03/index.xml:TC3_invalid": {
        # rule_incorrectTarget covers the UKFRC1 and UKFRC3 incorrectTarget conditions.
        # UKFRC1 and UKFRC5 have the same conditions for the test case, but have different checks and fire different errors
        "noUKFRSData": 2,
        "segmentUsed": 1,
    },
    "FRC_03/index.xml:TC4_invalid": {
        # UKFRC3 and UKFRC5 have the same conditions for the test case, but have different checks and fire different errors
        "noUKFRSData": 2,
        "segmentUsed": 1,
    },
    "FRC_04/index.xml:TC2_invalid": {
        # Data in this test case is invalid for the rule UKFRC5
        "noESEFData": 2,
    },
    "FRC_05/index.xml:TC4_invalid": {
        "incorrectTarget": 1,
    },
    "FRC_05/index.xml:TC5_invalid": {
        # the `targetAttributeUsedForESEFContents` error appears because the test case
        # has only one `ix:references` element with a target attribute "UKFRS"
        # and has no `ix:references` element without a target attribute (default);
        # it is similar to the rule UKFRC5, which fires `noESEFData` error.
        "targetAttributeUsedForESEFContents": 1,
    },
    "FRC_07/index.xml:TC2_invalid": {
        # By the same logic that FRC_06:TC2 fires multipleIdentifiers, so should FRC_07:TC2
        "multipleIdentifiers": 1,
    },
    "FRC_08/index.xml:TC2_invalid": {
        # Unexpected segment also triggers lxml error
        "lxml.SCHEMAV_ELEMENT_CONTENT": 20,
        # Testcase does not specify count (1 is default), so 19 additional occurrences
        "xmlSchema:elementUnexpected": 19,
    },
    # Report package uses CR document type URI instead of rec URI.
    "FRC_09/index.xml:TC2_valid": {"rpe:unsupportedReportPackageVersion": 1},
    "FRC_09/index.xml:TC4_valid": {"rpe:unsupportedReportPackageVersion": 1},
    "FRC_09/index.xml:TC6_invalid": {
        "segmentUsed": 1,
    },
    "FRC_10/index.xml:TC3_invalid": {
        "spaceInFilePath": 2,
        "multipleReports": 1,
    },
    "FRC_10/index.xml:TC4_invalid": {
        "noReportsPresent": 1,
        "IOerror": 1,
        "arelle:nonIxdsDocument": 1,

    },
    "FRC_10/index.xml:TC5_invalid": {
        "noReportsPresent": 1,
        "IOerror": 1,
        "arelle:nonIxdsDocument": 1,

    },
    "FRC_11/index.xml:TC2_invalid": {
        "reportFileNameDoesNotFollowNamingConvention": 1,
        "ix11.10.1.2:contextReference": 2,
        "ix11.11.1.2:contextReference": 19,
        "ix11.10.1.2:unitReference": 47,
        "lxml.SCHEMAV_ELEMENT_CONTENT": 2,
        "xbrl.4.6.1:itemContextRef": 21,
        "xbrl.4.6.2:numericUnit": 47,
        "xmlSchema:syntax": 4,
    },
    "FRC_11/index.xml:TC3_invalid": {
        "spaceInFilePath": 2,
        "multipleReports": 1,
    },
    "FRC_12/index.xml:TC3_invalid": {
        # `FRC_10:TC5` checks the report file extension, same as `FRC_12:TC3` but fires a different error code
        "noReportsPresent": 2,
        "segmentUsed": 1,
    },
    "FRC_17/index.xml:TC2_invalid": {
        "reportFileNameDoesNotFollowNamingConvention": 1,
    },
    "FRC_17/index.xml:TC3_invalid": {
        "reportFileNameDoesNotFollowNamingConvention": 1,
    },
    "FRC_19/index.xml:TC2_invalid": {
        "executableCodePresent": 1,
    },
    "FRC_20/index.xml:TC3_invalid": {
        # The testcase ignores these schema errors as cvc-complex-type_3_2_2 and cvc-complex-type_4,
        # but Arelle reports them with lxml error codes (the charset attribute on xhtml:meta).
        "lxml.SCHEMAV_CVC_COMPLEX_TYPE_3_2_1": 1,
        "lxml.SCHEMAV_CVC_COMPLEX_TYPE_4": 1,
    },
}


def _expected_errors() -> dict[str, dict[str, int]]:
    """Merge the per-rule incidental error counts with the per-testcase ones."""
    expected: dict[str, dict[str, int]] = {}
    for errorCode, perTestcase in (
        ("missingCompaniesHouseMandatoryItem", _MISSING_MANDATORY_ITEM_COUNTS),
        ("reportPackageNameDoesNotFollowNamingConvention", _PACKAGE_NAME_COUNTS),
    ):
        for testcase, count in perTestcase.items():
            expected.setdefault(testcase, {})[errorCode] = count

    for testcase, errors in _OTHER_ERRORS.items():
        expected.setdefault(testcase, {}).update(errors)
    return {f"*tests/FRC/{testcase}": errors for testcase, errors in expected.items()}


def _preprocessing_func(config: ConformanceSuiteConfig) -> None:
    """Patch corrupted ``index.xml`` files inside the extracted suite.

    Iterates over :data:`_CORRUPTED_TEST_CASES` and applies each
    ``(old, new)`` replacement in-place to the associated test case
    ``index.xml`` located under ``<entry_point_root>/tests/FRC/<tc>/``.

    This runs after the conformance suite archives have been extracted
    but before validation is executed.

    Args:
        config: The :class:`ConformanceSuiteConfig` whose
            ``entry_point_root`` points to the extracted suite root.
    """
    for tc, fixes in _CORRUPTED_TEST_CASES.items():
        with open(
                config.entry_point_root /
                f"tests/FRC/{tc}/index.xml",
                "r+"
        ) as f:
            content = f.read()
            for old, new in fixes:
                content = content.replace(old, new)
            f.seek(0)
            f.write(content)
            f.truncate()


ZIP_PATH = Path("uksef-conformance-suite-v2.0.zip")
EXTRACTED_PATH = Path(ZIP_PATH.stem)
EXTRACTED_ZIP_PATH = EXTRACTED_PATH / "uksef-conformance-suite-v2.0" / "uksef-conformance-suite-v2.0.zip"
EXTRACTED_EXTRACTED_PATH = Path(EXTRACTED_ZIP_PATH.parent) / EXTRACTED_ZIP_PATH.stem


config = ConformanceSuiteConfig(
    args=[
        "--formula", "none",
    ],
    assets=[
        ConformanceSuiteAssetConfig.extracted_conformance_suite(
            (
                (ZIP_PATH, EXTRACTED_PATH),
                (EXTRACTED_ZIP_PATH, EXTRACTED_EXTRACTED_PATH),
            ),
            entry_point_root=EXTRACTED_EXTRACTED_PATH / "uksef-conformance-suite",
            entry_point=Path("index.xml"),
            public_download_url="https://www.frc.org.uk/documents/8116/uksef-conformance-suite-v2.0.zip",
            source=AssetSource.S3_PUBLIC,
        )
    ] +
    list(UKFRC_PACKAGES.values()) +
    [
        package for year in [2021, 2022, 2024] for package in ESEF_PACKAGES[year]
    ],
    base_taxonomy_validation="none",
    expected_additional_testcase_errors=_expected_errors(),
    info_url="https://www.frc.org.uk/library/standards-codes-policy/accounting-and-reporting/frc-taxonomies/frc-taxonomies-documentation-and-guidance/",
    name=PurePath(__file__).stem,
    disclosure_system="uksef-only-2025",
    plugins=frozenset({"inlineXbrlDocumentSet", "validate/ESEF"}),
    preprocessing_func=_preprocessing_func,
    shards=4,
)
