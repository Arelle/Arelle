"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass
from typing import Any, TypeVar, overload

from arelle.oim._tc.const import (
    TC_COLUMN_ORDER_PROPERTY_NAME,
    TC_CONSTRAINTS_PROPERTY_NAME,
    TC_KEYS_PROPERTY_NAME,
    TC_NAMESPACES,
    TC_PARAMETERS_PROPERTY_NAME,
    TC_TABLE_CONSTRAINTS_PROPERTY_NAME,
    TCME_INVALID_JSON_STRUCTURE,
)
from arelle.oim._tc.metadata.common import TCMetadataValidationError
from arelle.oim._tc.metadata.model import (
    TCKeys,
    TCMetadata,
    TCReferenceKey,
    TCTableConstraints,
    TCTemplateConstraints,
    TCUniqueKey,
    TCValueConstraint,
)
from arelle.oim.const import IDENTIFIER_PATTERN, XBRLCE_INVALID_IDENTIFIER
from arelle.typing import TypeGetText

_: TypeGetText


class TCMetadataParseError(TCMetadataValidationError):
    def __init__(self, message: str, *path: str, code: str = TCME_INVALID_JSON_STRUCTURE) -> None:
        super().__init__(message, *path, code=code)


class TCMetadataParseTypeError(TCMetadataParseError):
    def __init__(self, expected_type: type, actual_value: Any, *path: str) -> None:
        super().__init__(
            _("Expected {expected}, got {actual}: {value}").format(
                expected=expected_type.__name__,
                actual=type(actual_value).__name__,
                value=repr(actual_value),
            ),
            *path,
        )


class TCMetadataUnknownPropertiesError(TCMetadataParseError):
    def __init__(self, property_names: list[str]) -> None:
        names = ", ".join(repr(n) for n in sorted(property_names))
        super().__init__(_("Unknown properties: {names}").format(names=names))


class TCMetadataMissingPropertiesError(TCMetadataParseError):
    def __init__(self, property_names: list[str]) -> None:
        names = ", ".join(repr(n) for n in sorted(property_names))
        super().__init__(_("Missing required properties: {}").format(names))


def _prepend_paths(errors: list[TCMetadataParseError], *segments: str) -> list[TCMetadataParseError]:
    for error in errors:
        error.prepend_path(*segments)
    return errors


@dataclass(frozen=True, slots=True)
class TCParseResult:
    metadata: TCMetadata | None
    errors: tuple[TCMetadataParseError, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


def parse_tc_metadata(
    oim_object: dict[str, Any],
    namespaces: dict[str, str],
) -> TCParseResult:
    if not any(uri in TC_NAMESPACES for uri in namespaces.values()):
        return TCParseResult(metadata=None, errors=())

    errors: list[TCMetadataParseError] = []
    template_constraints: dict[str, TCTemplateConstraints] = {}
    table_templates = oim_object.get("tableTemplates", {})
    if isinstance(table_templates, dict):
        for template_id, template_obj in table_templates.items():
            if not isinstance(template_obj, dict):
                continue
            local_errors: list[TCMetadataParseError] = []
            tc = _parse_template_constraints(template_obj, local_errors)
            if local_errors:
                errors.extend(_prepend_paths(local_errors, "tableTemplates", template_id))
            if tc is not None:
                template_constraints[template_id] = tc

    metadata = None if errors else TCMetadata(template_constraints=template_constraints)

    return TCParseResult(metadata=metadata, errors=tuple(errors))


def _parse_template_constraints(
    template_obj: dict[str, Any],
    errors: list[TCMetadataParseError],
) -> TCTemplateConstraints | None:
    local_errors: list[TCMetadataParseError] = []

    col = _parse_column_constraints(template_obj.get("columns", {}), local_errors)
    params = _parse_param_constraints(template_obj, local_errors)
    keys = _parse_template_keys(template_obj, local_errors)
    column_order = _parse_ordered_set(template_obj, TC_COLUMN_ORDER_PROPERTY_NAME, local_errors)
    table_constraints = _parse_template_table_constraints(template_obj, local_errors)

    if local_errors:
        errors.extend(local_errors)
        return None

    if col or params or keys or column_order is not None or table_constraints:
        return TCTemplateConstraints(
            constraints=col,
            parameters=params,
            keys=keys,
            column_order=column_order,
            table_constraints=table_constraints,
        )
    return None


def _parse_column_constraints(
    columns: Any,
    errors: list[TCMetadataParseError],
) -> dict[str, TCValueConstraint]:
    result: dict[str, TCValueConstraint] = {}
    if not isinstance(columns, dict):
        return result
    for col_name, col_obj in columns.items():
        if not isinstance(col_obj, dict):
            continue
        if TC_CONSTRAINTS_PROPERTY_NAME not in col_obj:
            continue
        constraint_obj = col_obj[TC_CONSTRAINTS_PROPERTY_NAME]
        if not isinstance(constraint_obj, dict):
            errors.append(
                TCMetadataParseTypeError(dict, constraint_obj, "columns", col_name, TC_CONSTRAINTS_PROPERTY_NAME)
            )
            continue
        item_errors: list[TCMetadataParseError] = []
        value_constraint = _parse_value_constraint(constraint_obj, item_errors)
        if item_errors:
            errors.extend(_prepend_paths(item_errors, "columns", col_name, TC_CONSTRAINTS_PROPERTY_NAME))
        if value_constraint is not None:
            result[col_name] = value_constraint
    return result


def _parse_param_constraints(
    template_obj: dict[str, Any],
    errors: list[TCMetadataParseError],
) -> dict[str, TCValueConstraint]:
    result: dict[str, TCValueConstraint] = {}
    if TC_PARAMETERS_PROPERTY_NAME not in template_obj:
        return result
    params_obj = template_obj[TC_PARAMETERS_PROPERTY_NAME]
    if not isinstance(params_obj, dict):
        errors.append(TCMetadataParseTypeError(dict, params_obj, TC_PARAMETERS_PROPERTY_NAME))
        return result
    for param_name, param_obj in params_obj.items():
        if not (isinstance(param_name, str) and IDENTIFIER_PATTERN.match(param_name)):
            errors.append(
                TCMetadataParseError(
                    _("TC parameter name '{}' is not a valid identifier").format(param_name),
                    TC_PARAMETERS_PROPERTY_NAME,
                    param_name,
                    code=XBRLCE_INVALID_IDENTIFIER,
                )
            )
            continue
        if not isinstance(param_obj, dict):
            errors.append(TCMetadataParseTypeError(dict, param_obj, TC_PARAMETERS_PROPERTY_NAME, param_name))
            continue
        item_errors: list[TCMetadataParseError] = []
        value_constraint = _parse_value_constraint(param_obj, item_errors)
        if item_errors:
            errors.extend(_prepend_paths(item_errors, TC_PARAMETERS_PROPERTY_NAME, param_name))
        if value_constraint is not None:
            result[param_name] = value_constraint
    return result


def _parse_template_keys(
    template_obj: dict[str, Any],
    errors: list[TCMetadataParseError],
) -> TCKeys | None:
    if TC_KEYS_PROPERTY_NAME not in template_obj:
        return None
    keys_obj = template_obj[TC_KEYS_PROPERTY_NAME]
    if not isinstance(keys_obj, dict):
        errors.append(TCMetadataParseTypeError(dict, keys_obj, TC_KEYS_PROPERTY_NAME))
        return None
    local_errors: list[TCMetadataParseError] = []
    keys = _parse_keys(keys_obj, local_errors)
    if local_errors:
        errors.extend(_prepend_paths(local_errors, TC_KEYS_PROPERTY_NAME))
        return None
    return keys


def _parse_template_table_constraints(
    template_obj: dict[str, Any],
    errors: list[TCMetadataParseError],
) -> TCTableConstraints | None:
    if TC_TABLE_CONSTRAINTS_PROPERTY_NAME not in template_obj:
        return None
    obj = template_obj[TC_TABLE_CONSTRAINTS_PROPERTY_NAME]
    if not isinstance(obj, dict):
        errors.append(TCMetadataParseTypeError(dict, obj, TC_TABLE_CONSTRAINTS_PROPERTY_NAME))
        return None
    local_errors: list[TCMetadataParseError] = []
    result = _parse_table_constraints(obj, local_errors)
    if local_errors:
        errors.extend(_prepend_paths(local_errors, TC_TABLE_CONSTRAINTS_PROPERTY_NAME))
        return None
    return result


_VALUE_CONSTRAINT_PROPERTIES = frozenset(
    {
        "type",
        "optional",
        "nillable",
        "enumerationValues",
        "patterns",
        "timeZone",
        "periodType",
        "durationType",
        "length",
        "minLength",
        "maxLength",
        "minInclusive",
        "maxInclusive",
        "minExclusive",
        "maxExclusive",
        "totalDigits",
        "fractionDigits",
    }
)
_VALUE_CONSTRAINT_REQUIRED_PROPERTIES = frozenset({"type"})


def _parse_value_constraint(
    obj: dict[str, Any],
    errors: list[TCMetadataParseError],
) -> TCValueConstraint | None:
    local_errors: list[TCMetadataParseError] = []
    _validate_expected_properties(
        obj,
        local_errors,
        known_properties=_VALUE_CONSTRAINT_PROPERTIES,
        required_properties=_VALUE_CONSTRAINT_REQUIRED_PROPERTIES,
    )
    value_constraint_type = _parse_primitive_field(obj, "type", str, local_errors)
    optional = _parse_primitive_field(obj, "optional", bool, local_errors, default=False)
    nillable = _parse_primitive_field(obj, "nillable", bool, local_errors, default=False)
    enumeration_values = _parse_set(obj, "enumerationValues", local_errors, default=None, non_empty=True)
    patterns = _parse_set(obj, "patterns", local_errors, default=None, non_empty=True)
    time_zone = _parse_primitive_field(obj, "timeZone", bool, local_errors, default=None)
    period_type = _parse_primitive_field(obj, "periodType", str, local_errors, default=None)
    duration_type = _parse_primitive_field(obj, "durationType", str, local_errors, default=None)
    length = _parse_bounded_int(obj, "length", local_errors, min_value=0, default=None)
    min_length = _parse_bounded_int(obj, "minLength", local_errors, min_value=0, default=None)
    max_length = _parse_bounded_int(obj, "maxLength", local_errors, min_value=0, default=None)
    min_inclusive = _parse_primitive_field(obj, "minInclusive", str, local_errors, default=None)
    max_inclusive = _parse_primitive_field(obj, "maxInclusive", str, local_errors, default=None)
    min_exclusive = _parse_primitive_field(obj, "minExclusive", str, local_errors, default=None)
    max_exclusive = _parse_primitive_field(obj, "maxExclusive", str, local_errors, default=None)
    total_digits = _parse_bounded_int(obj, "totalDigits", local_errors, min_value=0, default=None)
    fraction_digits = _parse_bounded_int(obj, "fractionDigits", local_errors, min_value=0, default=None)
    if local_errors:
        errors.extend(local_errors)
        return None
    assert value_constraint_type is not None, "value_constraint_type is required if there are no errors"
    return TCValueConstraint(
        type=value_constraint_type,
        optional=optional,
        nillable=nillable,
        enumeration_values=enumeration_values,
        patterns=patterns,
        time_zone=time_zone,
        period_type=period_type,
        duration_type=duration_type,
        length=length,
        min_length=min_length,
        max_length=max_length,
        min_inclusive=min_inclusive,
        max_inclusive=max_inclusive,
        min_exclusive=min_exclusive,
        max_exclusive=max_exclusive,
        total_digits=total_digits,
        fraction_digits=fraction_digits,
    )


_KEYS_PROPERTIES = frozenset({"unique", "reference", "sortKey"})


def _parse_keys(obj: dict[str, Any], errors: list[TCMetadataParseError]) -> TCKeys:
    _validate_expected_properties(obj, errors, known_properties=_KEYS_PROPERTIES)
    unique = _parse_unique_keys(obj, errors)
    reference = _parse_reference_keys(obj, errors)
    sort_key = _parse_primitive_field(obj, "sortKey", str, errors, default=None)
    return TCKeys(unique=unique, reference=reference, sort_key=sort_key)


def _parse_unique_keys(
    obj: dict[str, Any],
    errors: list[TCMetadataParseError],
) -> tuple[TCUniqueKey, ...] | None:
    unique_key_name = "unique"
    if unique_key_name not in obj:
        return None
    unique_keys_json = obj[unique_key_name]
    if not isinstance(unique_keys_json, list) or len(unique_keys_json) == 0:
        errors.append(TCMetadataParseTypeError(list, unique_keys_json, unique_key_name))
        return None
    parsed_unique_keys: list[TCUniqueKey] = []
    for i, uni_key in enumerate(unique_keys_json):
        if not isinstance(uni_key, dict):
            errors.append(TCMetadataParseTypeError(dict, uni_key, unique_key_name, str(i)))
            continue
        item_errors: list[TCMetadataParseError] = []
        parsed_key = _parse_unique_key(uni_key, item_errors)
        if item_errors:
            errors.extend(_prepend_paths(item_errors, unique_key_name, str(i)))
        if parsed_key is not None:
            parsed_unique_keys.append(parsed_key)
    return tuple(parsed_unique_keys) if parsed_unique_keys else None


_UNIQUE_KEY_PROPERTIES = frozenset({"name", "fields", "severity", "shared"})
_UNIQUE_KEY_REQUIRED_PROPERTIES = frozenset({"name", "fields"})


def _parse_unique_key(
    obj: dict[str, Any],
    errors: list[TCMetadataParseError],
) -> TCUniqueKey | None:
    local_errors: list[TCMetadataParseError] = []
    _validate_expected_properties(
        obj,
        local_errors,
        known_properties=_UNIQUE_KEY_PROPERTIES,
        required_properties=_UNIQUE_KEY_REQUIRED_PROPERTIES,
    )
    name = _parse_primitive_field(obj, "name", str, local_errors)
    if name is not None and not IDENTIFIER_PATTERN.match(name):
        local_errors.append(
            TCMetadataParseError(
                _("Unique key name '{}' is not a valid identifier").format(name),
                "name",
                code=XBRLCE_INVALID_IDENTIFIER,
            )
        )
        name = None
    fields = _parse_ordered_set(obj, "fields", local_errors, non_empty=True)
    severity = _parse_primitive_field(obj, "severity", str, local_errors, default="error")
    shared = _parse_primitive_field(obj, "shared", bool, local_errors, default=False)
    if local_errors:
        errors.extend(local_errors)
        return None
    assert name is not None and fields is not None
    return TCUniqueKey(name=name, fields=fields, severity=severity, shared=shared)


def _parse_reference_keys(
    obj: dict[str, Any],
    errors: list[TCMetadataParseError],
) -> tuple[TCReferenceKey, ...] | None:
    reference_key_name = "reference"
    if reference_key_name not in obj:
        return None
    reference_keys_json = obj[reference_key_name]
    if not isinstance(reference_keys_json, list) or len(reference_keys_json) == 0:
        errors.append(TCMetadataParseTypeError(list, reference_keys_json, reference_key_name))
        return None
    parsed_reference_keys: list[TCReferenceKey] = []
    for i, ref_key in enumerate(reference_keys_json):
        if not isinstance(ref_key, dict):
            errors.append(TCMetadataParseTypeError(dict, ref_key, reference_key_name, str(i)))
            continue
        item_errors: list[TCMetadataParseError] = []
        parsed_key = _parse_reference_key(ref_key, item_errors)
        if item_errors:
            errors.extend(_prepend_paths(item_errors, reference_key_name, str(i)))
        if parsed_key is not None:
            parsed_reference_keys.append(parsed_key)
    return tuple(parsed_reference_keys) if parsed_reference_keys else None


_REFERENCE_KEY_PROPERTIES = frozenset({"name", "fields", "referencedKeyName", "negate", "severity"})
_REFERENCE_KEY_REQUIRED_PROPERTIES = frozenset({"name", "fields", "referencedKeyName"})


def _parse_reference_key(
    obj: dict[str, Any],
    errors: list[TCMetadataParseError],
) -> TCReferenceKey | None:
    local_errors: list[TCMetadataParseError] = []
    _validate_expected_properties(
        obj,
        local_errors,
        known_properties=_REFERENCE_KEY_PROPERTIES,
        required_properties=_REFERENCE_KEY_REQUIRED_PROPERTIES,
    )
    name = _parse_primitive_field(obj, "name", str, local_errors)
    if name is not None and not IDENTIFIER_PATTERN.match(name):
        local_errors.append(
            TCMetadataParseError(
                _("Reference key name '{}' is not a valid identifier").format(name),
                "name",
                code=XBRLCE_INVALID_IDENTIFIER,
            )
        )
        name = None
    fields = _parse_ordered_set(obj, "fields", local_errors, non_empty=True)
    referenced_key_name = _parse_primitive_field(obj, "referencedKeyName", str, local_errors)
    if referenced_key_name is not None and not IDENTIFIER_PATTERN.match(referenced_key_name):
        local_errors.append(
            TCMetadataParseError(
                _("Referenced key name '{}' is not a valid identifier").format(referenced_key_name),
                "referencedKeyName",
                code=XBRLCE_INVALID_IDENTIFIER,
            )
        )
        referenced_key_name = None
    negate = _parse_primitive_field(obj, "negate", bool, local_errors, default=False)
    severity = _parse_primitive_field(obj, "severity", str, local_errors, default="error")
    if local_errors:
        errors.extend(local_errors)
        return None
    assert name is not None and fields is not None and referenced_key_name is not None
    return TCReferenceKey(
        name=name,
        fields=fields,
        referenced_key_name=referenced_key_name,
        negate=negate,
        severity=severity,
    )


_TABLE_CONSTRAINTS_PROPERTIES = frozenset({"minTables", "maxTables", "minTableRows", "maxTableRows"})


def _parse_table_constraints(
    obj: dict[str, Any],
    errors: list[TCMetadataParseError],
) -> TCTableConstraints:
    _validate_expected_properties(obj, errors, known_properties=_TABLE_CONSTRAINTS_PROPERTIES)
    min_tables = _parse_bounded_int(obj, "minTables", errors, min_value=1, default=None)
    max_tables = _parse_bounded_int(obj, "maxTables", errors, min_value=1, default=None)
    min_table_rows = _parse_bounded_int(obj, "minTableRows", errors, min_value=1, default=None)
    max_table_rows = _parse_bounded_int(obj, "maxTableRows", errors, min_value=1, default=None)
    return TCTableConstraints(
        min_tables=min_tables,
        max_tables=max_tables,
        min_table_rows=min_table_rows,
        max_table_rows=max_table_rows,
    )


T = TypeVar("T", str, bool, int)


@overload
def _parse_primitive_field(
    obj: dict[str, Any],
    key: str,
    expected_type: type[T],
    errors: list[TCMetadataParseError],
    *,
    default: T,
) -> T: ...
@overload
def _parse_primitive_field(
    obj: dict[str, Any],
    key: str,
    expected_type: type[T],
    errors: list[TCMetadataParseError],
    *,
    default: None = ...,
) -> T | None: ...
def _parse_primitive_field(
    obj: dict[str, Any],
    key: str,
    expected_type: type[T],
    errors: list[TCMetadataParseError],
    *,
    default: T | None = None,
) -> T | None:
    if key not in obj:
        return default
    val = obj[key]
    if isinstance(val, expected_type) and not (expected_type is int and isinstance(val, bool)):
        return val
    errors.append(TCMetadataParseTypeError(expected_type, val, key))
    return default


@overload
def _parse_bounded_int(
    obj: dict[str, Any], key: str, errors: list[TCMetadataParseError], *, min_value: int, default: int
) -> int: ...
@overload
def _parse_bounded_int(
    obj: dict[str, Any], key: str, errors: list[TCMetadataParseError], *, min_value: int, default: None = ...
) -> int | None: ...
def _parse_bounded_int(
    obj: dict[str, Any], key: str, errors: list[TCMetadataParseError], *, min_value: int, default: int | None = None
) -> int | None:
    val = _parse_primitive_field(obj, key, int, errors, default=default)
    if val is not None and val < min_value:
        errors.append(
            TCMetadataParseError(_("Value {value} is less than minimum {min}").format(value=val, min=min_value), key)
        )
        return default
    return val


def _validate_expected_properties(
    obj: dict[str, Any],
    errors: list[TCMetadataParseError],
    known_properties: Set[str],
    required_properties: Set[str] = frozenset(),
) -> None:
    if unknown_properties := sorted(prop for prop in obj if prop not in known_properties):
        errors.append(TCMetadataUnknownPropertiesError(unknown_properties))
    if missing_properties := sorted(prop for prop in required_properties if prop not in obj):
        errors.append(TCMetadataMissingPropertiesError(missing_properties))


def _validate_str_list(
    key: str,
    val: Any,
    errors: list[TCMetadataParseError],
    *,
    unique: bool = False,
    non_empty: bool = False,
) -> bool:
    if not isinstance(val, list) or not all(isinstance(v, str) for v in val):
        errors.append(TCMetadataParseTypeError(list, val, key))
        return False
    if non_empty and len(val) == 0:
        errors.append(TCMetadataParseError(_("'{}' must not be empty").format(key), key))
        return False
    if unique and len(val) != len(set(val)):
        errors.append(TCMetadataParseError(_("'{}' must not contain duplicate values").format(key), key))
        return False
    return True


@overload
def _parse_ordered_set(
    obj: dict[str, Any],
    key: str,
    errors: list[TCMetadataParseError],
    *,
    default: tuple[str, ...],
    non_empty: bool = ...,
) -> tuple[str, ...]: ...
@overload
def _parse_ordered_set(
    obj: dict[str, Any],
    key: str,
    errors: list[TCMetadataParseError],
    *,
    default: None = ...,
    non_empty: bool = ...,
) -> tuple[str, ...] | None: ...
def _parse_ordered_set(
    obj: dict[str, Any],
    key: str,
    errors: list[TCMetadataParseError],
    *,
    default: tuple[str, ...] | None = None,
    non_empty: bool = False,
) -> tuple[str, ...] | None:
    if key not in obj:
        return default
    val = obj[key]
    if not _validate_str_list(key, val, errors, unique=True, non_empty=non_empty):
        return default
    return tuple(val)


@overload
def _parse_set(
    obj: dict[str, Any],
    key: str,
    errors: list[TCMetadataParseError],
    *,
    default: Set[str],
    non_empty: bool = ...,
) -> Set[str]: ...
@overload
def _parse_set(
    obj: dict[str, Any],
    key: str,
    errors: list[TCMetadataParseError],
    *,
    default: None = ...,
    non_empty: bool = ...,
) -> Set[str] | None: ...
def _parse_set(
    obj: dict[str, Any],
    key: str,
    errors: list[TCMetadataParseError],
    *,
    default: Set[str] | None = None,
    non_empty: bool = False,
) -> Set[str] | None:
    if key not in obj:
        return default
    val = obj[key]
    if not _validate_str_list(key, val, errors, unique=True, non_empty=non_empty):
        return default
    return frozenset(val)
