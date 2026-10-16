"""
See COPYRIGHT.md for copyright information.

UKSEF mandatory facts validation rules for Companies House.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from arelle.ModelValue import QName
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.ValidateXbrl import ValidateXbrl
from ...Const import AUTHORITY_UKFRC
from ...PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText

# FRC taxonomy namespaces carry the release date, e.g. http://xbrl.frc.org.uk/cd/2025-01-01/business.
# The final path segment ("business", "core", "aurep", "direp") identifies the taxonomy independent of release.
_NS_PATTERN = re.compile(r"^http://xbrl\.frc\.org\.uk/(?:cd|fr|reports)/\d{4}-\d{2}-\d{2}/(\w+)$")

# Concepts are identified by (taxonomy namespace, local name), never by prefix, since prefixes are not fixed.
# (namespace, local name) of the mandatory concepts; each must have at least one non-nil fact.
_MANDATORY_ALL: tuple[tuple[str, str], ...] = (
    ("business", "UKCompaniesHouseRegisteredNumber"),
    ("business", "BalanceSheetDate"),
    ("business", "StartDateForPeriodCoveredByReport"),
    ("business", "EndDateForPeriodCoveredByReport"),
    ("business", "EntityCurrentLegalOrRegisteredName"),
    ("core", "DateAuthorisationFinancialStatementsForIssue"),
    ("core", "DirectorSigningFinancialStatements"),
    ("business", "EntityDormantTruefalse"),
    ("business", "EntityTradingStatus"),
    ("business", "AccountingStandardsApplied"),
    ("business", "AccountsStatusAuditedOrUnaudited"),
    ("business", "AccountsType"),
    ("core", "AverageNumberEmployeesDuringPeriod"),
    ("core", "ProfitLoss"),
)
_MANDATORY_GROUP_AUDITED: tuple[tuple[str, str], ...] = (
    ("aurep", "DateAuditorsReport"),
    ("business", "NameEntityAuditors"),
    ("aurep", "NameSeniorStatutoryAuditor"),
    ("direp", "DateSigningDirectorsReport"),
    ("direp", "DirectorSigningDirectorsReport"),
)
# Item 16: at least one of these must be present (in addition to bus:NameEntityAuditors).
_AUDITOR_OPINION_ALTERNATIVES = (("aurep", "OpinionAuditorsOnEntity"), ("aurep", "NamedIndividualAuditor"))

# Conventional prefixes, used only to render concept names in messages.
_DISPLAY_PREFIX = {"business": "bus", "core": "core", "aurep": "aurep", "direp": "direp"}

_ACCOUNTS_STATUS_DIMENSION = "AccountsStatusDimension"
_SCOPE_ACCOUNTS_DIMENSION = "ScopeAccountsDimension"
_AUDITED_MEMBER = "Audited"
_GROUP_SCOPE_MEMBERS = frozenset({"GroupAccountsOnly", "ConsolidatedGroupCompanyAccounts"})


def _key(qname: QName) -> tuple[str, str] | None:
    """(taxonomy namespace, local name) for an FRC taxonomy QName, otherwise None."""
    match = _NS_PATTERN.match(qname.namespaceURI or "")
    return (match.group(1), qname.localName) if match else None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_missingCompaniesHouseMandatoryItem(
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

    present: set[tuple[str, str]] = set()
    audited = False
    groupScope = False
    for fact in val.modelXbrl.factsInInstance:
        if fact.isNil:
            continue

        key = _key(fact.qname)
        if key is not None:
            present.add(key)

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
    required = _MANDATORY_ALL + (_MANDATORY_GROUP_AUDITED if isGroupAudited else ())
    for namespace, localName in required:
        if (namespace, localName) not in present:
            missing.append(f"{_DISPLAY_PREFIX[namespace]}:{localName}")

    if isGroupAudited and not present.intersection(_AUDITOR_OPINION_ALTERNATIVES):
        missing.append(" or ".join(f"{_DISPLAY_PREFIX[ns]}:{n}" for ns, n in _AUDITOR_OPINION_ALTERNATIVES))

    if missing:
        yield Validation.error(
            codes="ESEF.UK.missingCompaniesHouseMandatoryItem",
            msg=_("The UKSEF report is missing mandatory Companies House items: %(concepts)s"),
            modelObject=val.modelXbrl,
            concepts=", ".join(missing),
        )
