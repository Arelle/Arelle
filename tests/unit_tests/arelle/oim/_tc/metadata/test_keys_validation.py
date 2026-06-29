from __future__ import annotations

import dataclasses

from arelle import XbrlConst
from arelle.oim._tc.const import TCME_MISSING_KEY_PROPERTY
from arelle.oim._tc.metadata.common import TCMetadataValidationError
from arelle.oim._tc.metadata.keys_validation import validate_keys
from arelle.oim._tc.metadata.model import (
    TCKeys,
    TCMetadata,
    TCReferenceKey,
    TCTemplateConstraints,
    TCUniqueKey,
)

_T = "t"

_NAMESPACES = {"xs": XbrlConst.xsd}


def _errors(keys: TCKeys, tc: TCTemplateConstraints | None = None) -> list[TCMetadataValidationError]:
    tc_obj = dataclasses.replace(tc or TCTemplateConstraints(), keys=keys)
    return list(validate_keys(TCMetadata(template_constraints={_T: tc_obj}), _NAMESPACES))


_UNIQUE_KEY = TCUniqueKey(name="k", fields=("c",))
_REFERENCE_KEY = TCReferenceKey(name="r", fields=("c",), referenced_key_name="k")


class TestMissingKeyProperty:
    def test_empty_keys(self) -> None:
        errors = _errors(TCKeys())
        assert len(errors) == 1
        assert errors[0].code == TCME_MISSING_KEY_PROPERTY
        assert errors[0].json_pointers == [f"/tableTemplates/{_T}/tc:keys"]

    def test_unique_only(self) -> None:
        assert _errors(TCKeys(unique=(_UNIQUE_KEY,))) == []

    def test_reference_only(self) -> None:
        assert _errors(TCKeys(reference=(_REFERENCE_KEY,))) == []

    def test_both_present(self) -> None:
        assert _errors(TCKeys(unique=(_UNIQUE_KEY,), reference=(_REFERENCE_KEY,))) == []
