from collections.abc import Iterable
from typing import Any

from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.PluginData import PluginData
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=["House rules"],
)
def ruleMandatoryConcept(
    pluginData: PluginData,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    mandatoryConcept = "AuditReport"
    if mandatoryConcept not in val.modelXbrl.factsByLocalName:
        yield Validation.error(
            codes="house.01.01",
            msg=f"{mandatoryConcept} must be reported.",
            modelObject=val.modelXbrl,
        )
