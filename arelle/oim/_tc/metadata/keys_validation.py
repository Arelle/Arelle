"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Generator, Mapping

from arelle.oim._tc.const import TC_KEYS_PROPERTY_NAME, TCME_DUPLICATE_KEY_NAME, TCME_MISSING_KEY_PROPERTY
from arelle.oim._tc.metadata.common import TCMetadataValidationError
from arelle.oim._tc.metadata.model import TCKeys, TCMetadata, TCReferenceKey, TCTemplateConstraints, TCUniqueKey
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
