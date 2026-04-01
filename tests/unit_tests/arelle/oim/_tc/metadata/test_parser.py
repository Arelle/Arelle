from __future__ import annotations

from typing import Any

from arelle.oim._model import OimReport
from arelle.oim._tc.const import (
    TC_NS_CR,
    TC_NS_DRAFT,
    TC_PREFIX,
    TCME_INVALID_JSON_STRUCTURE,
)
from arelle.oim._tc.metadata.model import TCValueConstraint
from arelle.oim._tc.metadata.parser import TCMetadataMissingPropertiesError, parse_tc_metadata

TC_MINIMAL_NAMESPACES = {TC_PREFIX: TC_NS_DRAFT}


def _oim_report(
    oim_object: dict[str, Any],
    namespaces: dict[str, str],
) -> OimReport:
    oim_object.setdefault("documentInfo", {})["namespaces"] = namespaces
    return OimReport(oim_object=oim_object)


def _with_constraint(constraint: dict[str, Any]) -> dict[str, Any]:
    return {"tableTemplates": {"t1": {"columns": {"col": {"tc:constraints": constraint}}}}}


def _with_template(template: dict[str, Any]) -> dict[str, Any]:
    return {"tableTemplates": {"t1": {"columns": {}, **template}}}


class TestNamespaceDetection:
    def test_returns_none_without_tc_namespace(self) -> None:
        result = parse_tc_metadata(_oim_report({"tableTemplates": {}}, {"xbrl": "https://xbrl.org/2021"}))
        assert result is None

    def test_returns_none_when_namespaces_empty(self) -> None:
        result = parse_tc_metadata(_oim_report({"tableTemplates": {}}, {}))
        assert result is None

    def test_detects_draft_namespace(self) -> None:
        result = parse_tc_metadata(_oim_report({"tableTemplates": {}}, {"tc": TC_NS_DRAFT}))
        assert result is not None
        assert result.metadata is not None

    def test_detects_cr_namespace(self) -> None:
        result = parse_tc_metadata(_oim_report({"tableTemplates": {}}, {"tc": TC_NS_CR}))
        assert result is not None
        assert result.metadata is not None

    def test_detects_non_tc_prefix(self) -> None:
        result = parse_tc_metadata(_oim_report({"tableTemplates": {}}, {"custom": TC_NS_DRAFT}))
        assert result is not None
        assert result.metadata is not None


class TestPrimitiveStr:
    def test_present_correct_type(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:integer"}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints["t1"].constraints["col"].type == "xs:integer"

    def test_missing_required_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert not result.is_valid

    def test_wrong_type_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": 123}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert not result.is_valid

    def test_default_when_missing(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:string"}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints["t1"].constraints["col"].period_type is None

    def test_json_null_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": None}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert not result.is_valid


class TestPrimitiveBool:
    def test_present_correct_type(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:string", "optional": True}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints["t1"].constraints["col"].optional is True

    def test_default_when_missing(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:string"}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints["t1"].constraints["col"].optional is False

    def test_wrong_type_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:string", "optional": "true"}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert not result.is_valid

    def test_json_null_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:string", "optional": None}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert not result.is_valid


class TestPrimitiveInt:
    def test_present_correct_type(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:string", "length": 10}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints["t1"].constraints["col"].length == 10

    def test_default_when_missing(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:string"}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints["t1"].constraints["col"].length is None

    def test_wrong_type_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:string", "length": "10"}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert not result.is_valid

    def test_bool_true_rejected(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:string", "length": True}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert not result.is_valid

    def test_bool_false_rejected(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:string", "length": False}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert not result.is_valid

    def test_json_null_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:string", "length": None}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert not result.is_valid

    def test_zero_accepted_for_non_negative(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:string", "length": 0}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints["t1"].constraints["col"].length == 0

    def test_negative_rejected_for_non_negative(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:string", "length": -1}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert not result.is_valid
        assert "Value -1 is less than minimum 0" in str(result.errors[0])
        assert result.errors[0].code == TCME_INVALID_JSON_STRUCTURE

    def test_positive_int_rejects_zero(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:tableConstraints": {"minTables": 0}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert "Value 0 is less than minimum 1" in str(result.errors[0])

    def test_positive_int_rejects_negative(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:tableConstraints": {"minTables": -1}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert "Value -1 is less than minimum 1" in str(result.errors[0])


class TestSetFields:
    def test_returns_frozenset(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_constraint({"type": "xs:string", "enumerationValues": ["a", "b"]}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        ev = result.metadata.template_constraints["t1"].constraints["col"].enumeration_values
        assert isinstance(ev, frozenset)
        assert ev == frozenset({"a", "b"})

    def test_none_when_missing(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:string"}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints["t1"].constraints["col"].enumeration_values is None

    def test_empty_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_constraint({"type": "xs:string", "enumerationValues": []}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid

    def test_duplicates_raise(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_constraint({"type": "xs:string", "enumerationValues": ["a", "a"]}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid

    def test_non_list_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_constraint({"type": "xs:string", "enumerationValues": "not a list"}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid

    def test_non_str_element_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_constraint({"type": "xs:string", "enumerationValues": ["a", 1]}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid

    def test_patterns_returns_frozenset(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_constraint({"type": "xs:string", "patterns": ["^x$"]}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        assert isinstance(result.metadata.template_constraints["t1"].constraints["col"].patterns, frozenset)

    def test_empty_patterns_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_constraint({"type": "xs:string", "patterns": []}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid


class TestValueConstraint:
    def test_minimal_defaults(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:date"}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints["t1"].constraints["col"] == TCValueConstraint(type="xs:date")

    def test_all_fields_populated(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_constraint(
                {
                    "type": "xs:string",
                    "optional": True,
                    "nillable": True,
                    "enumerationValues": ["a", "b"],
                    "patterns": ["^x$"],
                    "timeZone": False,
                    "periodType": "month",
                    "durationType": "yearMonth",
                    "length": 10,
                    "minLength": 1,
                    "maxLength": 100,
                    "minInclusive": "0",
                    "maxInclusive": "999",
                    "minExclusive": "-1",
                    "maxExclusive": "1000",
                    "totalDigits": 5,
                    "fractionDigits": 2,
                }
            ),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints["t1"].constraints["col"] == TCValueConstraint(
            type="xs:string",
            optional=True,
            nillable=True,
            enumeration_values=frozenset({"a", "b"}),
            patterns=frozenset({"^x$"}),
            time_zone=False,
            period_type="month",
            duration_type="yearMonth",
            length=10,
            min_length=1,
            max_length=100,
            min_inclusive="0",
            max_inclusive="999",
            min_exclusive="-1",
            max_exclusive="1000",
            total_digits=5,
            fraction_digits=2,
        )


class TestOrderedSetFields:
    def test_returns_tuple_preserving_order(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:columnOrder": ["c", "a", "b"]}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints["t1"].column_order == ("c", "a", "b")

    def test_missing_returns_none(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:string"}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints["t1"].column_order is None

    def test_duplicates_raise(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_template({"tc:columnOrder": ["a", "a"]}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert not result.is_valid

    def test_non_list_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_template({"tc:columnOrder": "not a list"}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert not result.is_valid

    def test_non_string_element_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_template({"tc:columnOrder": ["a", 1]}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert not result.is_valid

    def test_fields_preserves_order(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"unique": [{"name": "k", "fields": ["b", "a"]}]}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints["t1"].keys.unique[0].fields == ("b", "a")

    def test_empty_fields_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"unique": [{"name": "k", "fields": []}]}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid


class TestColumnConstraints:
    def test_single_column(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": "xs:integer"}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints["t1"].constraints["col"].type == "xs:integer"

    def test_multiple_columns(self) -> None:
        result = parse_tc_metadata(_oim_report(
            {
                "tableTemplates": {
                    "t1": {
                        "columns": {
                            "col_a": {"tc:constraints": {"type": "xs:integer"}},
                            "col_b": {"tc:constraints": {"type": "xs:string"}},
                            "col_c": {},
                        }
                    }
                }
            },
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        tc = result.metadata.template_constraints["t1"]
        assert len(tc.constraints) == 2
        assert "col_c" not in tc.constraints

    def test_non_dict_constraint_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            {"tableTemplates": {"t1": {"columns": {"col": {"tc:constraints": "not a dict"}}}}},
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid

    def test_skips_non_dict_column(self) -> None:
        result = parse_tc_metadata(_oim_report(
            {"tableTemplates": {"t1": {"columns": {"col": "not a dict"}}}},
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        assert "t1" not in result.metadata.template_constraints


class TestParameters:
    def test_parses_parameter_constraints(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:parameters": {"p1": {"type": "period", "periodType": "month"}}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        p = result.metadata.template_constraints["t1"].parameters["p1"]
        assert p.type == "period"
        assert p.period_type == "month"

    def test_non_dict_parameter_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template(
                {
                    "tc:parameters": {
                        "good": {"type": "xs:string"},
                        "bad": "not a dict",
                    },
                }
            ),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid


class TestUniqueKeys:
    def test_parses_with_defaults(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"unique": [{"name": "pk", "fields": ["id"]}]}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        uk = result.metadata.template_constraints["t1"].keys.unique[0]
        assert uk.name == "pk"
        assert uk.fields == ("id",)
        assert uk.severity == "error"
        assert uk.shared is False

    def test_parses_with_all_fields(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template(
                {
                    "tc:keys": {
                        "unique": [
                            {
                                "name": "pk",
                                "fields": ["id", "date"],
                                "severity": "warning",
                                "shared": True,
                            }
                        ]
                    },
                }
            ),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        uk = result.metadata.template_constraints["t1"].keys.unique[0]
        assert uk.severity == "warning"
        assert uk.shared is True
        assert uk.fields == ("id", "date")

    def test_multiple_keys(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template(
                {
                    "tc:keys": {
                        "unique": [
                            {"name": "pk", "fields": ["id"]},
                            {"name": "ak", "fields": ["code"]},
                        ]
                    },
                }
            ),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        keys = result.metadata.template_constraints["t1"].keys
        assert keys is not None
        assert keys.unique is not None
        assert len(keys.unique) == 2
        assert keys.unique[0].name == "pk"
        assert keys.unique[1].name == "ak"

    def test_missing_name_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"unique": [{"fields": ["id"]}]}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid

    def test_missing_fields_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"unique": [{"name": "pk"}]}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid

    def test_absent_returns_none(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"sortKey": "pk"}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints["t1"].keys.unique is None

    def test_empty_list_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"unique": []}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid

    def test_non_dict_element_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"unique": ["not a dict"]}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        error = result.errors[0]
        assert error.json_pointer == "/tableTemplates/t1/tc:keys/unique/0"
        assert "Expected dict" in str(error)
        assert "'not a dict'" in str(error)

    def test_non_list_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"unique": "not a list"}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid

    def test_error_pointer_includes_index(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template(
                {
                    "tc:keys": {
                        "unique": [
                            {"name": "pk", "fields": ["id"]},
                            {"fields": ["id"]},
                        ]
                    },
                }
            ),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert "/unique/1" in result.errors[0].json_pointer


class TestReferenceKeys:
    def test_parses_with_defaults(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template(
                {
                    "tc:keys": {"reference": [{"name": "fk", "fields": ["col"], "referencedKeyName": "pk"}]},
                }
            ),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        rk = result.metadata.template_constraints["t1"].keys.reference[0]
        assert rk.name == "fk"
        assert rk.fields == ("col",)
        assert rk.referenced_key_name == "pk"
        assert rk.negate is False
        assert rk.severity == "error"

    def test_parses_with_all_fields(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template(
                {
                    "tc:keys": {
                        "reference": [
                            {
                                "name": "fk",
                                "fields": ["a", "b"],
                                "referencedKeyName": "pk",
                                "negate": True,
                                "severity": "warning",
                            }
                        ]
                    },
                }
            ),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        rk = result.metadata.template_constraints["t1"].keys.reference[0]
        assert rk.negate is True
        assert rk.severity == "warning"

    def test_missing_referenced_key_name_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"reference": [{"name": "fk", "fields": ["col"]}]}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid

    def test_absent_returns_none(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"sortKey": "pk"}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints["t1"].keys.reference is None

    def test_empty_list_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"reference": []}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid

    def test_non_dict_element_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"reference": ["not a dict"]}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        error = result.errors[0]
        assert error.json_pointer == "/tableTemplates/t1/tc:keys/reference/0"
        assert "Expected dict" in str(error)
        assert "'not a dict'" in str(error)

    def test_error_pointer_includes_index(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template(
                {
                    "tc:keys": {"reference": [{"name": "fk", "fields": ["col"]}]},
                }
            ),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert "/reference/0" in result.errors[0].json_pointer


class TestKeys:
    def test_empty_keys_object(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {}, "tc:columnOrder": ["a"]}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        keys = result.metadata.template_constraints["t1"].keys
        assert keys is not None
        assert keys.unique is None
        assert keys.reference is None
        assert keys.sort_key is None

    def test_sort_key(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template(
                {
                    "tc:keys": {
                        "unique": [{"name": "pk", "fields": ["id"]}],
                        "sortKey": "pk",
                    },
                }
            ),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints["t1"].keys.sort_key == "pk"

    def test_unique_and_reference_together(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template(
                {
                    "tc:keys": {
                        "unique": [{"name": "pk", "fields": ["id"]}],
                        "reference": [{"name": "fk", "fields": ["col"], "referencedKeyName": "pk"}],
                    },
                }
            ),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        keys = result.metadata.template_constraints["t1"].keys
        assert keys is not None
        assert keys.unique is not None
        assert keys.reference is not None


class TestTableConstraints:
    def test_all_fields(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template(
                {
                    "tc:tableConstraints": {
                        "minTables": 1,
                        "maxTables": 5,
                        "minTableRows": 10,
                        "maxTableRows": 100,
                    },
                }
            ),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        tc_obj = result.metadata.template_constraints["t1"].table_constraints
        assert tc_obj is not None
        assert tc_obj.min_tables == 1
        assert tc_obj.max_tables == 5
        assert tc_obj.min_table_rows == 10
        assert tc_obj.max_table_rows == 100

    def test_partial_fields(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:tableConstraints": {"minTables": 1}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        tc_obj = result.metadata.template_constraints["t1"].table_constraints
        assert tc_obj is not None
        assert tc_obj.min_tables == 1
        assert tc_obj.max_tables is None
        assert tc_obj.min_table_rows is None
        assert tc_obj.max_table_rows is None

    def test_wrong_type_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:tableConstraints": {"minTables": "1"}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid

    def test_bool_rejected_for_int(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:tableConstraints": {"minTables": True}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid

    def test_non_dict_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:tableConstraints": "not a dict"}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid

    def test_unknown_property_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:tableConstraints": {"minTables": 1, "unknownField": 42}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid


class TestUnknownProperties:
    def test_unknown_keys_property_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template(
                {
                    "tc:keys": {
                        "unique": [{"name": "pk", "fields": ["id"]}],
                        "unknown": "stuff",
                    },
                }
            ),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert result.errors[0].code == TCME_INVALID_JSON_STRUCTURE

    def test_unknown_unique_key_property_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template(
                {
                    "tc:keys": {
                        "unique": [{"name": "pk", "fields": ["id"], "unknownField": ""}],
                    },
                }
            ),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert result.errors[0].code == TCME_INVALID_JSON_STRUCTURE

    def test_unknown_reference_key_property_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template(
                {
                    "tc:keys": {
                        "reference": [
                            {
                                "name": "fk",
                                "fields": ["col"],
                                "referencedKeyName": "pk",
                                "unknownField": "",
                            }
                        ],
                    },
                }
            ),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert result.errors[0].code == TCME_INVALID_JSON_STRUCTURE

    def test_unknown_value_constraint_property_raises(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_constraint({"type": "xs:string", "unknownField": "stuff"}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert result.errors[0].code == TCME_INVALID_JSON_STRUCTURE
        assert "unknownField" in str(result.errors[0])

    def test_unknown_table_constraints_property_uses_correct_code(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:tableConstraints": {"minTables": 1, "unknownField": 42}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert result.errors[0].code == TCME_INVALID_JSON_STRUCTURE


class TestMissingProperties:
    def test_missing_required_value_constraint_type(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({}), TC_MINIMAL_NAMESPACES))
        assert not result.is_valid
        assert len(result.errors) == 1
        assert isinstance(result.errors[0], TCMetadataMissingPropertiesError)
        assert "'type'" in str(result.errors[0])

    def test_missing_required_unique_key_fields_consolidated(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"unique": [{}]}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert not result.is_valid
        assert len(result.errors) == 1
        assert isinstance(result.errors[0], TCMetadataMissingPropertiesError)
        assert "'fields'" in str(result.errors[0])
        assert "'name'" in str(result.errors[0])

    def test_missing_required_reference_key_fields_consolidated(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"reference": [{}]}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert not result.is_valid
        assert len(result.errors) == 1
        assert isinstance(result.errors[0], TCMetadataMissingPropertiesError)
        assert "'fields'" in str(result.errors[0])
        assert "'name'" in str(result.errors[0])
        assert "'referencedKeyName'" in str(result.errors[0])


class TestTemplateFiltering:
    def test_no_tc_properties_excluded(self) -> None:
        result = parse_tc_metadata(_oim_report(
            {"tableTemplates": {"t1": {"columns": {"col": {}}}}},
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints == {}

    def test_non_dict_template_skipped(self) -> None:
        result = parse_tc_metadata(_oim_report(
            {
                "tableTemplates": {
                    "bad": "not a dict",
                    "good": {"columns": {"c": {"tc:constraints": {"type": "xs:string"}}}},
                }
            },
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        assert "bad" not in result.metadata.template_constraints
        assert "good" in result.metadata.template_constraints

    def test_multiple_templates(self) -> None:
        result = parse_tc_metadata(_oim_report(
            {
                "tableTemplates": {
                    "t1": {"columns": {"c": {"tc:constraints": {"type": "xs:integer"}}}},
                    "t2": {"columns": {"c": {"tc:constraints": {"type": "xs:string"}}}},
                    "t3": {"columns": {"c": {}}},
                }
            },
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert result.metadata is not None
        assert "t1" in result.metadata.template_constraints
        assert "t2" in result.metadata.template_constraints
        assert "t3" not in result.metadata.template_constraints


class TestEdgeCases:
    def test_missing_table_templates(self) -> None:
        result = parse_tc_metadata(_oim_report({}, TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints == {}

    def test_empty_table_templates(self) -> None:
        result = parse_tc_metadata(_oim_report({"tableTemplates": {}}, TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.template_constraints == {}


class TestErrorPointers:
    def test_column_constraint_type_error(self) -> None:
        result = parse_tc_metadata(_oim_report(_with_constraint({"type": 123}), TC_MINIMAL_NAMESPACES))
        assert result is not None
        assert not result.is_valid
        assert result.errors[0].json_pointer == "/tableTemplates/t1/columns/col/tc:constraints/type"

    def test_parameter_constraint_error(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:parameters": {"p1": {"type": 999}}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert result.errors[0].json_pointer == "/tableTemplates/t1/tc:parameters/p1/type"

    def test_keys_error(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"unique": "not a list"}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert result.errors[0].json_pointer == "/tableTemplates/t1/tc:keys/unique"

    def test_column_order_error(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:columnOrder": 42}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert result.errors[0].json_pointer == "/tableTemplates/t1/tc:columnOrder"

    def test_table_constraints_error(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:tableConstraints": {"minTables": "not int"}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert result.errors[0].json_pointer == "/tableTemplates/t1/tc:tableConstraints/minTables"


class TestErrorCollection:
    def test_collects_errors_across_templates(self) -> None:
        result = parse_tc_metadata(_oim_report(
            {
                "tableTemplates": {
                    "t1": {"columns": {"c": {"tc:constraints": {"type": 1}}}},
                    "t2": {"columns": {"c": {"tc:constraints": {"type": 2}}}},
                }
            },
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert len(result.errors) == 2
        assert result.metadata is None

    def test_collects_errors_across_unique_key_fields(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"unique": [{"name": 1, "fields": ["id"], "severity": 2}]}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert len(result.errors) == 2

    def test_collects_errors_across_reference_key_fields(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template(
                {"tc:keys": {"reference": [{"name": 1, "fields": ["col"], "referencedKeyName": "pk", "severity": 2}]}}
            ),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert len(result.errors) == 2

    def test_collects_errors_across_table_constraint_fields(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:tableConstraints": {"minTables": "x", "maxTables": "y"}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert len(result.errors) == 2

    def test_reports_all_unknown_properties_in_one_error(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template({"tc:keys": {"unique": [{"name": "k", "fields": ["id"]}], "foo": 1, "bar": 2}}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert len(result.errors) == 1
        assert "foo" in str(result.errors[0])
        assert "bar" in str(result.errors[0])

    def test_collects_errors_across_unique_key_items(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template(
                {
                    "tc:keys": {"unique": [{"fields": ["id"]}, {"fields": ["code"]}]},
                }
            ),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert len(result.errors) == 2

    def test_collects_errors_across_value_constraint_fields(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_constraint({"type": 1, "optional": "not_a_bool"}),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert len(result.errors) == 2

    def test_collects_errors_from_unique_and_reference_keys(self) -> None:
        result = parse_tc_metadata(_oim_report(
            _with_template(
                {
                    "tc:keys": {
                        "unique": [{"fields": ["id"]}],
                        "reference": [{"name": "fk", "fields": ["col"]}],
                    },
                }
            ),
            TC_MINIMAL_NAMESPACES,
        ))
        assert result is not None
        assert not result.is_valid
        assert len(result.errors) == 2
