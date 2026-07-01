"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Generator, Mapping

from arelle.ModelValue import QName
from arelle.oim._tc.const import (
    TC_KEYS_PROPERTY_NAME,
    TCME_DUPLICATE_KEY_NAME,
    TCME_ILLEGAL_KEY_FIELD,
    TCME_INCONSISTENT_REFERENCE_KEY_FIELDS,
    TCME_INCONSISTENT_SHARED_KEY_FIELDS,
    TCME_MISSING_KEY_PROPERTY,
    TCME_UNKNOWN_KEY,
    TCME_UNKNOWN_SEVERITY,
)
from arelle.oim._tc.metadata.common import TCMetadataValidationError
from arelle.oim._tc.metadata.model import (
    TCKeys,
    TCMetadata,
    TCReferenceKey,
    TCTemplateConstraints,
    TCUniqueKey,
    TCValueConstraint,
)
from arelle.oim._tc.metadata.types import (
    CORE_PERIOD,
    DURATION,
    OPTIONALLY_TIME_ZONED_TYPES,
    PROHIBITED_KEY_TYPES,
    resolve_effective_lexical_type,
)
from arelle.oim.csv.metadata.common import TABLE_TEMPLATES_KEY
from arelle.typing import TypeGetText

_: TypeGetText

_VALID_SEVERITIES = frozenset(
    {
        "error",
        "warning",
    }
)


def validate_keys(
    tc_metadata: TCMetadata,
    namespaces: Mapping[str, str],
) -> Generator[TCMetadataValidationError, None, None]:
    """Validates all tc:keys structures across metadata.

    Yields TCMetadataValidationError with full path segments.
    """
    for template_id, tc in tc_metadata.template_constraints.items():
        if tc.keys is not None:
            keys_path = (TABLE_TEMPLATES_KEY, template_id, TC_KEYS_PROPERTY_NAME)
            for error in _validate_template_keys(tc.keys, tc, namespaces):
                error.prepend_path(*keys_path)
                yield error
    yield from _validate_cross_template_key_names(tc_metadata)
    yield from _validate_reference_key_field_consistency(tc_metadata, namespaces)
    yield from _validate_shared_key_consistency(tc_metadata, namespaces)


def _validate_template_keys(
    keys: TCKeys,
    tc: TCTemplateConstraints,
    namespaces: Mapping[str, str],
) -> Generator[TCMetadataValidationError, None, None]:
    """Yields TCMetadataValidationError with relative path segments."""
    if keys.unique is None and keys.reference is None:
        yield TCMetadataValidationError(
            _("At least one of 'unique' and 'reference' must be specified"),
            code=TCME_MISSING_KEY_PROPERTY,
        )
        return

    paths_by_key_name = defaultdict(list)
    if keys.unique is not None:
        for i, unique_key in enumerate(keys.unique):
            paths_by_key_name[unique_key.name].append(("unique", str(i), "name"))
            for error in _validate_key(unique_key, tc, namespaces):
                error.prepend_path("unique", str(i))
                yield error
    if keys.reference is not None:
        for i, reference_key in enumerate(keys.reference):
            paths_by_key_name[reference_key.name].append(("reference", str(i), "name"))
            for error in _validate_key(reference_key, tc, namespaces):
                error.prepend_path("reference", str(i))
                yield error

    for key_name, key_paths in paths_by_key_name.items():
        if len(key_paths) < 2:
            continue
        first_key_path, *other_key_paths = key_paths
        yield TCMetadataValidationError(
            _("Duplicate key name '{}'").format(key_name),
            *first_key_path,
            code=TCME_DUPLICATE_KEY_NAME,
            related_paths=tuple(other_key_paths),
        )

    if keys.sort_key is not None:
        unique_key_names = {key.name for key in (keys.unique or ())}
        if keys.sort_key not in unique_key_names:
            yield TCMetadataValidationError(
                _("Sort key '{}' does not refer to a unique key in this template").format(keys.sort_key),
                "sortKey",
                code=TCME_UNKNOWN_KEY,
            )


def _validate_cross_template_key_names(tc_metadata: TCMetadata) -> Generator[TCMetadataValidationError, None, None]:
    unique_keys_by_name: dict[str, list[tuple[str, str, bool]]] = defaultdict(list)
    for template_id, tc in tc_metadata.template_constraints.items():
        if tc.keys is None or tc.keys.unique is None:
            continue
        for i, unique_key in enumerate(tc.keys.unique):
            unique_keys_by_name[unique_key.name].append((template_id, str(i), unique_key.shared))

    for key_name, occurrences in unique_keys_by_name.items():
        if len({tid for tid, _, _ in occurrences}) < 2:
            continue
        non_shared_paths = [
            (TABLE_TEMPLATES_KEY, template_id, TC_KEYS_PROPERTY_NAME, "unique", key_index, "name")
            for template_id, key_index, shared in occurrences
            if not shared
        ]
        if non_shared_paths:
            first_path, *related_paths = non_shared_paths
            yield TCMetadataValidationError(
                _("Duplicate key name '{}'").format(key_name),
                *first_path,
                code=TCME_DUPLICATE_KEY_NAME,
                related_paths=tuple(related_paths),
            )


def _resolve_field_constraint(tc: TCTemplateConstraints, field: str) -> TCValueConstraint | None:
    return tc.constraints.get(field) or tc.parameters.get(field)


def _validate_key(
    key: TCUniqueKey | TCReferenceKey,
    tc: TCTemplateConstraints,
    namespaces: Mapping[str, str],
) -> Generator[TCMetadataValidationError, None, None]:
    """Validates a single key, yielding errors with relative path segments."""
    if key.severity not in _VALID_SEVERITIES:
        yield TCMetadataValidationError(
            _("Unknown severity '{}' for key '{}'").format(key.severity, key.name),
            "severity",
            code=TCME_UNKNOWN_SEVERITY,
        )
    for field_j, field in enumerate(key.fields):
        constraint = _resolve_field_constraint(tc, field)
        if constraint is None:
            yield TCMetadataValidationError(
                _("Key field '{}' does not correspond to a constrained column or defined parameter").format(field),
                "fields",
                str(field_j),
                code=TCME_ILLEGAL_KEY_FIELD,
            )
            continue
        effective_type = resolve_effective_lexical_type(constraint.type, namespaces)
        if effective_type is None:
            continue
        if effective_type in PROHIBITED_KEY_TYPES:
            yield TCMetadataValidationError(
                _("Key field '{}' uses prohibited type '{}'").format(field, constraint.type),
                "fields",
                str(field_j),
                code=TCME_ILLEGAL_KEY_FIELD,
            )
        if effective_type == DURATION and constraint.duration_type is None:
            yield TCMetadataValidationError(
                _("Key field '{}' has type xs:duration but no durationType is specified").format(field),
                "fields",
                str(field_j),
                code=TCME_ILLEGAL_KEY_FIELD,
            )
        is_time_zone_type = effective_type in OPTIONALLY_TIME_ZONED_TYPES or constraint.type == CORE_PERIOD
        if is_time_zone_type and constraint.time_zone is None:
            yield TCMetadataValidationError(
                _("Key field '{}' has a time-zone-applicable type but no timeZone is specified").format(field),
                "fields",
                str(field_j),
                code=TCME_ILLEGAL_KEY_FIELD,
            )


def _normalized_field_type(constraint_type: str, namespaces: Mapping[str, str]) -> str | QName:
    prefix, separator, local_name = constraint_type.partition(":")
    if separator and (namespace_uri := namespaces.get(prefix)):
        return QName(prefix, namespace_uri, local_name)
    return constraint_type


def _find_inconsistent_fields(
    tc_a: TCTemplateConstraints,
    fields_a: tuple[str, ...],
    tc_b: TCTemplateConstraints,
    fields_b: tuple[str, ...],
    namespaces: Mapping[str, str],
) -> tuple[int, ...]:
    inconsistent_fields = []
    for i, (field_a, field_b) in enumerate(zip(fields_a, fields_b, strict=True)):
        constraint_a = _resolve_field_constraint(tc_a, field_a)
        constraint_b = _resolve_field_constraint(tc_b, field_b)
        if constraint_a is None or constraint_b is None:
            continue
        if (
            _normalized_field_type(constraint_a.type, namespaces)
            != _normalized_field_type(constraint_b.type, namespaces)
            or constraint_a.time_zone != constraint_b.time_zone
            or constraint_a.duration_type != constraint_b.duration_type
        ):
            inconsistent_fields.append(i)
    return tuple(inconsistent_fields)


def _validate_reference_key_field_consistency(
    tc_metadata: TCMetadata,
    namespaces: Mapping[str, str],
) -> Generator[TCMetadataValidationError, None, None]:
    """Validates that reference key fields are consistent with the referenced unique key's fields."""
    unique_key_registry: dict[str, tuple[str, int, TCUniqueKey]] = {}
    for template_id, tc in tc_metadata.template_constraints.items():
        if tc.keys is None or tc.keys.unique is None:
            continue
        for key_i, key in enumerate(tc.keys.unique):
            # When a unique key name is defined in multiple templates (a shared key), the first
            # occurrence in template order wins. Shared keys with the same name are required to
            # have consistent fields (tcme:inconsistentSharedKeyFields), so which occurrence is
            # used for the reference-key consistency check does not matter for valid metadata.
            unique_key_registry.setdefault(key.name, (template_id, key_i, key))

    for template_id, tc in tc_metadata.template_constraints.items():
        if tc.keys is None or tc.keys.reference is None:
            continue
        for ref_i, ref_key in enumerate(tc.keys.reference):
            ref_path = (TABLE_TEMPLATES_KEY, template_id, TC_KEYS_PROPERTY_NAME, "reference", str(ref_i))
            if ref_key.referenced_key_name not in unique_key_registry:
                yield TCMetadataValidationError(
                    _("Referenced key '{}' does not exist as a unique key in any template").format(
                        ref_key.referenced_key_name
                    ),
                    *ref_path,
                    "referencedKeyName",
                    code=TCME_UNKNOWN_KEY,
                )
                continue
            unique_template_id, unique_key_i, unique_key = unique_key_registry[ref_key.referenced_key_name]
            unique_tc = tc_metadata.template_constraints[unique_template_id]
            unique_path = (TABLE_TEMPLATES_KEY, unique_template_id, TC_KEYS_PROPERTY_NAME, "unique", str(unique_key_i))

            if len(ref_key.fields) != len(unique_key.fields):
                yield TCMetadataValidationError(
                    _("Reference key '{}' has {} fields but referenced key '{}' has {} fields").format(
                        ref_key.name,
                        len(ref_key.fields),
                        ref_key.referenced_key_name,
                        len(unique_key.fields),
                    ),
                    *ref_path,
                    "fields",
                    code=TCME_INCONSISTENT_REFERENCE_KEY_FIELDS,
                    related_paths=((*unique_path, "fields"),),
                )
                continue

            if fields := _find_inconsistent_fields(tc, ref_key.fields, unique_tc, unique_key.fields, namespaces):
                related_paths: list[tuple[str, ...]] = [(*unique_path, "fields")]
                for field_index in fields:
                    related_paths.append((*ref_path, "fields", str(field_index)))
                    related_paths.append((*unique_path, "fields", str(field_index)))
                yield TCMetadataValidationError(
                    _("Reference key '{}' has fields inconsistent with referenced unique key '{}'").format(
                        ref_key.name, ref_key.referenced_key_name
                    ),
                    *ref_path,
                    "fields",
                    code=TCME_INCONSISTENT_REFERENCE_KEY_FIELDS,
                    related_paths=related_paths,
                )


def _validate_shared_key_consistency(
    tc_metadata: TCMetadata,
    namespaces: Mapping[str, str],
) -> Generator[TCMetadataValidationError, None, None]:
    """Validates that shared unique keys with the same name have consistent fields and severity."""
    shared_key_occurrences: dict[str, list[tuple[str, str, TCUniqueKey]]] = defaultdict(list)
    for template_id, tc in tc_metadata.template_constraints.items():
        if tc.keys is None or tc.keys.unique is None:
            continue
        for key_i, key in enumerate(tc.keys.unique):
            if key.shared:
                shared_key_occurrences[key.name].append((template_id, str(key_i), key))

    for key_name, occurrences in shared_key_occurrences.items():
        if len({tid for tid, _, _ in occurrences}) < 2:
            continue
        first_key_occurrence, *rest_key_occurrences = occurrences
        first_template_id, first_key_index, first_key = first_key_occurrence
        first_tc = tc_metadata.template_constraints[first_template_id]
        first_key_path = (
            TABLE_TEMPLATES_KEY,
            first_template_id,
            TC_KEYS_PROPERTY_NAME,
            "unique",
            first_key_index,
        )
        first_key_fields_path = (*first_key_path, "fields")
        inconsistent_field_paths: list[tuple[str, ...]] = []
        for tid, key_index, key in rest_key_occurrences:
            other_key_fields_path = (TABLE_TEMPLATES_KEY, tid, TC_KEYS_PROPERTY_NAME, "unique", key_index, "fields")
            if len(key.fields) != len(first_key.fields):
                inconsistent_field_paths.append(other_key_fields_path)
                continue
            this_tc = tc_metadata.template_constraints[tid]
            if inconsistent_fields := _find_inconsistent_fields(
                this_tc, key.fields, first_tc, first_key.fields, namespaces
            ):
                inconsistent_field_paths.append(other_key_fields_path)
                for field_index in inconsistent_fields:
                    inconsistent_field_paths.append((*first_key_fields_path, str(field_index)))
                    inconsistent_field_paths.append((*other_key_fields_path, str(field_index)))
        if inconsistent_field_paths:
            yield TCMetadataValidationError(
                _("Shared key '{}' has inconsistent fields across templates").format(key_name),
                *first_key_fields_path,
                code=TCME_INCONSISTENT_SHARED_KEY_FIELDS,
                related_paths=tuple(inconsistent_field_paths),
            )
