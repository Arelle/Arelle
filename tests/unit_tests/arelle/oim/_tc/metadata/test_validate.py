from __future__ import annotations

from typing import Any

from arelle.oim._model import OimReport
from arelle.oim._tc.const import (
    TC_NS_DRAFT,
    TC_PREFIX,
    TCME_INVALID_NAMESPACE_PREFIX,
    TCME_MISPLACED_OR_UNKNOWN_PROPERTY,
)
from arelle.oim._tc.metadata.model import TCMetadata
from arelle.oim._tc.metadata.parser import TCMetadataParseError
from arelle.oim._tc.metadata.validate import TCMetadataValidator

TC_NAMESPACES = {TC_PREFIX: TC_NS_DRAFT}
_EMPTY_TC_METADATA = TCMetadata(template_constraints={})


def _validate(oim: dict[str, Any], namespaces: dict[str, str] | None = None) -> list[TCMetadataParseError]:
    if namespaces is not None:
        oim.setdefault("documentInfo", {})["namespaces"] = namespaces
    return list(TCMetadataValidator(OimReport(oim_object=oim), _EMPTY_TC_METADATA).validate())


class TestUnknownTcProperty:
    def test_unknown_at_root(self) -> None:
        oim: dict[str, Any] = {"tc:unknown": True}
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].code == TCME_MISPLACED_OR_UNKNOWN_PROPERTY
        assert errors[0].json_pointer == "/tc:unknown"

    def test_unknown_in_document_info(self) -> None:
        oim: dict[str, Any] = {"documentInfo": {"tc:unknown": True}}
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].code == TCME_MISPLACED_OR_UNKNOWN_PROPERTY
        assert errors[0].json_pointer == "/documentInfo/tc:unknown"

    def test_unknown_in_table_template(self) -> None:
        oim: dict[str, Any] = {"tableTemplates": {"t1": {"columns": {}, "tc:unknown": True}}}
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/tableTemplates/t1/tc:unknown"

    def test_unknown_in_column(self) -> None:
        oim: dict[str, Any] = {"tableTemplates": {"t1": {"columns": {"c1": {"tc:unknown": True}}}}}
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/tableTemplates/t1/columns/c1/tc:unknown"

    def test_unknown_in_property_group(self) -> None:
        oim: dict[str, Any] = {
            "tableTemplates": {
                "t1": {
                    "columns": {
                        "c1": {
                            "propertyGroups": {
                                "pg1": {"tc:unknown": True},
                            },
                        },
                    },
                },
            },
        }
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/tableTemplates/t1/columns/c1/propertyGroups/pg1/tc:unknown"

    def test_unknown_in_table(self) -> None:
        oim: dict[str, Any] = {"tables": {"t1": {"url": "foo.csv", "tc:unknown": True}}}
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/tables/t1/tc:unknown"

    def test_unknown_in_document_info_final(self) -> None:
        oim: dict[str, Any] = {"documentInfo": {"final": {"tc:unknown": True}}}
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/documentInfo/final/tc:unknown"

    def test_unknown_in_root_dimensions(self) -> None:
        oim: dict[str, Any] = {"dimensions": {"tc:unknown": "value"}}
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/dimensions/tc:unknown"

    def test_unknown_in_template_dimensions(self) -> None:
        oim: dict[str, Any] = {"tableTemplates": {"t1": {"columns": {}, "dimensions": {"tc:unknown": "value"}}}}
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/tableTemplates/t1/dimensions/tc:unknown"

    def test_unknown_in_column_dimensions(self) -> None:
        oim: dict[str, Any] = {"tableTemplates": {"t1": {"columns": {"c1": {"dimensions": {"tc:unknown": "value"}}}}}}
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/tableTemplates/t1/columns/c1/dimensions/tc:unknown"

    def test_unknown_in_table_parameters(self) -> None:
        oim: dict[str, Any] = {"tables": {"t1": {"url": "foo.csv", "parameters": {"tc:unknown": "value"}}}}
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/tables/t1/parameters/tc:unknown"

    def test_unknown_in_property_group_dimensions(self) -> None:
        oim: dict[str, Any] = {
            "tableTemplates": {
                "t1": {
                    "columns": {
                        "c1": {
                            "propertyGroups": {
                                "pg1": {"dimensions": {"tc:unknown": "value"}},
                            },
                        },
                    },
                },
            },
        }
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/tableTemplates/t1/columns/c1/propertyGroups/pg1/dimensions/tc:unknown"


class TestMisplacedTcProperty:
    def test_table_constraints_at_root(self) -> None:
        oim: dict[str, Any] = {"tc:tableConstraints": {}}
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].code == TCME_MISPLACED_OR_UNKNOWN_PROPERTY
        assert errors[0].json_pointer == "/tc:tableConstraints"

    def test_table_constraints_in_document_info(self) -> None:
        oim: dict[str, Any] = {"documentInfo": {"tc:tableConstraints": {}}}
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/documentInfo/tc:tableConstraints"

    def test_constraints_in_table_template(self) -> None:
        oim: dict[str, Any] = {"tableTemplates": {"t1": {"columns": {}, "tc:constraints": {"type": "xs:string"}}}}
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/tableTemplates/t1/tc:constraints"

    def test_table_constraints_in_column(self) -> None:
        oim: dict[str, Any] = {"tableTemplates": {"t1": {"columns": {"c1": {"tc:tableConstraints": {}}}}}}
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/tableTemplates/t1/columns/c1/tc:tableConstraints"

    def test_table_constraints_in_table(self) -> None:
        oim: dict[str, Any] = {"tables": {"t1": {"url": "foo.csv", "tc:tableConstraints": {}}}}
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/tables/t1/tc:tableConstraints"


class TestUnknownInsideTcPropertyValue:
    def test_unknown_inside_tc_constraints(self) -> None:
        oim: dict[str, Any] = {
            "tableTemplates": {"t1": {"columns": {"c1": {"tc:constraints": {"type": "xs:string", "tc:unknown": True}}}}}
        }
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/tableTemplates/t1/columns/c1/tc:constraints/tc:unknown"

    def test_unknown_inside_tc_parameters(self) -> None:
        oim: dict[str, Any] = {
            "tableTemplates": {
                "t1": {"columns": {}, "tc:parameters": {"p1": {"type": "xs:string", "tc:unknown": True}}}
            }
        }
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/tableTemplates/t1/tc:parameters/p1/tc:unknown"

    def test_unknown_inside_tc_keys(self) -> None:
        oim: dict[str, Any] = {
            "tableTemplates": {
                "t1": {
                    "columns": {},
                    "tc:keys": {"unique": [{"name": "k", "fields": ["c"], "tc:unknown": True}]},
                },
            },
        }
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/tableTemplates/t1/tc:keys/unique/0/tc:unknown"

    def test_unknown_inside_tc_table_constraints(self) -> None:
        oim: dict[str, Any] = {"tableTemplates": {"t1": {"columns": {}, "tc:tableConstraints": {"tc:unknown": True}}}}
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 1
        assert errors[0].json_pointer == "/tableTemplates/t1/tc:tableConstraints/tc:unknown"


class TestValidTcProperties:
    def test_constraints_in_column(self) -> None:
        oim: dict[str, Any] = {"tableTemplates": {"t1": {"columns": {"c1": {"tc:constraints": {"type": "xs:string"}}}}}}
        assert _validate(oim, TC_NAMESPACES) == []

    def test_all_template_properties(self) -> None:
        oim = {
            "documentInfo": {
                "documentType": "https://xbrl.org/2021/xbrl-csv",
                "namespaces": {
                    "eg": "http://example.com/oim/tc",
                    "lei": "http://standards.iso.org/iso/17442",
                    "iso4217": "http://www.xbrl.org/2003/iso4217",
                    "xs": "http://www.w3.org/2001/XMLSchema",
                    "tc": "https://xbrl.org/PR/2026-03-18/tc",
                },
                "taxonomy": ["../base/sales.xsd"],
            },
            "dimensions": {"entity": "lei:legalEntityIdentifier"},
            "tableTemplates": {
                "sales": {
                    "columns": {
                        "product_id": {"tc:constraints": {"type": "xs:token", "nillable": False}},
                        "sales": {
                            "dimensions": {
                                "concept": "eg:Sales",
                                "period": "$calendar_month",
                                "unit": "iso4217:EUR",
                                "eg:ProductId": "$product_id",
                            }
                        },
                    },
                    "tc:parameters": {"calendar_month": {"type": "period", "periodType": "month", "timeZone": False}},
                    "tc:keys": {"unique": [{"name": "sales_pk", "fields": ["calendar_month", "product_id"]}]},
                }
            },
            "tables": {
                "salesJan24": {
                    "url": "../base/salesJan24.csv",
                    "template": "sales",
                    "parameters": {"calendar_month": "2024-01"},
                },
                "salesFeb24": {
                    "url": "../base/salesFeb24.csv",
                    "template": "sales",
                    "parameters": {"calendar_month": "2024-02"},
                },
                "salesMar24": {
                    "url": "../base/salesMar24.csv",
                    "template": "sales",
                    "parameters": {"calendar_month": "2024-03"},
                },
            },
        }
        assert _validate(oim, TC_NAMESPACES) == []

    def test_no_errors_inside_valid_tc_constraints(self) -> None:
        oim: dict[str, Any] = {
            "tableTemplates": {"t1": {"columns": {"c1": {"tc:constraints": {"type": "xs:string", "optional": True}}}}}
        }
        assert _validate(oim, TC_NAMESPACES) == []

    def test_no_errors_inside_valid_tc_keys(self) -> None:
        oim: dict[str, Any] = {
            "tableTemplates": {
                "t1": {
                    "columns": {},
                    "tc:keys": {
                        "unique": [{"name": "k", "fields": ["c"], "severity": "warning", "shared": False}],
                        "reference": [{"name": "r", "fields": ["c"], "referencedKeyName": "k"}],
                        "sortKey": "k",
                    },
                },
            },
        }
        assert _validate(oim, TC_NAMESPACES) == []

    def test_no_errors_inside_valid_tc_table_constraints(self) -> None:
        oim: dict[str, Any] = {
            "tableTemplates": {"t1": {"columns": {}, "tc:tableConstraints": {"minTables": 1, "maxTables": 5}}}
        }
        assert _validate(oim, TC_NAMESPACES) == []

    def test_no_errors_inside_valid_tc_parameters(self) -> None:
        oim: dict[str, Any] = {
            "tableTemplates": {"t1": {"columns": {}, "tc:parameters": {"p1": {"type": "xs:string", "optional": True}}}}
        }
        assert _validate(oim, TC_NAMESPACES) == []


class TestNamespacePrefix:
    def test_non_tc_prefix_reports_error(self) -> None:
        oim: dict[str, object] = {}
        errors = _validate(oim, {"custom": TC_NS_DRAFT})
        assert len(errors) == 1
        assert errors[0].code == TCME_INVALID_NAMESPACE_PREFIX

    def test_tc_prefix_no_error(self) -> None:
        oim: dict[str, object] = {}
        assert _validate(oim, TC_NAMESPACES) == []


class TestMultipleErrors:
    def test_reports_all_errors(self) -> None:
        oim: dict[str, Any] = {
            "tc:unknown": True,
            "documentInfo": {"tc:tableConstraints": {}},
            "tables": {"t1": {"url": "foo.csv", "tc:unknown": True}},
        }
        errors = _validate(oim, TC_NAMESPACES)
        assert len(errors) == 3
        codes = {e.code for e in errors}
        assert codes == {TCME_MISPLACED_OR_UNKNOWN_PROPERTY}
