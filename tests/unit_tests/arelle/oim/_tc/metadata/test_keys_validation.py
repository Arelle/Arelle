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
_T1 = "t1"
_T2 = "t2"
_T3 = "t3"


_CONSTRAINT_C = TCTemplateConstraints(constraints={"c": TCValueConstraint(type="xs:string")})
_CONSTRAINT_ID = TCTemplateConstraints(constraints={"id": TCValueConstraint(type="xs:string")})

_NAMESPACES = {"xs": XbrlConst.xsd}


def _errors(keys: TCKeys, tc: TCTemplateConstraints | None = None) -> list[TCMetadataValidationError]:
    tc_obj = dataclasses.replace(tc if tc is not None else _CONSTRAINT_C, keys=keys)
    return list(validate_keys(TCMetadata(template_constraints={_T: tc_obj}), _NAMESPACES))


def _cross_errors(
    t1_keys: TCKeys,
    t2_keys: TCKeys,
    t1_tc: TCTemplateConstraints | None = None,
    t2_tc: TCTemplateConstraints | None = None,
) -> list[TCMetadataValidationError]:
    t1 = dataclasses.replace(t1_tc if t1_tc is not None else _CONSTRAINT_ID, keys=t1_keys)
    t2 = dataclasses.replace(t2_tc if t2_tc is not None else _CONSTRAINT_ID, keys=t2_keys)
    return list(validate_keys(TCMetadata(template_constraints={_T1: t1, _T2: t2}), _NAMESPACES))


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


class TestCrossTemplateDuplicateKeyName:
    def test_both_shared(self) -> None:
        key = TCUniqueKey(name="customer", fields=("id",), shared=True)
        assert _cross_errors(TCKeys(unique=(key,)), TCKeys(unique=(key,))) == []

    def test_distinct_names(self) -> None:
        k1 = TCUniqueKey(name="key1", fields=("id",))
        k2 = TCUniqueKey(name="key2", fields=("id",))
        assert _cross_errors(TCKeys(unique=(k1,)), TCKeys(unique=(k2,))) == []

    def test_both_non_shared(self) -> None:
        key = TCUniqueKey(name="customer", fields=("id",))
        errors = _cross_errors(TCKeys(unique=(key,)), TCKeys(unique=(key,)))
        assert len(errors) == 1
        assert errors[0].code == TCME_DUPLICATE_KEY_NAME
        assert errors[0].json_pointers == [
            f"/tableTemplates/{_T1}/tc:keys/unique/0/name",
            f"/tableTemplates/{_T2}/tc:keys/unique/0/name",
        ]

    def test_first_shared_second_non_shared(self) -> None:
        k1 = TCUniqueKey(name="customer", fields=("id",), shared=True)
        k2 = TCUniqueKey(name="customer", fields=("id",))
        errors = _cross_errors(TCKeys(unique=(k1,)), TCKeys(unique=(k2,)))
        assert len(errors) == 1
        assert errors[0].code == TCME_DUPLICATE_KEY_NAME
        assert errors[0].json_pointers == [
            f"/tableTemplates/{_T2}/tc:keys/unique/0/name",
        ]

    def test_first_non_shared_second_shared(self) -> None:
        k1 = TCUniqueKey(name="customer", fields=("id",))
        k2 = TCUniqueKey(name="customer", fields=("id",), shared=True)
        errors = _cross_errors(TCKeys(unique=(k1,)), TCKeys(unique=(k2,)))
        assert len(errors) == 1
        assert errors[0].code == TCME_DUPLICATE_KEY_NAME
        assert errors[0].json_pointers == [
            f"/tableTemplates/{_T1}/tc:keys/unique/0/name",
        ]

    def test_three_templates_mixed_shared_reports_only_non_shared(self) -> None:
        shared = TCUniqueKey(name="customer", fields=("id",), shared=True)
        non_shared = TCUniqueKey(name="customer", fields=("id",))
        t1 = dataclasses.replace(_CONSTRAINT_ID, keys=TCKeys(unique=(shared,)))
        t2 = dataclasses.replace(_CONSTRAINT_ID, keys=TCKeys(unique=(non_shared,)))
        t3 = dataclasses.replace(_CONSTRAINT_ID, keys=TCKeys(unique=(non_shared,)))
        errors = list(validate_keys(TCMetadata(template_constraints={_T1: t1, _T2: t2, _T3: t3}), _NAMESPACES))
        assert len(errors) == 1
        assert errors[0].code == TCME_DUPLICATE_KEY_NAME
        assert errors[0].json_pointers == [
            f"/tableTemplates/{_T2}/tc:keys/unique/0/name",
            f"/tableTemplates/{_T3}/tc:keys/unique/0/name",
        ]
