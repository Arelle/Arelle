"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import regex
import unicodedata
from jaconv import jaconv

from arelle import ValidateDuplicateFacts, ValidateXbrlCalcs, XbrlConst, XmlUtil
from arelle.Cntlr import Cntlr
from arelle.FileSource import FileSource
from arelle.LinkbaseType import LinkbaseType
from arelle.ModelDtsObject import ModelResource, ModelConcept
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.ModelValue import QName, qname
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateDuplicateFacts import DuplicateType
from arelle.ValidateXbrl import ValidateXbrl
from arelle.XmlValidateConst import VALID
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.utils.validate.ValidationUtil import hasPresentationalConceptsWithFacts
from ..Constants import AccountingStandard, HALF_KANA, JAPAN_LANGUAGE_CODES, REPORT_ELR_URI_PATTERN, REPORT_ELR_ID_PATTERN
from ..ControllerPluginData import ControllerPluginData
from ..DeiRequirements import DeiItemStatus
from ..DisclosureSystems import DISCLOSURE_SYSTEM_EDINET
from ..FilingFormat import DocumentType
from ..PluginValidationDataExtension import PluginValidationDataExtension
from ..ReportFolderType import ReportFolderType
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
def rule_calculations(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5611W: The calculated totals for the accounts in the main financial statements, when
    using the appropriate combination of context and extended link roles, should be within the
    range of differences due to rounding.
    """
    for _validation in ValidateXbrlCalcs.validate(
        val.modelXbrl,
        ValidateXbrlCalcs.ValidateCalcsMode.XBRL_v2_1
    ):
        if _validation.codes != "xbrl.5.2.5.2:calcInconsistency":
            continue
        contextId = _validation.args.get("contextID")
        assert contextId is not None
        linkrole = _validation.args.get("linkrole")
        assert linkrole is not None
        isSemiAnnualContext = 'Interim' in contextId
        isSemiAnnualLinkRole = "SemiAnnual" in linkrole
        if isSemiAnnualLinkRole != isSemiAnnualContext:
            # Period of context and linkrole do not match.
            continue
        context = val.modelXbrl.contexts[contextId]
        member = context.dimMemberQname(pluginData.consolidatedOrNonConsolidatedAxisQn, includeDefaults=True)
        isConsolidatedContext = member != pluginData.nonConsolidatedMemberQn
        isConsolidatedLinkRole = "Consolidated" in linkrole
        if isConsolidatedLinkRole != isConsolidatedContext:
            # Consolidated status of context and linkrole do not match.
            continue
        yield Validation.warning(
            codes='EDINET.EC5611W',
            msg=_("The value \"%(reportedSum)s\" of the total subject \"%(concept)s\" does not match the calculated value \"%(computedSum)s\" (number of items: %(count)s) of the calculation link. "
                  "Please correct the settings of the relevant elements and calculation links "
                  "<roleUri=%(linkrole)s> <contextID=%(contextID)s> <unit=%(unitID)s>."),
            count=len(_validation.args.get("modelObject", [])) - 1,
            **_validation.args,
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

    def _normalizeValue(value: str) -> str:
        value = regex.sub(r'\s+', ' ', value).strip()
        return jaconv.h2z(value, kana=True, ascii=True, digit=True)

    def _collectMismatchedValues(deiQName: QName, coverPageQnames: list[QName]) -> None:
        deiFact = next((
            fact
            for fact in pluginData.iterValidNonNilFacts(val.modelXbrl, deiQName)
        ), None)
        if deiFact is None or deiFact.xValue is None:
            return
        deiValue = _normalizeValue(str(deiFact.xValue))
        for coverPageQname in coverPageQnames:
            for coverPageFact in pluginData.iterValidNonNilFacts(val.modelXbrl, coverPageQname):
                factValue = _normalizeValue(str(coverPageFact.xValue))
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
    if pluginData.namespaces.jpigp not in val.modelXbrl.prefixedNamespaces.values():
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
def rule_namespace_prefixes(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8003W: The namespace prefix used in the namespace declaration of the
    report schema file must conform to the rules.
        jp{府令略号}{様式番号}-{報告書略号}_{EDINET コード又はファンドコード}-{追番(3 桁)}
    EDINET.EC8004W: The namespace prefix used in the namespace declaration of the
    audit report schema file must conform to the rules.
        jpaud-{監査報告書略号}-{当期又は前期の別}{連結又は個別の別}_{EDINET コード又はファンドコード}-{追番(3 桁)}
    """
    extensionSchemas = pluginData.getExtensionSchemas(val.modelXbrl)
    for modelDocument in val.modelXbrl.urlDocs.values():
        for prefix, namespace in modelDocument.xmlRootElement.nsmap.items():
            if namespace not in extensionSchemas:
                continue # Not an extension schema namespace
            pathInfo = extensionSchemas[namespace]
            assert pathInfo.reportFolderType is not None
            patterns = pathInfo.reportFolderType.prefixPatterns
            if len(patterns) == 0:
                continue # No patterns to check against
            match = any(pattern.fullmatch(prefix) for pattern in patterns)
            if match:
                continue # Valid namespace URI
            if pathInfo.reportFolderType == ReportFolderType.AUDIT_DOC:
                yield Validation.warning(
                    codes='EDINET.EC8004W',
                    msg=_("The namespace prefix used in the namespace declaration of the "
                          "audit report schema file does not conform to the rules. "
                          "File name: '%(file)s'. "
                          "Prefix: '%(prefix)s'."),
                    file=pathInfo.path.name,
                    prefix=prefix
                )
            else:
                yield Validation.warning(
                    codes='EDINET.EC8003W',
                    msg=_("The namespace prefix used in the namespace declaration of the "
                          "report schema file does not conform to the rules. "
                          "File name: '%(file)s'. "
                          "Prefix: '%(prefix)s'."),
                    file=pathInfo.path.name,
                    prefix=prefix
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_namespace_uris(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8000W: A report's extension taxonomy namespace URI must conform to the rules.
        http://disclosure.edinet-fsa.go.jp/jp{府令略号}{様式番号}/{報告書略号}/{報告書連番(3 桁)}
            /{EDINET コード又はファンドコード}-{追番(3 桁)}/{報告対象期間期末日|報告義務発生日}
            /{報告書提出回数(2 桁)}/{報告書提出日}
    EDINET.EC8001W: An audit report's extension taxonomy namespace URI must conform to the rules.
        http://disclosure.edinet-fsa.go.jp/jpaud/{監査報告書略号}/{当期又は前期の別}{連結又は個別の別}
            /{報告書連番(3 桁)}/{EDINET コード又はファンドコード}-{追番(3桁)}/{報告対象期間期末日}
            /{報告書提出回数(2 桁)}/{報告書提出日}
    """
    for targetNamespace, pathInfo in pluginData.getExtensionSchemas(val.modelXbrl).items():
        assert pathInfo.reportFolderType is not None
        patterns = pathInfo.reportFolderType.namespaceUriPatterns
        if len(patterns) == 0:
            continue # No patterns to check against
        match = any(pattern.fullmatch(targetNamespace) for pattern in patterns)
        if match:
            continue # Valid namespace URI
        if pathInfo.reportFolderType == ReportFolderType.AUDIT_DOC:
            yield Validation.warning(
                codes='EDINET.EC8001W',
                msg=_("The namespace URI used in the namespace declaration of the "
                      "audit report schema file does not conform to the rules. "
                      "File name: '%(file)s'. "
                      "URI: '%(uri)s'."),
                file=pathInfo.path.name,
                uri=targetNamespace
            )
        else:
            yield Validation.warning(
                codes='EDINET.EC8000W',
                msg=_("The namespace URI used in the namespace declaration of the "
                      "report schema file does not conform to the rules. "
                      "File name: '%(file)s'. "
                      "URI: '%(uri)s'."),
                file=pathInfo.path.name,
                uri=targetNamespace
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_roles(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8006W: The ID of the report's extended link role must conform to the rules.
        rol_{Root element name (excluding Abstract and Heading)}(-{Modifier})(-{2-digit sequential number})
    EDINET.EC8007W: The URI of the report's extended link role must conform to the rules.
        http://disclosure.edinet-fsa.go.jp/role/jp{Prefecture Ordinance abbreviation|dei}
            (-{report abbreviation})/rol_{root element name (excluding Abstract and Heading)}
            (-{modifier})(-{two-digit sequential number})
    """
    for roleTypes in val.modelXbrl.roleTypes.values():
        for roleType in roleTypes:
            if not pluginData.isExtensionUri(roleType.modelDocument.uri, val.modelXbrl):
                continue
            if not REPORT_ELR_ID_PATTERN.fullmatch(str(roleType.id)):
                yield Validation.warning(
                    codes='EDINET.EC8006W',
                    msg=_("The ID of the report's extended link role does not conform to the rules. "
                          "File name: '%(file)s'. "
                          "ID: '%(id)s'."),
                    file=roleType.modelDocument.basename,
                    id=roleType.id
                )
            if not REPORT_ELR_URI_PATTERN.fullmatch(roleType.roleURI):
                yield Validation.warning(
                    codes='EDINET.EC8007W',
                    msg=_("The URI of the report's extended link role does not conform to the rules. "
                          "File name: '%(file)s'. "
                          "URI: '%(uri)s'."),
                    file=roleType.modelDocument.basename,
                    uri=roleType.roleURI
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
def rule_EC8028W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8028W: The priority attribute must not be duplicated for the same
    element and label role within the submitter's taxonomy.

    Note: Not mentioned in documentation, but inferring from sample filings that
    label language should also be considered.
    """
    labelsRelationshipSet = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    if labelsRelationshipSet is None:
        return
    for concept, rels in labelsRelationshipSet.fromModelObjects().items():
        groups = defaultdict(list)
        for rel in rels:
            if not isinstance(rel.toModelObject, ModelResource):
                continue
            if not pluginData.isExtensionUri(rel.modelDocument.uri, val.modelXbrl):
                continue
            groups[(rel.toModelObject.xmlLang, rel.toModelObject.role, rel.priority)].append(rel)
        for (lang, role, priority), group in groups.items():
            if len(group) > 1:
                yield Validation.warning(
                    codes='EDINET.EC8028W',
                    msg=_("The priority attribute must not be duplicated for the same "
                          "element and label role in the same submitter taxonomy. "
                          "File name: '%(path)s'. Concept: '%(concept)s'. "
                          "Role: '%(role)s'. Priority: %(priority)s. "
                          "Please check the element and label name of the corresponding "
                          "file. Please set the priority attribute so that the same "
                          "element and the same label role in the submitter's taxonomy "
                          "are not duplicated."),
                    path=rels[0].document.basename,
                    concept=concept.qname,
                    role=role,
                    priority=priority,
                    modelObject=group,
                )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8029W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8029W: Any non-abstract element referenced in the definition or presentation linkbase must
    be present in an instance.
    """
    linkbaseTypes = (LinkbaseType.DEFINITION, LinkbaseType.PRESENTATION)
    arcroles = tuple(
        arcrole
        for linkbaseType in linkbaseTypes
        for arcrole in linkbaseType.getArcroles()
    )
    referencedConcepts: set[ModelConcept] = set()
    usedConcepts: set[ModelConcept] = set()
    for modelXbrl in pluginData.loadedModelXbrls:
        usedConcepts.update(fact.concept for fact in modelXbrl.facts)
        relSet = modelXbrl.relationshipSet(arcroles)
        if relSet is None:
            continue
        concepts = list(relSet.fromModelObjects().keys()) + list(relSet.toModelObjects().keys())
        for concept in concepts:
            if not isinstance(concept, ModelConcept):
                continue
            if concept.isAbstract:
                continue
            referencedConcepts.add(concept)
    unusedConcepts = referencedConcepts - usedConcepts
    for concept in unusedConcepts:
        yield Validation.warning(
            codes='EDINET.EC8029W',
            msg=_("The non-abstract element present in the presentation link or definition "
                  "link is not set in an inline XBRL file. "
                  "Element: '%(concept)s'. "
                  "Please use the element in the inline XBRL file. If it is an unnecessary "
                  "element, please delete it from the presentation link and definition link."),
            concept=concept.qname.localName,
            modelObject=concept,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8030W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8030W: Any concept (other than DEI concepts) used in an instance must
    be in the presentation linkbase.
    """
    usedConcepts = pluginData.getUsedConcepts(val.modelXbrl)
    relSet = val.modelXbrl.relationshipSet(tuple(LinkbaseType.PRESENTATION.getArcroles()))
    for concept in usedConcepts:
        if concept.qname.namespaceURI == pluginData.namespaces.jpdei:
            continue
        if concept.qname.localName.endswith('DEI'):
            # Example: jpsps_cor:SecuritiesRegistrationStatementAmendmentFlagDeemedRegistrationStatementDEI
            continue
        if not relSet.contains(concept):
            yield Validation.warning(
                codes='EDINET.EC8030W',
                msg=_("An element (other than DEI) set in the inline XBRL file is not set in the "
                      "presentation linkbase. "
                      "Element: '%(concept)s'. "
                      "Please set the relevant element in the presentation linkbase."),
                concept=concept.qname.localName,
                modelObject=concept,
            )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8031W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8031W: For contexts having an ID beginning with "FilingDate", the instant
    date value must match the report submission date set in the file name.

    However, when reporting corrections, please set the following:
    Context beginning with "FilingDate": The submission date on the cover page of the attached inline XBRL (original submission date)
    "Report submission date" in the file name: The submission date of the correction report, etc.
    """
    isAmendment = pluginData.getDeiValue('ReportAmendmentFlagDEI')
    if isAmendment:
        # Amendment/corrections report are not subject to this validation, but documentation does note:
        #   However, when reporting corrections, please set the following:
        #   Context beginning with "FilingDate": The submission date on the cover page of the attached inline XBRL (original submission date)
        #   "Report submission date" in the file name: The submission date of the correction report, etc.
        return
    uploadContents = pluginData.getUploadContents()
    if uploadContents is None:
        return
    docUris = {
        docUri
        for modelXbrl in pluginData.loadedModelXbrls
        for docUri in modelXbrl.urlDocs.keys()
    }
    actualDates = defaultdict(set)
    for uri in docUris:
        path = Path(uri)
        pathInfo = uploadContents.uploadPathsByFullPath.get(path)
        if pathInfo is None or pathInfo.reportFolderType is None:
            continue
        patterns = pathInfo.reportFolderType.ixbrlFilenamePatterns
        for pattern in patterns:
            matches = pattern.match(path.name)
            if not matches:
                continue
            groups = matches.groupdict()
            year = groups['submission_year']
            month = groups['submission_month']
            day = groups['submission_day']
            actualDate = f'{year:04}-{month:02}-{day:02}'
            actualDates[actualDate].add(path)
    expectedDates = defaultdict(set)
    for modelXbrl in pluginData.loadedModelXbrls:
        for context in modelXbrl.contexts.values():
            if context.id is None:
                continue
            if not context.id.startswith("FilingDate"):
                continue
            if not context.isInstantPeriod:
                continue
            expectedDate = XmlUtil.dateunionValue(context.instantDatetime, subtractOneDay=True)[:10]
            expectedDates[expectedDate].add(context)
    invalidDates = {k: v for k, v in actualDates.items() if k not in expectedDates}
    if len(invalidDates) == 0:
        return
    paths = [
        path
        for paths in invalidDates.values()
        for path in paths
    ]
    contexts = [
        context
        for contexts in expectedDates.values()
        for context in contexts
    ]
    for path in paths:
        for context in contexts:
            yield Validation.warning(
                codes='EDINET.EC8031W',
                msg=_("The value of the instant element in context '%(context)s' "
                      "must match the report submission date set in the file name. "
                      "File name: '%(file)s'. "
                      "Please correct the report submission date in the filename or "
                      "the instant element value for the context with ID '%(context)s'."),
                context=context.id,
                file=path.name,
                modelObject=context,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8034W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8034W: English labels for extension concepts must not contain full-width characters.
    """
    labelsRelationshipSet = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    for concept, modelLabelRels in labelsRelationshipSet.fromModelObjects().items():
        for modelLabelRel in modelLabelRels:
            modelLabel = modelLabelRel.toModelObject
            if not isinstance(modelLabel, ModelResource):
                continue
            if not pluginData.isExtensionUri(modelLabel.modelDocument.uri, val.modelXbrl):
                continue
            if modelLabel.xmlLang != 'en':
                continue
            label = modelLabel.textValue.strip()  # Does not trim full-width spaces
            if any(
                unicodedata.east_asian_width(char) in ('F', 'W')
                for char in label
            ):
                yield Validation.warning(
                    codes='EDINET.EC8034W',
                    msg=_("The English label must be set using half-width alphanumeric characters "
                          "and half-width symbols. "
                          "File name: '%(file)s'. "
                          "English label: '%(label)s'. "
                          "Please use only half-width alphanumeric characters and half-width symbols "
                          "for the English labels of concepts in the relevant files."),
                    file=modelLabel.document.basename,
                    label=modelLabel.id,
                    modelObject=modelLabel,
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8069W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8069W: If tagging IssuedSharesTotalNumberOfSharesEtcTextBlock, also tag using at least one of the following three elements:"
    "Overview of the corporate governance system (company with auditors) [text block]" (CorporateGovernanceCompanyWithCorporateAuditorsTextBlock) ・
    "Overview of the corporate governance system (company with audit and supervisory committee) [text block]" (CorporateGovernanceCompanyWithAuditAndSupervisoryCommitteeTextBlock)
    "Overview of the corporate governance system (company with nominating committee, etc.) [text block]" (CorporateGovernanceCompanyWithNominatingAndOtherCommitteesTextBlock)

    If a role indicating a disclosure of securities information and if IssuedSharesTotalNumberOfSharesEtcTextBlock is tagged and non-nil then the one or more of the above three elements must also be tagged and non-nil.
    """
    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_CabinetOfficeOrdinanceOnDisclosureOfCorporateInformationEtcFormNo24SecuritiesRegistrationStatement',
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_CabinetOfficeOrdinanceOnDisclosureOfCorporateInformationEtcFormNo27SecuritiesRegistrationStatement',
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_CabinetOfficeOrdinanceOnDisclosureOfCorporateInformationEtcFormNo3AnnualSecuritiesReport',
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_CabinetOfficeOrdinanceOnDisclosureOfCorporateInformationEtcFormNo32AnnualSecuritiesReport',
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_CabinetOfficeOrdinanceOnDisclosureOfCorporateInformationEtcFormNo4AnnualSecuritiesReport',
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_CabinetOfficeOrdinanceOnDisclosureOfCorporateInformationEtcFormNo43QuarterlySecuritiesReport',
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_CabinetOfficeOrdinanceOnDisclosureOfCorporateInformationEtcFormNo43SemiAnnualSecuritiesReport',
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_CabinetOfficeOrdinanceOnDisclosureOfCorporateInformationEtcFormNo24SecuritiesRegistrationStatement',
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_CabinetOfficeOrdinanceOnDisclosureOfCorporateInformationEtcFormNo27SecuritiesRegistrationStatement',
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_CabinetOfficeOrdinanceOnDisclosureOfCorporateInformationEtcFormNo3AnnualSecuritiesReport',
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_CabinetOfficeOrdinanceOnDisclosureOfCorporateInformationEtcFormNo32AnnualSecuritiesReport',
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_CabinetOfficeOrdinanceOnDisclosureOfCorporateInformationEtcFormNo4AnnualSecuritiesReport',
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_CabinetOfficeOrdinanceOnDisclosureOfCorporateInformationEtcFormNo43QuarterlySecuritiesReport',
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_CabinetOfficeOrdinanceOnDisclosureOfCorporateInformationEtcFormNo43SemiAnnualSecuritiesReport'
    )
    if not hasPresentationalConceptsWithFacts(val.modelXbrl, roleUris):
        return
    if not pluginData.hasValidNonNilFact(val.modelXbrl, pluginData.issuedSharesTotalNumberOfSharesEtcQn):
        return
    if (
            pluginData.hasValidNonNilFact(val.modelXbrl, pluginData.corporateGovernanceCompanyWithAuditAndSupervisoryCommitteeTextBlockQn) or
            pluginData.hasValidNonNilFact(val.modelXbrl, pluginData.corporateGovernanceCompanyWithCorporateAuditorsTextBlockQn) or
            pluginData.hasValidNonNilFact(val.modelXbrl, pluginData.corporateGovernanceCompanyWithNominatingAndOtherCommitteesTextBlockQn)
    ):
        return
    totalStockShares = val.modelXbrl.factsByQname.get(pluginData.issuedSharesTotalNumberOfSharesEtcQn)
    yield Validation.error(
        codes='EDINET.EC8069W',
        msg=_("If tagging IssuedSharesTotalNumberOfSharesEtcTextBlock, also tag using at least one of the following three elements: \n"
              "'Overview of corporate governance system (company with auditors) [Text Block]' (CorporateGovernanceCompanyWithCorporateAuditorsTextBlock) \n"
              "'Overview of corporate governance system (company with audit and supervisory committee) [Text Block]' (CorporateGovernanceCompanyWithAuditAndSupervisoryCommitteeTextBlock)\n"
              "'Overview of corporate governance system (company with nominating committee, etc.) [Text Block]' (CorporateGovernanceCompanyWithNominatingAndOtherCommitteesTextBlock)\n"),
        modelObject=totalStockShares
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8073E(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8073E: Prohibited characters are used in the labels for descendents of
                    CategoriesOfDirectorsAndOtherOfficersAxis except for ExecutiveOfficersMember
    """
    axisConcept = val.modelXbrl.qnameConcepts.get(pluginData.categoriesOfDirectorsAndOtherOfficersAxisQn)
    if axisConcept is None:
        return
    defRelSet = val.modelXbrl.relationshipSet(tuple(LinkbaseType.DEFINITION.getArcroles()))
    labelRelSet = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    for rel in defRelSet.fromModelObject(axisConcept):
        if rel.toModelObject is None or rel.toModelObject.qname == pluginData.executiveOfficersMemberQn:
            continue
        for labelRel in labelRelSet.fromModelObject(rel.toModelObject):
            if labelRel.toModelObject is None or labelRel.toModelObject.textValue is None:
                continue
            illegalChars = HALF_KANA.intersection(set(labelRel.toModelObject.textValue))
            if any(illegalChars):
                yield Validation.error(
                    codes='EDINET.EC8073E',
                    msg=_("The concept: %(concept)s has a %(role)s label which contains characters that are not "
                          "allowed. Label: %(label)s, disallowed characters: %(characters)s"),
                    concept=rel.toModelObject.qname.localName,
                    role=labelRel.toModelObject.role,
                    label=labelRel.toModelObject.textValue,
                    characters=list(illegalChars)
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8073W_EC8074W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8073W: Prohibited characters are used in Japanese labels for descendents of ExecutiveOfficersMember
    EDINET.EC8074W: Prohibited characters are used in English labels for descendents of ExecutiveOfficersMember
    """
    def getIllegalCharsJapanese(textValue: str) -> set[str]:
        """Check for prohibited characters in Japanese labels."""
        return set(HALF_KANA.intersection(set(textValue)))

    def getIllegalCharsEnglish(textValue: str) -> set[str]:
        """Check for prohibited characters in English labels."""
        illegalChars = set()
        for char in textValue:
            if char in HALF_KANA:
                illegalChars.add(char)
                continue
            codePoint = ord(char)
            if 0xA1 <= codePoint <= 0xBF:
                # Exclude symbols
                illegalChars.add(char)
            elif codePoint in (0xD7, 0xF7):
                # Exclude multiplication and division symbols
                illegalChars.add(char)
            elif codePoint > 0xFF:
                # Characters beyond Latin-1
                illegalChars.add(char)
        return illegalChars

    memberConcept = val.modelXbrl.qnameConcepts.get(pluginData.executiveOfficersMemberQn)
    if memberConcept is None:
        return
    defRelSet = val.modelXbrl.relationshipSet(tuple(LinkbaseType.DEFINITION.getArcroles()))
    labelRelSet = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    conceptsLabelsToCheck = {memberConcept}.union(
        {rel.toModelObject for rel in defRelSet.fromModelObject(memberConcept) if rel.toModelObject is not None}
    )
    for concept in conceptsLabelsToCheck:
        for labelRel in labelRelSet.fromModelObject(concept):
            label = labelRel.toModelObject
            if label is None or label.textValue is None:
                continue

            # Check Japanese labels
            if label.xmlLang in JAPAN_LANGUAGE_CODES:
                illegalChars = getIllegalCharsJapanese(label.textValue)
                if illegalChars:
                    yield Validation.warning(
                        codes='EDINET.EC8073W',
                        msg=_("The concept: %(concept)s has a %(role)s label which contains characters that are not "
                              "allowed. Label: %(label)s, disallowed characters: %(characters)s"),
                        concept=concept.qname.localName,
                        role=label.role,
                        label=label.textValue,
                        characters=list(illegalChars)
                    )

            # Check English labels
            elif label.xmlLang == 'en':
                illegalChars = getIllegalCharsEnglish(label.textValue)
                if illegalChars:
                    yield Validation.warning(
                        codes='EDINET.EC8074W',
                        msg=_("The concept: %(concept)s has a %(role)s label which contains characters that are not "
                              "allowed. Label: %(label)s, disallowed characters: %(characters)s"),
                        concept=concept.qname.localName,
                        role=label.role,
                        label=label.textValue,
                        characters=sorted(illegalChars)
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


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8038W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8038W: The details of the major shareholders' status have not been tagged.
    Should have facts in one of the major shareholders roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_MajorShareholders-01',
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_MajorShareholders-02',
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_MajorShareholders-01',
        'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_MajorShareholders-02',
    )
    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8038W',
        msg=_("The details of the major shareholders' status have not been tagged. "
              "Please provide detailed tagging of the status of major shareholders."),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8039W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8039W: The consolidated balance sheet details have not been tagged.
    If WhetherConsolidatedFinancialStatementsArePreparedDEI is TRUE and AccountingStandardsDEI is "Japan GAAP",
    then a BS must exist using one of the specified roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    if pluginData.isConsolidated() != True:
        return
    accountingStandard = pluginData.getDeiValue('AccountingStandardsDEI')
    if accountingStandard != AccountingStandard.JAPAN_GAAP.value:
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedBalanceSheet',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedBalanceSheet',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_SemiAnnualConsolidatedBalanceSheet',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualConsolidatedBalanceSheet',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_Type1SemiAnnualConsolidatedBalanceSheet',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_Type1SemiAnnualConsolidatedBalanceSheet',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_QuarterlyConsolidatedBalanceSheet',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_QuarterlyConsolidatedBalanceSheet',
    )

    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8039W',
        msg=_("The consolidated balance sheet details have not been tagged. "
              "Please provide detailed tagging of the consolidated balance sheet. "
              "If you do not provide a consolidated balance sheet, please confirm that "
              'the "Consolidated Financial Statements" field in the DEI information is correct.'),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8040W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8040W: Balance sheet details not tagged.
    If WhetherConsolidatedFinancialStatementsArePreparedDEI is FALSE and AccountingStandardsDEI is "Japan GAAP",
    then a BS must exist using one of the specified roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    if pluginData.isConsolidated() != False:
        return
    accountingStandard = pluginData.getDeiValue('AccountingStandardsDEI')
    if accountingStandard != AccountingStandard.JAPAN_GAAP.value:
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_BalanceSheet',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_SemiAnnualBalanceSheet',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualBalanceSheet',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_Type1SemiAnnualBalanceSheet',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_Type1SemiAnnualBalanceSheet',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_QuarterlyBalanceSheet',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_QuarterlyBalanceSheet',
    )

    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8040W',
        msg=_("Balance sheet details not tagged. Please tag the balance sheet in detail."),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8041W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8041W: The consolidated income statement has not been tagged in detail.
    If WhetherConsolidatedFinancialStatementsArePreparedDEI is TRUE and AccountingStandardsDEI is "Japan GAAP",
    then an IS must exist using one of the specified roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    if pluginData.isConsolidated() != True:
        return
    accountingStandard = pluginData.getDeiValue('AccountingStandardsDEI')
    if accountingStandard != AccountingStandard.JAPAN_GAAP.value:
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedStatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_SemiAnnualConsolidatedStatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualConsolidatedStatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_Type1SemiAnnualConsolidatedStatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_Type1SemiAnnualConsolidatedStatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_YearToQuarterEndConsolidatedStatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_YearToQuarterEndConsolidatedStatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_QuarterPeriodConsolidatedStatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_QuarterPeriodConsolidatedStatementOfIncome',
    )

    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8041W',
        msg=_("The consolidated income statement has not been tagged in detail. "
              "Please provide detailed tagging for the consolidated income statement. "
              "If you do not provide a consolidated income statement, please confirm that "
              'the "Consolidated Financial Statements" field in the DEI information is correct.'),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8042W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8042W: The income statement details are not tagged.
    If WhetherConsolidatedFinancialStatementsArePreparedDEI is FALSE and AccountingStandardsDEI is "Japan GAAP",
    then an IS must exist using one of the specified roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    if pluginData.isConsolidated() != False:
        return
    accountingStandard = pluginData.getDeiValue('AccountingStandardsDEI')
    if accountingStandard != AccountingStandard.JAPAN_GAAP.value:
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_StatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_SemiAnnualStatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualStatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_Type1SemiAnnualStatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_Type1SemiAnnualStatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_YearToQuarterEndStatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_YearToQuarterEndStatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_QuarterPeriodStatementOfIncome',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_QuarterPeriodStatementOfIncome',
    )

    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8042W',
        msg=_("The income statement details are not tagged. "
              "Please provide detailed tagging of your income statement."),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8043W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8043W: The profit and loss statement has not been tagged in detail.
    If AccountingStandardsDEI = "Japan GAAP" and WhetherConsolidatedFinancialStatementsArePreparedDEI = "false",
    then a P&L must exist using one of the specified roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    if pluginData.isConsolidated() != False:
        return
    accountingStandard = pluginData.getDeiValue('AccountingStandardsDEI')
    if accountingStandard != AccountingStandard.JAPAN_GAAP.value:
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfIncomeAndRetainedEarnings',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_StatementOfIncomeAndRetainedEarnings',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_SemiAnnualStatementOfIncomeAndRetainedEarnings',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualStatementOfIncomeAndRetainedEarnings',
    )

    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8043W',
        msg=_("The profit and loss statement has not been tagged in detail. "
              "Please provide detailed tagging of the profit and loss and retained earnings statement."),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8044W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8044W: The consolidated statement of changes in equity has not been detailed.
    If WhetherConsolidatedFinancialStatementsArePreparedDEI is TRUE and AccountingStandardsDEI is "Japan GAAP",
    then an Equity Statement must exist using one of the specified roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    if pluginData.isConsolidated() != True:
        return
    accountingStandard = pluginData.getDeiValue('AccountingStandardsDEI')
    if accountingStandard != AccountingStandard.JAPAN_GAAP.value:
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfChangesInEquity',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedStatementOfChangesInEquity',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfChangesInNetAssets',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedStatementOfChangesInNetAssets',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_SemiAnnualConsolidatedStatementOfChangesInEquity',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualConsolidatedStatementOfChangesInEquity',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_SemiAnnualConsolidatedStatementOfChangesInNetAssets',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualConsolidatedStatementOfChangesInNetAssets',
    )

    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8044W',
        msg=_("The consolidated statement of changes in equity has not been detailed. "
              "Please tag the details of the consolidated statement of changes in equity. "
              "If you do not include a consolidated statement of changes in equity, please confirm that "
              'the "Consolidated Financial Statements" field in the DEI information is correct.'),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8045W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8045W: The statement of changes in equity has not been tagged in detail.
    If WhetherConsolidatedFinancialStatementsArePreparedDEI is FALSE and AccountingStandardsDEI is "Japan GAAP",
    then an Equity Statement must exist using one of the specified roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    if pluginData.isConsolidated() != False:
        return
    accountingStandard = pluginData.getDeiValue('AccountingStandardsDEI')
    if accountingStandard != AccountingStandard.JAPAN_GAAP.value:
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfChangesInEquity',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_StatementOfChangesInEquity',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfChangesInNetAssets',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_StatementOfChangesInNetAssets',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_SemiAnnualStatementOfChangesInEquity',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualStatementOfChangesInEquity',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_SemiAnnualStatementOfChangesInNetAssets',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualStatementOfChangesInNetAssets',
    )

    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8045W',
        msg=_("The statement of changes in equity has not been tagged in detail. "
              "Please provide detailed tagging for the Statement of Changes in Equity."),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8046W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8046W: The statement of changes in unitholders' equity has not been tagged in detail.
    If industry code is "inv", then facts must exist in one of the specified roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    industryCodeConsolidated = pluginData.getDeiValue('IndustryCodeWhenConsolidatedFinancialStatementsArePreparedInAccordanceWithIndustrySpecificRegulationsDEI')
    industryCodeNonConsolidated = pluginData.getDeiValue('IndustryCodeWhenFinancialStatementsArePreparedInAccordanceWithIndustrySpecificRegulationsDEI')

    if industryCodeConsolidated != 'INV' and industryCodeNonConsolidated != 'INV':
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfUnitholdersEquity',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_StatementOfUnitholdersEquity',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_SemiAnnualStatementOfUnitholdersEquity',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualStatementOfUnitholdersEquity',
    )

    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8046W',
        msg=_("The statement of changes in unitholders' equity has not been tagged in detail. "
              "Please provide detailed tagging for the Statement of Changes in Unitholders' Equity."),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8047W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8047W: The statement of changes in employee capital etc. has not been tagged in detail.
    If industry code is "liq", then facts must exist in one of the specified roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    industryCodeConsolidated = pluginData.getDeiValue('IndustryCodeWhenConsolidatedFinancialStatementsArePreparedInAccordanceWithIndustrySpecificRegulationsDEI')
    industryCodeNonConsolidated = pluginData.getDeiValue('IndustryCodeWhenFinancialStatementsArePreparedInAccordanceWithIndustrySpecificRegulationsDEI')

    if industryCodeConsolidated != 'LIQ' and industryCodeNonConsolidated != 'LIQ':
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfMembersEquity',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_StatementOfMembersEquity',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_SemiAnnualStatementOfMembersEquity',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualStatementOfMembersEquity',
    )

    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8047W',
        msg=_("The statement of changes in employee capital etc. has not been tagged in detail. "
              "Please provide detailed tagging for the Statement of Changes in Employee Capital, etc."),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8048W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8048W: The consolidated cash flow statement is not detailed.
    If WhetherConsolidatedFinancialStatementsArePreparedDEI is TRUE, then an SCF must exist using one of the specified roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    if pluginData.isConsolidated() != True:
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfCashFlows-direct',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedStatementOfCashFlows-direct',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_SemiAnnualConsolidatedStatementOfCashFlows-direct',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualConsolidatedStatementOfCashFlows-direct',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_Type1SemiAnnualConsolidatedStatementOfCashFlows-direct',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_Type1SemiAnnualConsolidatedStatementOfCashFlows-direct',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_QuarterlyConsolidatedStatementOfCashFlows-direct',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_QuarterlyConsolidatedStatementOfCashFlows-direct',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfCashFlows-indirect',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedStatementOfCashFlows-indirect',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_SemiAnnualConsolidatedStatementOfCashFlows-indirect',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualConsolidatedStatementOfCashFlows-indirect',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_Type1SemiAnnualConsolidatedStatementOfCashFlows-indirect',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_Type1SemiAnnualConsolidatedStatementOfCashFlows-indirect',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_QuarterlyConsolidatedStatementOfCashFlows-indirect',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_QuarterlyConsolidatedStatementOfCashFlows-indirect',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_ConsolidatedStatementOfCashFlowsIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_std_ConsolidatedStatementOfCashFlowsIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualConsolidatedStatementOfCashFlowsIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyConsolidatedStatementOfCashFlowsIFRS',
    )

    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8048W',
        msg=_("The consolidated cash flow statement is not detailed. "
              "Please tag the details of the consolidated cash flow statement. "
              "If you do not provide a consolidated cash flow statement, please make sure that "
              'the "Consolidated Financial Statements" in the DEI information is correct.'),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8049W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8049W: The cash flow statement is not tagged in detail.
    If WhetherConsolidatedFinancialStatementsArePreparedDEI is FALSE, then an SCF must exist using one of the specified roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    if pluginData.isConsolidated() != False:
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfCashFlows-direct',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_StatementOfCashFlows-direct',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_SemiAnnualStatementOfCashFlows-direct',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualStatementOfCashFlows-direct',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_Type1SemiAnnualStatementOfCashFlows-direct',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_Type1SemiAnnualStatementOfCashFlows-direct',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_QuarterlyStatementOfCashFlows-direct',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_QuarterlyStatementOfCashFlows-direct',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfCashFlows-indirect',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_StatementOfCashFlows-indirect',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_SemiAnnualStatementOfCashFlows-indirect',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualStatementOfCashFlows-indirect',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_Type1SemiAnnualStatementOfCashFlows-indirect',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_Type1SemiAnnualStatementOfCashFlows-indirect',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_QuarterlyStatementOfCashFlows-indirect',
        'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_QuarterlyStatementOfCashFlows-indirect',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_StatementOfCashFlowsIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualStatementOfCashFlowsIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyStatementOfCashFlowsIFRS',
    )

    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8049W',
        msg=_("The cash flow statement is not tagged in detail. "
              "Please provide detailed tagging for the cash flow statement. "
              "If you do not provide a cash flow statement, please provide the DEI information with "
              '"Whether or not consolidated financial statements are provided."'),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8050W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8050W: Segment information is not tagged in detail.
    Based on AccountingStandardsDEI, segment information with ReportableSegmentsMember must exist.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT, }):
        return

    accountingStandard = pluginData.getDeiValue('AccountingStandardsDEI')
    if accountingStandard == AccountingStandard.JAPAN_GAAP.value:
        roleUris: tuple[str, ...] = (
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcType1SemiAnnualFinancialStatements-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcType1SemiAnnualFinancialStatements-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcType1SemiAnnualFinancialStatements-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcType1SemiAnnualConsolidatedFinancialStatements-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcType1SemiAnnualConsolidatedFinancialStatements-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcType1SemiAnnualConsolidatedFinancialStatements-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualFinancialStatements-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualFinancialStatements-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualFinancialStatements-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualFinancialStatements-04',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualFinancialStatements-05',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualFinancialStatements-06',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualFinancialStatements-07',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualFinancialStatements-08',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualFinancialStatements-09',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-04',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-05',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-06',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-07',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-08',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-09',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcQuarterlyFinancialStatements-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcQuarterlyFinancialStatements-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcQuarterlyFinancialStatements-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcQuarterlyConsolidatedFinancialStatements-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcQuarterlyConsolidatedFinancialStatements-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcQuarterlyConsolidatedFinancialStatements-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcFinancialStatements-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcFinancialStatements-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcFinancialStatements-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcFinancialStatements-04',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcFinancialStatements-05',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcFinancialStatements-06',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcFinancialStatements-07',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcFinancialStatements-08',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcFinancialStatements-09',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcConsolidatedFinancialStatements-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcConsolidatedFinancialStatements-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcConsolidatedFinancialStatements-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcConsolidatedFinancialStatements-04',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcConsolidatedFinancialStatements-05',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcConsolidatedFinancialStatements-06',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcConsolidatedFinancialStatements-07',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcConsolidatedFinancialStatements-08',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_std_NotesSegmentInformationEtcConsolidatedFinancialStatements-09',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcType1SemiAnnualFinancialStatements-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcType1SemiAnnualFinancialStatements-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcType1SemiAnnualFinancialStatements-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcType1SemiAnnualConsolidatedFinancialStatements-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcType1SemiAnnualConsolidatedFinancialStatements-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcType1SemiAnnualConsolidatedFinancialStatements-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualFinancialStatements-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualFinancialStatements-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualFinancialStatements-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualFinancialStatements-04',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualFinancialStatements-05',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualFinancialStatements-06',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualFinancialStatements-07',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualFinancialStatements-08',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualFinancialStatements-09',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-04',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-05',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-06',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-07',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-08',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcSemiAnnualConsolidatedFinancialStatements-09',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcQuarterlyFinancialStatements-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcQuarterlyFinancialStatements-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcQuarterlyFinancialStatements-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcQuarterlyConsolidatedFinancialStatements-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcQuarterlyConsolidatedFinancialStatements-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcQuarterlyConsolidatedFinancialStatements-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcFinancialStatements-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcFinancialStatements-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcFinancialStatements-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcFinancialStatements-04',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcFinancialStatements-05',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcFinancialStatements-06',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcFinancialStatements-07',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcFinancialStatements-08',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcFinancialStatements-09',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-04',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-05',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-06',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-07',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-08',
            'http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_NotesSegmentInformationEtcConsolidatedFinancialStatements-09',
        )
    elif accountingStandard == AccountingStandard.IFRS.value:
        roleUris = (
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_std_NotesSegmentInformationConsolidatedFinancialStatementsIFRS-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_std_NotesSegmentInformationConsolidatedFinancialStatementsIFRS-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_std_NotesSegmentInformationConsolidatedFinancialStatementsIFRS-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationFinancialStatementsIFRS-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationFinancialStatementsIFRS-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationFinancialStatementsIFRS-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationConsolidatedFinancialStatementsIFRS-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationConsolidatedFinancialStatementsIFRS-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationConsolidatedFinancialStatementsIFRS-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationCondensedSemiAnnualFinancialStatementsIFRS-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationCondensedSemiAnnualFinancialStatementsIFRS-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationCondensedSemiAnnualFinancialStatementsIFRS-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationCondensedSemiAnnualConsolidatedFinancialStatementsIFRS-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationCondensedSemiAnnualConsolidatedFinancialStatementsIFRS-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationCondensedSemiAnnualConsolidatedFinancialStatementsIFRS-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationCondensedQuarterlyFinancialStatementsIFRS-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationCondensedQuarterlyFinancialStatementsIFRS-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationCondensedQuarterlyFinancialStatementsIFRS-03',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationCondensedQuarterlyConsolidatedFinancialStatementsIFRS-01',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationCondensedQuarterlyConsolidatedFinancialStatementsIFRS-02',
            'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_NotesSegmentInformationCondensedQuarterlyConsolidatedFinancialStatementsIFRS-03',
        )
    else:
        return

    reportableSegmentsMemberQn = qname(pluginData.namespaces.jpcrp, "ReportableSegmentsMember")

    def _getConceptAndDescendantQNames(
            modelXbrl: ModelXbrl,
            concept: ModelConcept,
            relSet: ModelRelationshipSet,
    ) -> Iterable[QName]:
        # This is crude (doesn't handle target roles), but appears to be good enough for EDINET.
        if concept.qname is None:
            return
        yield concept.qname
        for rel in relSet.fromModelObject(concept):
            if isinstance(rel.toModelObject, ModelConcept):
                yield from _getConceptAndDescendantQNames(modelXbrl, rel.toModelObject, relSet)

    for modelXbrl in pluginData.loadedModelXbrls:
        reportableSegmentsMember = modelXbrl.qnameConcepts.get(reportableSegmentsMemberQn)
        if reportableSegmentsMember is None:
            continue
        for roleUri in roleUris:
            domainMemberRelSet = modelXbrl.relationshipSet(XbrlConst.domainMember, roleUri)
            members = set(_getConceptAndDescendantQNames(modelXbrl, reportableSegmentsMember, domainMemberRelSet))
            if members and hasPresentationalConceptsWithFacts(modelXbrl, [roleUri], members):
                return

    yield Validation.warning(
        codes='EDINET.EC8050W',
        msg=_("Segment information is not tagged in detail. "
              "Please provide detailed tagging of segment information."),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8061W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8061W: The consolidated statement of financial position has not been tagged in detail.
    If AccountingStandardsDEI = "IFRS" and WhetherConsolidatedFinancialStatementsArePreparedDEI = "true",
    then a section must exist using one of the specified roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    if pluginData.isConsolidated() != True:
        return

    accountingStandard = pluginData.getDeiValue('AccountingStandardsDEI')
    if accountingStandard != AccountingStandard.IFRS.value:
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_ConsolidatedStatementOfFinancialPositionIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_std_ConsolidatedStatementOfFinancialPositionIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualConsolidatedStatementOfFinancialPositionIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyConsolidatedStatementOfFinancialPositionIFRS',
    )

    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8061W',
        msg=_("The consolidated statement of financial position has not been tagged in detail. "
              "Please provide a detailed tag for the consolidated statement of financial position. "
              "If you do not provide a consolidated statement of financial position, please confirm that "
              'the "Consolidated Financial Statements" field in the DEI information is correct.'),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8063W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8063W: The statement of financial position has not been tagged in detail.
    If AccountingStandardsDEI = "IFRS" and WhetherConsolidatedFinancialStatementsArePreparedDEI = "false",
    then a section must exist using one of the specified roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    if pluginData.isConsolidated() != False:
        return
    accountingStandard = pluginData.getDeiValue('AccountingStandardsDEI')
    if accountingStandard != AccountingStandard.IFRS.value:
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_StatementOfFinancialPositionIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualStatementOfFinancialPositionIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyStatementOfFinancialPositionIFRS',
    )

    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8063W',
        msg=_("The statement of financial position has not been tagged in detail. "
              "Please provide detailed tagging of the statement of financial position."),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8065W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8065W: The consolidated statement of comprehensive income has not been tagged in detail.
    If AccountingStandardsDEI = "IFRS" and WhetherConsolidatedFinancialStatementsArePreparedDEI = "true",
    then a section must exist using one of the specified roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    if pluginData.isConsolidated() != True:
        return
    accountingStandard = pluginData.getDeiValue('AccountingStandardsDEI')
    if accountingStandard != AccountingStandard.IFRS.value:
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_ConsolidatedStatementOfComprehensiveIncomeSingleStatementIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualConsolidatedStatementOfComprehensiveIncomeSingleStatementIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedYearToQuarterEndConsolidatedStatementOfComprehensiveIncomeSingleStatementIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterPeriodConsolidatedStatementOfComprehensiveIncomeSingleStatementIFRS',
    )

    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8065W',
        msg=_("The consolidated statement of comprehensive income has not been tagged in detail. "
              "Please provide detailed tagging for the consolidated statement of comprehensive income. "
              "If you do not provide a consolidated statement of comprehensive income, please confirm that "
              'the "Consolidated Financial Statements" field in the DEI information is correct.'),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8066W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8066W: The statement of comprehensive income has not been tagged in detail.
    If AccountingStandardsDEI = "IFRS" and WhetherConsolidatedFinancialStatementsArePreparedDEI = "false",
    then a section must exist using one of the specified roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    if pluginData.isConsolidated() != False:
        return
    accountingStandard = pluginData.getDeiValue('AccountingStandardsDEI')
    if accountingStandard != AccountingStandard.IFRS.value:
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_StatementOfComprehensiveIncomeSingleStatementIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualStatementOfComprehensiveIncomeSingleStatementIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedYearToQuarterEndStatementOfComprehensiveIncomeSingleStatementIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterPeriodStatementOfComprehensiveIncomeSingleStatementIFRS',
    )

    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8066W',
        msg=_("The statement of comprehensive income has not been tagged in detail. "
              "Please provide detailed tagging for the statement of comprehensive income."),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8067W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8067W: The consolidated statement of changes in equity has not been tagged in detail.
    If AccountingStandardsDEI = "IFRS" and WhetherConsolidatedFinancialStatementsArePreparedDEI = "true",
    then a section must exist using one of the specified roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    if pluginData.isConsolidated() != True:
        return
    accountingStandard = pluginData.getDeiValue('AccountingStandardsDEI')
    if accountingStandard != AccountingStandard.IFRS.value:
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyConsolidatedStatementOfChangesInEquityIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualConsolidatedStatementOfChangesInEquityIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_std_ConsolidatedStatementOfChangesInEquityIFRS',
    )

    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8067W',
        msg=_("The consolidated statement of changes in equity has not been tagged in detail. "
              "Please tag the details of the consolidated statement of changes in equity. "
              "If you do not include a consolidated statement of changes in equity, please confirm that "
              'the "Consolidated" field in the DEI information is correct.'),
    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8068W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8068W: The statement of changes in equity is not tagged in detail.
    If AccountingStandardsDEI = "IFRS" and WhetherConsolidatedFinancialStatementsArePreparedDEI = "false",
    then a section must exist using one of the specified roles.
    """
    if not pluginData.hasDocumentType({DocumentType.ANNUAL_SECURITIES_REPORT, DocumentType.SEMI_ANNUAL_REPORT}):
        return

    if pluginData.isConsolidated() != False:
        return
    accountingStandard = pluginData.getDeiValue('AccountingStandardsDEI')
    if accountingStandard != AccountingStandard.IFRS.value:
        return

    roleUris = (
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_StatementOfChangesInEquityIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualStatementOfChangesInEquityIFRS',
        'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyStatementOfChangesInEquityIFRS',
    )

    for modelXbrl in pluginData.loadedModelXbrls:
        if hasPresentationalConceptsWithFacts(modelXbrl, roleUris):
            return

    yield Validation.warning(
        codes='EDINET.EC8068W',
        msg=_("The statement of changes in equity is not tagged in detail. "
              "Please provide detailed tagging of the statement of changes in equity."),
    )
