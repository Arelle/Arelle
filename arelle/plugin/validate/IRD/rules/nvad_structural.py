"""
See COPYRIGHT.md for copyright information.

NVAD Structural rules — core filing-level checks.

Rules implemented here:
  NVAD-E-0010  Mandatory monetary/decimal/percentage facts must use
               decimals="INF"
  NVAD-E-0020  Mandatory duration facts' period must match the basis period
  NVAD-E-0021  Mandatory instant facts' instant must equal the basis
               period end date
  NVAD-E-0030  Inconsistent duplicate facts must not exist
  NVAD-E-0050  Every mandatory TC item must have at least one tagged fact

NVAD-E-0040 is NOT implemented here. Per the IRD's own published spec, it
requires cross-referencing the IRD file number and year of assessment tagged
in this file against "the Profits Tax return" — a separate BIR51/BIR52
submission that is not part of, or derivable from, the iXBRL
supporting document(s) this plugin validates. It is therefore
untestable by a digital-file validator, in the same category as
NVAD-E-1320/1330/1331/1332/1440/1441.
  NVAD-E-0170  HongKongStandardIndustrialClassificationCode must be tagged
  NVAD-E-0180  HKSIC code must be exactly 6 numeric digits
  NVAD-E-0190  HKSIC code must be in the official HKSIC 2.0 list
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from typing import Any

from arelle.ModelInstanceObject import ModelFact
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateDuplicateFacts import getDuplicateFactSetsWithType
from arelle.ValidateDuplicateFactsConst import DuplicateType
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Facts import hasValidNonNilFactByQname, iterValidNonNilFactsByQname
from arelle.utils.validate.Validation import Validation
from . import getFactsByDateValue
from ..DisclosureSystems import ALL_IRD_DISCLOSURE_SYSTEMS
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


def _getBasisRanges(pluginData: PluginValidationDataExtension, modelXbrl: ModelXbrl) -> dict[tuple[date, date], list[ModelFact]]:
    """Maps basis start/end ranges to the facts that define the range.

    Excludes ranges where the dates are inverted.
    """
    basisFactsByRange = defaultdict(list)
    startFactsByValue = getFactsByDateValue(modelXbrl, (pluginData.basisPeriodStartDateQn, ))
    endFactsByValue = getFactsByDateValue(modelXbrl, (pluginData.basisPeriodEndDateQn, ))
    for startValue, startFacts in startFactsByValue.items():
        for endValue, endFacts in endFactsByValue.items():
            if startValue <= endValue:
                basisFactsByRange[(startValue, endValue)].extend(startFacts + endFacts)
    return dict(basisFactsByRange)


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0010(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0010: mandatory numeric facts must be tagged with decimals="INF".

    Every mandatory BIR51/BIR52 TC element that is numeric (monetary,
    decimal, or percentage item type) must be reported to full precision.
    The IRD does not permit rounding of these figures, so any tagged fact
    with a ``decimals`` attribute other than ``"INF"`` triggers this error.

    Checked against the combined BIR51 ∪ BIR52 mandatory element set so the
    rule applies uniformly regardless of form type; non-numeric facts for
    the same concepts (booleans, dates, strings) are skipped since decimals
    do not apply to them.
    """
    mandatoryQns = (
        pluginData.mandatoryTcBir51Qns | pluginData.mandatoryTcBir52Qns
    )

    for qn in mandatoryQns:
        for fact in iterValidNonNilFactsByQname(val.modelXbrl, qn):
            if not fact.isNumeric:
                continue
            if fact.decimals != "INF":
                yield Validation.error(
                    codes="IRD.NVAD-E-0010",
                    msg=_(
                        '%(qname)s is a mandatory monetary/decimal/'
                        'percentage item and must be tagged with '
                        'decimals="INF" (found decimals="%(decimals)s").'
                    ),
                    modelObject=fact,
                    qname=qn.localName,
                    decimals=fact.decimals,
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0020(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0020: mandatory duration facts must be tagged in the basis period.

    Every mandatory BIR51/BIR52 TC element whose concept has
    ``periodType="duration"`` must be reported in a context whose
    start/end dates exactly match the basis period declared via
    ``BasisPeriodStartDate`` / ``BasisPeriodEndDate``.

    Skips entirely if the basis period itself is not tagged (that
    omission is covered separately by NVAD-E-0050).
    """
    modelXbrl = val.modelXbrl

    basisFactsByRange = _getBasisRanges(pluginData, modelXbrl)
    if not basisFactsByRange:
        return

    mandatoryQns = (
        pluginData.mandatoryTcBir51Qns | pluginData.mandatoryTcBir52Qns
    )
    for qn in mandatoryQns:
        concept = modelXbrl.qnameConcepts.get(qn)
        if concept is None or concept.periodType != "duration":
            continue
        for (basisStart, basisEnd), basisFacts in basisFactsByRange.items():
            for fact in iterValidNonNilFactsByQname(modelXbrl, qn):
                ctx = fact.context
                if ctx is None or not ctx.isStartEndPeriod:
                    continue
                if ctx.startDatetime is None or ctx.endDate is None:
                    continue
                foundStart = ctx.startDatetime.date()
                foundEnd = ctx.endDate
                if foundStart != basisStart or foundEnd != basisEnd:
                    yield Validation.error(
                        codes="IRD.NVAD-E-0020",
                        msg=_(
                            "%(qname)s is a mandatory duration fact and "
                            "must be tagged in the basis period "
                            "(%(basisStart)s to %(basisEnd)s); found "
                            "context period %(foundStart)s to %(foundEnd)s."
                        ),
                        modelObject=[fact] + basisFacts,
                        qname=qn.localName,
                        basisStart=basisStart,
                        basisEnd=basisEnd,
                        foundStart=foundStart,
                        foundEnd=foundEnd,
                    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0021(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0021: mandatory instant facts must equal the basis period end date.

    Every mandatory BIR51/BIR52 TC element whose concept has
    ``periodType="instant"`` must be reported in a context whose instant
    exactly matches ``BasisPeriodEndDate``.

    Skips entirely if the basis period end date itself is not tagged
    (covered separately by NVAD-E-0050).
    """
    modelXbrl = val.modelXbrl

    basisFactsByRange = _getBasisRanges(pluginData, modelXbrl)
    if not basisFactsByRange:
        return

    mandatoryQns = (
        pluginData.mandatoryTcBir51Qns | pluginData.mandatoryTcBir52Qns
    )
    for qn in mandatoryQns:
        concept = modelXbrl.qnameConcepts.get(qn)
        if concept is None or concept.periodType != "instant":
            continue
        for (__, basisEnd), basisFacts in basisFactsByRange.items():
            for fact in iterValidNonNilFactsByQname(modelXbrl, qn):
                ctx = fact.context
                if ctx is None or not ctx.isInstantPeriod:
                    continue
                if ctx.instantDate is None:
                    continue
                if ctx.instantDate != basisEnd:
                    yield Validation.error(
                        codes="IRD.NVAD-E-0021",
                        msg=_(
                            "%(qname)s is a mandatory instant fact and "
                            "must be tagged at the basis period end date "
                            "(%(basisEnd)s); found instant %(instantDate)s."
                        ),
                        modelObject=fact,
                        qname=qn.localName,
                        basisEnd=basisEnd,
                        instantDate=ctx.instantDate,
                    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0030(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0030: inconsistent duplicate facts must not exist.

    Delegates entirely to Arelle's built-in duplicate-fact detection
    (``arelle.ValidateDuplicateFacts``) rather than re-implementing
    fact-equivalence logic. Two facts for the same concept are
    "duplicates" when their contexts and units are *s-equal*
    (structurally/value equivalent per XBRL 2.1) — not necessarily
    tagged against the literal same ``contextRef`` — so a fact
    reported twice under two different contexts that happen to carry
    the same entity/period/dimensions is caught just as readily as one
    reported twice under a single shared contextRef.

    A duplicate set is "inconsistent" when the facts disagree on value
    (beyond the rounding tolerance implied by their respective
    ``decimals`` attributes), i.e. they cannot represent the same
    underlying fact to any level of precision.
    """
    for duplicateSet in getDuplicateFactSetsWithType(
        val.modelXbrl.facts, DuplicateType.INCONSISTENT
    ):
        facts = duplicateSet.facts
        qname = facts[0].qname
        values = ", ".join((f.value or "").strip() for f in facts)
        yield Validation.error(
            codes="IRD.NVAD-E-0030",
            msg=_(
                "%(qname)s was tagged more than once with "
                "inconsistent values in equivalent contexts: %(values)s."
            ),
            modelObject=facts,
            qname=qname.localName,
            values=values,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0050(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0050: every mandatory TC item must have at least one tagged fact.

    Selects the BIR51 or BIR52 mandatory element set based on the
    detected form type, then yields one error per concept with no
    non-nil fact in the document, substituting the concept's local name
    into the message.

    Rule is guarded to TC documents only (schemaRef in TC entry points)
    so that FS-only documents in combined filings — which never carry
    ird_tc concepts — are not mis-flagged as missing every mandatory item.
    """
    modelXbrl = val.modelXbrl
    hrefs = pluginData.getSchemaRefHrefs(modelXbrl)
    if not any(href in pluginData.validTcEntryPoints for href in hrefs):
        return  # FS document — NVAD-E-0050 does not apply

    mandatoryQns = (
        pluginData.mandatoryTcBir52Qns
        if pluginData.isBir52(modelXbrl)
        else pluginData.mandatoryTcBir51Qns
    )

    for qn in sorted(mandatoryQns, key=lambda q: q.localName):
        if not hasValidNonNilFactByQname(modelXbrl, qn):
            yield Validation.error(
                codes="IRD.NVAD-E-0050",
                msg=_(
                    "%(qname)s is a mandatory TC item and must be "
                    "tagged with at least one fact."
                ),
                modelDocument=modelXbrl.modelDocument,
                qname=qn.localName,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0170(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0170: HKSIC code must be tagged in every TC submission.

    HongKongStandardIndustrialClassificationCode is mandatory in every
    BIR51 and BIR52 TC filing.  Even when there is no business activity
    the code must be present (the IRD specifies '000000' for no-activity
    filers).  Absence of any tagged fact for this concept triggers this
    error.

    Rule is guarded to TC documents only (schemaRef in TC entry points)
    so that FS-only documents in combined filings are not mis-flagged.
    """
    hrefs = pluginData.getSchemaRefHrefs(val.modelXbrl)
    if not any(href in pluginData.validTcEntryPoints for href in hrefs):
        return  # FS document — NVAD-E-0170 does not apply

    if not hasValidNonNilFactByQname(val.modelXbrl, pluginData.hksicCodeQn):
        yield Validation.error(
            codes="IRD.NVAD-E-0170",
            msg=_(
                "HongKongStandardIndustrialClassificationCode must be "
                "tagged in all BIR51 and BIR52 TC submissions."
            ),
            modelDocument=val.modelXbrl.modelDocument,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0180(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0180: HKSIC code must be exactly 6 numeric digits.

    Every tagged HongKongStandardIndustrialClassificationCode value must
    match ``^\\d{6}$``.
    """
    for fact in iterValidNonNilFactsByQname(val.modelXbrl, pluginData.hksicCodeQn):
        value = (fact.value or "").strip()
        if not pluginData.hksicCodeRegex.match(value):
            yield Validation.error(
                codes="IRD.NVAD-E-0180",
                msg=_(
                    "HongKongStandardIndustrialClassificationCode must be "
                    "exactly 6 numeric digits; found '%(value)s'."
                ),
                modelObject=fact,
                value=value,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0190(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0190: HKSIC code must be in the official HKSIC 2.0 list.

    Beyond the 6-digit format check in NVAD-E-0180, every tagged
    HongKongStandardIndustrialClassificationCode value must also match
    a code in the Census and Statistics Department's official HKSIC
    (version 2.0) index, loaded into
    ``pluginData.validHksicCodes`` from
    ``resources/hksic_codes.json``.

    Malformed values (already reported by NVAD-E-0180) are skipped here
    so a single bad tag does not raise two unrelated errors.
    """
    for fact in iterValidNonNilFactsByQname(val.modelXbrl, pluginData.hksicCodeQn):
        value = (fact.value or "").strip()
        if not pluginData.hksicCodeRegex.match(value):
            continue
        if value not in pluginData.validHksicCodes:
            yield Validation.error(
                codes="IRD.NVAD-E-0190",
                msg=_(
                    "HongKongStandardIndustrialClassificationCode "
                    "'%(value)s' is not a valid code in the official "
                    "HKSIC 2.0 index."
                ),
                modelObject=fact,
                value=value,
            )
