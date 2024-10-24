from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

config = ConformanceSuiteConfig(
    args=[
        "--reportPackage"
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path("report-package-conformance.zip"),
            entry_point=Path("report-package-conformance/index.csv"),
        ),
    ],
    expected_additional_testcase_errors={f"report-package-conformance/index.csv:{s}": val for s, val in {
        # "Empty" iXBRL docs are missing schema required elements.
        "V-301-xbri-with-single-ixds": frozenset({"lxml.SCHEMAV_ELEMENT_CONTENT", "ix11.14.1.2:missingResources"}),
        "V-302-xbri-with-single-html": frozenset({"lxml.SCHEMAV_ELEMENT_CONTENT", "ix11.14.1.2:missingResources"}),
        "V-303-xbri-with-single-htm": frozenset({"lxml.SCHEMAV_ELEMENT_CONTENT", "ix11.14.1.2:missingResources"}),
        # Report package references a taxonomy which does not exist.
        "V-508-xbr-with-no-taxonomy": frozenset({"IOerror", "oime:invalidTaxonomy"}),
        "V-509-xbr-with-json-in-dot-xhtml-directory": frozenset({"IOerror", "oime:invalidTaxonomy"}),
        "V-701-zip-with-no-taxonomy": frozenset({"IOerror", "oime:invalidTaxonomy"}),
        # Additional OIM errors from invalid OIM test reports.
        "V-603-xbr-with-invalid-jrr": frozenset({"xbrlje:invalidJSON"}),
        "V-604-xbr-with-invalid-jrr-duplicate-keys": frozenset({"oimce:unsupportedDocumentType", "xbrlje:invalidJSON"}),
        "V-605-xbr-with-invalid-jrr-utf32": frozenset({"xbrlje:invalidJSON"}),
        "V-606-xbr-with-invalid-jrr-utf16": frozenset({"xbrlje:invalidJSON"}),
        "V-607-xbr-with-invalid-jrr-utf7": frozenset({"xbrlje:invalidJSON"}),
        "V-608-xbr-with-invalid-jrr-missing-documentInfo": frozenset({"oimce:unsupportedDocumentType"}),
        "V-609-xbr-with-invalid-jrr-missing-documentType": frozenset({"oimce:unsupportedDocumentType"}),
        "V-610-xbr-with-invalid-jrr-non-string-documentType": frozenset({"oimce:unsupportedDocumentType"}),
        "V-611-xbr-with-invalid-jrr-non-object-documentInfo": frozenset({"oimce:unsupportedDocumentType"}),
    }.items()},
    expected_missing_testcase_errors={f"report-package-conformance/index.csv:{s}": val for s, val in {
        # Expects both report package and taxonomy package invalidDirectoryStructure errors, but test cases are not taxonomy packages.
        "V-010-duplicate-paths-in-zip-entry": frozenset({"tpe:invalidDirectoryStructure"}),
        "V-011-duplicate-paths-in-zip-entry-dir-under-file": frozenset({"tpe:invalidDirectoryStructure"}),
    }.items()},
    info_url="https://specifications.xbrl.org/work-product-index-taxonomy-packages-report-packages-1.0.html",
    membership_url="https://www.xbrl.org/join",
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset(["inlineXbrlDocumentSet"]),
)
