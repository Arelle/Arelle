"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, cast

from arelle.ModelValue import QName
from arelle.oim._tc.metadata.model import TCValueConstraint
from arelle.oim._tc.metadata.types import resolve_effective_lexical_type
from arelle.XmlValidate import XmlValidationResult, validateFacetValueString, validateValueString


class ValueConstraintValidator:
    def __init__(self, constraint: TCValueConstraint, namespaces: Mapping[str, str]) -> None:
        self._constraint = constraint
        self._namespaces = namespaces
        self._effective_lexical_type = resolve_effective_lexical_type(constraint.type, namespaces)
        self._facets = self._build_facets()

    def _build_facets(self) -> Mapping[str, Any]:
        if self._effective_lexical_type is None:
            return MappingProxyType({})
        facets: dict[str, Any] = {}
        if self._constraint.length is not None:
            facets["length"] = self._constraint.length
        if self._constraint.min_length is not None:
            facets["minLength"] = self._constraint.min_length
        if self._constraint.max_length is not None:
            facets["maxLength"] = self._constraint.max_length
        if self._constraint.total_digits is not None:
            facets["totalDigits"] = self._constraint.total_digits
        if self._constraint.fraction_digits is not None:
            facets["fractionDigits"] = self._constraint.fraction_digits
        for facet_name, raw_value in (
            ("minInclusive", self._constraint.min_inclusive),
            ("maxInclusive", self._constraint.max_inclusive),
            ("minExclusive", self._constraint.min_exclusive),
            ("maxExclusive", self._constraint.max_exclusive),
        ):
            if raw_value is not None:
                result = validateFacetValueString(facet_name, raw_value, self._effective_lexical_type.localName)
                if result.isXValid and not isinstance(result.xValue, str):
                    facets[facet_name] = result.xValue
        return MappingProxyType(facets)

    def validate(self, value: str) -> bool:
        if self._effective_lexical_type is None:
            return False
        return self._validate_base_type(self._effective_lexical_type, value).isXValid

    def _validate_base_type(self, base_xsd_type: QName, value_string: str) -> XmlValidationResult:
        return validateValueString(
            base_xsd_type.localName,
            value_string,
            facets=self._facets,
            nsmap=cast(Mapping[str | None, str], self._namespaces),
        )
