"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping
from typing import Any

from arelle.ModelValue import QName
from arelle.oim._tc.const import (
    TCME_ILLEGAL_CONSTRAINT,
    TCME_UNKNOWN_DURATION_TYPE,
    TCME_UNKNOWN_PERIOD_TYPE,
    TCME_UNKNOWN_TYPE,
)
from arelle.oim._tc.metadata.common import TCMetadataValidationError
from arelle.oim._tc.metadata.model import TCValueConstraint
from arelle.oim._tc.metadata.restrictions import (
    BOUNDS_RESTRICTIONS,
    TCRestriction,
    get_constraint_values_by_restriction,
    permitted_restrictions,
)
from arelle.oim._tc.metadata.types import resolve_effective_lexical_type
from arelle.typing import TypeGetText
from arelle.XmlValidate import XmlValidationResult, validateFacetValueString

_: TypeGetText

_VALID_PERIOD_TYPES = frozenset(
    {
        "year",
        "half",
        "quarter",
        "week",
        "month",
        "day",
        "instant",
    }
)


_VALID_DURATION_TYPES = frozenset(
    {
        "dayTime",
        "yearMonth",
    }
)


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
    yield from _validate_patterns_restriction(constraint)
    yield from _validate_period_type_restriction(constraint)
    yield from _validate_duration_type_restriction(constraint)
    yield from _validate_length_restrictions(constraint)
    yield from _validate_bounds_restrictions(constraint, effective_lexical_type)


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


def _validate_patterns_restriction(constraint: TCValueConstraint) -> Generator[TCMetadataValidationError, None, None]:
    if constraint.patterns is None:
        return
    invalid_patterns = sorted(
        pattern
        for pattern in constraint.patterns
        if not validateFacetValueString("pattern", pattern, "xsd-pattern").isXValid
    )
    if invalid_patterns:
        yield TCMetadataIllegalConstraintError(
            _("Patterns {} are not valid XSD regular expressions").format(invalid_patterns),
            TCRestriction.PATTERNS,
        )


def _validate_period_type_restriction(
    constraint: TCValueConstraint,
) -> Generator[TCMetadataValidationError, None, None]:
    if constraint.period_type is not None and constraint.period_type not in _VALID_PERIOD_TYPES:
        yield TCMetadataValidationError(
            _("Unknown period type: '{}'").format(constraint.period_type),
            TCRestriction.PERIOD_TYPE,
            code=TCME_UNKNOWN_PERIOD_TYPE,
        )


def _validate_duration_type_restriction(
    constraint: TCValueConstraint,
) -> Generator[TCMetadataValidationError, None, None]:
    if constraint.duration_type is not None and constraint.duration_type not in _VALID_DURATION_TYPES:
        yield TCMetadataValidationError(
            _("Unknown duration type: '{}'").format(constraint.duration_type),
            TCRestriction.DURATION_TYPE,
            code=TCME_UNKNOWN_DURATION_TYPE,
        )


def _validate_length_restrictions(constraint: TCValueConstraint) -> Generator[TCMetadataValidationError, None, None]:
    if constraint.length is not None:
        conflicting_properties = []
        if constraint.min_length is not None:
            conflicting_properties.append(TCRestriction.MIN_LENGTH)
        if constraint.max_length is not None:
            conflicting_properties.append(TCRestriction.MAX_LENGTH)
        if conflicting_properties:
            yield TCMetadataIllegalConstraintError(
                _("length must not be specified together with {}").format(" or ".join(conflicting_properties)),
                TCRestriction.LENGTH,
                *conflicting_properties,
            )

    min_length = constraint.min_length
    max_length = constraint.max_length
    if min_length is not None and max_length is not None and min_length > max_length:
        yield TCMetadataIllegalConstraintError(
            _("minLength ({}) must be less than or equal to maxLength ({})").format(min_length, max_length),
            TCRestriction.MIN_LENGTH,
            TCRestriction.MAX_LENGTH,
        )


def _validate_bounds_restrictions(
    constraint: TCValueConstraint,
    effective_lexical_type: QName,
) -> Generator[TCMetadataValidationError, None, None]:
    permitted = permitted_restrictions(constraint.type, effective_lexical_type)
    if not permitted & BOUNDS_RESTRICTIONS:
        return

    min_inclusive = constraint.min_inclusive
    min_exclusive = constraint.min_exclusive
    if min_inclusive is not None and min_exclusive is not None:
        yield TCMetadataIllegalConstraintError(
            _("minInclusive and minExclusive must not be specified together"),
            TCRestriction.MIN_INCLUSIVE,
            TCRestriction.MIN_EXCLUSIVE,
        )

    max_inclusive = constraint.max_inclusive
    max_exclusive = constraint.max_exclusive
    if max_inclusive is not None and max_exclusive is not None:
        yield TCMetadataIllegalConstraintError(
            _("maxInclusive and maxExclusive must not be specified together"),
            TCRestriction.MAX_INCLUSIVE,
            TCRestriction.MAX_EXCLUSIVE,
        )

    base_xsd_type = effective_lexical_type.localName
    min_inc_result = _parse_bounds_facet_value(TCRestriction.MIN_INCLUSIVE, min_inclusive, base_xsd_type)
    min_exc_result = _parse_bounds_facet_value(TCRestriction.MIN_EXCLUSIVE, min_exclusive, base_xsd_type)
    max_inc_result = _parse_bounds_facet_value(TCRestriction.MAX_INCLUSIVE, max_inclusive, base_xsd_type)
    max_exc_result = _parse_bounds_facet_value(TCRestriction.MAX_EXCLUSIVE, max_exclusive, base_xsd_type)

    restriction_parsed_values = [
        (TCRestriction.MIN_INCLUSIVE, min_inclusive, min_inc_result),
        (TCRestriction.MAX_INCLUSIVE, max_inclusive, max_inc_result),
        (TCRestriction.MIN_EXCLUSIVE, min_exclusive, min_exc_result),
        (TCRestriction.MAX_EXCLUSIVE, max_exclusive, max_exc_result),
    ]
    for restriction, raw, result in restriction_parsed_values:
        if result is None or result.isXValid or isinstance(result.xValue, str):
            continue
        yield TCMetadataIllegalConstraintError(
            _("{} value '{}' is not valid for type '{}'").format(restriction, raw, constraint.type),
            restriction,
        )

    min_inc = _comparable_value(min_inc_result)
    min_exc = _comparable_value(min_exc_result)
    max_inc = _comparable_value(max_inc_result)
    max_exc = _comparable_value(max_exc_result)

    if min_inc is not None and max_inc is not None and min_inc > max_inc:
        yield _bounds_ordering_error(
            TCRestriction.MIN_INCLUSIVE, min_inclusive, "<=", TCRestriction.MAX_INCLUSIVE, max_inclusive
        )
    if min_inc is not None and max_exc is not None and min_inc >= max_exc:
        yield _bounds_ordering_error(
            TCRestriction.MIN_INCLUSIVE, min_inclusive, "<", TCRestriction.MAX_EXCLUSIVE, max_exclusive
        )
    if min_exc is not None and max_inc is not None and min_exc >= max_inc:
        yield _bounds_ordering_error(
            TCRestriction.MIN_EXCLUSIVE, min_exclusive, "<", TCRestriction.MAX_INCLUSIVE, max_inclusive
        )
    if min_exc is not None and max_exc is not None and min_exc > max_exc:
        yield _bounds_ordering_error(
            TCRestriction.MIN_EXCLUSIVE, min_exclusive, "<=", TCRestriction.MAX_EXCLUSIVE, max_exclusive
        )


def _bounds_ordering_error(
    lower: TCRestriction,
    lower_value: str | None,
    relation: str,
    upper: TCRestriction,
    upper_value: str | None,
) -> TCMetadataIllegalConstraintError:
    return TCMetadataIllegalConstraintError(
        _("{} ({}) must be {} {} ({})").format(lower, lower_value, relation, upper, upper_value),
        lower,
        upper,
    )


def _parse_bounds_facet_value(
    restriction: TCRestriction,
    raw: str | None,
    base_xsd_type: str,
) -> XmlValidationResult | None:
    if raw is None:
        return None
    return validateFacetValueString(restriction.value, raw, base_xsd_type)


def _comparable_value(result: XmlValidationResult | None) -> Any:
    if result is not None and result.isXValid and not isinstance(result.xValue, str):
        return result.xValue
    return None
