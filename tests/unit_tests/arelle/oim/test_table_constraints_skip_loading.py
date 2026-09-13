from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arelle.api.Session import Session
from arelle.ModelXbrl import ModelXbrl
from arelle.RuntimeOptions import RuntimeOptions

_TAXONOMY = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           xmlns:xbrli="http://www.xbrl.org/2003/instance"
           xmlns:eg="http://example.com/eg"
           targetNamespace="http://example.com/eg"
           elementFormDefault="qualified">
  <xs:import namespace="http://www.xbrl.org/2003/instance"
             schemaLocation="http://www.xbrl.org/2003/xbrl-instance-2003-12-31.xsd"/>
  <xs:element name="Item" id="eg_Item" type="xbrli:stringItemType"
              substitutionGroup="xbrli:item" xbrli:periodType="duration" nillable="true"/>
</xs:schema>
"""

_CSV = "id,value\n1,ten\n"


def _csv_metadata(constraint_type: str | None) -> dict[str, Any]:
    id_column: dict[str, Any] = {}
    namespaces = {
        "eg": "http://example.com/eg",
        "id": "http://example.com/id",
        "xs": "http://www.w3.org/2001/XMLSchema",
    }
    if constraint_type is not None:
        id_column["tc:constraints"] = {"type": constraint_type}
        namespaces["tc"] = "https://xbrl.org/2026/tc"
    return {
        "documentInfo": {
            "documentType": "https://xbrl.org/2021/xbrl-csv",
            "namespaces": namespaces,
            "taxonomy": ["taxonomy.xsd"],
        },
        "dimensions": {
            "entity": "id:1",
            "period": "2024-01-01..2024-12-31",
        },
        "tableTemplates": {
            "t": {
                "columns": {
                    "id": id_column,
                    "value": {"dimensions": {"concept": "eg:Item", "eg:Id": "$id"}},
                },
            },
        },
        "tables": {"t": {"url": "data.csv"}},
    }


_JSON_METADATA = {
    "documentInfo": {
        "documentType": "https://xbrl.org/2021/xbrl-json",
        "namespaces": {"eg": "http://example.com/eg"},
        "taxonomy": ["taxonomy.xsd"],
    },
    "facts": {},
}


def _run(tmp_path: Path, metadata: dict[str, Any], table_constraints_skip_loading: bool) -> ModelXbrl:
    (tmp_path / "taxonomy.xsd").write_text(_TAXONOMY, encoding="utf-8")
    (tmp_path / "data.csv").write_text(_CSV, encoding="utf-8")
    metadata_path = tmp_path / "report.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with Session() as session:
        session.run(
            RuntimeOptions(
                entrypointFile=str(metadata_path),
                internetConnectivity="offline",
                keepOpen=True,
                logFormat="[%(messageCode)s] %(message)s",
                validate=True,
                validateTableConstraintsSkipLoading=table_constraints_skip_loading,
            )
        )
        (model,) = session.get_models()
        return model


def test_normal_validation_runs_table_constraints_validation(tmp_path: Path) -> None:
    model = _run(tmp_path, _csv_metadata("xs:integerish"), table_constraints_skip_loading=False)
    assert not model.tableConstraintsSkipLoading
    assert "tcme:unknownType" in model.errors
    assert len(model.facts) == 1


def test_table_constraints_skip_loading_skips_taxonomy_and_facts(tmp_path: Path) -> None:
    model = _run(tmp_path, _csv_metadata("xs:integerish"), table_constraints_skip_loading=True)
    assert model.tableConstraintsSkipLoading
    assert "tcme:unknownType" in model.errors
    assert len(model.facts) == 0
    assert not any(doc.uri.endswith("taxonomy.xsd") for doc in model.urlDocs.values())


def test_table_constraints_skip_loading_valid_report_has_no_errors(tmp_path: Path) -> None:
    model = _run(tmp_path, _csv_metadata("xs:integer"), table_constraints_skip_loading=True)
    assert model.errors == []


@pytest.mark.parametrize(
    "metadata, expected_error",
    [
        (_csv_metadata(None), "arelle:noTableConstraints"),
        (_JSON_METADATA, "arelle:tableConstraintsSkipLoadingRequiresXbrlCsv"),
    ],
)
def test_table_constraints_skip_loading_rejects_unsuitable_reports(
    tmp_path: Path, metadata: dict[str, Any], expected_error: str
) -> None:
    model = _run(tmp_path, metadata, table_constraints_skip_loading=True)
    assert expected_error in model.errors
    assert model.modelDocument is None
