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
        "V-301-xbri-with-single-ixds": {
            # There are two documents in the package, empty1.xhtml and empty2.xhtml,
            # each missing a title, so we must see two schema errors.
            "lxml.SCHEMAV_ELEMENT_CONTENT": 2,
            "ix11.14.1.2:missingResources": 1,
        },
        "V-302-xbri-with-single-html": {
            "lxml.SCHEMAV_ELEMENT_CONTENT": 1,
            "ix11.14.1.2:missingResources": 1,
        },
        "V-303-xbri-with-single-htm": {
            "lxml.SCHEMAV_ELEMENT_CONTENT": 1,
            "ix11.14.1.2:missingResources": 1,
        },
        # Report package references a taxonomy which does not exist.
        "V-508-xbr-with-no-taxonomy": {
            "IOerror": 1,
            "oime:invalidTaxonomy": 1,
        },
        "V-509-xbr-with-json-in-dot-xhtml-directory": {
            "IOerror": 1,
            "oime:invalidTaxonomy": 1,
        },
        "V-701-zip-with-no-taxonomy": {
            "IOerror": 1,
            "oime:invalidTaxonomy": 1,
        },
    }.items()},
    info_url="https://specifications.xbrl.org/work-product-index-taxonomy-packages-report-packages-1.0.html",
    membership_url="https://www.xbrl.org/join",
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset(["inlineXbrlDocumentSet"]),
)
