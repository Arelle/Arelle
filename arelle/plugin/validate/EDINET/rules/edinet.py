"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any, Iterable

from arelle import XbrlConst, ValidateDuplicateFacts
from arelle.LinkbaseType import LinkbaseType
from arelle.ValidateDuplicateFacts import DuplicateType
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..Constants import AccountingStandard
from ..DisclosureSystems import (DISCLOSURE_SYSTEM_EDINET)
from ..PluginValidationDataExtension import PluginValidationDataExtension
from ..Statement import StatementType

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_balances(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8057W: On the consolidated balance sheet, the sum of all liabilities and
    equity must equal the sum of all assets.
    EDINET.EC8058W: On the nonconsolidated balance sheet, the sum of all liabilities and
    equity must equal the sum of all assets.
    EDINET.EC8062W: On the consolidated statement of financial position, the sum of all liabilities and
    equity must equal the sum of all assets.
    EDINET.EC8064W: On the nonconsolidated statement of financial position, the sum of all liabilities and
    equity must equal the sum of all assets.
    """
    for statementInstance in pluginData.getStatementInstances(val.modelXbrl):
        statement = statementInstance.statement
        for balanceSheet in statementInstance.balanceSheets:
            if balanceSheet.assetsTotal == balanceSheet.liabilitiesAndEquityTotal:
                continue
            code = None
            if statement.statementType == StatementType.BALANCE_SHEET:
                if statement.isConsolidated:
                    code = "EDINET.EC8057W"
                else:
                    code = "EDINET.EC8058W"
            elif statement.statementType == StatementType.STATEMENT_OF_FINANCIAL_POSITION:
                if statement.isConsolidated:
                    code = "EDINET.EC8062W"
                else:
                    code = "EDINET.EC8064W"
            assert code is not None, "Unknown balance sheet encountered."
            yield Validation.warning(
                codes=code,
                msg=_("The %(consolidated)s %(balanceSheet)s is not balanced. "
                      "The sum of all liabilities and equity must equal the sum of all assets. "
                      "Please correct the debit (%(liabilitiesAndEquitySum)s) and credit (%(assetSum)s) "
                      "values so that they match "
                      "<roleUri=%(roleUri)s> <contextID=%(contextId)s> <unitID=%(unitId)s>."),
                consolidated=_("consolidated") if statement.isConsolidated
                else _("nonconsolidated"),
                balanceSheet=_("balance sheet") if statement.statementType == StatementType.BALANCE_SHEET
                else _("statement of financial position"),
                liabilitiesAndEquitySum=f"{balanceSheet.liabilitiesAndEquityTotal:,}",
                assetSum=f"{balanceSheet.assetsTotal:,}",
                roleUri=statement.roleUri,
                contextId=balanceSheet.contextId,
                unitId=balanceSheet.unitId,
                modelObject=balanceSheet.facts,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC1057E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC1057E: The submission date on the cover page has not been filled in.
    Ensure that there is a nonnil value disclosed for FilingDateCoverPage
    Note: This rule is only applicable to the public documents.
    """
    dei = pluginData.getDocumentTypes(val.modelXbrl)
    if len(dei) > 0:
        if not (pluginData.hasValidNonNilFact(val.modelXbrl, pluginData.jpcrpEsrFilingDateCoverPageQn)
                or pluginData.hasValidNonNilFact(val.modelXbrl, pluginData.jpcrpFilingDateCoverPageQn)
                or pluginData.hasValidNonNilFact(val.modelXbrl, pluginData.jpspsFilingDateCoverPageQn)):
            yield Validation.error(
                codes='EDINET.EC1057E',
                msg=_("The [Submission Date] on the cover page has not been filled in."),
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC5002E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5002E: A unit other than number of shares (xbrli:shares) has been set for the
    Number of Shares (xbrli:sharesItemType) item '{xxx}yyy'.
    Please check the units and enter the correct information.

    Similar to "xbrl.4.8.2:sharesFactUnit-notSharesMeasure" and "xbrl.4.8.2:sharesFactUnit-notSingleMeasure"
    TODO: Consolidate this rule with the above two rules if possible.
    """
    errorFacts = []
    for fact in val.modelXbrl.facts:
        concept = fact.concept
        if concept is None or not concept.isShares:
            continue
        unit = fact.unit
        measures = unit.measures
        if (
                not measures or
                len(measures[0]) != 1 or
                len(measures[1]) != 0 or
                measures[0][0] != XbrlConst.qnXbrliShares
        ):
            errorFacts.append(fact)
    for fact in errorFacts:
        yield Validation.error(
            codes='EDINET.EC5002E',
            msg=_("A unit other than number of shares (xbrli:shares) has been set for "
                  "the Number of Shares (xbrli:sharesItemType) item '%(qname)s'. "
                  "Please check the units and enter the correct information."),
            qname=fact.qname.clarkNotation,
            modelObject=fact,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC5613W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5613W: Please set the DEI "Accounting Standard" value to one
    of the following: "Japan GAAP", "US GAAP", "IFRS".
    """
    validAccountingStandards = {s.value for s in AccountingStandard}
    errorFacts = [
        fact for fact in pluginData.iterValidNonNilFacts(val.modelXbrl, pluginData.accountingStandardsDeiQn)
        if fact.xValue not in validAccountingStandards
    ]
    if len(errorFacts) > 0:
        yield Validation.warning(
            codes='EDINET.EC5613W',
            msg=_("Please set the DEI \"Accounting Standard\" value to one "
                  "of the following: %(values)s."),
            values=', '.join(f'"{s.value}"' for s in AccountingStandard),
            modelObject=errorFacts,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8024E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8024E: Instance values of the same element, context, and unit may not
    have different values or different decimals attributes.
    Correct the element with the relevant context ID. For elements in an inline XBRL file that have
    duplicate elements, context IDs, and unit IDs, set the same values for the value and
    decimals attribute.
    """
    duplicateFactSets = ValidateDuplicateFacts.getDuplicateFactSetsWithType(val.modelXbrl.facts, DuplicateType.INCOMPLETE)
    for duplicateFactSet in duplicateFactSets:
        fact = duplicateFactSet.facts[0]
        yield Validation.error(
            codes='EDINET.EC8024E',
            msg=_("Instance values of the same element, context, and unit may not "
                  "have different values or different decimals attributes. <element=%(concept)s> "
                  "<contextID=%(context)s> <unit=%(unit)s>. Correct the element with the relevant "
                  "context ID. For elements in an inline XBRL file that have duplicate "
                  "elements, context IDs, and unit IDs, set the same values for the value and "
                  "decimals attribute."),
            concept=fact.qname,
            context=fact.contextID,
            unit=fact.unitID,
            modelObject=duplicateFactSet.facts,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8027W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8027W: For presentation links and definition links, there must be
    only one root element.
    File name: xxx <Extended link role = yyy>
    Please correct the extended link role of the relevant file. Please set only one
    root element of the extended link role in the presentation link and definition link.
    """
    linkbaseTypes = (LinkbaseType.PRESENTATION, LinkbaseType.DEFINITION)
    roleTypes = [
        roleType
        for roleTypes in val.modelXbrl.roleTypes.values()
        for roleType in roleTypes
    ]
    for roleType in roleTypes:
        for linkbaseType in linkbaseTypes:
            if linkbaseType.getLinkQn() not in roleType.usedOns:
                continue
            arcroles = linkbaseType.getArcroles()
            relSet = val.modelXbrl.relationshipSet(tuple(arcroles), roleType.roleURI)
            relSetFrom = relSet.fromModelObjects()
            rootConcepts = relSet.rootConcepts
            if len(rootConcepts) < 2:
                continue
            rels = [
                rel
                for rootConcept in rootConcepts
                for rel in relSetFrom[rootConcept]
            ]
            yield Validation.warning(
                codes='EDINET.EC8027W',
                msg=_("For presentation links and definition links, there must be only one root element. "
                      "File name: %(filename)s <Extended link role = %(roleUri)s> "
                      "Please correct the extended link role of the relevant file. Please set only one "
                      "root element of the extended link role in the presentation link and definition link."),
                filename=rels[0].modelDocument.basename,
                roleUri=roleType.roleURI,
                modelObject=rels,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8075W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8075W: The percentage of female executives has not been tagged in detail. Ensure that there is
    a nonnil value disclosed for jpcrp_cor:RatioOfFemaleDirectorsAndOtherOfficers.
    """
    if pluginData.isCorporateForm(val.modelXbrl):
        if not pluginData.hasValidNonNilFact(val.modelXbrl, pluginData.ratioOfFemaleDirectorsAndOtherOfficersQn):
            yield Validation.warning(
                codes='EDINET.EC8075W',
                msg=_("The percentage of female executives has not been tagged in detail."),
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8076W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8076W: "Issued Shares, Total Number of Shares, etc. [Text Block]" (IssuedSharesTotalNumberOfSharesEtcTextBlock) is not tagged.
    Applies to forms 3 and 4.
    """
    if pluginData.isStockForm(val.modelXbrl) and pluginData.isCorporateReport(val.modelXbrl):
        if not pluginData.hasValidNonNilFact(val.modelXbrl, pluginData.issuedSharesTotalNumberOfSharesEtcQn):
            yield Validation.warning(
                codes='EDINET.EC8076W',
                msg=_('"Issued Shares, Total Number of Shares, etc. [Text Block]" (IssuedSharesTotalNumberOfSharesEtcTextBlock) is not tagged.'),
            )
