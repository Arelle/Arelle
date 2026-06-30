from __future__ import annotations

import dataclasses

from arelle import XbrlConst
from arelle.oim._tc.const import TCME_DUPLICATE_KEY_NAME, TCME_MISSING_KEY_PROPERTY
from arelle.oim._tc.metadata.common import TCMetadataValidationError
from arelle.oim._tc.metadata.keys_validation import validate_keys
from arelle.oim._tc.metadata.model import (
    TCKeys,
    TCMetadata,
    TCReferenceKey,
    TCTemplateConstraints,
    TCUniqueKey,
    TCValueConstraint,
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


class TestDuplicateKeyName:
    def test_no_error_distinct_names(self) -> None:
        assert _errors(TCKeys(unique=(_UNIQUE_KEY,), reference=(_REFERENCE_KEY,))) == []

    def test_unique_duplicate(self) -> None:
        tc = TCTemplateConstraints(
            constraints={
                "a": TCValueConstraint(type="xs:string"),
                "b": TCValueConstraint(type="xs:string"),
            }
        )
        keys = TCKeys(unique=(TCUniqueKey(name="k", fields=("a",)), TCUniqueKey(name="k", fields=("b",))))
        errors = _errors(keys, tc)
        assert len(errors) == 1
        assert errors[0].code == TCME_DUPLICATE_KEY_NAME
        assert errors[0].json_pointers == [
            f"/tableTemplates/{_T}/tc:keys/unique/0/name",
            f"/tableTemplates/{_T}/tc:keys/unique/1/name",
        ]

    def test_reference_duplicate(self) -> None:
        tc = TCTemplateConstraints(
            constraints={
                "c": TCValueConstraint(type="xs:string"),
                "a": TCValueConstraint(type="xs:string"),
                "b": TCValueConstraint(type="xs:string"),
            }
        )
        keys = TCKeys(
            unique=(_UNIQUE_KEY,),
            reference=(
                TCReferenceKey(name="r", fields=("a",), referenced_key_name="k"),
                TCReferenceKey(name="r", fields=("b",), referenced_key_name="k"),
            ),
        )
        errors = _errors(keys, tc)
        assert len(errors) == 1
        assert errors[0].code == TCME_DUPLICATE_KEY_NAME
        assert errors[0].json_pointers == [
            f"/tableTemplates/{_T}/tc:keys/reference/0/name",
            f"/tableTemplates/{_T}/tc:keys/reference/1/name",
        ]

    def test_three_occurrences_one_error_all_paths(self) -> None:
        tc = TCTemplateConstraints(
            constraints={
                "a": TCValueConstraint(type="xs:string"),
                "b": TCValueConstraint(type="xs:string"),
                "c": TCValueConstraint(type="xs:string"),
            }
        )
        keys = TCKeys(
            unique=(TCUniqueKey(name="k", fields=("a",)), TCUniqueKey(name="k", fields=("b",))),
            reference=(TCReferenceKey(name="k", fields=("c",), referenced_key_name="k"),),
        )
        errors = _errors(keys, tc)
        assert len(errors) == 1
        assert errors[0].code == TCME_DUPLICATE_KEY_NAME
        assert errors[0].json_pointers == [
            f"/tableTemplates/{_T}/tc:keys/unique/0/name",
            f"/tableTemplates/{_T}/tc:keys/unique/1/name",
            f"/tableTemplates/{_T}/tc:keys/reference/0/name",
        ]

    def test_same_name_shared_keys_in_one_template(self) -> None:
        tc = TCTemplateConstraints(
            constraints={
                "a": TCValueConstraint(type="xs:string"),
                "b": TCValueConstraint(type="xs:string"),
            }
        )
        keys = TCKeys(
            unique=(
                TCUniqueKey(name="k", fields=("a",), shared=True),
                TCUniqueKey(name="k", fields=("b",), shared=True),
            )
        )
        errors = _errors(keys, tc)
        assert len(errors) == 1
        assert errors[0].code == TCME_DUPLICATE_KEY_NAME

    def test_unique_and_reference_same_name(self) -> None:
        tc = TCTemplateConstraints(
            constraints={
                "a": TCValueConstraint(type="xs:string"),
                "b": TCValueConstraint(type="xs:string"),
            }
        )
        keys = TCKeys(
            unique=(TCUniqueKey(name="k", fields=("a",)),),
            reference=(TCReferenceKey(name="k", fields=("b",), referenced_key_name="k"),),
        )
        errors = _errors(keys, tc)
        assert len(errors) == 1
        assert errors[0].code == TCME_DUPLICATE_KEY_NAME
        assert errors[0].json_pointers == [
            f"/tableTemplates/{_T}/tc:keys/unique/0/name",
            f"/tableTemplates/{_T}/tc:keys/reference/0/name",
        ]
