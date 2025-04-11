"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from datetime import date, timedelta
from dateutil import relativedelta
from collections.abc import Iterable
from typing import Any, cast, TYPE_CHECKING

from regex import regex

from arelle import XmlUtil, XbrlConst
from arelle.ModelObject import ModelObject
from arelle.ValidateXbrl import ValidateXbrl
from arelle.XmlValidate import INVALID
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import (
    DISCLOSURE_SYSTEM_INLINE_NT19
)
from ..PluginValidationDataExtension import PluginValidationDataExtension, XBRLI_IDENTIFIER_PATTERN

if TYPE_CHECKING:
    from arelle.ModelXbrl import ModelXbrl
    from arelle.ModelValue import QName

_: TypeGetText


def _getReportingPeriodDateValue(modelXbrl: ModelXbrl, qname: QName) -> date | None:
    facts = modelXbrl.factsByQname.get(qname)
    if facts and len(facts) == 1:
        datetimeValue = XmlUtil.datetimeValue(next(iter(facts)))
        if datetimeValue:
            return datetimeValue.date()
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_INLINE_NT19
    ],
)
def rule_nl_kvk_3_1_1_1(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.1.1.1: xbrli:identifier content to match KVK number format that must consist of 8 consecutive digits;
    first two digits must not be '00'.
    """
    entityIdentifierValues = {context.entityIdentifier for context in val.modelXbrl.contexts.values()}
    for entityId in entityIdentifierValues:
        if not XBRLI_IDENTIFIER_PATTERN.match(entityId):
            yield Validation.error(
                codes='NL.NL-KVK-3.1.1.1',
                msg=_('xbrli:identifier content to match KVK number format that must consist of 8 consecutive digits.'
                      'Additionally the first two digits must not be "00".'),
                modelObject = val.modelXbrl
            )
            return
