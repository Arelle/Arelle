"""
See COPYRIGHT.md for copyright information.

UKSEF mandatory facts validation rules for Companies House.
"""
from __future__ import annotations

import re
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

# FRC taxonomy namespaces carry the release date, e.g. http://xbrl.frc.org.uk/cd/2025-01-01/business.
# Match on the stable part so earlier supported releases (2023, 2024) are handled the same way.
_NS_PATTERN = re.compile(r"^http://xbrl\.frc\.org\.uk/(?:cd|fr|reports)/\d{4}-\d{2}-\d{2}/(\w+)$")

# (prefix, local name) of mandatory concepts and the minimum number of facts required.
_MANDATORY_ALL: tuple[tuple[str, str, int], ...] = (
    ("bus", "UKCompaniesHouseRegisteredNumber", 1),
    ("bus", "BalanceSheetDate", 1),
    ("bus", "StartDateForPeriodCoveredByReport", 1),
    ("bus", "EndDateForPeriodCoveredByReport", 1),
    ("bus", "EntityCurrentLegalOrRegisteredName", 1),
    ("core", "DateAuthorisationFinancialStatementsForIssue", 1),
    ("core", "DirectorSigningFinancialStatements", 1),
    ("bus", "EntityDormantTruefalse", 1),
    ("bus", "EntityTradingStatus", 1),
    ("bus", "AccountingStandardsApplied", 1),
    ("bus", "AccountsStatusAuditedOrUnaudited", 1),
    ("bus", "AccountsType", 1),
    ("core", "AverageNumberEmployeesDuringPeriod", 1),
    ("core", "ProfitLoss", 1),
)
_MANDATORY_GROUP_AUDITED: tuple[tuple[str, str, int], ...] = (
    ("aurep", "DateAuditorsReport", 1),
    ("bus", "NameEntityAuditors", 1),
    ("aurep", "NameSeniorStatutoryAuditor", 1),
    ("direp", "DateSigningDirectorsReport", 1),
    ("direp", "DirectorSigningDirectorsReport", 1),
)
# Item 16: at least one of these must be present (in addition to bus:NameEntityAuditors).
_AUDITOR_OPINION_ALTERNATIVES = (("aurep", "OpinionAuditorsOnEntity"), ("aurep", "NamedIndividualAuditor"))

_ACCOUNTS_STATUS_DIMENSION = "AccountsStatusDimension"
_SCOPE_ACCOUNTS_DIMENSION = "ScopeAccountsDimension"
_AUDITED_MEMBER = "Audited"
_GROUP_SCOPE_MEMBERS = frozenset({"GroupAccountsOnly", "ConsolidatedGroupCompanyAccounts"})


def _key(qname: Any) -> tuple[str, str] | None:
    """(namespace prefix, local name) for an FRC taxonomy QName, otherwise None."""
    match = _NS_PATTERN.match(qname.namespaceURI or "")
    return (match.group(1), qname.localName) if match else None


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

    counts: dict[tuple[str, str], int] = {}
    audited = False
    groupScope = False
    for fact in val.modelXbrl.factsInInstance:
        key = _key(fact.qname)
        if key is not None:
            counts[key] = counts.get(key, 0) + 1

        context = fact.context
        if context is None:
            continue

        for dimQname, dimValue in context.qnameDims.items():
            member = getattr(dimValue, "memberQname", None)
            if member is None:
                continue

            if dimQname.localName == _ACCOUNTS_STATUS_DIMENSION and member.localName == _AUDITED_MEMBER:
                audited = True

            elif dimQname.localName == _SCOPE_ACCOUNTS_DIMENSION and member.localName in _GROUP_SCOPE_MEMBERS:
                groupScope = True

    isGroupAudited = audited and groupScope

    missing: list[str] = []
    required = _MANDATORY_ALL + (_MANDATORY_GROUP_AUDITED if isGroupAudited else ())
    for prefix, localName, minimum in required:
        if counts.get((prefix, localName), 0) < minimum:
            missing.append(f"{prefix}:{localName}")

    if isGroupAudited and not any(counts.get(alt, 0) for alt in _AUDITOR_OPINION_ALTERNATIVES):
        missing.append(" or ".join(f"{p}:{n}" for p, n in _AUDITOR_OPINION_ALTERNATIVES))

    if missing:
        yield Validation.error(
            codes="ESEF.UK.missingCompaniesHouseMandatoryItem",
            msg=_("The UKSEF report is missing mandatory Companies House items: %(concepts)s"),
            modelObject=val.modelXbrl,
            concepts=", ".join(missing),
        )
