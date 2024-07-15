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
    expected_failure_ids=frozenset(f"report-package-conformance/index.csv:{s}" for s in [
        # 0xx - basic zip structure and package identification tests
        "V-000-invalid-zip",  # rpe:invalidArchiveFormat tpe:invalidArchiveFormat,0,A report package MUST conform to the .ZIP File Format Specification
        # "V-001-valid-taxonomy-package",  # ,0,"Minimal valid taxonomy package (not a report package). If the package has a file extension of .zip and neither [META-INF/reportPackage.json nor reports] exists, the file is treated as a taxonomy package, and further constraints and processing defined by this specification are not applied."
        # "V-002-invalid-taxonomy-package-metadata",  # tpe:invalidMetaDataFile,0,If a report package contains the path META-INF/taxonomyPackage.xml within the STLD then it MUST be a valid taxonomy package.
        "V-003-multiple-top-level-directories",  # rpe:invalidDirectoryStructure tpe:invalidDirectoryStructure,0,A report package conforming to this specification MUST contain a single top-level directory
        "V-004-empty-zip",  # rpe:invalidDirectoryStructure tpe:invalidDirectoryStructure,0,A report package conforming to this specification MUST contain a single top-level directory
        "V-005-leading-slash-in-zip-entry",  # rpe:invalidArchiveFormat tpe:invalidArchiveFormat,0,Leading slash is illegal according to the ZIP specficiation
        "V-006-dot-slash-in-zip-entry",  # rpe:invalidDirectoryStructure tpe:invalidDirectoryStructure,0,Forbidden dot segment
        "V-007-dot-dot-slash-in-zip-entry",  # rpe:invalidDirectoryStructure tpe:invalidDirectoryStructure,0,Forbidden dot dot segment
        "V-008-double-slash-in-zip-entry",  # rpe:invalidDirectoryStructure tpe:invalidDirectoryStructure,0,Forbidden empty segment
        "V-009-backslash-in-zip-entry",  # rpe:invalidArchiveFormat tpe:invalidArchiveFormat,0,Backslash is illegal according to the zip specification
        "V-010-duplicate-paths-in-zip-entry",  # rpe:invalidDirectoryStructure tpe:invalidDirectoryStructure,0,Two entries with the same path
        "V-011-duplicate-paths-in-zip-entry-dir-under-file",  # rpe:invalidDirectoryStructure tpe:invalidDirectoryStructure,0,reportPackage.json as a directory as well as a file
        "V-012-encrypted-zip",  # rpe:invalidArchiveFormat tpe:invalidArchiveFormat,0,A report package MUST NOT make use of the encryption features of the .ZIP File Format

        # 1xx - structural JSON constraints for reportPackage.json
        "V-100-invalid-documentType",  # rpe:invalidJSONStructure,0,The JSON Pointer /documentInfo/documentType MUST resolve to a string (rpe:invalidJSONStructure).
        "V-101-missing-documentType",  # rpe:invalidJSONStructure,0,The JSON Pointer /documentInfo/documentType MUST resolve to a string (rpe:invalidJSONStructure).
        "V-102-invalid-documentInfo",  # rpe:invalidJSONStructure,0,The JSON Pointer /documentInfo/documentType MUST resolve to a string (rpe:invalidJSONStructure).
        "V-103-missing-documentInfo",  # rpe:invalidJSONStructure,0,The JSON Pointer /documentInfo/documentType MUST resolve to a string (rpe:invalidJSONStructure).
        "V-104-invalid-reportPackage-json",  # rpe:invalidJSON,0,"JSON files defined by this specification MUST be valid JSON, per RFC 8259"
        "V-105-invalid-reportPackage-json-duplicate-keys",  # rpe:invalidJSON,0,JSON documents defined by this specification MUST have unique keys
        "V-106-utf16-reportPackage-json",  # rpe:invalidJSON,0,JSON documents MUST use the UTF-8 character encoding
        "V-107-utf7-reportPackage-json",  # rpe:invalidJSON,0,JSON documents MUST use the UTF-8 character encoding
        "V-108-utf32-reportPackage-json",  # rpe:invalidJSON,0,JSON documents MUST use the UTF-8 character encoding
        # "V-109-utf8-reportPackage-json",  # ,1,"MAY include a Unicode Byte Order Mark, although this is neither required nor recommended"

        # 2xx - co-constraints on documentType and package file extension
        "V-200-unsupportedReportPackageVersion",  # rpe:unsupportedReportPackageVersion,0,There will never be a version of the spec with this documentType
        "V-201-missing-report-package-json",  # rpe:documentTypeFileExtensionMismatch,0,"rpe:documentTypeFileExtensionMismatch is ... raised if ... The .xbr ... file extension is used, and reportPackage.json is absent"
        "V-202-missing-report-package-json",  # rpe:documentTypeFileExtensionMismatch,0,"rpe:documentTypeFileExtensionMismatch is ... raised if ... The .xbri ... file extension is used, and reportPackage.json is absent"
        "V-203-xbri-documentType",  # rpe:documentTypeFileExtensionMismatch,0,rpe:documentTypeFileExtensionMismatch is ... raised if ... One of the three document type URIs specified in Section 3.4 is used with the incorrect file extension
        "V-204-xbr-documentType",  # rpe:documentTypeFileExtensionMismatch,0,rpe:documentTypeFileExtensionMismatch is ... raised if ... One of the three document type URIs specified in Section 3.4 is used with the incorrect file extension
        "V-205-unconstrained-documentType",  # rpe:documentTypeFileExtensionMismatch,0,rpe:documentTypeFileExtensionMismatch is ... raised if ... One of the three document type URIs specified in Section 3.4 is used with the incorrect file extension
        "V-206-xbri-documentType",  # rpe:documentTypeFileExtensionMismatch,0,rpe:documentTypeFileExtensionMismatch is ... raised if ... One of the three document type URIs specified in Section 3.4 is used with the incorrect file extension
        "V-207-xbri-without-reportPackage-json",  # rpe:documentTypeFileExtensionMismatch,0,rpe:documentTypeFileExtensionMismatch is ... raised if ... One of the three document type URIs specified in Section 3.4 is used with the incorrect file extension
        "V-208-xbri-without-reportPackage-json-and-reports",  # rpe:documentTypeFileExtensionMismatch,0,rpe:documentTypeFileExtensionMismatch is ... raised if ... One of the three document type URIs specified in Section 3.4 is used with the incorrect file extension
        "V-209-xbr-without-reportPackage-json",  # rpe:documentTypeFileExtensionMismatch,0,rpe:documentTypeFileExtensionMismatch is ... raised if ... One of the three document type URIs specified in Section 3.4 is used with the incorrect file extension
        "V-210-xbr-without-reportPackage-json-and-reports",  # rpe:documentTypeFileExtensionMismatch,0,rpe:documentTypeFileExtensionMismatch is ... raised if ... One of the three document type URIs specified in Section 3.4 is used with the incorrect file extension
        "V-211-unsupported-file-extension",  # rpe:unsupportedFileExtension,0,Current report package with unsupported file extension (.xbrx)

        # 3xx - valid.xbri packages
        "V-300-xbri-with-single-xhtml",  # ,1,Simple .xbri file with a single .xhtml document
        "V-301-xbri-with-single-ixds",  # ,1,.xbri file with multiple .xhtml documents in a single IXDS
        "V-302-xbri-with-single-html",  # ,1,Simple .xbri file with a single .html document
        "V-303-xbri-with-single-htm",  # ,1,Simple .xbri file with a single .htm document
        "V-304-xbri-with-no-taxonomy",  # ,1,.xbri package without a taxonomy
        "V-305-xbri-with-xhtml-in-dot-json-directory",  # ,1,.xhtml in reports subdirectory with recognised extension (tricky.json)
        "V-306-xbri-with-xhtml-in-dot-xbrl-directory",  # ,1,.xhtml in reports subdirectory with recognised extension (tricky.xbrl)

        # 4xx - invalid.xbri packages
        "V-400-xbri-without-reports-directory",  # rpe:missingReportsDirectory,0,A report package MUST contain a directory called reports as a child of the STLD
        "V-401-xbri-with-only-txt-in-reports-directory",  # rpe:missingReport,0,.xbri file without recognised files in the reports directory
        "V-402-xbri-with-xhtml-too-deep",  # rpe:missingReport,0,.xbri file with .xhtml buried too deep to be recognised
        "V-403-xbri-with-multiple-reports",  # rpe:multipleReports,0,If the report package is an Inline XBRL report package ... then there MUST NOT be more than one report in the report package
        "V-404-xbri-with-json-report",  # rpe:incorrectReportType,0,If the report package is an Inline XBRL report package then the contained report MUST be an Inline XBRL Document Set 
        "V-405-xbri-with-xbrl-report",  # rpe:incorrectReportType,0,If the report package is an Inline XBRL report package then the contained report MUST be an Inline XBRL Document Set 
        "V-406-xbri-with-multiple-reports-in-a-subdirectory",  # rpe:multipleReportsInSubdirectory,0,.xbri file with multiple reports in a subdirectory

        # 5xx - valid.xbr packages
        "V-502-xbr-with-single-json",  # ,1,.xbr file with a single xBRL-JSON report
        "V-503-xbr-with-single-csv",  # ,1,.xbr file with a single xBRL-CSV metadata file
        "V-504-xbr-with-single-xbrl",  # ,1,.xbr file with a single xBRL-XML document (.xbrl)
        "V-505-xbr-with-single-xbrl-in-subdir",  # ,1,.xbr file with a single xBRL-XML document (.xbrl) in a subdirectory
        "V-506-xbr-with-single-json-and-extra-files",  # ,1,".xbr file with a single xBRL-JSON report and files with non-recognised extensions (.txt, .xml)"
        "V-507-xbr-with-single-json-with-bom",  # ,1,.xbr file with a single xBRL-JSON report with a byte order mark 
        "V-508-xbr-with-no-taxonomy",  # ,1,.xbr package without a taxonomy
        "V-509-xbr-with-json-in-dot-xhtml-directory",  # ,1,.json in reports subdirectory with recognised extension (tricky.xhtml)

        # 6xx - invalid.xbr packages
        "V-600-xbr-without-reports-directory",  # rpe:missingReportsDirectory,0,A report package MUST contain a directory called reports as a child of the STLD
        "V-601-xbr-with-only-txt-in-reports-directory",  # rpe:missingReport,0,.xbr file without recognised files in the reports directory
        "V-603-xbr-with-invalid-jrr",  # rpe:invalidJSON,0,.xbr file with a single invalid JSON-rooted report
        "V-604-xbr-with-invalid-jrr-duplicate-keys",  # rpe:invalidJSON,0,.xbr file with a single invalid JSON-rooted report (duplicate keys)
        "V-605-xbr-with-invalid-jrr-utf32",  # rpe:invalidJSON,0,JSON documents MUST use the UTF-8 character encoding
        "V-606-xbr-with-invalid-jrr-utf16",  # rpe:invalidJSON,0,JSON documents MUST use the UTF-8 character encoding
        "V-607-xbr-with-invalid-jrr-utf7",  # rpe:invalidJSON,0,JSON documents MUST use the UTF-8 character encoding
        "V-608-xbr-with-invalid-jrr-missing-documentInfo",  # rpe:invalidJSONStructure,0,The JSON Pointer /documentInfo/documentType MUST resolve to a string (rpe:invalidJSONStructure).
        "V-609-xbr-with-invalid-jrr-missing-documentType",  # rpe:invalidJSONStructure,0,The JSON Pointer /documentInfo/documentType MUST resolve to a string (rpe:invalidJSONStructure).
        "V-610-xbr-with-invalid-jrr-non-string-documentType",  # rpe:invalidJSONStructure,0,The JSON Pointer /documentInfo/documentType MUST resolve to a string (rpe:invalidJSONStructure).
        "V-611-xbr-with-invalid-jrr-non-object-documentInfo",  # rpe:invalidJSONStructure,0,The JSON Pointer /documentInfo/documentType MUST resolve to a string (rpe:invalidJSONStructure).
        "V-612-xbr-with-multiple-reports",  # rpe:multipleReports,0,.xbr file with multiple reports
        "V-613-xbr-with-json-and-xbrl-too-deep",  # rpe:missingReport,0,.xbr file with .json and .xbrl buried too deep to be recognised
        "V-614-xbr-with-xhtml-report",  # rpe:incorrectReportType,0,If the report package is a non-Inline XBRL report package then the contained report MUST be either an XBRL v2.1 report or an JSON-rooted report
        "V-615-xbr-with-html-report",  # rpe:incorrectReportType,0,If the report package is a non-Inline XBRL report package then the contained report MUST be either an XBRL v2.1 report or an JSON-rooted report
        "V-616-xbr-with-htm-report",  # rpe:incorrectReportType,0,If the report package is a non-Inline XBRL report package then the contained report MUST be either an XBRL v2.1 report or an JSON-rooted report
        "V-617-xbr-with-multiple-reports-in-a-subdirectory",  # rpe:multipleReportsInSubdirectory,0,.xbr file with multiple reports in a subdirectory

        # 7xx - valid.zip packages
        # "V-700-zip-with-multiple-reports",  # ,4,.zip package with multiple reports
        "V-701-zip-with-no-taxonomy",  # ,1,.zip package without a taxonomy

        # 8xx - invalid.zip packages
        "V-800-zip-without-reports-directory",  # rpe:missingReportsDirectory,0,A report package MUST contain a directory called reports as a child of the STLD
        "V-801-zip-with-only-txt-in-reports-directory",  # rpe:missingReport,0,.zip file without recognised files in the reports directory
        "V-802-zip-with-reports-too-deep",  # rpe:missingReport,0,".zip file with .json, .xbrl and .xhtml buried too deep to be recognised"
        "V-803-zip-with-multiple-reports-in-a-subdirectory",  # rpe:multipleReportsInSubdirectory,0,.zip file with multiple reports in a subdirectory
        "V-804-zip-with-multiple-reports-in-a-subdirectory-uppercase",  # rpe:multipleReportsInSubdirectory,0,.ZIP file (uppercase) with multiple reports in a subdirectory

        # 9xx - future report packages
        "V-900-future-zip",  # rpe:unsupportedReportPackageVersion,0,A future report package with a .zip extension
        "V-901-future-xbri",  # rpe:unsupportedReportPackageVersion,0,A future report package with a .xbri extension
        "V-902-future-xbr",  # rpe:unsupportedReportPackageVersion,0,A future report package with a .xbr extension
        "V-903-future-xbrx",  # rpe:unsupportedFileExtension,0,A future report package with an as-yet-undefined extension (.xbrx)
        "V-904-future-package-with-invalid-reportPackage-json",  # rpe:invalidJSON,0,Future report package with invalid JSON in META-INF/reportPackage.json
        "V-905-future-package-with-invalid-reportPackage-json-duplicate-keys",  # rpe:invalidJSON,0,Future report package with invalid JSON in META-INF/reportPackage.json
        "V-906-future-package-with-invalid-reportPackage-json-utf32",  # rpe:invalidJSON,0,Future report package with invalid JSON in META-INF/reportPackage.json
        "V-907-future-package-with-invalid-reportPackage-json-utf16",  # rpe:invalidJSON,0,Future report package with invalid JSON in META-INF/reportPackage.json
        "V-908-future-package-with-invalid-reportPackage-json-utf7",  # rpe:invalidJSON,0,Future report package with invalid JSON in META-INF/reportPackage.json
        "V-909-future-package-with-invalid-reportPackage-json-missing-documentInfo",  # rpe:invalidJSONStructure,0,Future report package with invalid JSON in META-INF/reportPackage.json
        "V-910-future-package-with-invalid-reportPackage-json-missing-documentType",  # rpe:invalidJSONStructure,0,Future report package with invalid JSON in META-INF/reportPackage.json
        "V-911-future-package-with-invalid-reportPackage-json-non-string-documentType",  # rpe:invalidJSONStructure,0,Future report package with invalid JSON in META-INF/reportPackage.json
        "V-912-future-package-with-invalid-reportPackage-json-non-object-documentInfo",  # rpe:invalidJSONStructure,0,Future report package with invalid JSON in META-INF/reportPackage.json
        "V-913-future-package-with-bom-in-reportPackage-json",  # rpe:unsupportedReportPackageVersion,0,Future report package with Byte Order Mark in META-INF/reportPackage.json
        "V-914-current-and-future-package",  # rpe:unsupportedReportPackageVersion,0,META-INF as STLD means this gets interpreted as a future report package
    ]),
    info_url="https://specifications.xbrl.org/work-product-index-taxonomy-packages-report-packages-1.0.html",
    membership_url="https://www.xbrl.org/join",
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
)
