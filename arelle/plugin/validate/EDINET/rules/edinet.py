"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any, Iterable

import regex

from arelle import XbrlConst, ValidateDuplicateFacts
from arelle.LinkbaseType import LinkbaseType
from arelle.ModelValue import QName
from arelle.ValidateDuplicateFacts import DuplicateType
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..Constants import AccountingStandard
from ..DeiRequirements import DeiItemStatus
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
            if balanceSheet.creditSum == balanceSheet.debitSum:
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
                      "Please correct the debit (%(debitSum)s) and credit (%(creditSum)s) "
                      "values so that they match "
                      "<roleUri=%(roleUri)s> <contextID=%(contextId)s> <unitID=%(unitId)s>."),
                consolidated=_("consolidated") if statement.isConsolidated
                else _("nonconsolidated"),
                balanceSheet=_("balance sheet") if statement.statementType == StatementType.BALANCE_SHEET
                else _("statement of financial position"),
                debitSum=f"{balanceSheet.debitSum:,}",
                creditSum=f"{balanceSheet.creditSum:,}",
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
    facts = [
        fact
        for qname in (
            pluginData.jpcrpEsrFilingDateCoverPageQn,
            pluginData.jpcrpFilingDateCoverPageQn,
            pluginData.jpspsFilingDateCoverPageQn
        )
        for fact in pluginData.iterValidNonNilFacts(val.modelXbrl, qname)
    ]
    for modelDocument in pluginData.iterCoverPages(val.modelXbrl):
        if any(fact.modelDocument == modelDocument for fact in facts):
            continue
        if not (pluginData.hasValidNonNilFact(val.modelXbrl, pluginData.jpcrpEsrFilingDateCoverPageQn)
                or pluginData.hasValidNonNilFact(val.modelXbrl, pluginData.jpcrpFilingDateCoverPageQn)
                or pluginData.hasValidNonNilFact(val.modelXbrl, pluginData.jpspsFilingDateCoverPageQn)):
            yield Validation.error(
                codes='EDINET.EC1057E',
                msg=_("There is no submission date ('【提出日】') on the cover page. "
                      "File name: '%(file)s'. "
                      "Please add '【提出日】' to the relevant file."),
                file=modelDocument.basename,
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
def rule_EC5602R(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5602R: DEI value must match corresponding cover page value.

    Applies to FilerNameInJapaneseDEI, FilerNameInEnglishDEI, FundNameInJapaneseDEI.
    """
    errors = []
    def _collectMismatchedValues(deiQName: QName, coverPageQnames: list[QName]) -> None:
        deiFact = next((
            fact
            for fact in pluginData.iterValidNonNilFacts(val.modelXbrl, deiQName)
        ), None)
        if deiFact is None or deiFact.xValue is None:
            return
        deiValue = regex.sub(r'\s+', ' ', str(deiFact.xValue)).strip()
        for coverPageQname in coverPageQnames:
            for coverPageFact in pluginData.iterValidNonNilFacts(val.modelXbrl, coverPageQname):
                factValue = regex.sub(r'\s+', ' ', str(coverPageFact.xValue)).strip()
                if not factValue.startswith(deiValue):
                    errors.append((deiFact, coverPageFact))

    _collectMismatchedValues(
        pluginData.qname('jpdei_cor', 'FilerNameInJapaneseDEI'),
        [
            #【発行者名】
            pluginData.qname('jpsps-esr_cor', 'IssuerNameCoverPage'),
            pluginData.qname('jpsps-sbr_cor', 'IssuerNameCoverPage'),
            pluginData.qname('jpsps_cor', 'IssuerNameCoverPage'),
            #【会社名】
            pluginData.qname('jpcrp-esr_cor', 'CompanyNameCoverPage'),
            pluginData.qname('jpcrp-sbr_cor', 'CompanyNameCoverPage'),
            pluginData.qname('jpcrp_cor', 'CompanyNameCoverPage'),
            pluginData.qname('jpctl_cor', 'CompanyNameCoverPage'),
            #【氏名又は名称】
            pluginData.qname('jplvh_cor', 'NameCoverPage'),
            #【届出者の名称】
            pluginData.qname('jptoi_cor', 'FullNameOrNameOfFilerOfNotificationCoverPage'),
            #【届出者の氏名又は名称】
            pluginData.qname('jptoo-ton_cor', 'FullNameOrNameOfFilerOfNotificationCoverPage'),
            pluginData.qname('jptoo-wto_cor', 'FullNameOrNameOfFilerOfNotificationCoverPage'),
            #【報告者の名称】
            pluginData.qname('jptoi_cor', 'NameOfFilerCoverPage'),
            pluginData.qname('jptoo-pst_cor', 'NameOfFilerCoverPage'),
            #【報告者の氏名又は名称】
            pluginData.qname('jptoo-toa_cor', 'FullNameOrNameOfFilerCoverPage'),
            pluginData.qname('jptoo-tor_cor', 'FullNameOrNameOfFilerCoverPage'),
        ]
    )

    _collectMismatchedValues(
        pluginData.qname('jpdei_cor', 'FilerNameInEnglishDEI'),
        [
            #【英訳名】
            pluginData.qname('jpcrp-esr_cor', 'CompanyNameInEnglishCoverPage'),
            pluginData.qname('jpcrp-sbr_cor', 'CompanyNameInEnglishCoverPage'),
            pluginData.qname('jpcrp_cor', 'CompanyNameInEnglishCoverPage'),
            pluginData.qname('jpctl_cor', 'CompanyNameInEnglishCoverPage'),
        ]
    )

    _collectMismatchedValues(
        pluginData.qname('jpdei_cor', 'FundNameInJapaneseDEI'),
        [
            #【ファンド名】
            pluginData.qname('jpsps-esr_cor', 'FundNameCoverPage'),
            pluginData.qname('jpsps_cor', 'FundNameCoverPage'),
            #【届出の対象とした募集（売出）内国投資信託受益証券に係るファンドの名称】
            pluginData.qname('jpsps_cor', 'NameOfFundRelatedToDomesticInvestmentTrustBeneficiaryCertificateToRegisterForOfferingOrDistributionCoverPageTextBlock'),
            #【届出の対象とした募集（売出）内国投資証券に係る投資法人の名称】
            pluginData.qname('jpsps_cor', 'NameOfInvestmentCorporationRelatedToDomesticInvestmentSecuritiesToRegisterForOfferingOrDistributionCoverPage'),
        ]
    )

    for deiFact, coverPageFact in errors:
        yield Validation.warning(
            codes='EDINET.EC5602R',
            msg=_("The DEI information \"%(deiQname)s\" (%(deiValue)s) does not match "
                  "\"%(coverPageQname)s\" (%(coverPageValue)s) . "
                  "Please check the content of the corresponding DEI (the element "
                  "displayed in the message) and the value in the submitted document, "
                  "and correct it so that they match."),
            deiQname=deiFact.qname,
            deiValue=deiFact.xValue,
            coverPageQname=coverPageFact.qname,
            coverPageValue=coverPageFact.xValue,
            modelObject=[deiFact, coverPageFact],
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC5613E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5613E: Please set the DEI "Accounting Standard" value to one
    of the following: "Japan GAAP", "US GAAP", "IFRS".
    """
    validAccountingStandards = {s.value for s in AccountingStandard}
    errorFacts = [
        fact for fact in pluginData.iterValidNonNilFacts(val.modelXbrl, pluginData.accountingStandardsDeiQn)
        if fact.xValue not in validAccountingStandards
    ]
    if len(errorFacts) > 0:
        yield Validation.error(
            codes='EDINET.EC5613E',
            msg=_("Please set the DEI \"Accounting Standard\" value to one "
                  "of the following: %(values)s."),
            values=', '.join(f'"{s.value}"' for s in AccountingStandard),
            modelObject=errorFacts,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC5614E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5614E: A required DEI value is missing.
    """
    for coverPageDocument in pluginData.iterCoverPages(val.modelXbrl):
        filingFormat = pluginData.getFilingFormat(val.modelXbrl)
        if filingFormat is None:
            return
        deiRequirements = pluginData.getDeiRequirements(val.modelXbrl)
        for qname in pluginData.deiItems:
            status = deiRequirements.get(qname, filingFormat)
            if (
                    status == DeiItemStatus.REQUIRED and
                    not pluginData.hasValidNonNilFact(val.modelXbrl, qname)
            ):
                yield Validation.error(
                    codes='EDINET.EC5614E',
                    msg=_("The value of '%(localName)s' in the DEI does not exist. "
                          "File name: '%(file)s'. "
                          "Please add the cover item %(localName)s to the relevant file."),
                    localName=qname.localName,
                    file=coverPageDocument.basename,
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC5623W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5623W: Instances using IFRS taxonomies must set the DEI "Accounting Standard" value to "IFRS".
    """
    if pluginData.jpigpNamespace not in val.modelXbrl.prefixedNamespaces.values():
        return
    errorFacts = [
        fact for fact in pluginData.iterValidNonNilFacts(val.modelXbrl, pluginData.accountingStandardsDeiQn)
        if fact.xValue != AccountingStandard.IFRS.value
    ]
    if len(errorFacts) > 0:
        yield Validation.warning(
            codes='EDINET.EC5623W',
            msg=_("Please set the DEI \"Accounting Standard\" value to \"IFRS\"."),
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
