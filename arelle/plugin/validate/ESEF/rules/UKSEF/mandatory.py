"""
See COPYRIGHT.md for copyright information.

UKSEF mandatory facts validation rules for Companies House.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.ValidateXbrl import ValidateXbrl
from ...Const import AUTHORITY_UKFRC
from ...PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText

_ACCOUNTS_STATUS_DIMENSION = "AccountsStatusDimension"
_SCOPE_ACCOUNTS_DIMENSION = "ScopeAccountsDimension"
_AUDITED_MEMBER = "Audited"
_GROUP_SCOPE_MEMBERS = frozenset({"GroupAccountsOnly", "ConsolidatedGroupCompanyAccounts"})


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_mandatory_facts(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    Companies House mandatory facts: Validates that all required facts
    are present in the filing.
    """
    if val.authority != AUTHORITY_UKFRC or not pluginData.isUkfrsTarget(val.modelXbrl):
        return

    mandatory = pluginData.uksefMandatoryFacts
    if not mandatory:
        return

    present = {fact.qname for fact in val.modelXbrl.factsInInstance if not fact.isNil}
    audited = False
    groupScope = False

    for context in val.modelXbrl.contexts.values():
        for dimQname, dimValue in context.qnameDims.items():
            member = getattr(dimValue, "memberQname", None)
            if member is None:
                continue

            if dimQname.localName == _ACCOUNTS_STATUS_DIMENSION and member.localName == _AUDITED_MEMBER:
                audited = True

            elif dimQname.localName == _SCOPE_ACCOUNTS_DIMENSION and member.localName in _GROUP_SCOPE_MEMBERS:
                groupScope = True

        if audited and groupScope:
            break

    isGroupAudited = audited and groupScope

    missing: list[str] = []
    required = mandatory + (pluginData.uksefGroupAuditedMandatoryFacts if isGroupAudited else ())
    missing.extend(str(qname) for qname in required if qname not in present)

    alternatives = pluginData.uksefAuditorOpinionAlternatives
    if isGroupAudited and alternatives and not any(qname in present for qname in alternatives):
        missing.append(" or ".join(str(qname) for qname in alternatives))

    if missing:
        yield Validation.error(
            codes="ESEF.UK.missingCompaniesHouseMandatoryItem",
            msg=_("The UKSEF report is missing mandatory Companies House items: %(concepts)s"),
            modelObject=val.modelXbrl,
            concepts=", ".join(missing),
        )
