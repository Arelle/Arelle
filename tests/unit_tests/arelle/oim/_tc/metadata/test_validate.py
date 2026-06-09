from __future__ import annotations

from types import MappingProxyType

from arelle import XbrlConst
from arelle.oim._tc.const import (
    TC_NS_DRAFT,
    TC_PREFIX,
    TCME_COLUMN_PARAMETER_CONFLICT,
    TCME_INCONSISTENT_COLUMN_ORDER_DEFINITION,
    TCME_INVALID_NAMESPACE_PREFIX,
    TCME_UNKNOWN_TYPE,
)
from arelle.oim._tc.metadata.common import TCMetadataValidationError
from arelle.oim._tc.metadata.model import TCMetadata, TCTemplateConstraints, TCValueConstraint
from arelle.oim._tc.metadata.validate import TCMetadataValidator
from arelle.oim.csv.metadata.model import (
    XbrlCsvColumn,
    XbrlCsvDocumentInfo,
    XbrlCsvEffectiveMetadata,
    XbrlCsvTableTemplate,
)

_TC_NAMESPACES = {TC_PREFIX: TC_NS_DRAFT, "xs": XbrlConst.xsd}
_EMPTY_TC_METADATA = TCMetadata(template_constraints={})


def _build_effective_metadata(
    namespaces: dict[str, str],
    table_templates: dict[str, XbrlCsvTableTemplate] | None = None,
) -> XbrlCsvEffectiveMetadata:
    return XbrlCsvEffectiveMetadata(
        document_info=XbrlCsvDocumentInfo(
            document_type="https://xbrl.org/2021/xbrl-csv",
            namespaces=namespaces,
        ),
        table_templates=table_templates or MappingProxyType({}),
    )


def _validate(namespaces: dict[str, str] | None = None) -> list[TCMetadataValidationError]:
    return list(
        TCMetadataValidator(
            _build_effective_metadata(namespaces or {}),
            _EMPTY_TC_METADATA,
        ).validate()
    )


class TestNamespacePrefix:
    def test_non_tc_prefix_reports_error(self) -> None:
        errors = _validate({"custom": TC_NS_DRAFT})
        assert len(errors) == 1
        assert errors[0].code == TCME_INVALID_NAMESPACE_PREFIX

    def test_tc_prefix_no_error(self) -> None:
        assert _validate(_TC_NAMESPACES) == []


class TestColumnParameterConflict:
    def test_conflict_detected(self) -> None:
        tc_metadata = TCMetadata(
            template_constraints={
                "t1": TCTemplateConstraints(
                    constraints={"col1": TCValueConstraint(type="xs:decimal")},
                    parameters={"col1": TCValueConstraint(type="xs:decimal")},
                ),
            }
        )
        errors = list(TCMetadataValidator(_build_effective_metadata(_TC_NAMESPACES), tc_metadata).validate())
        assert len(errors) == 1
        assert errors[0].code == TCME_COLUMN_PARAMETER_CONFLICT
        assert set(errors[0].json_pointers) == {
            "/tableTemplates/t1/columns/col1",
            "/tableTemplates/t1/tc:parameters/col1",
        }

    def test_no_conflict_different_names(self) -> None:
        tc_metadata = TCMetadata(
            template_constraints={
                "t1": TCTemplateConstraints(
                    constraints={"col1": TCValueConstraint(type="xs:decimal")},
                    parameters={"param1": TCValueConstraint(type="xs:decimal")},
                ),
            }
        )
        errors = list(TCMetadataValidator(_build_effective_metadata(_TC_NAMESPACES), tc_metadata).validate())
        assert errors == []

    def test_no_conflict_only_columns(self) -> None:
        tc_metadata = TCMetadata(
            template_constraints={
                "t1": TCTemplateConstraints(
                    constraints={"col1": TCValueConstraint(type="xs:string")},
                ),
            }
        )
        errors = list(TCMetadataValidator(_build_effective_metadata(_TC_NAMESPACES), tc_metadata).validate())
        assert errors == []

    def test_no_conflict_only_parameters(self) -> None:
        tc_metadata = TCMetadata(
            template_constraints={
                "t1": TCTemplateConstraints(
                    parameters={"param1": TCValueConstraint(type="xs:string")},
                ),
            }
        )
        errors = list(TCMetadataValidator(_build_effective_metadata(_TC_NAMESPACES), tc_metadata).validate())
        assert errors == []

    def test_conflict_in_one_template_not_other(self) -> None:
        tc_metadata = TCMetadata(
            template_constraints={
                "t1": TCTemplateConstraints(
                    constraints={"shared": TCValueConstraint(type="xs:string")},
                    parameters={"shared": TCValueConstraint(type="xs:string")},
                ),
                "t2": TCTemplateConstraints(
                    constraints={"shared": TCValueConstraint(type="xs:string")},
                    parameters={"other": TCValueConstraint(type="xs:string")},
                ),
            }
        )
        errors = list(TCMetadataValidator(_build_effective_metadata(_TC_NAMESPACES), tc_metadata).validate())
        assert len(errors) == 1
        assert set(errors[0].json_pointers) == {
            "/tableTemplates/t1/columns/shared",
            "/tableTemplates/t1/tc:parameters/shared",
        }

    def test_multiple_conflicts_in_one_template(self) -> None:
        tc_metadata = TCMetadata(
            template_constraints={
                "t1": TCTemplateConstraints(
                    constraints={
                        "shared1": TCValueConstraint(type="xs:string"),
                        "shared2": TCValueConstraint(type="xs:string"),
                        "unique1": TCValueConstraint(type="xs:string"),
                    },
                    parameters={
                        "shared1": TCValueConstraint(type="xs:string"),
                        "shared2": TCValueConstraint(type="xs:string"),
                        "unique2": TCValueConstraint(type="xs:string"),
                    },
                ),
            }
        )
        errors = list(TCMetadataValidator(_build_effective_metadata(_TC_NAMESPACES), tc_metadata).validate())
        assert len(errors) == 2
        assert {p for e in errors for p in e.json_pointers} == {
            "/tableTemplates/t1/columns/shared2",
            "/tableTemplates/t1/columns/shared1",
            "/tableTemplates/t1/tc:parameters/shared1",
            "/tableTemplates/t1/tc:parameters/shared2",
        }

    def test_conflict_in_multiple_templates(self) -> None:
        tc_metadata = TCMetadata(
            template_constraints={
                "t1": TCTemplateConstraints(
                    constraints={"shared": TCValueConstraint(type="xs:string")},
                    parameters={"shared": TCValueConstraint(type="xs:string")},
                ),
                "t2": TCTemplateConstraints(
                    constraints={"shared": TCValueConstraint(type="xs:string")},
                    parameters={"shared": TCValueConstraint(type="xs:string")},
                ),
            }
        )
        errors = list(TCMetadataValidator(_build_effective_metadata(_TC_NAMESPACES), tc_metadata).validate())
        assert len(errors) == 2
        assert {p for e in errors for p in e.json_pointers} == {
            "/tableTemplates/t1/columns/shared",
            "/tableTemplates/t2/columns/shared",
            "/tableTemplates/t1/tc:parameters/shared",
            "/tableTemplates/t2/tc:parameters/shared",
        }


class TestColumnOrderDefinition:
    def test_no_column_order_no_error(self) -> None:
        tc_metadata = TCMetadata(
            template_constraints={
                "t1": TCTemplateConstraints(
                    constraints={"col": TCValueConstraint(type="xs:string")},
                )
            }
        )
        errors = list(TCMetadataValidator(_build_effective_metadata(_TC_NAMESPACES), tc_metadata).validate())
        assert errors == []

    def test_all_constrained_columns_present(self) -> None:
        tc_metadata = TCMetadata(
            template_constraints={
                "t1": TCTemplateConstraints(
                    constraints={"col": TCValueConstraint(type="xs:string")},
                    column_order=("col",),
                )
            }
        )
        csv_template = XbrlCsvTableTemplate(columns={"col": XbrlCsvColumn()})
        meta = _build_effective_metadata(_TC_NAMESPACES, {"t1": csv_template})
        errors = list(TCMetadataValidator(meta, tc_metadata).validate())
        assert errors == []

    def test_constrained_column_missing_from_column_order(self) -> None:
        tc_metadata = TCMetadata(
            template_constraints={
                "t1": TCTemplateConstraints(
                    constraints={
                        "col1": TCValueConstraint(type="xs:string"),
                        "col2": TCValueConstraint(type="xs:string"),
                    },
                    column_order=("col1",),
                )
            }
        )
        csv_template = XbrlCsvTableTemplate(columns={"col1": XbrlCsvColumn(), "col2": XbrlCsvColumn()})
        meta = _build_effective_metadata(_TC_NAMESPACES, {"t1": csv_template})
        errors = list(TCMetadataValidator(meta, tc_metadata).validate())
        assert len(errors) == 1
        assert errors[0].code == TCME_INCONSISTENT_COLUMN_ORDER_DEFINITION
        assert errors[0].json_pointers == [
            "/tableTemplates/t1/tc:columnOrder",
            "/tableTemplates/t1/columns/col2",
        ]

    def test_unknown_column_in_column_order(self) -> None:
        tc_metadata = TCMetadata(
            template_constraints={
                "t1": TCTemplateConstraints(
                    constraints={"col1": TCValueConstraint(type="xs:string")},
                    column_order=("col1", "unknown"),
                )
            }
        )
        csv_template = XbrlCsvTableTemplate(columns={"col1": XbrlCsvColumn()})
        meta = _build_effective_metadata(_TC_NAMESPACES, {"t1": csv_template})
        errors = list(TCMetadataValidator(meta, tc_metadata).validate())
        assert len(errors) == 1
        assert errors[0].code == TCME_INCONSISTENT_COLUMN_ORDER_DEFINITION
        assert errors[0].json_pointers == [
            "/tableTemplates/t1/tc:columnOrder",
            "/tableTemplates/t1/tc:columnOrder/1",
        ]

    def test_no_csv_template_skips_unknown_check(self) -> None:
        # If no CSV template is available for this id, only check constrained columns.
        tc_metadata = TCMetadata(
            template_constraints={
                "t1": TCTemplateConstraints(
                    constraints={"col1": TCValueConstraint(type="xs:string")},
                    column_order=("col1", "anything"),
                )
            }
        )
        errors = list(TCMetadataValidator(_build_effective_metadata(_TC_NAMESPACES), tc_metadata).validate())
        assert errors == []


class TestValueConstraintIntegration:
    def test_column_constraint_error_path(self) -> None:
        tc_metadata = TCMetadata(
            template_constraints={
                "t1": TCTemplateConstraints(
                    constraints={"col1": TCValueConstraint(type="xs:bogus")},
                ),
            }
        )
        errors = list(TCMetadataValidator(_build_effective_metadata(_TC_NAMESPACES), tc_metadata).validate())
        assert len(errors) == 1
        assert errors[0].code == TCME_UNKNOWN_TYPE
        assert errors[0].json_pointers == ["/tableTemplates/t1/columns/col1/tc:constraints/type"]

    def test_parameter_constraint_error_path(self) -> None:
        tc_metadata = TCMetadata(
            template_constraints={
                "t1": TCTemplateConstraints(
                    parameters={"p1": TCValueConstraint(type="xs:bogus")},
                ),
            }
        )
        errors = list(TCMetadataValidator(_build_effective_metadata(_TC_NAMESPACES), tc_metadata).validate())
        assert len(errors) == 1
        assert errors[0].code == TCME_UNKNOWN_TYPE
        assert errors[0].json_pointers == ["/tableTemplates/t1/tc:parameters/p1/type"]
