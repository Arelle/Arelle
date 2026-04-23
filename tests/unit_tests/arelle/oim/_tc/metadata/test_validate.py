from __future__ import annotations

from types import MappingProxyType

from arelle.oim._tc.const import (
    TC_NS_DRAFT,
    TC_PREFIX,
    TCME_INVALID_NAMESPACE_PREFIX,
)
from arelle.oim._tc.metadata.common import TCMetadataValidationError
from arelle.oim._tc.metadata.model import TCMetadata
from arelle.oim._tc.metadata.validate import TCMetadataValidator
from arelle.oim.csv.metadata.model import XbrlCsvDocumentInfo, XbrlCsvEffectiveMetadata, XbrlCsvTableTemplate

TC_NAMESPACES = {TC_PREFIX: TC_NS_DRAFT}
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
        assert _validate(TC_NAMESPACES) == []
