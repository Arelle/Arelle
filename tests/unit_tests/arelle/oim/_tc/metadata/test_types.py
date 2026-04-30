from __future__ import annotations

import pytest

from arelle import XbrlConst
from arelle.ModelValue import QName
from arelle.oim._tc.metadata import types as tc_types
from arelle.oim._tc.metadata.types import (
    _CORE_EFFECTIVE_LEXICAL_TYPES,
    _TC_PERMITTED_SCHEMA_TYPES,
    resolve_effective_lexical_type,
)

_XSD_NS = XbrlConst.xsd
_EXAMPLE_NS = "http://example.com/ns"
_XS_NAMESPACES = {"xs": _XSD_NS}


def _xsd(local: str) -> QName:
    return QName("xs", _XSD_NS, local)


class TestSchemaTypesConsistency:
    def test_all_public_qname_constants_in_schema_types(self) -> None:
        public_qnames = {v for k, v in vars(tc_types).items() if not k.startswith("_") and isinstance(v, QName)}
        assert public_qnames == _TC_PERMITTED_SCHEMA_TYPES

    def test_core_effective_types_are_schema_types(self) -> None:
        assert frozenset(_CORE_EFFECTIVE_LEXICAL_TYPES.values()) <= _TC_PERMITTED_SCHEMA_TYPES

    def test_all_core_constants_in_effective_types_mapping(self) -> None:
        public_core_strings = {v for k, v in vars(tc_types).items() if k.startswith("CORE_") and isinstance(v, str)}
        assert public_core_strings == frozenset(_CORE_EFFECTIVE_LEXICAL_TYPES.keys())


class TestResolveEffectiveLexicalTypeCoreTypes:
    @pytest.mark.parametrize(
        "core_type,expected_local",
        [
            ("concept", "QName"),
            ("entity", "token"),
            ("period", "string"),
            ("unit", "string"),
            ("language", "language"),
            ("decimals", "integer"),
        ],
    )
    def test_core_type_resolves_to_xsd_qname(self, core_type: str, expected_local: str) -> None:
        result = resolve_effective_lexical_type(core_type, {})
        assert result == _xsd(expected_local)

    def test_core_types_match_core_effective_types_mapping(self) -> None:
        for core_type, expected_qname in _CORE_EFFECTIVE_LEXICAL_TYPES.items():
            assert resolve_effective_lexical_type(core_type, {}) == expected_qname


class TestResolveEffectiveLexicalTypeXsdTypes:
    def test_xs_string_with_bound_prefix(self) -> None:
        assert resolve_effective_lexical_type("xs:string", _XS_NAMESPACES) == _xsd("string")

    def test_xs_decimal_with_bound_prefix(self) -> None:
        assert resolve_effective_lexical_type("xs:decimal", _XS_NAMESPACES) == _xsd("decimal")

    def test_xs_duration_with_bound_prefix(self) -> None:
        assert resolve_effective_lexical_type("xs:duration", _XS_NAMESPACES) == _xsd("duration")

    def test_xs_date_with_bound_prefix(self) -> None:
        assert resolve_effective_lexical_type("xs:date", _XS_NAMESPACES) == _xsd("date")

    def test_xs_integer_with_bound_prefix(self) -> None:
        assert resolve_effective_lexical_type("xs:integer", _XS_NAMESPACES) == _xsd("integer")

    def test_xs_type_with_unbound_prefix_returns_none(self) -> None:
        assert resolve_effective_lexical_type("xs:string", {}) is None

    def test_xs_type_bound_to_non_xsd_namespace_returns_none(self) -> None:
        assert resolve_effective_lexical_type("xs:string", {"xs": _EXAMPLE_NS}) is None

    def test_xsd_type_with_alternative_prefix(self) -> None:
        assert resolve_effective_lexical_type("xsd:string", {"xsd": _XSD_NS}) == _xsd("string")

    def test_xs_type_not_in_allowed_schema_types_returns_none(self) -> None:
        assert resolve_effective_lexical_type("xs:bogusType", _XS_NAMESPACES) is None


class TestResolveEffectiveLexicalTypeCustomNamespace:
    def test_custom_ns_type_with_bound_prefix_returns_none(self) -> None:
        assert resolve_effective_lexical_type("ex:myType", {"ex": _EXAMPLE_NS}) is None

    def test_custom_ns_type_with_unbound_prefix_returns_none(self) -> None:
        assert resolve_effective_lexical_type("ex:myType", {}) is None


class TestResolveEffectiveLexicalTypeUnknown:
    def test_unprefixed_non_core_type_returns_none(self) -> None:
        assert resolve_effective_lexical_type("unknown", _XS_NAMESPACES) is None

    def test_empty_string_returns_none(self) -> None:
        assert resolve_effective_lexical_type("", _XS_NAMESPACES) is None

    def test_multiple_colons_returns_none(self) -> None:
        assert resolve_effective_lexical_type("xs:string:invalid", _XS_NAMESPACES) is None

    def test_whitespace_padded_xs_type_returns_none(self) -> None:
        assert resolve_effective_lexical_type(" xs:string", _XS_NAMESPACES) is None
