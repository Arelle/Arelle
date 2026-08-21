from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path("ird"),
            entry_point=Path("testcases.xml"),
        ),
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path("IRD_Taxonomies_2026-04-01.zip"),
            public_download_url="https://www.ird.gov.hk/eng/tax/ixbrl/IRD_Taxonomies_2026-04-01.zip",
        ),
    ],
    base_taxonomy_validation="none",
    disclosure_system="ird-2025-draft",
    expected_additional_testcase_errors={f"*{s}": val for s, val in {
        "NVAD-E-0420_invalid_testcase.xml:NVAD-E-0420_invalid": {
            # 2 total missing mandatory facts, conformance suites expects 1
            "IRD.NVAD-E-0050": 1,
        },
        "NVAD-E-0450_invalid_testcase.xml:NVAD-E-0450_invalid": {
            # 4 total missing mandatory facts, conformance suites expects 1
            "IRD.NVAD-E-0050": 3,
        },
        "NVAD-E-1270-negative_invalid_testcase.xml:NVAD-E-1270-negative_invalid": {
            "ix11.10.1.2:nonFractionNegative": 1,
        },
    }.items()},
    expected_failure_ids=frozenset({
        # Not implemented
        "553-E-0467-unknown-entrypoint_invalid_testcase.xml:553-E-0467-unknown-entrypoint_invalid",
        "553-E-0467_invalid_testcase.xml:553-E-0467_invalid",
        "553-E-0468_invalid_testcase.xml:553-E-0468_invalid",
        "553-E-0470_invalid_testcase.xml:553-E-0470_invalid",
        "553-E-0498_invalid_testcase.xml:553-E-0498_invalid",
        "553-E-0535_invalid_testcase.xml:553-E-0535_invalid",
        "NVAD-E-0740_invalid_testcase.xml:NVAD-E-0740_invalid",
        "NVAD-E-0750_invalid_testcase.xml:NVAD-E-0750_invalid",
        "NVAD-E-0760_invalid_testcase.xml:NVAD-E-0760_invalid",
        "NVAD-E-0770_invalid_testcase.xml:NVAD-E-0770_invalid",
        "NVAD-E-0780_invalid_testcase.xml:NVAD-E-0780_invalid",
        "NVAD-E-0790_invalid_testcase.xml:NVAD-E-0790_invalid",
        "NVAD-E-0800_invalid_testcase.xml:NVAD-E-0800_invalid",
        "NVAD-E-0810_invalid_testcase.xml:NVAD-E-0810_invalid",
        "NVAD-E-0940_invalid_testcase.xml:NVAD-E-0940_invalid",
        "NVAD-E-0950_invalid_testcase.xml:NVAD-E-0950_invalid",
        "NVAD-E-0960_invalid_testcase.xml:NVAD-E-0960_invalid",
        "NVAD-E-0970_invalid_testcase.xml:NVAD-E-0970_invalid",
        "NVAD-E-0980_invalid_testcase.xml:NVAD-E-0980_invalid",
        "NVAD-E-0981_invalid_testcase.xml:NVAD-E-0981_invalid",
        "NVAD-E-0982_invalid_testcase.xml:NVAD-E-0982_invalid",
        "NVAD-E-1000_invalid_testcase.xml:NVAD-E-1000_invalid",
        "NVAD-E-1010_invalid_testcase.xml:NVAD-E-1010_invalid",
        "NVAD-E-1020_invalid_testcase.xml:NVAD-E-1020_invalid",
        "NVAD-E-1030_invalid_testcase.xml:NVAD-E-1030_invalid",
        "NVAD-E-1040_invalid_testcase.xml:NVAD-E-1040_invalid",
        "NVAD-E-1050_invalid_testcase.xml:NVAD-E-1050_invalid",
        "NVAD-E-1060_invalid_testcase.xml:NVAD-E-1060_invalid",
        "NVAD-E-1070_invalid_testcase.xml:NVAD-E-1070_invalid",
        "NVAD-E-1080_invalid_testcase.xml:NVAD-E-1080_invalid",
        "NVAD-E-1081_invalid_testcase.xml:NVAD-E-1081_invalid",
        "NVAD-E-1340-textblock_invalid_testcase.xml:NVAD-E-1340-textblock_invalid",
        "NVAD-E-1340_invalid_testcase.xml:NVAD-E-1340_invalid",
        "NVAD-E-1360_invalid_testcase.xml:NVAD-E-1360_invalid",
    }),
    info_url="https://www.ird.gov.hk/eng/tax/bus_ixbrl.htm",
    name=PurePath(__file__).stem,
    plugins=frozenset({"validate/IRD", "inlineXbrlDocumentSet"}),
)
