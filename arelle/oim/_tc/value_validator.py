"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from arelle.ModelValue import QName
from arelle.oim._tc.metadata.model import TCValueConstraint
from arelle.oim._tc.metadata.types import resolve_effective_lexical_type
from arelle.XmlValidate import XmlValidationResult, validateValueString


class ValueConstraintValidator:
    def __init__(self, constraint: TCValueConstraint, namespaces: Mapping[str, str]) -> None:
        self._constraint = constraint
        self._namespaces = namespaces
        self._effective_lexical_type = resolve_effective_lexical_type(constraint.type, namespaces)

    def validate(self, value: str) -> bool:
        if self._effective_lexical_type is None:
            return False
        return self._validate_base_type(self._effective_lexical_type, value).isXValid

    def _validate_base_type(self, base_xsd_type: QName, value_string: str) -> XmlValidationResult:
        return validateValueString(
            base_xsd_type.localName,
            value_string,
            nsmap=cast(Mapping[str | None, str], self._namespaces),
        )
