"""
See COPYRIGHT.md for copyright information.

NVAD Special Flags rules — flag/details pairing for advance ruling,
permanent establishment, and auditor practising certificate.

Rules implemented here:
  NVAD-E-0940  AdvanceRuling must be true when AdvanceRulingDetails
               is present
  NVAD-E-0950  AdvanceRulingDetails required when AdvanceRuling is true
  NVAD-E-0960  PermanentEstablishment flag must be true when
               TransactionsWithOtherParts is tagged
  NVAD-E-0970  TransactionsWithOtherParts required when
               PermanentEstablishment is true
  NVAD-E-0980  PractisingCertificateNumber must only use English
               characters and numbers and must not exceed 6 digits.
  NVAD-E-0981  PractisingCertificateNumber required when
               HongKongPracticeUnit is true
  NVAD-E-0982  HongKongPracticeUnit must be true when
               PractisingCertificateNumber is present
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Facts import hasValidNonNilFactByQname, hasTrueValueFactByQname, getValidNonNilFactsByQname, iterValidNonNilFactsByQname
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import ALL_IRD_DISCLOSURE_SYSTEMS
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText

PRACTISING_CERT_PATTERN = re.compile(r"[A-Za-z0-9]{0,6}")


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0940(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0940: AdvanceRuling must be true when AdvanceRulingDetails
    is present.

    Whenever AdvanceRulingDetails is tagged, AdvanceRuling must be
    tagged true; details present alongside a false (or absent) flag is
    inconsistent.
    """
    modelXbrl = val.modelXbrl
    if not hasValidNonNilFactByQname(modelXbrl, pluginData.advanceRulingDetailsQn):
        return

    if not hasTrueValueFactByQname(modelXbrl, pluginData.advanceRulingQn):
        yield Validation.error(
            codes="IRD.NVAD-E-0940",
            msg=_(
                "AdvanceRuling must be true when AdvanceRulingDetails "
                "is tagged."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.advanceRulingDetailsQn
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0950(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0950: AdvanceRulingDetails required when AdvanceRuling
    is true.

    Whenever AdvanceRuling is tagged true, AdvanceRulingDetails must
    also be tagged.
    """
    modelXbrl = val.modelXbrl
    if not hasTrueValueFactByQname(modelXbrl, pluginData.advanceRulingQn):
        return

    if not hasValidNonNilFactByQname(modelXbrl, pluginData.advanceRulingDetailsQn):
        yield Validation.error(
            codes="IRD.NVAD-E-0950",
            msg=_(
                "AdvanceRulingDetails must be tagged when AdvanceRuling "
                "is true."
            ),
            modelObject=getValidNonNilFactsByQname(modelXbrl, pluginData.advanceRulingQn),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0960(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0960: PermanentEstablishment must be true when
    TransactionsWithOtherParts is present.

    Whenever TransactionsWithOtherPartsNonHongKongResidentPerson is
    tagged, PermanentEstablishmentHongKongNonHongKongResidentPerson
    must be tagged true; the transactions fact present alongside a
    false (or absent) PE flag is inconsistent.
    """
    modelXbrl = val.modelXbrl
    if not hasValidNonNilFactByQname(modelXbrl, pluginData.transactionsWithOtherPartsQn):
        return

    if not hasTrueValueFactByQname(modelXbrl, pluginData.permanentEstablishmentQn):
        yield Validation.error(
            codes="IRD.NVAD-E-0960",
            msg=_(
                "PermanentEstablishmentHongKongNonHongKongResidentPerson "
                "must be true when "
                "TransactionsWithOtherPartsNonHongKongResidentPerson "
                "is tagged."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.transactionsWithOtherPartsQn
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0970(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0970: TransactionsWithOtherParts required when
    PermanentEstablishment is true.

    Whenever PermanentEstablishmentHongKongNonHongKongResidentPerson
    is tagged true, TransactionsWithOtherPartsNonHongKongResidentPerson
    must also be tagged.
    """
    modelXbrl = val.modelXbrl
    if not hasTrueValueFactByQname(modelXbrl, pluginData.permanentEstablishmentQn):
        return

    if not hasValidNonNilFactByQname(modelXbrl, pluginData.transactionsWithOtherPartsQn):
        yield Validation.error(
            codes="IRD.NVAD-E-0970",
            msg=_(
                "TransactionsWithOtherPartsNonHongKongResidentPerson "
                "must be tagged when "
                "PermanentEstablishmentHongKongNonHongKongResidentPerson "
                "is true."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.permanentEstablishmentQn
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0980(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0980: PractisingCertificateNumber must not exceed 6
    characters.

    The IRD restricts the practising certificate number of the CPA who
    signed the Auditor's Report to English characters and
    numbers, with a maximum length of 6. Facts that are absent are
    skipped (presence is covered by
    NVAD-E-0981).
    """
    for fact in iterValidNonNilFactsByQname(val.modelXbrl, pluginData.practisingCertificateNumberQn):
        if not isinstance(fact.xValue, str):
            continue
        if not PRACTISING_CERT_PATTERN.fullmatch(fact.xValue):
            yield Validation.error(
                codes="IRD.NVAD-E-0980",
                msg=_(
                    "PractisingCertificateNumber must only use English characters and "
                    "numbers and must not exceed 6 digits."
                ),
                modelObject=fact,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0981(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0981: PractisingCertificateNumber required when
    HongKongPracticeUnit is true.

    Whenever HongKongPracticeUnit is tagged true, PractisingCertificateNumber
    must also be tagged.
    """
    modelXbrl = val.modelXbrl
    if not hasTrueValueFactByQname(modelXbrl, pluginData.hongKongPracticeUnitQn):
        return

    if not hasValidNonNilFactByQname(modelXbrl, pluginData.practisingCertificateNumberQn):
        yield Validation.error(
            codes="IRD.NVAD-E-0981",
            msg=_(
                "PractisingCertificateNumber must be tagged when "
                "HongKongPracticeUnit is true."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.hongKongPracticeUnitQn
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0982(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0982: HongKongPracticeUnit must be true when
    PractisingCertificateNumber is present.

    Whenever PractisingCertificateNumber is tagged, HongKongPracticeUnit
    must be tagged true; a certificate number present alongside a false
    (or absent) flag is inconsistent.
    """
    modelXbrl = val.modelXbrl
    if not hasValidNonNilFactByQname(modelXbrl, pluginData.practisingCertificateNumberQn):
        return

    if not hasTrueValueFactByQname(modelXbrl, pluginData.hongKongPracticeUnitQn):
        yield Validation.error(
            codes="IRD.NVAD-E-0982",
            msg=_(
                "HongKongPracticeUnit must be true when "
                "PractisingCertificateNumber is tagged."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.practisingCertificateNumberQn
            ),
        )
