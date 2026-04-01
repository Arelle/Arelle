"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Generator

from arelle import XbrlConst
from arelle.ModelValue import QName, qname
from arelle.oim._tc.const import TCME_ILLEGAL_CONSTRAINT, TCME_UNKNOWN_PERIOD_TYPE, TCME_UNKNOWN_TYPE
from arelle.oim._tc.metadata.common import TCMetadataValidationError
from arelle.oim._tc.metadata.model import TCValueConstraint
from arelle.typing import TypeGetText
from arelle.XbrlConst import qnXsdDuration
from arelle.XmlValidate import decimalPattern, floatPattern, integerPattern, lexicalPatterns

_: TypeGetText


def _xsd_qnames(*names: str) -> frozenset[QName]:
    return frozenset(QName("xs", XbrlConst.xsd, n) for n in names)


_CORE_DIMENSION_AND_DECIMALS_TYPES = frozenset(
    {
        "concept",
        "entity",
        "period",
        "unit",
        "language",
        "decimals",
    }
)

_ALLOWED_XS_TYPES = frozenset(
    {
        "anySimpleType",
        "anyURI",
        "base64Binary",
        "boolean",
        "byte",
        "date",
        "dateTime",
        "decimal",
        "double",
        "duration",
        "float",
        "gDay",
        "gMonth",
        "gMonthDay",
        "gYear",
        "gYearMonth",
        "hexBinary",
        "int",
        "integer",
        "language",
        "long",
        "NCName",
        "Name",
        "negativeInteger",
        "nonNegativeInteger",
        "nonPositiveInteger",
        "normalizedString",
        "positiveInteger",
        "QName",
        "short",
        "string",
        "time",
        "token",
        "unsignedByte",
        "unsignedInt",
        "unsignedLong",
        "unsignedShort",
    }
)

_CORE_DIMENSION_EFFECTIVE_TYPES: dict[str, QName] = {
    "concept": QName("xs", XbrlConst.xsd, "QName"),
    "entity": QName("xs", XbrlConst.xsd, "token"),
    "period": QName("xs", XbrlConst.xsd, "string"),
    "unit": QName("xs", XbrlConst.xsd, "string"),
    "language": QName("xs", XbrlConst.xsd, "language"),
}
_DECIMALS_EFFECTIVE_TYPE = QName("xs", XbrlConst.xsd, "integer")

_OPTIONALLY_TIME_ZONED_TYPES = _xsd_qnames(
    "date",
    "time",
    "dateTime",
    "gYearMonth",
    "gMonthDay",
    "gDay",
)

_LENGTH_APPLICABLE_TYPES = _xsd_qnames(
    "string",
    "normalizedString",
    "token",
    "language",
    "Name",
    "NCName",
    "NMTOKEN",
    "ID",
    "IDREF",
    "ENTITY",
    "hexBinary",
    "base64Binary",
    "anyURI",
    "QName",
    "NOTATION",
)

_BOUNDARY_APPLICABLE_TYPES = _xsd_qnames(
    "decimal",
    "integer",
    "nonPositiveInteger",
    "negativeInteger",
    "nonNegativeInteger",
    "positiveInteger",
    "long",
    "int",
    "short",
    "byte",
    "unsignedLong",
    "unsignedInt",
    "unsignedShort",
    "unsignedByte",
    "float",
    "double",
    "dateTime",
    "date",
    "time",
    "gYearMonth",
    "gYear",
    "gMonthDay",
    "gDay",
    "gMonth",
    "duration",
)

_DIGITS_APPLICABLE_TYPES = _xsd_qnames(
    "decimal",
    "integer",
    "nonPositiveInteger",
    "negativeInteger",
    "nonNegativeInteger",
    "positiveInteger",
    "long",
    "int",
    "short",
    "byte",
    "unsignedLong",
    "unsignedInt",
    "unsignedShort",
    "unsignedByte",
)

_INTEGER_TYPES = _xsd_qnames(
    "integer",
    "nonPositiveInteger",
    "negativeInteger",
    "nonNegativeInteger",
    "positiveInteger",
    "long",
    "int",
    "short",
    "byte",
    "unsignedLong",
    "unsignedInt",
    "unsignedShort",
    "unsignedByte",
)

_VALID_PERIOD_TYPES = frozenset({"year", "half", "quarter", "week", "month", "day", "instant"})


def validate_value_constraint(
    constraint: TCValueConstraint,
    namespaces: dict[str, str],
) -> Generator[TCMetadataValidationError, None, None]:
    """Yields TCMetadataValidationError with relative path segments.

    The caller is responsible for prepending the full path prefix via prepend_path().
    """
    if not is_valid_constraint_type(constraint.type):
        yield TCMetadataValidationError(
            _("Unknown type: '{type}'").format(type=constraint.type),
            "type",
            code=TCME_UNKNOWN_TYPE,
        )
        return
    effective_type = resolve_effective_type(constraint.type, namespaces)
    if effective_type is None:
        yield TCMetadataValidationError(
            _("Unknown type: '{type}'").format(type=constraint.type),
            "type",
            code=TCME_UNKNOWN_TYPE,
        )
        return

    if constraint.duration_type is not None and effective_type != qnXsdDuration:
        yield _illegalConstraintError(_("durationType is not applicable to type '{type}'").format(type=constraint.type))

    if constraint.period_type is not None:
        if constraint.type != "period":
            yield _illegalConstraintError(
                _("periodType is not applicable to type '{type}'").format(type=constraint.type)
            )
        if constraint.period_type not in _VALID_PERIOD_TYPES:
            yield TCMetadataValidationError(
                _("Unknown periodType: '{period_type}'").format(period_type=constraint.period_type),
                "periodType",
                code=TCME_UNKNOWN_PERIOD_TYPE,
            )

    if (
        constraint.time_zone is not None
        and constraint.type != "period"
        and effective_type not in _OPTIONALLY_TIME_ZONED_TYPES
    ):
        yield _illegalConstraintError(_("timeZone is not applicable to type '{type}'").format(type=constraint.type))

    if effective_type not in _LENGTH_APPLICABLE_TYPES:
        length_facet_names = {
            "length": constraint.length,
            "minLength": constraint.min_length,
            "maxLength": constraint.max_length,
        }
        for length_facet_name, length_facet_value in length_facet_names.items():
            if length_facet_value is not None:
                yield _illegalConstraintError(
                    _("{facet} is not applicable to type '{type}'").format(
                        facet=length_facet_name, type=constraint.type
                    )
                )

    boundary_facet_names = {
        "minInclusive": constraint.min_inclusive,
        "maxInclusive": constraint.max_inclusive,
        "minExclusive": constraint.min_exclusive,
        "maxExclusive": constraint.max_exclusive,
    }
    for boundary_facet_name, boundary_facet_value in boundary_facet_names.items():
        if boundary_facet_value is None:
            continue
        if effective_type not in _BOUNDARY_APPLICABLE_TYPES:
            yield _illegalConstraintError(
                _("{facet} is not applicable to type '{type}'").format(facet=boundary_facet_name, type=constraint.type)
            )
        elif not is_valid_lexical_value(boundary_facet_value, effective_type):
            yield _illegalConstraintError(
                _("{facet} value '{value}' is not valid for type '{type}'").format(
                    facet=boundary_facet_name,
                    value=boundary_facet_value,
                    type=constraint.type,
                )
            )

    if constraint.total_digits is not None and effective_type not in _DIGITS_APPLICABLE_TYPES:
        yield _illegalConstraintError(_("totalDigits is not applicable to type '{type}'").format(type=constraint.type))

    if constraint.fraction_digits is not None:
        if effective_type not in _DIGITS_APPLICABLE_TYPES:
            yield _illegalConstraintError(
                _("fractionDigits is not applicable to type '{type}'").format(type=constraint.type)
            )
        elif effective_type in _INTEGER_TYPES and constraint.fraction_digits != 0:
            yield _illegalConstraintError(
                _("fractionDigits must be 0 for type '{type}', got {value}").format(
                    type=constraint.type,
                    value=constraint.fraction_digits,
                )
            )

    if constraint.enumeration_values is not None:
        invalid_values = [
            value
            for value in sorted(constraint.enumeration_values)
            if not is_valid_lexical_value(value, effective_type)
        ]
        if invalid_values:
            yield _illegalConstraintError(
                _("Enumeration values {values} are not valid for type '{type}'").format(
                    values=invalid_values,
                    type=constraint.type,
                )
            )


def is_valid_constraint_type(type_value: str) -> bool:
    if type_value != type_value.strip():
        return False
    prefix, sep, local_name = type_value.partition(":")
    if sep:
        return prefix == "xs" and local_name in _ALLOWED_XS_TYPES
    return type_value in _CORE_DIMENSION_AND_DECIMALS_TYPES


def resolve_effective_type(constraint_type: str, namespaces: dict[str, str]) -> QName | None:
    if constraint_type in _CORE_DIMENSION_EFFECTIVE_TYPES:
        return _CORE_DIMENSION_EFFECTIVE_TYPES[constraint_type]
    if constraint_type == "decimals":
        return _DECIMALS_EFFECTIVE_TYPE
    return qname(constraint_type, namespaces)


def is_valid_lexical_value(value: str, xsd_type: QName) -> bool:
    if xsd_type in _INTEGER_TYPES:
        return integerPattern.match(value) is not None
    local_name = xsd_type.localName
    if local_name == "decimal":
        return decimalPattern.match(value) is not None
    if local_name in ("float", "double"):
        return floatPattern.match(value) is not None
    pattern = lexicalPatterns.get(local_name)
    if pattern is not None:
        return pattern.match(value) is not None
    return True


def _illegalConstraintError(message: str) -> TCMetadataValidationError:
    return TCMetadataValidationError(message, code=TCME_ILLEGAL_CONSTRAINT)
