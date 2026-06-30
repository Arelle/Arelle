"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Generator, Mapping

from arelle.oim._tc.const import (
    TC_KEYS_PROPERTY_NAME,
    TCME_DUPLICATE_KEY_NAME,
    TCME_ILLEGAL_KEY_FIELD,
    TCME_MISSING_KEY_PROPERTY,
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
