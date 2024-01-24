"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from functools import cached_property
from typing import cast

import regex as re

from arelle.ModelInstanceObject import ModelFact
from arelle.ModelXbrl import ModelXbrl

# Error codes
CO_ABRID = 'Co.Abrid'
CO_AUDIT_NR = 'Co.AuditNR'
CO_DIR_RESP = 'Co.DirResp'
CO_MICRO = 'Co.Micro'
CO_MISSING_ELEMENT = 'Co.MissingElement'
CO_SM_CO = 'Co.SmCo'
CO_SEC_480 = 'Co.Sec480'
LP_ABRID = 'Lp.Abrid'
LP_MEM_RESP = 'Lp.MemResp'
LP_SEC_477 = 'Lp.Sec477'
LP_SEC_480 = 'Lp.Sec480'
LP_SM_LP = 'Lp.SmLp'


# Concept local names
CONCEPT_ACCOUNTS_STATUS = 'AccountsStatusAuditedOrUnaudited'
CONCEPT_ACCOUNTS_STATUS_DIMENSION = 'AccountsStatusDimension'
CONCEPT_ENTITY_DORMANT = 'EntityDormantTruefalse'
CONCEPT_LANGUAGES_DIMENSION = 'LanguagesDimension'
CONCEPT_LEGAL_FORM_ENTIY = 'LegalFormEntity'
CONCEPT_LEGAL_FORM_ENTIY_DIMENSION = 'LegalFormEntityDimension'
CONCEPT_LLP = 'LimitedLiabilityPartnershipLLP'
CONCEPT_REPORT_PRINCIPAL_LANGUAGE = 'ReportPrincipalLanguage'
CONCEPT_WELSH = 'Welsh'

# Map of error code > concept local name > tuple of pairings of descriptions and regex patterns
TEXT_VALIDATION_PATTERNS: dict[str, dict[str, tuple[tuple[str, re.regex.Pattern[str]], ...]]] = {
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


class AccountStatus(Enum):
    AUDIT_EXEMPT_NO_REPORT = 'AuditExempt-NoAccountantsReport'
    AUDIT_EXEMPT_WITH_REPORT = 'AuditExemptWithAccountantsReport'


@dataclass
class CodeResult:
    success: bool = field(default=True)
    conceptLocalName: str | None = field(default=None)
    fact: ModelFact | None = field(default=None)
    message: str | None = field(default=None)


class HmrcLang(Enum):
    ENGLISH = 0
    WELSH = 1


@dataclass
class ValidateHmrc:
    modelXbrl: ModelXbrl
    _codeResultMap: dict[str, CodeResult] = field(default_factory=dict)

    def _errorOnMissingFact(self, conceptLocalName: str) -> None:
        """
        Logs an error explaining that a fact of the given concept was missing.
        :param conceptLocalName:
        :return:
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
        :return:
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

    def _evaluateCode(self, code: str) -> CodeResult:
        """
        Evaluates whether the conditions associated with the given code pass.
        Result is cached.
        :param code:
        :return: Result object that can be used for additional logic or to trigger an error.
        """
        if code in self._codeResultMap:
            return self._codeResultMap[code]

        textValidationPatterns = TEXT_VALIDATION_PATTERNS.get(code, {})
        for conceptLocalName, textMatchers in textValidationPatterns.items():
            facts = self._getFacts(conceptLocalName)
            if not facts:
                return self._setCode(code, CodeResult(
                    success=False,
                    conceptLocalName=conceptLocalName
                ))
            for fact in facts:
                message, pattern = textMatchers[self._lang.value]
                match = pattern.match(fact.value, re.MULTILINE)
                if not match:
                    return self._setCode(code, CodeResult(
                        success=False,
                        conceptLocalName=conceptLocalName,
                        fact=fact,
                        message=message
                    ))
        return self._setCode(code, CodeResult())

    def _getFacts(self, conceptLocalName: str) -> list[ModelFact]:
        return [f for f in self.modelXbrl.factsByLocalName.get(conceptLocalName, set()) if f is not None]

    @cached_property
    def _lang(self) -> HmrcLang:
        """
        Determines if the language is set to Welsh, otherwise defaults to English.
        :return:
        """
        for fact in self._getFacts(CONCEPT_REPORT_PRINCIPAL_LANGUAGE):
            if fact is None or fact.context is None:
                continue
            for qname, value in fact.context.qnameDims.items():
                if qname.localName == CONCEPT_LANGUAGES_DIMENSION:
                    if value.xValue.localName == CONCEPT_WELSH:
                        return HmrcLang.WELSH
        return HmrcLang.ENGLISH

    @cached_property
    def accountStatus(self) -> str | None:
        facts = self._getFacts(CONCEPT_ACCOUNTS_STATUS)
        for fact in facts:
            if fact is None:
                continue
            if fact.isNil:
                continue
            for qname, value in fact.context.qnameDims.items():
                if qname.localName == CONCEPT_ACCOUNTS_STATUS_DIMENSION:
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
            if fact is None:
                continue
            if fact.isNil:
                continue
            for qname, value in fact.context.qnameDims.items():
                if qname.localName == CONCEPT_LEGAL_FORM_ENTIY_DIMENSION:
                    return cast(str, value.xValue.localName)
        return None

    def validate(self) -> None:
        """
        Find the appropriate set of validations to run on this document and runs them.
        :return:
        """
        if self.isEntityDormant and self.accountStatus in {
            AccountStatus.AUDIT_EXEMPT_NO_REPORT.value,
            AccountStatus.AUDIT_EXEMPT_NO_REPORT.value,
        }:
            if self.legalFormEntity == CONCEPT_LLP:
                self.validateUnauditedDormantLLP()
            else:
                self.validateUnauditedDormantCompany()

    def validateUnauditedDormantCompany(self) -> None:
        """
        Checks conditions applicable to unaudited dormant companies:
        Co.Sec480 and Co.AuditNR and Co.DirResp and (Co.Micro or Co.SmCo).
        :return:
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
        :return:
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
