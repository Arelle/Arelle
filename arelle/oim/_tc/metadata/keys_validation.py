"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Generator, Mapping

from arelle.oim._tc.const import TC_KEYS_PROPERTY_NAME, TCME_DUPLICATE_KEY_NAME, TCME_MISSING_KEY_PROPERTY
from arelle.oim._tc.metadata.common import TCMetadataValidationError
from arelle.oim._tc.metadata.model import TCKeys, TCMetadata, TCTemplateConstraints
from arelle.oim.csv.metadata.common import TABLE_TEMPLATES_KEY
from arelle.typing import TypeGetText

_: TypeGetText


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
    if keys.reference is not None:
        for i, reference_key in enumerate(keys.reference):
            paths_by_key_name[reference_key.name].append(("reference", str(i), "name"))

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
