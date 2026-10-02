"""
See COPYRIGHT.md for copyright information.

NVAD BIR52 Partner rules — proprietor/partner emoluments flags and
per-partner dimension checks. BIR52 (partnership/sole-proprietorship)
filings only.

Rules implemented here:
  NVAD-E-1151  BIR52ProprietorPartnerEmoluments must be true when
               BIR52ProprietorPartnerEmolumentsAdjustment is tagged
  NVAD-E-1152  BIR52ProprietorPartnerEmolumentsAdjustment required
               when BIR52ProprietorPartnerEmoluments is true
  NVAD-E-1210  All 6 mandatory per-partner elements must be present
               in each partner context
  NVAD-E-1220  FullName required in the same partner context when
               DateEntered is tagged
  NVAD-E-1230  FullName required in the same partner context when
               DateLeft is tagged
  NVAD-E-1240  HKIDOrBRNumber must be a valid HKID or 8-digit BRN
  NVAD-E-1250  Non-individual partner (BRN) must not have
               PersonalAssessment=true
  NVAD-E-1251  At most one partner may have PrecedentPartner=true
  NVAD-E-1260  Sum of partner AllocationOfAssessableProfits must
               equal total AssessableProfits
  NVAD-E-1270  Each partner ProfitLossSharingRatio must be ≥ 0
               and expressed to ≤ 4 decimal places
  NVAD-E-1280  Sum of partner ProfitLossSharingRatio must be ≥ 100%

All rules in this module apply to BIR52 filings only; the partner
emoluments concepts are BIR52-exclusive (see NVAD-E-0060), so each
rule is additionally guarded with ``isBir52`` to skip cleanly on
BIR51 filings.
"""
from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from arelle.ModelInstanceObject import ModelFact
from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateDuplicateFacts import getDuplicateFactSets
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Facts import hasValidNonNilFactByQname, hasTrueValueFactByQname, getValidNonNilFactsByQname, iterValidNonNilFactsByQname
from arelle.utils.validate.Validation import Validation
from . import getNumericValue, getFactsByNumericValue
from ..DisclosureSystems import ALL_IRD_DISCLOSURE_SYSTEMS
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


MAX_RATIO_PERCENT_DECIMAL_PLACES = 4
MIN_RATIO_SUM = Decimal("1")  # 100% as percentItemType (1.0 = 100%)


def _decimalPlaces(value: Decimal) -> int:
    """Return the number of decimal places in *value* after normalisation."""
    exponent = value.normalize().as_tuple().exponent
    if not isinstance(exponent, int):
        return 0
    return max(-exponent, 0)


def _representativeFacts(facts: list[ModelFact]) -> list[ModelFact]:
    """Keep one fact from each numeric set that is fully consistent.

    Complete duplicates and consistent duplicates (overlapping intervals)
    contribute the highest-precision fact once. An inconsistent set drops
    identical ``(decimals, value)`` copies and keeps the remaining values.
    Facts that are not s-equal stay separate.
    """
    kept: list[ModelFact] = []
    for duplicateSet in getDuplicateFactSets(facts, includeSingles=True):
        selected, _message = duplicateSet.deduplicateConsistentSet()
        kept.extend(selected)
    return kept


def _getPartnerFactSum(
        pluginData: PluginValidationDataExtension,
        modelXbrl: ModelXbrl,
        qname: QName
) -> tuple[list[ModelFact], Decimal]:
    partnerFacts = []
    for facts in pluginData.factsByPartnerContext(modelXbrl).values():
        for fact in facts:
            if fact.qname != qname:
                continue
            if getNumericValue(fact) is None:
                continue
            partnerFacts.append(fact)
    representativeFacts = _representativeFacts(partnerFacts)
    partnerSum = Decimal(0)
    for fact in representativeFacts:
        value = getNumericValue(fact)
        if value is None:
            continue
        partnerSum += value
    return representativeFacts, partnerSum


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1151(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1151: BIR52ProprietorPartnerEmoluments must be true when
    BIR52ProprietorPartnerEmolumentsAdjustment is tagged.

    BIR52 (partnership/sole-proprietorship) filings must tag
    BIR52ProprietorPartnerEmoluments as true whenever
    BIR52ProprietorPartnerEmolumentsAdjustment is tagged — even if
    the adjustment value itself is false. Skips entirely on BIR51
    filings, where these concepts are not required.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir52(modelXbrl):
        return

    if not hasValidNonNilFactByQname(
        modelXbrl, pluginData.bir52ProprietorPartnerEmolumentsAdjQn
    ):
        return

    if not hasTrueValueFactByQname(
        modelXbrl, pluginData.bir52ProprietorPartnerEmolumentsQn
    ):
        yield Validation.error(
            codes="IRD.NVAD-E-1151",
            msg=_(
                "BIR52ProprietorPartnerEmoluments must be true when "
                "BIR52ProprietorPartnerEmolumentsAdjustment is tagged "
                "in a BIR52 filing."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.bir52ProprietorPartnerEmolumentsAdjQn
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1152(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1152: BIR52ProprietorPartnerEmolumentsAdjustment required
    when BIR52ProprietorPartnerEmoluments is true.

    BIR52 (partnership/sole-proprietorship) filings must tag
    BIR52ProprietorPartnerEmolumentsAdjustment — even if its value is
    false — whenever BIR52ProprietorPartnerEmoluments is true. Skips
    entirely on BIR51 filings, where these concepts are not required.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir52(modelXbrl):
        return

    if not hasTrueValueFactByQname(
        modelXbrl, pluginData.bir52ProprietorPartnerEmolumentsQn
    ):
        return

    if not hasValidNonNilFactByQname(
        modelXbrl, pluginData.bir52ProprietorPartnerEmolumentsAdjQn
    ):
        yield Validation.error(
            codes="IRD.NVAD-E-1152",
            msg=_(
                "BIR52ProprietorPartnerEmolumentsAdjustment must be "
                "tagged when BIR52ProprietorPartnerEmoluments is true "
                "in a BIR52 filing."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.bir52ProprietorPartnerEmolumentsQn
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1210(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1210: all 6 mandatory per-partner elements must be
    present in each partner context.

    BIR52 (partnership/sole-proprietorship) filings must tag the
    complete set of personal particulars in every partner typed-
    dimension context: FullName, PrecedentPartner, PersonalAssessment,
    ProfitLossSharingRatio, AllocationOfAssessableProfitsAdjustedLoss,
    and MPF. Yields one error per incomplete partner context, listing
    the missing concept local names. Skips entirely on BIR51 filings,
    where these concepts are not required.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir52(modelXbrl):
        return

    for partnerKey, facts in pluginData.factsByPartnerContext(modelXbrl).items():
        presentQns = {f.qname for f in facts}
        missing = pluginData.mandatoryPartnerQns - presentQns
        if not missing:
            continue
        missingNames = ", ".join(
            sorted(qn.localName for qn in missing)
        )
        yield Validation.error(
            codes="IRD.NVAD-E-1210",
            msg=_(
                "Personal particulars of proprietor or partners must "
                "be tagged as a complete set in each partner context. "
                "Missing in partner context '%(partner)s': "
                "%(missing)s."
            ),
            modelObject=facts,
            partner=partnerKey,
            missing=missingNames,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1220(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1220: FullName required in the same partner context
    when DateEntered is tagged.

    BIR52 (partnership/sole-proprietorship) filings must tag
    BIR52ProprietorPartnerFullName in a partner typed-dimension
    context whenever BIR52ProprietorPartnerDateEntered is tagged in
    that same context. Yields one error per partner context that has
    DateEntered but no FullName. Skips entirely on BIR51 filings,
    where these concepts are not required.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir52(modelXbrl):
        return

    for partnerKey, facts in pluginData.factsByPartnerContext(modelXbrl).items():
        presentQns = {f.qname for f in facts}
        if pluginData.bir52PartnerDateEnteredQn not in presentQns:
            continue
        if pluginData.bir52PartnerFullNameQn in presentQns:
            continue
        yield Validation.error(
            codes="IRD.NVAD-E-1220",
            msg=_(
                "BIR52ProprietorPartnerFullName must be tagged in the "
                "same partner context when "
                "BIR52ProprietorPartnerDateEntered is tagged "
                "(partner context '%(partner)s')."
            ),
            modelObject=[
                f
                for f in facts
                if f.qname == pluginData.bir52PartnerDateEnteredQn
            ],
            partner=partnerKey,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1230(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1230: FullName required in the same partner context
    when DateLeft is tagged.

    BIR52 (partnership/sole-proprietorship) filings must tag
    BIR52ProprietorPartnerFullName in a partner typed-dimension
    context whenever BIR52ProprietorPartnerDateLeft is tagged in
    that same context. Yields one error per partner context that has
    DateLeft but no FullName. Skips entirely on BIR51 filings, where
    these concepts are not required.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir52(modelXbrl):
        return

    for partnerKey, facts in pluginData.factsByPartnerContext(modelXbrl).items():
        presentQns = {f.qname for f in facts}
        if pluginData.bir52PartnerDateLeftQn not in presentQns:
            continue
        if pluginData.bir52PartnerFullNameQn in presentQns:
            continue
        yield Validation.error(
            codes="IRD.NVAD-E-1230",
            msg=_(
                "BIR52ProprietorPartnerFullName must be tagged in the "
                "same partner context when "
                "BIR52ProprietorPartnerDateLeft is tagged "
                "(partner context '%(partner)s')."
            ),
            modelObject=[
                f
                for f in facts
                if f.qname == pluginData.bir52PartnerDateLeftQn
            ],
            partner=partnerKey,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1240(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1240: HKIDOrBRNumber must be a valid HKID or 8-digit BRN.

    Every tagged BIR52ProprietorPartnerHKIDOrBRNumber value must match
    either the HKID pattern (1–2 uppercase letters, 6 digits, and a
    check digit that is a digit or ``A``) or an 8-digit Business
    Registration Number. Skips entirely on BIR51 filings, where this
    concept is not required.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir52(modelXbrl):
        return

    for fact in iterValidNonNilFactsByQname(modelXbrl, pluginData.bir52PartnerHkidOrBrnQn):
        value = fact.xValue
        if not isinstance(value, str):
            continue
        if pluginData.hkidRegex.match(value) or pluginData.brnRegex.match(value):
            continue
        yield Validation.error(
            codes="IRD.NVAD-E-1240",
            msg=_(
                "BIR52ProprietorPartnerHKIDOrBRNumber must be a valid "
                "HKID (1–2 letters, 6 digits, check digit) or an "
                "8-digit BRN; found '%(value)s'."
            ),
            modelObject=fact,
            value=fact.xValue,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1250(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1250: a non-individual partner (identified by BRN)
    must not elect personal assessment.

    BIR52 (partnership/sole-proprietorship) filings must not tag
    BIR52ProprietorPartnerPersonalAssessment as true in a partner
    context whose BIR52ProprietorPartnerHKIDOrBRNumber is a valid
    8-digit Business Registration Number. Individual partners
    (HKID format) may elect personal assessment. Skips entirely on
    BIR51 filings, where these concepts are not required.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir52(modelXbrl):
        return

    for partnerKey, facts in pluginData.factsByPartnerContext(modelXbrl).items():
        brnValues = [
            (f.value or "").strip()
            for f in facts
            if f.qname == pluginData.bir52PartnerHkidOrBrnQn
        ]
        if not any(pluginData.brnRegex.match(v) for v in brnValues):
            continue
        if not any(
            f.xValue is True
            for f in facts
            if f.qname == pluginData.bir52PartnerPersonalAssessmentQn
        ):
            continue
        yield Validation.error(
            codes="IRD.NVAD-E-1250",
            msg=_(
                "BIR52ProprietorPartnerPersonalAssessment must not be "
                "true for a non-individual partner identified by a "
                "Business Registration Number "
                "(partner context '%(partner)s')."
            ),
            modelObject=facts,
            partner=partnerKey,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1251(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1251: at most one partner context may have
    PrecedentPartner=true.

    BIR52 (partnership/sole-proprietorship) filings may tag at most
    one partner as the precedent partner. Zero precedent partners is
    permitted; two or more is not. Skips entirely on BIR51 filings,
    where these concepts are not required.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir52(modelXbrl):
        return

    precedentFacts = [
        f
        for facts in pluginData.factsByPartnerContext(modelXbrl).values()
        for f in facts
        if f.qname == pluginData.bir52PartnerPrecedentPartnerQn
        and f.xValue is True
    ]
    if len(precedentFacts) > 1:
        yield Validation.error(
            codes="IRD.NVAD-E-1251",
            msg=_(
                "At most one partner may be tagged as "
                "BIR52ProprietorPartnerPrecedentPartner=true; found "
                "%(count)s."
            ),
            modelObject=precedentFacts,
            count=len(precedentFacts),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1260(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1260: sum of partner AllocationOfAssessableProfits
    must equal total AssessableProfits.

    BIR52 (partnership/sole-proprietorship) filings must have the
    sum of BIR52ProprietorPartnerAllocationOfAssessableProfitsAdjustedLoss
    across all partner contexts equal
    AssessableProfitsAdjustedLossOfThePeriodHKD. Skips when either
    side is untagged (NVAD-E-0050 / NVAD-E-1210 cover those cases)
    and skips entirely on BIR51 filings.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir52(modelXbrl):
        return

    profitFacts = [
        fact
        for factsForValue in getFactsByNumericValue(
            modelXbrl, (pluginData.assessableProfitsQn,)
        ).values()
        for fact in factsForValue
    ]
    representativeProfitFacts = _representativeFacts(profitFacts)
    if not representativeProfitFacts:
        return

    allocationFacts, allocationSum = _getPartnerFactSum(
        pluginData,
        modelXbrl,
        pluginData.bir52PartnerAllocationOfAssessableProfitsQn
    )
    if not allocationFacts:
        return

    profitFactsByValue: dict[Decimal, list[ModelFact]] = {}
    for fact in representativeProfitFacts:
        profitValue = getNumericValue(fact)
        if profitValue is None:
            continue
        profitFactsByValue.setdefault(profitValue, []).append(fact)

    for profitValue, profitFacts in profitFactsByValue.items():
        if allocationSum != profitValue:
            yield Validation.error(
                codes="IRD.NVAD-E-1260",
                msg=_(
                    "Sum of "
                    "BIR52ProprietorPartnerAllocationOfAssessableProfitsAdjustedLoss "
                    "(%(allocationSum)s) must equal "
                    "AssessableProfitsAdjustedLossOfThePeriodHKD "
                    "(%(totalProfits)s)."
                ),
                modelObject=allocationFacts + profitFacts,
                allocationSum=allocationSum,
                totalProfits=profitValue,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1270(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1270: each ProfitLossSharingRatio must be ≥ 0 and
    expressed to ≤ 4 decimal places.

    BIR52 (partnership/sole-proprietorship) filings must tag each
    BIR52ProprietorPartnerProfitLossSharingRatio as a non-negative
    percent (XBRL ``percentItemType``, where 1.0 = 100%) whose
    percentage form (xValue × 100) has at most four decimal places.
    Yields one error per offending partner context. Skips entirely
    on BIR51 filings.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir52(modelXbrl):
        return

    for partnerKey, facts in pluginData.factsByPartnerContext(modelXbrl).items():
        for fact in facts:
            if fact.qname != pluginData.bir52PartnerProfitLossSharingRatioQn:
                continue
            value = getNumericValue(fact)
            if value is None:
                continue
            percent = value * Decimal(100)
            if value < 0 or _decimalPlaces(
                percent
            ) > MAX_RATIO_PERCENT_DECIMAL_PLACES:
                yield Validation.error(
                    codes="IRD.NVAD-E-1270",
                    msg=_(
                        "BIR52ProprietorPartnerProfitLossSharingRatio "
                        "must be ≥ 0 and expressed to at most 4 "
                        "decimal places "
                        "(partner context '%(partner)s'; "
                        "found %(percent)s%%)."
                    ),
                    modelObject=fact,
                    partner=partnerKey,
                    percent=percent,
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1280(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1280: sum of partner ProfitLossSharingRatio must be
    ≥ 100%.

    BIR52 (partnership/sole-proprietorship) filings must have the
    sum of BIR52ProprietorPartnerProfitLossSharingRatio across all
    partner contexts at least 1.0 (100% as XBRL percentItemType).
    Skips when no ratio is tagged (NVAD-E-1210 covers that case)
    and skips entirely on BIR51 filings.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir52(modelXbrl):
        return

    ratioFacts, ratioSum = _getPartnerFactSum(
        pluginData,
        modelXbrl,
        pluginData.bir52PartnerProfitLossSharingRatioQn
    )
    if not ratioFacts:
        return

    if ratioSum < MIN_RATIO_SUM:
        yield Validation.error(
            codes="IRD.NVAD-E-1280",
            msg=_(
                "Sum of BIR52ProprietorPartnerProfitLossSharingRatio "
                "must be ≥ 100%%; found %(ratioSum)s%%."
            ),
            modelObject=ratioFacts,
            ratioSum=ratioSum * Decimal(100),
        )
