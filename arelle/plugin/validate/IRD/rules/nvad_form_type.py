"""
See COPYRIGHT.md for copyright information.

NVAD Form-Type rules — BIR51/BIR52 cross-contamination and company name length.

Rules implemented here:
  NVAD-E-0060  BIR52-specific elements must not appear in a BIR51
               (corporation) filing
  NVAD-E-0070  BIR51-specific elements must not appear in a BIR52
               (partnership) filing
  NVAD-E-0080  English CompanyName text must not exceed 120 characters
  NVAD-E-0090  Chinese CompanyName text must not exceed 120 characters
"""
from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from typing import Any

from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Facts import iterValidNonNilFactsByQname, getValidNonNilFactsByQname
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import ALL_IRD_DISCLOSURE_SYSTEMS
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText

COMPANY_NAME_MAX_LEN = 120

HAN_UNICODE_NAME_PREFIXES = (
    "CJK UNIFIED IDEOGRAPH",
    "CJK COMPATIBILITY IDEOGRAPH",
)

def _is_han(text: str) -> bool:
    for ch in text:
        name = unicodedata.name(ch, "")
        if any(name.startswith(p) for p in HAN_UNICODE_NAME_PREFIXES):
            return True
    return False


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0060(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0060: BIR52-specific elements must not appear in a BIR51 filing.

    A BIR51 (corporation) return must never tag concepts that are
    reserved for BIR52 (partnership/sole-proprietorship) returns — e.g.
    the per-partner elements or BIR52PurchaseCBAIBA. Skips entirely when
    the document is detected as BIR52, where these concepts are expected.
    """
    modelXbrl = val.modelXbrl
    if pluginData.isBir52(modelXbrl):
        return

    for qn in sorted(pluginData.bir52ExclusiveQns, key=lambda q: q.localName):
        facts = getValidNonNilFactsByQname(modelXbrl, qn)
        if facts:
            yield Validation.error(
                codes="IRD.NVAD-E-0060",
                msg=_(
                    "%(qname)s is a BIR52-specific element and must "
                    "not be tagged in a BIR51 (corporation) filing."
                ),
                modelObject=facts,
                qname=qn.localName,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0070(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0070: BIR51-specific elements must not appear in a BIR52 filing.

    A BIR52 (partnership/sole-proprietorship) return must never tag
    concepts that are reserved for BIR51 (corporation) returns — e.g.
    PrivateCompany, ShareholderChange, or the share-based payment
    elements. Skips entirely when the document is detected as BIR51,
    where these concepts are expected.
    """
    modelXbrl = val.modelXbrl
    if pluginData.isBir51(modelXbrl):
        return

    for qn in sorted(pluginData.bir51ExclusiveQns, key=lambda q: q.localName):
        facts = getValidNonNilFactsByQname(modelXbrl, qn)
        if facts:
            yield Validation.error(
                codes="IRD.NVAD-E-0070",
                msg=_(
                    "%(qname)s is a BIR51-specific element and must "
                    "not be tagged in a BIR52 (partnership) filing."
                ),
                modelObject=facts,
                qname=qn.localName,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0080(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0080: English CompanyName text must not exceed 120 characters.

    CompanyName is a single concept shared by English- and Chinese-medium
    filers; a tagged value is treated as English when there are no Han
    characters. Values containing Han characters are considered Chinese and
    are checked separately by NVAD-E-0090.
    """
    for fact in iterValidNonNilFactsByQname(val.modelXbrl, pluginData.companyNameQn):
        value = (fact.value or "").strip()
        if _is_han(value):
            continue
        if len(value) > COMPANY_NAME_MAX_LEN:
            yield Validation.error(
                codes="IRD.NVAD-E-0080",
                msg=_(
                    "CompanyName (English) must not exceed "
                    "%(maxLength)s characters; found "
                    "%(length)s characters."
                ),
                modelObject=fact,
                maxLength=COMPANY_NAME_MAX_LEN,
                length=len(value),
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0090(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0090: Chinese CompanyName text must not exceed 120 characters.

    A tagged CompanyName value is treated as Chinese when it contains any
    Han character (the English case is checked separately by NVAD-E-0080).
    """
    for fact in iterValidNonNilFactsByQname(val.modelXbrl, pluginData.companyNameQn):
        value = (fact.value or "").strip()
        if not _is_han(value):
            continue
        if len(value) > COMPANY_NAME_MAX_LEN:
            yield Validation.error(
                codes="IRD.NVAD-E-0090",
                msg=_(
                    "CompanyName (Chinese) must not exceed "
                    "%(maxLength)s characters; found "
                    "%(length)s characters."
                ),
                modelObject=fact,
                maxLength=COMPANY_NAME_MAX_LEN,
                length=len(value),
            )
