"""
See COPYRIGHT.md for copyright information.

NVAD Currency rules — currency code validity, conversion rate consistency,
and monetary unit checks across the TC and FS documents.

Rules implemented here:
  NVAD-E-0240  CurrencyUsed must be a valid ISO 4217 code
  NVAD-E-0260  ConversionRate must equal 1 when CurrencyUsed is HKD
  NVAD-E-1170  AssessableProfitsAdjustedLossOfThePeriodHKD (non-zero) must
               use an HKD-denominated unit
  NVAD-E-1180  AssessableProfitsAdjustedLossOfThePeriodHKD digit count
               must not exceed 14
  NVAD-E-1370  All TC monetary facts must use a unit consistent with
               HKD or CurrencyUsed
  NVAD-E-1430  All FS monetary facts must use a unit consistent with
               HKD or the paired TC CurrencyUsed
"""
from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from arelle.ValidateXbrl import ValidateXbrl
from arelle.XbrlConst import qnIsoCurrency
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Facts import getValidNonNilFactsByQname, iterValidNonNilFactsByQname
from arelle.utils.validate.Validation import Validation
from . import factUnitCurrencyCode, getNumericValue
from ..DisclosureSystems import ALL_IRD_DISCLOSURE_SYSTEMS
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0240(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0240: CurrencyUsed must be a valid ISO 4217 currency code.

    Validity is membership in Arelle's Unit Type Registry
    (``http://www.xbrl.org/utr/utr.xml``): the fact value is converted
    to an ``iso4217`` QName via ``qnIsoCurrency`` and looked up in
    ``modelXbrl.qnameUtrUnits``.
    """
    utrUnits = val.modelXbrl.qnameUtrUnits
    for fact in iterValidNonNilFactsByQname(val.modelXbrl, pluginData.currencyUsedQn):
        value = (fact.value or "").strip()
        if qnIsoCurrency(value) not in utrUnits:
            yield Validation.error(
                codes="IRD.NVAD-E-0240",
                msg=_(
                    "CurrencyUsed must be a valid ISO 4217 currency code; "
                    "found '%(value)s'."
                ),
                modelObject=fact,
                value=value,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0260(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0260: ConversionRate must equal 1 when CurrencyUsed is HKD.

    Skips entirely if CurrencyUsed is not tagged, or is tagged with a
    value other than HKD (a non-HKD conversion rate is expected and
    unconstrained by this rule).
    """
    modelXbrl = val.modelXbrl

    if not any(
        (currencyFact.value or "").strip() == "HKD"
        for currencyFact in iterValidNonNilFactsByQname(modelXbrl, pluginData.currencyUsedQn)
    ):
        return  # No HKD currency fact

    rateFacts = {
        fact
        for fact in iterValidNonNilFactsByQname(modelXbrl, pluginData.conversionRateQn)
        if fact.xValue != Decimal("1")
    }
    if rateFacts:
        yield Validation.error(
            codes="IRD.NVAD-E-0260",
            msg=_(
                "ConversionRate must equal 1 when CurrencyUsed is "
                "HKD; found %(value)s."
            ),
            modelObject=rateFacts,
            value=", ".join(str(fact.xValue) for fact in rateFacts),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1170(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1170: non-zero AssessableProfitsAdjustedLossOfThePeriodHKD
    must use an HKD unit.

    This field is always denominated in Hong Kong dollars regardless of
    the entity's declared functional currency (CurrencyUsed), so its
    unit must resolve to ``iso4217:HKD`` whenever the value is non-zero.
    Zero-valued facts are exempt since a placeholder zero carries no
    currency significance.
    """
    modelXbrl = val.modelXbrl
    for fact in iterValidNonNilFactsByQname(modelXbrl, pluginData.assessableProfitsQn):
        if fact.xValue is None or fact.xValue == 0:
            continue
        code = factUnitCurrencyCode(fact)
        if code != "HKD":
            yield Validation.error(
                codes="IRD.NVAD-E-1170",
                msg=_(
                    "AssessableProfitsAdjustedLossOfThePeriodHKD must use "
                    "an HKD unit when non-zero; found unit '%(unit)s'."
                ),
                modelObject=fact,
                unit=code or "non-currency",
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1180(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1180: AssessableProfitsAdjustedLossOfThePeriodHKD must not
    exceed 14 digits.

    Counts the digits of the absolute integer value of the fact.
    """
    modelXbrl = val.modelXbrl
    for fact in iterValidNonNilFactsByQname(modelXbrl, pluginData.assessableProfitsQn):
        numeric = getNumericValue(fact)
        if numeric is None:
            continue
        digitCount = len(str(abs(int(numeric))))
        if digitCount > 14:
            yield Validation.error(
                codes="IRD.NVAD-E-1180",
                msg=_(
                    "AssessableProfitsAdjustedLossOfThePeriodHKD must not "
                    "exceed 14 digits; found %(digitCount)s digits "
                    "(%(value)s)."
                ),
                modelObject=fact,
                digitCount=digitCount,
                value=fact.xValue,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1370(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1370: TC monetary facts must be denominated in HKD or
    CurrencyUsed.

    Skips entirely if CurrencyUsed is not tagged (not a TC document, or
    covered separately by NVAD-E-0050).
    """
    modelXbrl = val.modelXbrl
    currencyValues = {
        currencyFact.xValue
        for currencyFact in getValidNonNilFactsByQname(modelXbrl, pluginData.currencyUsedQn)
        if currencyFact.xValue
    }
    if not currencyValues:
        return

    allowed = {"HKD"} | currencyValues

    for fact in pluginData.getMonetaryFacts(modelXbrl, pluginData.tcNamespace):
        code = factUnitCurrencyCode(fact)
        if code not in allowed:
            yield Validation.error(
                codes="IRD.NVAD-E-1370",
                msg=_(
                    "%(qname)s is a TC monetary fact and "
                    "must use a unit consistent with HKD or the declared "
                    "CurrencyUsed ('%(currency)s'); found unit "
                    "'%(unit)s'."
                ),
                modelObject=fact,
                qname=fact.qname.localName,
                currency="', '".join(str(v) for v in currencyValues),
                unit=code or "non-currency",
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1430(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1430: FS monetary facts must be denominated in HKD or the
    paired TC file's CurrencyUsed.

    Skips entirely if CurrencyUsed is not tagged anywhere in the IXDS —
    this happens when the FS file is validated standalone (no paired TC
    document loaded), in which case there is no functional currency to
    cross-validate against.
    """
    modelXbrl = val.modelXbrl
    currencyValues = {
        currencyFact.xValue
        for currencyFact in getValidNonNilFactsByQname(modelXbrl, pluginData.currencyUsedQn)
        if currencyFact.xValue
    }
    if not currencyValues:
        return

    allowed = {"HKD"} | currencyValues

    monetaryFacts = (pluginData.getMonetaryFacts(modelXbrl, pluginData.fsNamespace)
        | pluginData.getMonetaryFacts(modelXbrl, pluginData.fspeNamespace))
    for fact in monetaryFacts:
        code = factUnitCurrencyCode(fact)
        if code not in allowed:
            yield Validation.error(
                codes="IRD.NVAD-E-1430",
                msg=_(
                    "%(qname)s is an FS monetary fact and "
                    "must use a unit consistent with HKD or the paired "
                    "TC file's CurrencyUsed ('%(currency)s'); found unit "
                    "'%(unit)s'."
                ),
                modelObject=fact,
                qname=fact.qname.localName,
                currency="', '".join(str(v) for v in currencyValues),
                unit=code or "non-currency",
            )
