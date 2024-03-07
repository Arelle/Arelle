"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from functools import cached_property
from regex.regex import Pattern
from typing import Any, Dict, Tuple, cast

import regex as re

from arelle.ModelInstanceObject import ModelFact
from arelle.ModelXbrl import ModelXbrl

# Error codes
CH_AUDIT = 'Char.Audit'
CH_CHAR_FUND = 'Char.CharFund'
CH_DIR_REP = 'Char.DirReport'
CH_DIR_RESP = 'Char.DirResp'
CO_ABRID = 'Co.Abrid'
CO_AUDIT = 'Co.Audit'
CO_AUDIT_NR = 'Co.AuditNR'
CO_DIR_REP = 'Co.DirReport'
CO_DIR_RESP = 'Co.DirResp'
CO_MED_CO = 'Co.MedCo'
CO_MICRO = 'Co.Micro'
CO_MISSING_ELEMENT = 'Co.MissingElement'
CO_PROF_LOSS = 'Co.ProfLoss'
CO_QUAL_AUDIT = 'Co.QualAudit'
CO_SM_CO = 'Co.SmCo'
CO_SEC_477 = 'Co.Sec477'
CO_SEC_480 = 'Co.Sec480'
LP_ABRID = 'Lp.Abrid'
LP_AUDIT = 'Lp.Audit'
LP_MED_LP = 'Lp.MedLp'
LP_MEM_RESP = 'Lp.MemResp'
LP_MICRO = 'Lp.Micro'
LP_PROF_LOSS = 'Lp.ProfLoss'
LP_QUAL_AUDIT = 'Lp.QualAudit'
LP_SEC_477 = 'Lp.Sec477'
LP_SEC_480 = 'Lp.Sec480'
LP_SM_LP = 'Lp.SmLp'

# Concept local names
CONCEPT_ABRIDGED_ACCOUNTS = 'AbridgedAccounts'
CONCEPT_ABBREVIATED_ACCOUNTS = 'AbbreviatedAccounts'
CONCEPT_AUDITED = 'Audited'
CONCEPT_APPLICABLE_LEGISLATION = 'ApplicableLegislation'
CONCEPT_APPLICABLE_LEGISLATION_DIMENSION = 'ApplicableLegislationDimension'
CONCEPT_ACCOUNTING_STANDARDS_APPLIED = 'AccountingStandardsApplied'
CONCEPT_ACCOUNTING_STANDARDS_DIMENSION = 'AccountingStandardsDimension'
CONCEPT_ACCOUNTS_STATUS = 'AccountsStatusAuditedOrUnaudited'
CONCEPT_ACCOUNTS_STATUS_DIMENSION = 'AccountsStatusDimension'
CONCEPT_ACCOUNTS_TYPE_FULL_OR_ABBREVIATED = 'AccountsTypeFullOrAbbreviated'  # DEPRECATED IN 2022+ taxonomies.  No replacement yet.
CONCEPT_ACCOUNTS_TYPE_DIMENSION = 'AccountsTypeDimension'
CONCEPT_ADVERSE_OPINION = 'AdverseOpinion'
CONCEPT_CHARITY_FUNDS = 'CharityFunds'
CONCEPT_CHARITY_REGISTRATION_NUMBER_ENGLAND_WALES = 'CharityRegistrationNumberEnglandWales'
CONCEPT_CHARITY_REGISTRATION_NUMBER_NORTH_IRELAND = 'CharityRegistrationNumberNorthernIreland'
CONCEPT_CHARITY_REGISTRATION_NUMBER_SCOTLAND = 'CharityRegistrationNumberScotland'
CONCEPT_DATE_AUDITOR_REPORT = 'DateAuditorsReport'
CONCEPT_DATE_CHARITY_AUDITORS_REPORT = 'DateCharityAuditorsReport'
CONCEPT_DATE_SIGNING_DIRECTOR_REPORT = 'DateSigningDirectorsReport'
CONCEPT_DATE_SIGNING_TRUSTEES_REPORT = 'DateSigningTrusteesAnnualReport'
CONCEPT_DIRECTOR_SIGNING_DIRECTORS_REPORT = 'DirectorSigningDirectorsReport'
CONCEPT_DISCLAIMER_OPINION = 'DisclaimerOpinion'
CONCEPT_ENTITY_DORMANT = 'EntityDormantTruefalse'
CONCEPT_ENTITY_TRADING_STATUS = 'EntityTradingStatus'
CONCEPT_ENTITY_TRADING_STATUS_DIMENSION = 'EntityTradingStatusDimension'
CONCEPT_LANGUAGES_DIMENSION = 'LanguagesDimension'
CONCEPT_MEDIUM_COMPANY = 'StatementThatCompanyHasPreparedAccountsUnderProvisionsRelatingToMedium-sizedCompanies'
CONCEPT_MEDIUM_COMPANIES_REGIME_FOR_ACCOUNTS = 'Medium-sizedCompaniesRegimeForAccounts'
CONCEPT_MICRO_ENTITIES = 'Micro-entities'
CONCEPT_NAME_INDIVIDUAL_AUDITOR = 'NameIndividualAuditor'
CONCEPT_NAME_INDIVIDUAL_CHARITY_AUDITOR = 'NameIndividualCharityAuditor'
CONCEPT_NAME_ENTITY_AUDITORS = 'NameEntityAuditors'
CONCEPT_NAME_ENTITY_CHARITY_AUDITORS = 'NameEntityCharityAuditors'
CONCEPT_NAME_SENIOR_STATUTORY_AUDITOR = 'NameSeniorStatutoryAuditor'
CONCEPT_NAME_SENIOR_STATUTORY_CHARITY_AUDITOR = 'NameSeniorStatutoryCharityAuditor'
CONCEPT_OPINION_AUDITORS_ON_ENTITY = 'OpinionAuditorsOnEntity'
CONCEPT_QUALIFIED_OPINION = 'QualifiedOpinion'
CONCEPT_UNQUALIFIED_OPINION = 'UnqualifiedOpinion'
CONCEPT_LEGAL_FORM_ENTIY = 'LegalFormEntity'
CONCEPT_LEGAL_FORM_ENTIY_DIMENSION = 'LegalFormEntityDimension'
CONCEPT_LLP = 'LimitedLiabilityPartnershipLLP'
CONCEPT_PROFIT_LOSS = 'ProfitLoss'
CONCEPT_REPORT_PRINCIPAL_LANGUAGE = 'ReportPrincipalLanguage'
CONCEPT_SCOPE_ACCOUNTS = 'ScopeAccounts'
CONCEPT_SCOPE_ACCOUNTS_DIMENSION = 'ScopeAccountsDimension'
CONCEPT_STATEMENT_PROVIDED = 'StatementOnQualityCompletenessInformationProvidedToAuditors'
CONCEPT_SMALL_COMPANY_REGIME_FOR_ACCOUNTS = 'SmallCompaniesRegimeForAccounts'
CONCEPT_TRUSTEE_SIGNING_ANNUAL_REPORT = 'TrusteeSigningTrusteesAnnualReport'
CONCEPT_GROUP_ACCOUNTS_ONLY = 'GroupAccountsOnly'
CONCEPT_CONSOLIDATED_GROUP_COMPANY_ACCOUNTS = 'ConsolidatedGroupCompanyAccounts'
CONCEPT_WELSH = 'Welsh'

CHARITY_REGISTRATION_NUMBERS = [CONCEPT_CHARITY_REGISTRATION_NUMBER_ENGLAND_WALES, CONCEPT_CHARITY_REGISTRATION_NUMBER_NORTH_IRELAND, CONCEPT_CHARITY_REGISTRATION_NUMBER_SCOTLAND]

# Map of error code > concept local name > tuple of pairings of descriptions and regex patterns
TEXT_VALIDATION_PATTERNS: dict[str, dict[str, tuple[tuple[str, re.regex.Pattern[str]], ...]]] = {
    CH_DIR_RESP: {
        'StatementThatDirectorsAcknowledgeTheirResponsibilitiesUnderCompaniesAct': (
            (
                '"Directors acknowledge" or "Director acknowledges" or "Trustees acknowledge" or "Trustee acknowledges", then "responsibilities", then "Companies Act 2006" OR "the Act"',
                re.compile(r".*(Director acknowledges|Directors acknowledge|Trustees acknowledge|Trustee acknowledges).*responsibilities.*(Companies Act 2006|the Act).*"),
            ),
            (
                '"Cyfarwyddwyr yn cydnabod" or "Cyfarwyddwr yn cydnabod" or "ymddiriedolwyr yn cydnabod" or "ymddiriedolwr yn cydnabod", then "cyfrifoldebau", then "Ddeddf Cwmnïau 2006" or "y ddeddf"',
                re.compile(r".*(Cyfarwyddwyr yn cydnabod|Cyfarwyddwr yn cydnabod|ymddiriedolwyr yn cydnabod|ymddiriedolwr yn cydnabod).*cyfrifoldebau.*(Ddeddf Cwmnïau 2006|y ddeddf).*"),
            ),
        ),
    },
    CO_ABRID: {
        'StatementThatMembersHaveAgreedToPreparationAbridgedAccountsUnderSection444CompaniesAct2006': (
            (
                'Members" or "Member", then "agreed" or "consented", then "preparation", then "abridged")',
                re.compile(r".*(Members|Member).*(agreed|consented).*preparation.*abridged.*"),
            ),
            (
                '"Aelodau" or "Aelod", then "wedi cytuno" or "cydsynio", then "paratoi", then "talfyredig")',
                re.compile(r".*(Aelodau|Aelod).*(wedi cytuno|cydsynio).*paratoi.*talfyredig.*"),
            ),
        ),
    },
    CO_AUDIT_NR: {
        'StatementThatMembersHaveNotRequiredCompanyToObtainAnAudit': (
            (
                '"member has" or "members have" then "not required the company to obtain an audit"',
                re.compile(r".*([Mm]ember has|[Mm]embers have) not required the company to obtain an audit.*"),
            ),
            (
                '"aelodau heb ei gwneud yn ofynnol i\'r cwmni gael archwiliad" OR "aelod heb ei gwneud yn ofynnol i\'r cwmni gael archwiliad"',
                re.compile(r".*(aelodau heb ei gwneud yn ofynnol i\'r cwmni gael archwiliad|aelod heb ei gwneud yn ofynnol i\'r cwmni gael archwiliad).*"),
            ),
        ),
    },
    CO_DIR_RESP: {
        'StatementThatDirectorsAcknowledgeTheirResponsibilitiesUnderCompaniesAct': (
            (
                '"Directors acknowledge" or "Director acknowledges", then "responsibilities", then "Companies Act 2006" OR "the Act"',
                re.compile(r".*(Director acknowledges|Directors acknowledge).*responsibilities.*(Companies Act 2006|the Act).*"),
            ),
            (
                '"Cyfarwyddwyr yn cydnabod" or "Cyfarwyddwr yn cydnabod", then "cyfrifoldebau", then "Ddeddf Cwmnïau 2006" or "y ddeddf"',
                re.compile(r".*(Cyfarwyddwyr yn cydnabod|Cyfarwyddwr yn cydnabod).*cyfrifoldebau.*(Ddeddf Cwmnïau 2006|y ddeddf).*"),
            ),
        ),
    },
    CO_MICRO: {
        'StatementThatAccountsHaveBeenPreparedInAccordanceWithProvisionsSmallCompaniesRegime': (
            (
                '"Prepared", then "in accordance with", then "provisions", then "micro"',
                re.compile(r".*Prepared.*in accordance with.*provisions.*micro.*"),
            ),
            (
                '"wedi eu paratoi", then "yn unol â", then "darpariaethau", then "micro"',
                re.compile(r".*wedi eu paratoi.*yn unol â.*darpariaethau.*micro.*"),
            ),
        ),
    },
    CO_SEC_477: {
        'StatementThatCompanyEntitledToExemptionFromAuditUnderSection477CompaniesAct2006RelatingToSmallCompanies': (
            (
                '"Exempt" or "Exemption", then later "section 477 of the Companies Act 2006"',
                re.compile(r".*(Exempt|Exemption).*section 477 of the Companies Act 2006.*"),
            ),
            (
                '"Wedi\'i eithrio" or "Eithriad", then "adran 477 o Ddeddf Cwmnïau 2006"',
                re.compile(r".*(Wedi'i eithrio|Eithriad).*adran 477 o Ddeddf Cwmnïau 2006.*"),
            ),
        ),
    },
    CO_SEC_480: {
        'StatementThatCompanyEntitledToExemptionFromAuditUnderSection480CompaniesAct2006RelatingToDormantCompanies': (
            (
                '"Exempt" or "Exemption", then later "section 480 of the Companies Act 2006"',
                re.compile(r".*(Exempt|Exemption).*section 480 of the Companies Act 2006.*"),
            ),
            (
                '"Wedi\'i eithrio" or "Eithriad", then "adran 480 o Ddeddf Cwmnïau 2006"',
                re.compile(r".*(Wedi'i eithrio|Eithriad).*adran 480 o Ddeddf Cwmnïau 2006.*"),
            ),
        ),
    },
    CO_SM_CO: {
        'StatementThatAccountsHaveBeenPreparedInAccordanceWithProvisionsSmallCompaniesRegime': (
            (
                '"Prepared in accordance with", then "provisions", then "small companies"',
                re.compile(r".*Prepared in accordance with.*provisions.*small companies.*"),
            ),
            (
                '"Paratowyd yn unol â", then "darpariaethau", then "cwmnïau bach"',
                re.compile(r".*Paratowyd yn unol â.*darpariaethau.*cwmnïau bach.*"),
            ),
        ),
    },
    LP_ABRID: {
        'StatementThatMembersHaveAgreedToPreparationAbridgedAccountsUnderSection444CompaniesAct2006': (
            (
                'Members" or "Member", then "agreed" or "consented", then "preparation", then "abridged")',
                re.compile(r".*(Members|Member).*(agreed|consented).*preparation.*abridged.*"),
            ),
            (
                '"Aelodau" or "Aelod", then "wedi cytuno" or "cydsynio", then "paratoi", then "talfyredig")',
                re.compile(r".*(Aelodau|Aelod).*(wedi cytuno|cydsynio).*paratoi.*talfyredig.*"),
            ),
        ),
    },
    LP_MEM_RESP: {
            'StatementThatDirectorsAcknowledgeTheirResponsibilitiesUnderCompaniesAct': (
                (
                    '"Members acknowledge" or "Member acknowledges", then "responsibilities", then  "Companies Act 2006" or "the Act", then "Limited Liability Partnership" or "LLP"',
                    re.compile(r".*(Members acknowledge|Member acknowledges).*responsibilities.*(Companies Act 2006|the Act).*(Limited Liability Partnership|LLP).*"),
                ),
                (
                    '"Aelodau\'n cydnabod" or "Aelod yn cydnabod", then "cyfrifoldebau", then "Ddeddf Cwmnïau 2006" or "y Ddeddf", then "Partneriaeth Atebolrwydd Cyfyngedig" or "PAC"',
                    re.compile(r".*(Aelodau'n cydnabod|Aelod yn cydnabod).*cyfrifoldebau.*(Ddeddf Cwmnïau 2006|y Ddeddf).*(Partneriaeth Atebolrwydd Cyfyngedig|PAC).*"),
                ),
            ),
    },
    LP_MICRO: {
        'StatementThatAccountsHaveBeenPreparedInAccordanceWithProvisionsSmallCompaniesRegime': (
            (
                '"Prepared", then "in accordance with", then "provisions", then "micro"',
                re.compile(r".*Prepared.*in accordance with.*provisions.*micro.*"),
            ),
            (
                '"wedi eu paratoi", then "yn unol â", then "darpariaethau", then "micro"',
                re.compile(r".*wedi eu paratoi.*yn unol â.*darpariaethau.*micro.*"),
            ),
        ),
    },
    LP_SEC_477: {
        'StatementThatCompanyEntitledToExemptionFromAuditUnderSection477CompaniesAct2006RelatingToSmallCompanies': (
            (
                '"Exempt" OR "Exemption", then "section 477 of the Companies Act 2006" then, "Limited Liability Partnership" OR "LLP")',
                re.compile(r".*(Exempt|Exemption).*section 477 of the Companies Act 2006.*(Limited Liability Partnership|LLP).*"),
            ),
            (
                '"Wedi\'i eithrio" or "Eithriad", then "adran 477 o Ddeddf Cwmnïau 2006", then "Partneriaeth Atebolrwydd Cyfyngedig" OR "PAC"',
                re.compile(r".*(Wedi'i eithrio|Eithriad).*adran 477 o Ddeddf Cwmnïau 2006.*(Partneriaeth Atebolrwydd Cyfyngedig|PAC).*"),
            ),
        ),
    },
    LP_SEC_480: {
            'StatementThatCompanyEntitledToExemptionFromAuditUnderSection480CompaniesAct2006RelatingToDormantCompanies': (
                (
                    '"Exempt" or "Exemption", then "section 480 of the Companies Act 2006", then "Limited Liability Partnership" OR "LLP"',
                    re.compile(r".*(Exempt|Exemption).*section 480 of the Companies Act 2006.*(Limited Liability Partnership|LLP).*"),
                ),
                (
                    '"Wedi\'i eithrio" or "Eithriad", then "adran 480 o Ddeddf Cwmnïau 2006"',
                    re.compile(r".*(Wedi'i eithrio|Eithriad).*adran 480 o Ddeddf Cwmnïau 2006.*(Partneriaeth Atebolrwydd Cyfyngedig|PAC).*"),
                ),
            ),
    },
    LP_SM_LP: {
        'StatementThatAccountsHaveBeenPreparedInAccordanceWithProvisionsSmallCompaniesRegime': (
            (
                '"Prepared in accordance with", then "provisions", then "small Limited Liability Partnership" OR "small LLP',
                re.compile(r".*Prepared in accordance with.*provisions.*(small Limited Liability Partnership|small LLP).*"),
            ),
            (
                '"Paratowyd yn unol â", then "y darpariaethau", then "Partneriaeth Atebolrwydd Cyfyngedig bach" or "PAC bach")',
                re.compile(r".*Paratowyd yn unol â.*y darpariaethau.*(Partneriaeth Atebolrwydd Cyfyngedig bach|PAC bach).*"),
            ),
        ),
    },
}

# Map of codes > dict of local name and warning level boolean
SINGLE_CONCEPT_EVALUATIONS: dict[str, dict[str, bool]] = {
    CO_MED_CO: {CONCEPT_MEDIUM_COMPANY: True},
    LP_MED_LP: {CONCEPT_MEDIUM_COMPANY: True},
    CO_QUAL_AUDIT: {CONCEPT_STATEMENT_PROVIDED: False},
    LP_QUAL_AUDIT: {CONCEPT_STATEMENT_PROVIDED: False},
}


class AccountStatus(Enum):
    AUDIT_EXEMPT_NO_REPORT = 'AuditExempt-NoAccountantsReport'
    AUDIT_EXEMPT_WITH_REPORT = 'AuditExemptWithAccountantsReport'


class NotTrading(Enum):
    CONCEPT_ENTITY_HAS_NEVER_TRADED = 'EntityHasNeverTraded'
    CONCEPT_ENTITY_NO_LONGER_TRADING = 'EntityNoLongerTradingButTradedInPast'


class ScopeAccounts(Enum):
    GROUP_ONLY = 'GroupAccountsOnly'
    CONSOLIDATED_GROUP = 'ConsolidatedGroupCompanyAccounts'


@dataclass
class CodeResult:
    success: bool = field(default=True)
    conceptLocalName: str | None = field(default=None)
    conceptList: list[str] | None = field(default=None)
    fact: ModelFact | None = field(default=None)
    message: str | None = field(default=None)
    warning: bool = field(default=False)


class HmrcLang(Enum):
    ENGLISH = 0
    WELSH = 1


@dataclass
class ValidateHmrc:
    modelXbrl: ModelXbrl
    _codeResultMap: dict[str, CodeResult] = field(default_factory=dict)

    def _checkValidFact(self, fact: ModelFact ) -> bool:
        if fact is not None:
            if not fact.isNil:
                return True
        return False

    def _errorOnMissingFact(self, conceptLocalName: str) -> None:
        """
        Logs an error explaining that a fact of the given concept was missing.
        :param conceptLocalName:
        """
        self.modelXbrl.error(
            CO_MISSING_ELEMENT,
            "Based on facts regarding Entity and Report Information provided, "
            "your document is expected to have a fact tagged with the following concept: %(conceptLocalName)s.",
            conceptLocalName=conceptLocalName
        )

    def _errorOnMissingFactText(self, code: str, result: CodeResult) -> None:
        """
        Logs an error on the `ModelXbrl` explaining the actual fact value did not match expected patterns.
        If a fact of the expected type did not exist, an additional error will be logged.
        :param code:
        :param result:
        """
        if result.fact is None and result.conceptLocalName is not None:
            self._errorOnMissingFact(result.conceptLocalName)
        self.modelXbrl.error(
            code,
            "The value for the the fact tagged with the concept %(conceptLocalName)s "
            "is missing the text for language '%(lang)s': %(message)s",
            conceptLocalName=result.conceptLocalName,
            lang=self._lang.name.title(),
            message=result.message,
            modelObject=result.fact,
        )

    def _setCode(self, code: str, result: CodeResult) -> CodeResult:
        """
        Caches the given result for the given code.
        :param code:
        :param result:
        :return: The given result.
        """
        self._codeResultMap[code] = result
        return result

    def _evaluateTextPattern(self, code: str) -> CodeResult:
        pattern: dict[str, tuple[tuple[str, Pattern[str]], ...]] | Any = TEXT_VALIDATION_PATTERNS.get(code, {})
        for conceptLocalName, textMatchers in pattern.items():
            facts = self._getFacts(conceptLocalName)
            if not facts:
                return CodeResult(
                    success=False,
                    conceptLocalName=conceptLocalName
                )
            for fact in facts:
                message, pattern = textMatchers[self._lang.value]
                match = pattern.match(fact.value, re.MULTILINE)
                if not match:
                    return CodeResult(
                        success=False,
                        conceptLocalName=conceptLocalName,
                        fact=fact,
                        message=message
                    )
        return CodeResult()

    def _evaluateDirectorFacts(self, code: str) -> CodeResult:
        """
        Logs an error when an audited report does not facts tagged with the concepts of "DateSigningDirectorsReport" and "DirectorSigningDirectorsReport,
        or DateSigningTrusteesAnnualReport and TrusteeSigningTrusteesAnnualReport (for charities)."
        :return:
        """
        missingConcepts = []
        if not self._getAndCheckValidFacts([CONCEPT_DATE_SIGNING_DIRECTOR_REPORT]):
            missingConcepts.append(CONCEPT_DATE_SIGNING_DIRECTOR_REPORT)
        if not self._getAndCheckValidFacts([CONCEPT_DIRECTOR_SIGNING_DIRECTORS_REPORT]):
            missingConcepts.append(CONCEPT_DIRECTOR_SIGNING_DIRECTORS_REPORT)
        if len(missingConcepts) > 0:
            if code == CO_DIR_REP:
                return CodeResult(
                        success=False,
                        conceptList=missingConcepts,
                        message="Facts tagged with the DateSigningDirectorsReport and DirectorSigningDirectorsReport must exist with non-nil values. "
                                "There are no facts tagged with the concepts: %(conceptList)s.",
                    )
            elif code == CH_DIR_REP:
                missingCharConcepts = []
                if not self._getAndCheckValidFacts([CONCEPT_DATE_SIGNING_TRUSTEES_REPORT]):
                    missingCharConcepts.append(CONCEPT_DATE_SIGNING_TRUSTEES_REPORT)
                if not self._getAndCheckValidFacts([CONCEPT_TRUSTEE_SIGNING_ANNUAL_REPORT]):
                    missingCharConcepts.append(CONCEPT_TRUSTEE_SIGNING_ANNUAL_REPORT)
                if len(missingCharConcepts) > 0:
                    missingConcepts.extend(missingCharConcepts)
                    return CodeResult(
                        success=False,
                        conceptList=missingConcepts,
                        message="A set of facts must exist with non-nil values with the concepts of DateSigningDirectorsReport and DirectorSigningDirectorsReport "
                                "or DateSigningTrusteesAnnualReport and TrusteeSigningTrusteesAnnualReport. "
                                "There are no facts tagged with the concepts: %(conceptList)s.",
                    )
        return CodeResult()

    def _evaluateAuditFacts(self) -> CodeResult:
        """
        Logs an error when an audited report does not facts tagged with the concepts of "DateAuditorsReport" and  "OpinionAuditorsOnEntity"
        as well as either "NameIndividualAuditor" or the combination of "NameSeniorStatutoryAuditor" and "NameEntityAuditors".
        :return:
        """
        missingConcepts = []
        if not self._getAndCheckValidFacts([CONCEPT_DATE_AUDITOR_REPORT]):
            missingConcepts.append(CONCEPT_DATE_AUDITOR_REPORT)
        if not self._getAndCheckValidFacts([CONCEPT_OPINION_AUDITORS_ON_ENTITY]):
            missingConcepts.append(CONCEPT_OPINION_AUDITORS_ON_ENTITY)
        if (not (self._getAndCheckValidFacts([CONCEPT_NAME_ENTITY_AUDITORS]) and self._getAndCheckValidFacts([CONCEPT_NAME_SENIOR_STATUTORY_AUDITOR]))
                and not self._getAndCheckValidFacts([CONCEPT_NAME_INDIVIDUAL_AUDITOR])):
            missingConcepts.append(CONCEPT_NAME_INDIVIDUAL_AUDITOR)
            missingConcepts.append(CONCEPT_NAME_SENIOR_STATUTORY_AUDITOR)
            missingConcepts.append(CONCEPT_NAME_ENTITY_AUDITORS)
        if len(missingConcepts) > 0:
            return CodeResult(
                success=False,
                conceptList=missingConcepts,
                message="An audited report must contain facts tagged with the concepts of DateAuditorsReport, OpinionAuditorsOnEntity "
                        "as well as either NameIndividualAuditor or the combination of NameSeniorStatutoryAuditor and NameEntityAuditors. "
                        "There are no facts tagged with the concepts: %(conceptList)s."
            )
        return CodeResult()

    def _evaluateCharAuditFacts(self) -> CodeResult:
        """
        Logs an error when a charity report does not facts tagged with the concepts of "DateAuditorsReport" or "DateCharityAuditorsReport"
        and "OpinionAuditorsOnEntity" or "QualifiedOpinion" or "UnqualifiedOpinion" or "AdverseOpinion" or "DisclaimerOpinion"
        and "NameIndividualAuditor" or "NameIndividualCharityAuditor" or ("NameSeniorStatutoryAuditor" and "NameEntityAuditors") or ("NameSeniorStatutoryCharityAuditor" and "NameEntityCharityAuditors")
        :return:
        """
        missingConcepts = []
        if not self._getAndCheckValidFacts([CONCEPT_DATE_AUDITOR_REPORT, CONCEPT_DATE_CHARITY_AUDITORS_REPORT]):
            missingConcepts.extend([CONCEPT_DATE_AUDITOR_REPORT, CONCEPT_DATE_CHARITY_AUDITORS_REPORT])
        if not self._getAndCheckValidFacts(
                [CONCEPT_OPINION_AUDITORS_ON_ENTITY, CONCEPT_QUALIFIED_OPINION, CONCEPT_UNQUALIFIED_OPINION, CONCEPT_ADVERSE_OPINION, CONCEPT_DISCLAIMER_OPINION]
        ):
            missingConcepts.extend(
                [CONCEPT_OPINION_AUDITORS_ON_ENTITY, CONCEPT_QUALIFIED_OPINION, CONCEPT_UNQUALIFIED_OPINION, CONCEPT_ADVERSE_OPINION, CONCEPT_DISCLAIMER_OPINION]
            )
        if not self._getAndCheckValidFacts([CONCEPT_NAME_INDIVIDUAL_AUDITOR, CONCEPT_NAME_INDIVIDUAL_CHARITY_AUDITOR]):
            if not (self._getAndCheckValidFacts([CONCEPT_NAME_SENIOR_STATUTORY_AUDITOR]) and self._getAndCheckValidFacts([CONCEPT_NAME_ENTITY_AUDITORS])):
                if not (self._getAndCheckValidFacts([CONCEPT_NAME_SENIOR_STATUTORY_CHARITY_AUDITOR]) and self._getAndCheckValidFacts([CONCEPT_NAME_ENTITY_CHARITY_AUDITORS])):
                    missingConcepts.extend(
                        [
                            CONCEPT_NAME_INDIVIDUAL_AUDITOR, CONCEPT_NAME_INDIVIDUAL_CHARITY_AUDITOR, CONCEPT_NAME_SENIOR_STATUTORY_AUDITOR, CONCEPT_NAME_ENTITY_AUDITORS,
                            CONCEPT_NAME_SENIOR_STATUTORY_CHARITY_AUDITOR, CONCEPT_NAME_ENTITY_CHARITY_AUDITORS
                        ]
                    )
        if len(missingConcepts) > 0:
            return CodeResult(
                success=False,
                conceptList=missingConcepts,
                message="Audited charities accounts submission missing required audit-related information. Audited charity accounts submissions are required to include facts for: "
                        "i) DateAuditorsReport or DateCharityAuditorsReport "
                        "ii) OpinionAuditorsOnEntity, QualifiedOpinion, UnqualifiedOpinion, AdverseOpinion, or DisclaimerOpinion "
                        "iii) NameIndividualAuditor, NameIndividualCharityAuditor, OR either (NameSeniorStatutoryAuditor and NameEntityAuditors) or (NameSeniorStatutoryCharityAuditor and NameEntityCharityAuditors) "
                        "There are no facts tagged with the concepts: %(conceptList)s"
            )
        return CodeResult()

    def _evaluateRequiredSingleFact(self, code: str) -> CodeResult:
        """
        Logs a warning or error if the fact tied to the code is not found.
        """
        conceptAndLevel = SINGLE_CONCEPT_EVALUATIONS.get(code, {})
        for conceptLocalName, warning in conceptAndLevel.items():
            if not self._getAndCheckValidFacts([conceptLocalName]):
                return CodeResult(
                    success=False,
                    warning=warning,
                    message="The concept of %(conceptLocalName)s must exist and have a non-nil value.",
                    conceptLocalName=conceptLocalName,
                )
        return CodeResult()

    def _evaluateProfLossOrCharityFundsFact(self, code: str) -> CodeResult:
        """
        Logs an error if EntityTradingStatus with the dimension of EntityTradingStatusDimension/(EntityHasNeverTraded OR EntityNoLongerTradingButTradedInPast)
        or (ProfitLoss for a company/LLP of CharityFunds for a charity)
        """
        concept = ''
        if code in (CO_PROF_LOSS, LP_PROF_LOSS):
            concept = CONCEPT_PROFIT_LOSS
        elif code == CH_CHAR_FUND:
            concept = CONCEPT_CHARITY_FUNDS
        trading = False
        for fact in self._getFacts(CONCEPT_ENTITY_TRADING_STATUS):
            if fact is None or fact.context is None:
                continue
            for qname, value in fact.context.qnameDims.items():
                if qname.localName == CONCEPT_ENTITY_TRADING_STATUS_DIMENSION:
                    if value.xValue.localName in {
                        NotTrading.CONCEPT_ENTITY_NO_LONGER_TRADING.value,
                        NotTrading.CONCEPT_ENTITY_HAS_NEVER_TRADED.value,
                    }:
                        trading = True
        if not self._getAndCheckValidFacts([concept]) and not trading:
            return CodeResult(
                    conceptLocalName=concept,
                    success=False,
                    message="A fact tagged with %(conceptLocalName)s must exist if a fact tagged with EntityTradingStatus "
                            "with the dimension of EntityTradingStatusDimension/(EntityHasNeverTraded OR EntityNoLongerTradingButTradedInPast) "
                            "does not exist or has a nil value"
                )
        return CodeResult()

    def _evaluateCode(self, code: str) -> CodeResult:
        """
        Evaluates whether the conditions associated with the given code pass.
        Result is cached.
        :param code:
        :return: Result object that can be used for additional logic or to trigger an error.
        """
        if code in self._codeResultMap:
            return self._codeResultMap[code]
        if code in TEXT_VALIDATION_PATTERNS:
            result = self._evaluateTextPattern(code)
        elif code in (CO_AUDIT, LP_AUDIT):
            result = self._evaluateAuditFacts()
        elif code in (CH_DIR_REP, CO_DIR_REP):
            result = self._evaluateDirectorFacts(code)
        elif code in SINGLE_CONCEPT_EVALUATIONS:
            result = self._evaluateRequiredSingleFact(code)
        elif code in (CH_CHAR_FUND, CO_PROF_LOSS, LP_PROF_LOSS):
            result = self._evaluateProfLossOrCharityFundsFact(code)
        elif code == CH_AUDIT:
            result = self._evaluateCharAuditFacts()
        return self._setCode(code, result)

    def _getFacts(self, conceptLocalName: str) -> list[ModelFact]:
        return [f for f in self.modelXbrl.factsByLocalName.get(conceptLocalName, set()) if f is not None]

    def _getAndCheckValidFacts(self, conceptLocalNames: list[str]) -> bool:
        for concept in conceptLocalNames:
            facts = self._getFacts(concept)
            if any(self._checkValidFact(x) for x in facts):
                return True
        return False

    @cached_property
    def _lang(self) -> HmrcLang:
        """
        Determines if the language is set to Welsh, otherwise defaults to English.
        """
        for fact in self._getFacts(CONCEPT_REPORT_PRINCIPAL_LANGUAGE):
            if fact is None or fact.context is None:
                continue
            for qname, value in fact.context.qnameDims.items():
                if qname.localName == CONCEPT_LANGUAGES_DIMENSION:
                    if value.xValue.localName == CONCEPT_WELSH:
                        return HmrcLang.WELSH
        return HmrcLang.ENGLISH

    def _yieldErrorOrWarning(self, code: str, result: CodeResult) -> None:
        """
        Logs an error on the `ModelXbrl` explaining the actual fact value did not match expected patterns.
        If a fact of the expected type did not exist, an additional error will be logged.
        :param code:
        :param result:
        """
        if result.message is None:
            result.message = ''
        if not result.warning:
            self.modelXbrl.error(
                code,
                msg=result.message,
                conceptList=result.conceptList,
                conceptLocalName=result.conceptLocalName,
                message=result.message,
                modelObject=result.fact,
            )
        else:
            self.modelXbrl.warning(
                code,
                msg=result.message,
                conceptList=result.conceptList,
                conceptLocalName=result.conceptLocalName,
                message=result.message,
                modelObject=result.fact,
            )

    @cached_property
    def accountStatus(self) -> str | None:
        facts = self._getFacts(CONCEPT_ACCOUNTS_STATUS)
        for fact in facts:
            if not self._checkValidFact(fact):
                continue
            for qname, value in fact.context.qnameDims.items():
                if qname.localName == CONCEPT_ACCOUNTS_STATUS_DIMENSION:
                    return cast(str, value.xValue.localName)
        return None

    @cached_property
    def accountsType(self) -> str | None:
        facts = self._getFacts(CONCEPT_ACCOUNTS_TYPE_FULL_OR_ABBREVIATED)
        for fact in facts:
            if not self._checkValidFact(fact):
                continue
            for qname, value in fact.context.qnameDims.items():
                if qname.localName == CONCEPT_ACCOUNTS_TYPE_DIMENSION:
                    return cast(str, value.xValue.localName)
        return None

    @cached_property
    def accountingStandardsApplied(self) -> str | None:
        facts = self._getFacts(CONCEPT_ACCOUNTING_STANDARDS_APPLIED)
        for fact in facts:
            if not self._checkValidFact(fact):
                continue
            for qname, value in fact.context.qnameDims.items():
                if qname.localName == CONCEPT_ACCOUNTING_STANDARDS_DIMENSION:
                    return cast(str, value.xValue.localName)
        return None

    @cached_property
    def applicableLegislation(self) -> str | None:
        facts = self._getFacts(CONCEPT_APPLICABLE_LEGISLATION)
        for fact in facts:
            if not self._checkValidFact(fact):
                continue
            for qname, value in fact.context.qnameDims.items():
                if qname.localName == CONCEPT_APPLICABLE_LEGISLATION_DIMENSION:
                    return cast(str, value.xValue.localName)
        return None

    @cached_property
    def isEntityDormant(self) -> bool:
        facts = self._getFacts(CONCEPT_ENTITY_DORMANT)
        if not facts:
            return False
        return all(not f.isNil and isinstance(f.xValue, bool) and f.xValue for f in facts)

    @cached_property
    def legalFormEntity(self) -> str | None:
        facts = self._getFacts(CONCEPT_LEGAL_FORM_ENTIY)
        for fact in facts:
            if not self._checkValidFact(fact):
                continue
            for qname, value in fact.context.qnameDims.items():
                if qname.localName == CONCEPT_LEGAL_FORM_ENTIY_DIMENSION:
                    return cast(str, value.xValue.localName)
        return None

    @cached_property
    def scopeAccounts(self) -> str | None:
        facts = self._getFacts(CONCEPT_SCOPE_ACCOUNTS)
        for fact in facts:
            if not self._checkValidFact(fact):
                continue
            for qname, value in fact.context.qnameDims.items():
                if qname.localName == CONCEPT_SCOPE_ACCOUNTS_DIMENSION:
                    return cast(str, value.xValue.localName)
        return None

    def validate(self) -> None:
        """
        Find the appropriate set of validations to run on this document and runs them.
        """
        if self.accountStatus in {
            AccountStatus.AUDIT_EXEMPT_NO_REPORT.value,
            AccountStatus.AUDIT_EXEMPT_WITH_REPORT.value,
        }:
            if self.isEntityDormant:
                if self.legalFormEntity == CONCEPT_LLP:
                    self.validateUnauditedDormantLLP()
                else:
                    self.validateUnauditedDormantCompany()
            elif self.accountingStandardsApplied == CONCEPT_MICRO_ENTITIES:
                if self.legalFormEntity == CONCEPT_LLP:
                    self.validateUnauditedMicroLLP()
                else:
                    self.validateUnauditedMicroCompany()
            elif self.accountsType == CONCEPT_ABRIDGED_ACCOUNTS:
                if self.legalFormEntity == CONCEPT_LLP:
                    self.validateUnauditedLLPAbridgedAccounts()
                else:
                    self.validateUnauditedCompanyAbridgedAccounts()
            elif self.accountsType == CONCEPT_ABBREVIATED_ACCOUNTS:
                if self.legalFormEntity == CONCEPT_LLP:
                    self.validateUnauditedLLPAbbreviatedAccounts()
                else:
                    self.validateUnauditedCompanyAbbreviatedAccounts()
            elif self.scopeAccounts in {
                ScopeAccounts.GROUP_ONLY.value,
                ScopeAccounts.CONSOLIDATED_GROUP.value,
            }:
                if self.legalFormEntity == CONCEPT_LLP:
                    self.validateUnauditedLLPGroupAccounts()
                else:
                    self.validateUnauditedCompanyGroupAccounts()
            else:
                if self.legalFormEntity == CONCEPT_LLP and self.applicableLegislation == CONCEPT_SMALL_COMPANY_REGIME_FOR_ACCOUNTS :
                    self.validateUnauditedLLPFullAccounts()
                else:
                    self.validateUnauditedSmallCompanyFullAccounts()
        elif self.accountStatus == CONCEPT_AUDITED:
            if self.accountsType == CONCEPT_ABRIDGED_ACCOUNTS:
                if self.legalFormEntity == CONCEPT_LLP:
                    self.validateAuditedAbridgedLLPAccounts()
                else:
                    self.validateAuditedCompanyAbridgedAccounts()
            elif self.applicableLegislation == CONCEPT_SMALL_COMPANY_REGIME_FOR_ACCOUNTS:
                if self.legalFormEntity == CONCEPT_LLP:
                    self.validateAuditedSmallLLP()
                else:
                    self.validateAuditedSmallCompany()
            elif self.applicableLegislation == CONCEPT_MEDIUM_COMPANIES_REGIME_FOR_ACCOUNTS:
                if self.legalFormEntity == CONCEPT_LLP:
                    self.validateAuditedMediumLLP()
                else:
                    self.validateAuditedMediumCompany()
            elif self.accountingStandardsApplied == CONCEPT_MICRO_ENTITIES:
                if self.legalFormEntity == CONCEPT_LLP:
                    self.validateAuditedMicroLLP()
                else:
                    self.validateAuditedMicroCompany()
            elif not (self.scopeAccounts in {
                ScopeAccounts.GROUP_ONLY.value,
                ScopeAccounts.CONSOLIDATED_GROUP.value,
            } or self.accountsType == CONCEPT_ABRIDGED_ACCOUNTS or self.applicableLegislation == CONCEPT_SMALL_COMPANY_REGIME_FOR_ACCOUNTS):
                if self.legalFormEntity == CONCEPT_LLP:
                    self.validateAuditedOtherLLP()
                else:
                    self.validateAuditedOtherCompany()

    def validateCharities(self) -> None:
        """
        Find the appropriate set of validations to run on this document and runs them.
        """
        if self._getAndCheckValidFacts(CHARITY_REGISTRATION_NUMBERS):
            if self.accountStatus == CONCEPT_AUDITED:
                if self.applicableLegislation == CONCEPT_SMALL_COMPANY_REGIME_FOR_ACCOUNTS:
                    if self.legalFormEntity != CONCEPT_LLP:
                        self.validateAuditedSmallCharity()

                elif not (self.scopeAccounts in {
                            ScopeAccounts.GROUP_ONLY.value,
                            ScopeAccounts.CONSOLIDATED_GROUP.value,
                        } or self.accountsType == CONCEPT_ABRIDGED_ACCOUNTS):
                    self.validateAuditedOtherCharity()
            elif self.accountStatus in {
                AccountStatus.AUDIT_EXEMPT_NO_REPORT.value,
                AccountStatus.AUDIT_EXEMPT_WITH_REPORT.value,
            }:
                if self.isEntityDormant:
                    self.validateUnauditedDormantCharity()
                else:
                    self.validateUnauditedCharitySmallAndGroupAccounts()

    def validateAuditedAbridgedLLPAccounts(self) -> None:
        """
        Checks conditions applicable to audited abridged LLP accounts:
        Lp.Abrid, lp.Audit, and Lp.Smlp
        """
        result = self._evaluateCode(LP_ABRID)
        if not result.success:
            self._errorOnMissingFactText(LP_ABRID, result)
        result = self._evaluateCode(LP_SM_LP)
        if not result.success:
            self._errorOnMissingFactText(LP_SM_LP, result)
        result = self._evaluateCode(LP_AUDIT)
        if not result.success:
            self._yieldErrorOrWarning(LP_AUDIT, result)

    def validateAuditedCompanyAbridgedAccounts(self) -> None:
        """
        Checks conditions applicable to audited company abridged accounts:
        Co.Abrid, Co.Audit, and Co.SmCo
        """
        result = self._evaluateCode(CO_ABRID)
        if not result.success:
            self._errorOnMissingFactText(CO_ABRID, result)
        result = self._evaluateCode(CO_SM_CO)
        if not result.success:
            self._errorOnMissingFactText(CO_SM_CO, result)
        result = self._evaluateCode(CO_AUDIT)
        if not result.success:
            self._yieldErrorOrWarning(CO_AUDIT, result)

    def validateAuditedMediumCompany(self) -> None:
        """
        Checks conditions applicable to audited medium company filings:
        Co.Audit, and Co.MedCo
        """
        result = self._evaluateCode(CO_MED_CO)
        if not result.success:
            self._yieldErrorOrWarning(CO_MED_CO, result)
        result = self._evaluateCode(CO_AUDIT)
        if not result.success:
            self._yieldErrorOrWarning(CO_AUDIT, result)

    def validateAuditedMediumLLP(self) -> None:
        """
        Checks conditions applicable to audited medium llp filings:
        Lp.Audit, and Lp.MedLp
        """
        result = self._evaluateCode(LP_MED_LP)
        if not result.success:
            self._yieldErrorOrWarning(LP_MED_LP, result)
        result = self._evaluateCode(LP_AUDIT)
        if not result.success:
            self._yieldErrorOrWarning(LP_AUDIT, result)

    def validateAuditedMicroCompany(self) -> None:
        """
        Checks conditions applicable to audited micro company filings:
        Co.Micro and (Co.SmCo or Co.ProfLoss)
        """
        result = self._evaluateCode(CO_MICRO)
        if not result.success:
            self._errorOnMissingFactText(CO_MICRO, result)
        result = self._evaluateCode(CO_SM_CO)
        if not result.success:
            pLResult = self._evaluateCode(CO_PROF_LOSS)
            if not pLResult.success:
                self._errorOnMissingFactText(CO_SM_CO, result)
                self._yieldErrorOrWarning(CO_PROF_LOSS, pLResult)

    def validateAuditedMicroLLP(self) -> None:
        """
        Checks conditions applicable to audited micro LLP filings:
        LP.Micro and (Lp.SmLp or Lp.ProfLoss)
        """
        result = self._evaluateCode(LP_MICRO)
        if not result.success:
            self._errorOnMissingFactText(LP_MICRO, result)
        result = self._evaluateCode(LP_SM_LP)
        if not result.success:
            pLResult = self._evaluateCode(LP_PROF_LOSS)
            if not pLResult.success:
                self._errorOnMissingFactText(LP_SM_LP, result)
                self._yieldErrorOrWarning(LP_PROF_LOSS, pLResult)

    def validateAuditedOtherCharity(self) -> None:
        """
        Checks conditions applicable to audited other charity filings:
        Char.DirReport, Char.Audit, and Char.CharFunds
        """
        result = self._evaluateCode(CH_DIR_REP)
        if not result.success:
            self._yieldErrorOrWarning(CH_DIR_REP, result)
        result = self._evaluateCode(CH_AUDIT)
        if not result.success:
            self._yieldErrorOrWarning(CH_AUDIT, result)
        result = self._evaluateCode(CH_CHAR_FUND)
        if not result.success:
            self._yieldErrorOrWarning(CH_CHAR_FUND, result)

    def validateAuditedOtherCompany(self) -> None:
        """
        Checks conditions applicable to audited other company filings:
        Co.Audit, Co.DirReport, Co.QualAudit, and Co.ProfLoss
        """
        result = self._evaluateCode(CO_AUDIT)
        if not result.success:
            self._errorOnMissingFactText(CO_AUDIT, result)
        result = self._evaluateCode(CO_DIR_REP)
        if not result.success:
            self._yieldErrorOrWarning(CO_DIR_REP, result)
        result = self._evaluateCode(CO_QUAL_AUDIT)
        if not result.success:
            self._yieldErrorOrWarning(CO_QUAL_AUDIT, result)
        result = self._evaluateCode(CO_PROF_LOSS)
        if not result.success:
            self._yieldErrorOrWarning(CO_PROF_LOSS, result)

    def validateAuditedOtherLLP(self) -> None:
        """
        Checks conditions applicable to audited other LLP filings:
        Lp.Audit, Lp.QualAudit and Lp.ProfLoss
        """
        result = self._evaluateCode(LP_AUDIT)
        if not result.success:
            self._errorOnMissingFactText(LP_AUDIT, result)
        result = self._evaluateCode(LP_QUAL_AUDIT)
        if not result.success:
            self._yieldErrorOrWarning(LP_QUAL_AUDIT, result)
        result = self._evaluateCode(LP_PROF_LOSS)
        if not result.success:
            self._yieldErrorOrWarning(LP_PROF_LOSS, result)

    def validateAuditedSmallCharity(self) -> None:
        """
        Checks conditions applicable to audited small company filings:
        Char.Audit and Co.SmCo
        """
        result = self._evaluateCode(CO_SM_CO)
        if not result.success:
            self._errorOnMissingFactText(CO_SM_CO, result)
        result = self._evaluateCode(CH_AUDIT)
        if not result.success:
            self._yieldErrorOrWarning(CH_AUDIT, result)

    def validateAuditedSmallCompany(self) -> None:
        """
        Checks conditions applicable to audited small company filings:
        Co.Audit and Co.SmCo
        """
        result = self._evaluateCode(CO_SM_CO)
        if not result.success:
            self._errorOnMissingFactText(CO_SM_CO, result)
        result = self._evaluateCode(CO_AUDIT)
        if not result.success:
            self._yieldErrorOrWarning(CO_AUDIT, result)

    def validateAuditedSmallLLP(self) -> None:
        """
        Checks conditions applicable to audited small LLP filings:
        Lp.Audit and Lp.Smlp
        """
        result = self._evaluateCode(LP_SM_LP)
        if not result.success:
            self._errorOnMissingFactText(LP_SM_LP, result)
        result = self._evaluateCode(LP_AUDIT)
        if not result.success:
            self._yieldErrorOrWarning(LP_AUDIT, result)

    def validateUnauditedCharitySmallAndGroupAccounts(self) -> None:
        """
        Checks conditions applicable to unaudited small charities or unaudited charity group accounts:
        Co.Sec777, Co.AuditNR, Char.DirResp, and Co.SmCo
        """
        result = self._evaluateCode(CO_SEC_477)
        if not result.success:
            self._errorOnMissingFactText(CO_SEC_477, result)
        result = self._evaluateCode(CO_AUDIT_NR)
        if not result.success:
            self._errorOnMissingFactText(CO_AUDIT_NR, result)
        result = self._evaluateCode(CH_DIR_RESP)
        if not result.success:
            self._yieldErrorOrWarning(CH_DIR_RESP, result)
        result = self._evaluateCode(CO_SM_CO)
        if not result.success:
            self._errorOnMissingFactText(CO_SM_CO, result)

    def validateUnauditedCompanyAbbreviatedAccounts(self) -> None:
        """
        Checks conditions applicable to unaudited company abbreviated accounts:
        Co.Sec777, Co.AuditNR, Co.DirResp, and Co.SmCo
        """
        result = self._evaluateCode(CO_SEC_477)
        if not result.success:
            self._errorOnMissingFactText(CO_SEC_477, result)
        result = self._evaluateCode(CO_AUDIT_NR)
        if not result.success:
            self._errorOnMissingFactText(CO_AUDIT_NR, result)
        result = self._evaluateCode(CO_DIR_RESP)
        if not result.success:
            self._errorOnMissingFactText(CO_DIR_RESP, result)
        result = self._evaluateCode(CO_SM_CO)
        if not result.success:
            self._errorOnMissingFactText(CO_SM_CO, result)

    def validateUnauditedCompanyAbridgedAccounts(self) -> None:
        """
        Checks conditions applicable to unaudited company abridged accounts:
        Co.Sec777, Co.AuditNR, Co.DirResp, Co.SmCo, Co.Abrid
        """
        result = self._evaluateCode(CO_SEC_477)
        if not result.success:
            self._errorOnMissingFactText(CO_SEC_477, result)
        result = self._evaluateCode(CO_AUDIT_NR)
        if not result.success:
            self._errorOnMissingFactText(CO_AUDIT_NR, result)
        result = self._evaluateCode(CO_DIR_RESP)
        if not result.success:
            self._errorOnMissingFactText(CO_DIR_RESP, result)
        result = self._evaluateCode(CO_SM_CO)
        if not result.success:
            self._errorOnMissingFactText(CO_SM_CO, result)
        result = self._evaluateCode(CO_ABRID)
        if not result.success:
            self._errorOnMissingFactText(CO_ABRID, result)

    def validateUnauditedCompanyGroupAccounts(self) -> None:
        """
        Checks conditions applicable to unaudited company abridged accounts:
        Co.Sec477, Co.AuditNR, Co.DirResp, and Co.SmCo
        """
        result = self._evaluateCode(CO_SEC_477)
        if not result.success:
            self._errorOnMissingFactText(CO_SEC_477, result)
        result = self._evaluateCode(CO_AUDIT_NR)
        if not result.success:
            self._errorOnMissingFactText(CO_AUDIT_NR, result)
        result = self._evaluateCode(CO_DIR_RESP)
        if not result.success:
            self._errorOnMissingFactText(CO_DIR_RESP, result)
        result = self._evaluateCode(CO_SM_CO)
        if not result.success:
            self._errorOnMissingFactText(CO_SM_CO, result)

    def validateUnauditedDormantCharity(self) -> None:
        """
        Checks conditions applicable to unaudited dormant charities:
        Co.Sec480 and Co.AuditNR and Char.DirResp and (Char.DirReport or Co.SmCo).
        """
        result = self._evaluateCode(CO_SEC_480)
        if not result.success:
            self._errorOnMissingFactText(CO_SEC_480, result)
        result = self._evaluateCode(CO_AUDIT_NR)
        if not result.success:
            self._errorOnMissingFactText(CO_AUDIT_NR, result)
        result = self._evaluateCode(CH_DIR_RESP)
        if not result.success:
            self._errorOnMissingFactText(CH_DIR_RESP, result)

        result = self._evaluateCode(CH_DIR_REP)
        if not result.success:
            smCoResult = self._evaluateCode(CO_SM_CO)
            if not smCoResult.success:
                self._yieldErrorOrWarning(CH_DIR_REP, result)
                self._errorOnMissingFactText(CO_SM_CO, smCoResult)

    def validateUnauditedDormantCompany(self) -> None:
            """
            Checks conditions applicable to unaudited dormant companies:
            Co.Sec480 and Co.AuditNR and Co.DirResp and (Co.Micro or Co.SmCo).
            """
            result = self._evaluateCode(CO_SEC_480)
            if not result.success:
                self._errorOnMissingFactText(CO_SEC_480, result)
            result = self._evaluateCode(CO_AUDIT_NR)
            if not result.success:
                self._errorOnMissingFactText(CO_AUDIT_NR, result)
            result = self._evaluateCode(CO_DIR_RESP)
            if not result.success:
                self._errorOnMissingFactText(CO_DIR_RESP, result)

            result = self._evaluateCode(CO_MICRO)
            if not result.success:
                smCoResult = self._evaluateCode(CO_SM_CO)
                if not smCoResult.success:
                    self._errorOnMissingFactText(CO_MICRO, result)
                    self._errorOnMissingFactText(CO_SM_CO, smCoResult)

    def validateUnauditedDormantLLP(self) -> None:
        """
        Checks conditions applicable to unaudited dormant LLPs:
        LP.MemResp and LP.Sec480 and LP.SmLP).
        """
        result = self._evaluateCode(LP_MEM_RESP)
        if not result.success:
            self._errorOnMissingFactText(LP_MEM_RESP, result)
        result = self._evaluateCode(LP_SEC_480)
        if not result.success:
            self._errorOnMissingFactText(LP_SEC_480, result)
        result = self._evaluateCode(LP_SM_LP)
        if not result.success:
            self._errorOnMissingFactText(LP_SM_LP, result)

    def validateUnauditedLLPAbbreviatedAccounts(self) -> None:
        """
        Checks conditions applicable to unaudited LLP abbreviated accounts:
        Lp.Sec777, LP.MemResp, and Lp.SmLp
        """
        result = self._evaluateCode(LP_SEC_477)
        if not result.success:
            self._errorOnMissingFactText(LP_SEC_477, result)
        result = self._evaluateCode(LP_MEM_RESP)
        if not result.success:
            self._errorOnMissingFactText(LP_MEM_RESP, result)
        result = self._evaluateCode(LP_SM_LP)
        if not result.success:
            self._errorOnMissingFactText(LP_SM_LP, result)

    def validateUnauditedLLPAbridgedAccounts(self) -> None:
        """
        Checks conditions applicable to unaudited LLP abridged accounts:
        Lp.Sec777, LP.MemResp, Lp.SmLp, and Lp.Abrid
        """
        result = self._evaluateCode(LP_SEC_477)
        if not result.success:
            self._errorOnMissingFactText(LP_SEC_477, result)
        result = self._evaluateCode(LP_MEM_RESP)
        if not result.success:
            self._errorOnMissingFactText(LP_MEM_RESP, result)
        result = self._evaluateCode(LP_SM_LP)
        if not result.success:
            self._errorOnMissingFactText(LP_SM_LP, result)
        result = self._evaluateCode(LP_ABRID)
        if not result.success:
            self._errorOnMissingFactText(LP_ABRID, result)

    def validateUnauditedLLPFullAccounts(self) -> None:
        """
        Checks conditions applicable to unaudited LLP full accounts:
        Lp.Sec777, LP.MemResp, and Lp.SmLp
        """
        result = self._evaluateCode(LP_SEC_477)
        if not result.success:
            self._errorOnMissingFactText(LP_SEC_477, result)
        result = self._evaluateCode(LP_MEM_RESP)
        if not result.success:
            self._errorOnMissingFactText(LP_MEM_RESP, result)
        result = self._evaluateCode(LP_SM_LP)
        if not result.success:
            self._errorOnMissingFactText(LP_SM_LP, result)

    def validateUnauditedLLPGroupAccounts(self) -> None:
        """
        Checks conditions applicable to unaudited LLP group accounts:
        Lp.Sec777, LP.MemResp, and Lp.SmLp
        """
        result = self._evaluateCode(LP_SEC_477)
        if not result.success:
            self._errorOnMissingFactText(LP_SEC_477, result)
        result = self._evaluateCode(LP_MEM_RESP)
        if not result.success:
            self._errorOnMissingFactText(LP_MEM_RESP, result)
        result = self._evaluateCode(LP_SM_LP)
        if not result.success:
            self._errorOnMissingFactText(LP_SM_LP, result)

    def validateUnauditedMicroCompany(self) -> None:
        """
        Checks conditions applicable to unaudited micro companies:
        Co.Sec477 and Co.AuditNR and Co.DirResp and Co.Micro.
        """
        result = self._evaluateCode(CO_SEC_477)
        if not result.success:
            self._errorOnMissingFactText(CO_SEC_477, result)
        result = self._evaluateCode(CO_AUDIT_NR)
        if not result.success:
            self._errorOnMissingFactText(CO_AUDIT_NR, result)
        result = self._evaluateCode(CO_DIR_RESP)
        if not result.success:
            self._errorOnMissingFactText(CO_DIR_RESP, result)
        result = self._evaluateCode(CO_MICRO)
        if not result.success:
            self._errorOnMissingFactText(CO_MICRO, result)

    def validateUnauditedMicroLLP(self) -> None:
        """
        Checks conditions applicable to unaudited micro companies:
        Lp.Sec477 and Lp.MemResp and Lp.Micro.
        """
        result = self._evaluateCode(LP_SEC_477)
        if not result.success:
            self._errorOnMissingFactText(LP_SEC_477, result)
        result = self._evaluateCode(LP_MEM_RESP)
        if not result.success:
            self._errorOnMissingFactText(LP_MEM_RESP, result)
        result = self._evaluateCode(LP_MICRO)
        if not result.success:
            self._errorOnMissingFactText(LP_MICRO, result)

    def validateUnauditedSmallCompanyFullAccounts(self) -> None:
        """
        Checks conditions applicable to unaudited small company full accounts:
        Co.Sec777, Co.AuditNR, Co.DirResp, and Co.SmCo
        """
        result = self._evaluateCode(CO_SEC_477)
        if not result.success:
            self._errorOnMissingFactText(CO_SEC_477, result)
        result = self._evaluateCode(CO_AUDIT_NR)
        if not result.success:
            self._errorOnMissingFactText(CO_AUDIT_NR, result)
        result = self._evaluateCode(CO_DIR_RESP)
        if not result.success:
            self._errorOnMissingFactText(CO_DIR_RESP, result)
        result = self._evaluateCode(CO_SM_CO)
        if not result.success:
            self._errorOnMissingFactText(CO_SM_CO, result)
