from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

# Lack of detectable entrypoint causes the root of the zip to be treated as the entrypoint. ('' entry does not exist)
ERRORS_NO_ENTRYPOINT = {
    "IOerror": 1,
}

# OIM validations may also run against report package contents
ERRORS_OIM_UNSUPPORTED = {
    "oimce:unsupportedDocumentType": 1,
}
ERRORS_OIM_INVALID_JSON = {
    "xbrlje:invalidJSON": 1,
}
ERRORS_OIM_TAXONOMY_DOES_NOT_EXIST = {
    # Report package references a taxonomy which does not exist.
    "IOerror": 1,
    "oime:invalidTaxonomy": 1,
}

ERRORS_REPORT_COUNT = {
    "arelle:expectedInstanceCount": 1,
}

# We pass --taxonomyPackage which forces valdation as taxonomy package even if metdata file does not exist.
ERRORS_TPE_DIRECTORY_STRUCTURE = {
    "tpe:invalidDirectoryStructure": 1,
}
ERRORS_TPE_METADATA_DIRECTORY = {
    "tpe:metadataDirectoryNotFound": 1,
}
ERRORS_TPE_METADATA_FILE = {
    "tpe:metadataFileNotFound": 1,
}
ERRORS_TPE_METADATA = ERRORS_TPE_METADATA_DIRECTORY | ERRORS_TPE_METADATA_FILE


ZIP_PATH = Path("report-package-conformance.zip")
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH / "report-package-conformance",
            entry_point=Path("index.csv"),
        ),
    ],
    expected_additional_testcase_errors={f"index.csv:{s}": val for s, val in {
        # Invalid zip also fires FileSourceError.
        "V-000-invalid-zip": {
            "FileSourceError": 1,
            "xmlSchema:syntax": 1,
        },
        "V-001-valid-taxonomy-package": {
            # Taxonomy package references non-existent "http://www.xbrl.org/sample-taxonomy/1.0/base.xsd"
            "IOerror": 1,
        },
        "V-002-invalid-taxonomy-package-metadata": ERRORS_REPORT_COUNT,
        "V-003-multiple-top-level-directories": ERRORS_NO_ENTRYPOINT,
        "V-004-empty-zip": ERRORS_NO_ENTRYPOINT,
        "V-006-dot-slash-in-zip-entry": ERRORS_NO_ENTRYPOINT,
        "V-007-dot-dot-slash-in-zip-entry": ERRORS_NO_ENTRYPOINT,
        "V-008-double-slash-in-zip-entry": ERRORS_NO_ENTRYPOINT,
        "V-010-duplicate-paths-in-zip-entry": ERRORS_NO_ENTRYPOINT,
        "V-011-duplicate-paths-in-zip-entry-dir-under-file": ERRORS_NO_ENTRYPOINT,
        "V-200-unsupportedReportPackageVersion": ERRORS_REPORT_COUNT,
        "V-201-missing-report-package-json": ERRORS_REPORT_COUNT,
        "V-202-missing-report-package-json": ERRORS_REPORT_COUNT,
        "V-205-unconstrained-documentType": ERRORS_REPORT_COUNT,
        "V-206-xbri-documentType": ERRORS_REPORT_COUNT,
        "V-207-xbri-without-reportPackage-json": ERRORS_REPORT_COUNT,
        "V-209-xbr-without-reportPackage-json": ERRORS_REPORT_COUNT,
        # "Empty" iXBRL docs are missing schema required elements.
        "V-301-xbri-with-single-ixds": {
            # "Empty" iXBRL docs are missing schema required elements.
            # There are two documents in the package, empty1.xhtml and empty2.xhtml,
            # each missing a title, so we must see two schema errors.
            "lxml.SCHEMAV_ELEMENT_CONTENT": 2,
            "ix11.14.1.2:missingResources": 1,
        },
        "V-302-xbri-with-single-html": {
            # "Empty" iXBRL docs are missing schema required elements.
            "lxml.SCHEMAV_ELEMENT_CONTENT": 1,
            "ix11.14.1.2:missingResources": 1,
        },
        "V-303-xbri-with-single-htm": {
            # "Empty" iXBRL docs are missing schema required elements.
            "lxml.SCHEMAV_ELEMENT_CONTENT": 1,
            "ix11.14.1.2:missingResources": 1,
        },
        "V-304-xbri-with-no-taxonomy": ERRORS_TPE_METADATA_FILE,
        "V-305-xbri-with-xhtml-in-dot-json-directory": ERRORS_TPE_METADATA_FILE,
        "V-306-xbri-with-xhtml-in-dot-xbrl-directory": ERRORS_TPE_METADATA_FILE,
        "V-403-xbri-with-multiple-reports": ERRORS_REPORT_COUNT | {
            # "Empty" iXBRL docs are missing schema required elements.
            "lxml.SCHEMAV_ELEMENT_CONTENT": 2,
            "ix11.14.1.2:missingResources": 2,
        },
        "V-508-xbr-with-no-taxonomy":
            ERRORS_OIM_TAXONOMY_DOES_NOT_EXIST |
            ERRORS_TPE_METADATA_FILE,
        "V-509-xbr-with-json-in-dot-xhtml-directory":
            ERRORS_OIM_TAXONOMY_DOES_NOT_EXIST |
            ERRORS_TPE_METADATA_FILE,
        "V-603-xbr-with-invalid-jrr": ERRORS_OIM_INVALID_JSON,
        "V-604-xbr-with-invalid-jrr-duplicate-keys": ERRORS_OIM_INVALID_JSON | ERRORS_OIM_UNSUPPORTED,
        "V-605-xbr-with-invalid-jrr-utf32": ERRORS_OIM_INVALID_JSON,
        "V-606-xbr-with-invalid-jrr-utf16": ERRORS_OIM_INVALID_JSON,
        "V-607-xbr-with-invalid-jrr-utf7": ERRORS_OIM_INVALID_JSON,
        "V-608-xbr-with-invalid-jrr-missing-documentInfo": ERRORS_OIM_UNSUPPORTED,
        "V-609-xbr-with-invalid-jrr-missing-documentType": ERRORS_OIM_UNSUPPORTED,
        "V-610-xbr-with-invalid-jrr-non-string-documentType": ERRORS_OIM_UNSUPPORTED,
        "V-611-xbr-with-invalid-jrr-non-object-documentInfo": ERRORS_OIM_UNSUPPORTED,
        "V-612-xbr-with-multiple-reports": ERRORS_REPORT_COUNT,
        "V-617-xbr-with-multiple-reports-in-a-subdirectory": ERRORS_REPORT_COUNT,
        "V-701-zip-with-no-taxonomy":
            ERRORS_OIM_TAXONOMY_DOES_NOT_EXIST |
            ERRORS_TPE_METADATA_FILE,
        "V-803-zip-with-multiple-reports-in-a-subdirectory": ERRORS_REPORT_COUNT,
        "V-804-zip-with-multiple-reports-in-a-subdirectory-uppercase": ERRORS_REPORT_COUNT,
        "V-900-future-zip": ERRORS_TPE_METADATA,
        "V-901-future-xbri": ERRORS_TPE_DIRECTORY_STRUCTURE,
        "V-902-future-xbr": ERRORS_TPE_DIRECTORY_STRUCTURE,
        "V-903-future-xbrx": ERRORS_TPE_METADATA,
        "V-904-future-package-with-invalid-reportPackage-json": ERRORS_TPE_METADATA,
        "V-905-future-package-with-invalid-reportPackage-json-duplicate-keys": ERRORS_TPE_METADATA,
        "V-906-future-package-with-invalid-reportPackage-json-utf32": ERRORS_TPE_METADATA,
        "V-907-future-package-with-invalid-reportPackage-json-utf16": ERRORS_TPE_METADATA,
        "V-908-future-package-with-invalid-reportPackage-json-utf7": ERRORS_TPE_METADATA,
        "V-909-future-package-with-invalid-reportPackage-json-missing-documentInfo": ERRORS_TPE_METADATA,
        "V-910-future-package-with-invalid-reportPackage-json-missing-documentType": ERRORS_TPE_METADATA,
        "V-911-future-package-with-invalid-reportPackage-json-non-string-documentType": ERRORS_TPE_METADATA,
        "V-912-future-package-with-invalid-reportPackage-json-non-object-documentInfo": ERRORS_TPE_METADATA,
        "V-913-future-package-with-bom-in-reportPackage-json": ERRORS_TPE_METADATA,
        "V-914-current-and-future-package": ERRORS_TPE_METADATA_FILE,
    }.items()},
    expected_failure_ids=frozenset({f"index.csv:{s}" for s in {
        # Missing rpe:invalidArchiveFormat: Encrypted zip causes controller to exit at entry point detection (but after taxonomy package validation), report package validation does not run.
        "V-012-encrypted-zip",
    }}),
    info_url="https://specifications.xbrl.org/work-product-index-taxonomy-packages-report-packages-1.0.html",
    membership_url="https://www.xbrl.org/join",
    name=PurePath(__file__).stem,
    plugins=frozenset(["inlineXbrlDocumentSet"]),
    runtime_options={
        'reportPackage': True,
        'taxonomyPackage': True,
    },
    test_case_result_options='match-all', # README.md in suite says match-any is fine, but we can be more strict.
)
