from pathlib import Path, PurePath

from tests.integration_tests.validation.assets import ESEF_PACKAGES, UKFRC_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource, ConformanceSuiteConfig, ConformanceSuiteAssetConfig
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
    expected_additional_testcase_errors={f"*tests/FRC/{s}": val for s, val in {
        "FRC_01/index.xml:TC7_invalid": {
            "invalidIdentifier": 1,
            "multipleIdentifiers": 1,
            "segmentUsed": 1,
        },
        "FRC_02/index.xml:TC3_invalid": {
            "info:duplicatedSchema": 1,
            "xbrl:multipleTopLevelSchemasForNamespace": 1,
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
    }.items()},
    expected_failure_ids=frozenset({f"tests/FRC/{s}" for s in [
        # FRC XBRL Tagging Guide not yet implemented.
        "FRC_03/index.xml:TC2_invalid",
        "FRC_03/index.xml:TC3_invalid",
        "FRC_03/index.xml:TC4_invalid",
        "FRC_04/index.xml:TC2_invalid",
        "FRC_05/index.xml:TC4_invalid",
        "FRC_05/index.xml:TC5_invalid",
        "FRC_09/index.xml:TC6_invalid",
        "FRC_10/index.xml:TC3_invalid",
        "FRC_10/index.xml:TC4_invalid",
        "FRC_10/index.xml:TC5_invalid",
        "FRC_10/index.xml:TC6_invalid",
        "FRC_11/index.xml:TC2_invalid",
        "FRC_11/index.xml:TC3_invalid",
        "FRC_12/index.xml:TC3_invalid",
        "FRC_13/index.xml:TC2_invalid",
        "FRC_13/index.xml:TC3_invalid",
        "FRC_14/index.xml:TC4_invalid",
        "FRC_14/index.xml:TC5_invalid",
        "FRC_14/index.xml:TC6_invalid",
        "FRC_14/index.xml:TC7_invalid",
        "FRC_15/index.xml:TC2_invalid",
        "FRC_15/index.xml:TC3_invalid",
        "FRC_15/index.xml:TC4_invalid",
        "FRC_16/index.xml:TC2_invalid",
        "FRC_17/index.xml:TC2_invalid",
        "FRC_17/index.xml:TC3_invalid",
        "FRC_18/index.xml:TC3_invalid",
        "FRC_18/index.xml:TC4_invalid",
        "FRC_19/index.xml:TC2_invalid",
        "FRC_20/index.xml:TC3_invalid",
        "FRC_21/index.xml:TC2_invalid",
        "FRC_21/index.xml:TC3_invalid",
    ]}),
    info_url="https://www.frc.org.uk/library/standards-codes-policy/accounting-and-reporting/frc-taxonomies/frc-taxonomies-documentation-and-guidance/",
    name=PurePath(__file__).stem,
    disclosure_system="uksef-only-2025",
    plugins=frozenset({"inlineXbrlDocumentSet", "validate/ESEF"}),
    preprocessing_func=_preprocessing_func,
    shards=4,
)
