from __future__ import annotations

from typing import Any

from arelle.oim._model import OimReport
from arelle.oim._tc.const import (
    TC_NS_DRAFT,
    TC_PREFIX,
    TCME_INVALID_NAMESPACE_PREFIX,
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


class TestNamespacePrefix:
    def test_non_tc_prefix_reports_error(self) -> None:
        oim: dict[str, object] = {}
        errors = _validate(oim, {"custom": TC_NS_DRAFT})
        assert len(errors) == 1
        assert errors[0].code == TCME_INVALID_NAMESPACE_PREFIX

    def test_tc_prefix_no_error(self) -> None:
        oim: dict[str, object] = {}
        assert _validate(oim, TC_NAMESPACES) == []
