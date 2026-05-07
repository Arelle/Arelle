"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping

from arelle.ModelValue import QName
from arelle.oim._tc.const import TCME_ILLEGAL_CONSTRAINT, TCME_UNKNOWN_TYPE
from arelle.oim._tc.metadata.common import TCMetadataValidationError
from arelle.oim._tc.metadata.model import TCValueConstraint
from arelle.oim._tc.metadata.restrictions import (
    get_constraint_values_by_restriction,
    permitted_restrictions,
)
from arelle.oim._tc.metadata.types import resolve_effective_lexical_type
from arelle.typing import TypeGetText

_: TypeGetText


class TCMetadataIllegalConstraintError(TCMetadataValidationError):
    def __init__(self, message: str, *paths: str) -> None:
        primary, *related = paths
        super().__init__(
            message,
            primary,
            code=TCME_ILLEGAL_CONSTRAINT,
            related_paths=[(r,) for r in related],
        )


def validate_value_constraint(
    constraint: TCValueConstraint,
    namespaces: Mapping[str, str],
) -> Generator[TCMetadataValidationError, None, None]:
    """Yields TCMetadataValidationError with relative path segments.

    The caller is responsible for prepending the full path prefix via prepend_path().
    """
    effective_lexical_type = resolve_effective_lexical_type(constraint.type, namespaces)
    if effective_lexical_type is None:
        yield TCMetadataValidationError(
            _("Unknown type: '{}'").format(constraint.type),
            "type",
            code=TCME_UNKNOWN_TYPE,
        )
        return
    yield from _validate_permitted_restrictions(constraint, effective_lexical_type)


def _validate_permitted_restrictions(
    constraint: TCValueConstraint,
    effective_lexical_type: QName,
) -> Generator[TCMetadataValidationError, None, None]:
    restriction_values = get_constraint_values_by_restriction(constraint)
    applied_restrictions = {restriction for restriction, value in restriction_values.items() if value is not None}
    valid_restrictions = permitted_restrictions(constraint.type, effective_lexical_type)
    if disallowed_restrictions := sorted(applied_restrictions - valid_restrictions):
        yield TCMetadataIllegalConstraintError(
            _("Constraint of type '{}' must not define restrictions '{}'").format(
                constraint.type,
                ", ".join(disallowed_restrictions),
            ),
            "type",
            *disallowed_restrictions,
        )
