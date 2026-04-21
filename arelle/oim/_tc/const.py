"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

TC_NS_DRAFT = "https://xbrl.org/WGWD/YYYY-MM-DD/tc"
TC_NS_CR = "https://xbrl.org/CR/2025-10-07/tc"
TC_NS_PR = "https://xbrl.org/PR/2026-03-18/tc"

TC_NAMESPACES = frozenset({
    TC_NS_DRAFT,
    TC_NS_CR,
    TC_NS_PR,
})

TC_METADATA_ERROR_NAMESPACES = frozenset({
    "https://xbrl.org/WGWD/YYYY-MM-DD/tc/metadataerror",
    "https://xbrl.org/CR/2025-10-07/tc/metadataerror",
    "https://xbrl.org/PR/2026-03-18/tc/metadataerror",
})

TC_REPORT_ERROR_NAMESPACES = frozenset({
    "https://xbrl.org/WGWD/YYYY-MM-DD/tc/reporterror",
    "https://xbrl.org/CR/2025-10-07/tc/reporterror",
    "https://xbrl.org/PR/2026-03-18/tc/reporterror",
})

TC_PREFIX = "tc"

TC_COLUMN_ORDER_PROPERTY_NAME = "tc:columnOrder"
TC_CONSTRAINTS_PROPERTY_NAME = "tc:constraints"
TC_KEYS_PROPERTY_NAME = "tc:keys"
TC_PARAMETERS_PROPERTY_NAME = "tc:parameters"
TC_TABLE_CONSTRAINTS_PROPERTY_NAME = "tc:tableConstraints"

TC_PROPERTIES = frozenset({
    TC_COLUMN_ORDER_PROPERTY_NAME,
    TC_CONSTRAINTS_PROPERTY_NAME,
    TC_PARAMETERS_PROPERTY_NAME,
    TC_KEYS_PROPERTY_NAME,
    TC_TABLE_CONSTRAINTS_PROPERTY_NAME,
})

TCME_COLUMN_PARAMETER_CONFLICT = "tcme:columnParameterConflict"
TCME_DUPLICATE_KEY_NAME = "tcme:duplicateKeyName"
TCME_ILLEGAL_CONSTRAINT = "tcme:illegalConstraint"
TCME_ILLEGAL_KEY_FIELD = "tcme:illegalKeyField"
TCME_ILLEGAL_UNIQUE_KEY_ORDER = "tcme:illegalUniqueKeyOrder"
TCME_INCONSISTENT_COLUMN_ORDER_DEFINITION = "tcme:inconsistentColumnOrderDefinition"
TCME_INCONSISTENT_REFERENCE_KEY_FIELDS = "tcme:inconsistentReferenceKeyFields"
TCME_INCONSISTENT_SHARED_KEY_FIELDS = "tcme:inconsistentSharedKeyFields"
TCME_INCONSISTENT_SHARED_KEY_SEVERITY = "tcme:inconsistentSharedKeySeverity"
TCME_INVALID_JSON_STRUCTURE = "tcme:invalidJSONStructure"
TCME_INVALID_NAMESPACE_PREFIX = "tcme:invalidNamespacePrefix"
TCME_MISPLACED_OR_UNKNOWN_PROPERTY = "tcme:misplacedOrUnknownProperty"
TCME_MISSING_KEY_PROPERTY = "tcme:missingKeyProperty"
TCME_UNKNOWN_DURATION_TYPE = "tcme:unknownDurationType"
TCME_UNKNOWN_KEY = "tcme:unknownKey"
TCME_UNKNOWN_PERIOD_TYPE = "tcme:unknownPeriodType"
TCME_UNKNOWN_SEVERITY = "tcme:unknownSeverity"
TCME_UNKNOWN_TYPE = "tcme:unknownType"

TCRE_COLUMN_PARAMETER_CONFLICT = "tcre:columnParameterConflict"
TCRE_INVALID_COLUMN_ORDER = "tcre:invalidColumnOrder"
TCRE_INVALID_DURATION_TYPE = "tcre:invalidDurationType"
TCRE_INVALID_PERIOD_TYPE = "tcre:invalidPeriodType"
TCRE_INVALID_VALUE = "tcre:invalidValue"
TCRE_MAX_TABLE_ROWS_VIOLATION = "tcre:maxTableRowsViolation"
TCRE_MAX_TABLES_VIOLATION = "tcre:maxTablesViolation"
TCRE_MIN_TABLE_ROWS_VIOLATION = "tcre:minTableRowsViolation"
TCRE_MIN_TABLES_VIOLATION = "tcre:minTablesViolation"
TCRE_MISSING_COLUMN = "tcre:missingColumn"
TCRE_MISSING_TIME_ZONE = "tcre:missingTimeZone"
TCRE_MISSING_VALUE = "tcre:missingValue"
TCRE_REFERENCE_KEY_VIOLATION = "tcre:referenceKeyViolation"
TCRE_SORT_KEY_VIOLATION = "tcre:sortKeyViolation"
TCRE_UNEXPECTED_TIME_ZONE = "tcre:unexpectedTimeZone"
TCRE_UNIQUE_KEY_VIOLATION = "tcre:uniqueKeyViolation"
