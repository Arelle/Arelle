"""
See COPYRIGHT.md for copyright information.

NVAD Combined / Financial Statements rules — mandatory FS items and
cross-document checks that apply when a financial statements file is
present in the Inline XBRL Document Set.

Rules implemented here:
  NVAD-E-1290  _(BIR51)_ FS Equity (total equity) must be tagged
  NVAD-E-1291  FS Revenue must be tagged (BIR52, or BIR51
               non-consolidated)
  NVAD-E-1292  FS ProfitLossBeforeTax must be tagged (BIR52, or
               BIR51 non-consolidated)
  NVAD-E-1300  FS Assets must equal EquityAndLiabilities
  NVAD-E-1390  Combined filing: ProfitLossBeforeTax must be
               identical in TC and FS files
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from arelle.ModelInstanceObject import ModelFact, ModelUnit
from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.Contexts import ContextHashKey
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Facts import hasValidNonNilFactByQname, hasFalseValueFactByQname, iterValidNonNilFactsByQname
from arelle.utils.validate.Validation import Validation
from . import getNumericValue
from ..DisclosureSystems import ALL_IRD_DISCLOSURE_SYSTEMS
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


def _fsRevenueAndPbtRequired(
        modelXbrl: ModelXbrl,
        pluginData: PluginValidationDataExtension,
) -> bool:
    """True when Revenue / ProfitLossBeforeTax are mandatory FS items.

    Always required for BIR52. For BIR51, required only when
    ``AccountsPreparedAtConsolidatedLevel`` is explicitly false — the
    IRD waives both items for consolidated accounts, and FS-only
    filings (flag absent) cannot be classified as non-consolidated.
    """
    if pluginData.isBir52(modelXbrl):
        return True
    return hasFalseValueFactByQname(
        modelXbrl, pluginData.accountsPreparedAtConsolidatedLevelQn
    )


def _groupFactsByUnit(
        facts: Iterable[ModelFact],
) -> list[tuple[ModelUnit, list[ModelFact]]]:
    """Partition facts by unit s-equality. Facts with no unit are omitted."""
    groups: list[tuple[ModelUnit, list[ModelFact]]] = []
    for fact in facts:
        unit = fact.unit
        if unit is None:
            continue
        for groupUnit, groupFacts in groups:
            if groupUnit.isEqualTo(unit):
                groupFacts.append(fact)
                break
        else:
            groups.append((unit, [fact]))
    return groups


def _hasFsDocument(
    modelXbrl: ModelXbrl,
    pluginData: PluginValidationDataExtension,
) -> bool:
    """True when the IXDS contains an FS or FS-PE taxonomy schemaRef.

    TC-only filings have no financial statements document, so FS
    mandatory-item rules must not fire against them.
    """
    fsEntryPoints = (
        pluginData.validFsEntryPoints | pluginData.validFsPeEntryPoints
    )
    return any(
        href in fsEntryPoints for href in pluginData.getSchemaRefHrefs(modelXbrl)
    )


def _hasFsEquity(
    modelXbrl: ModelXbrl,
    pluginData: PluginValidationDataExtension,
) -> bool:
    """True if total equity is tagged under either FS taxonomy.

    Full HKFRS filings use ``ird_fs:Equity``; private-entity filings
    use the equivalent ``ird_fs_pe:Equity``.
    """
    return hasValidNonNilFactByQname(modelXbrl, pluginData.fsEquityQn) or hasValidNonNilFactByQname(
        modelXbrl, pluginData.fsPeEquityQn
    )


def _hasFsProfitLossBeforeTax(
        modelXbrl: ModelXbrl,
        pluginData: PluginValidationDataExtension,
) -> bool:
    """True if ProfitLossBeforeTax is tagged under either FS taxonomy."""
    return hasValidNonNilFactByQname(modelXbrl, pluginData.fsProfitLossBeforeTaxQn) or hasValidNonNilFactByQname(
        modelXbrl, pluginData.fsPeProfitLossBeforeTaxQn
    )


def _hasFsRevenue(
    modelXbrl: ModelXbrl,
    pluginData: PluginValidationDataExtension,
) -> bool:
    """True if Revenue is tagged under either FS taxonomy."""
    return hasValidNonNilFactByQname(modelXbrl, pluginData.fsRevenueQn) or hasValidNonNilFactByQname(
        modelXbrl, pluginData.fsPeRevenueQn
    )


def _isVEqualToAny(fact: ModelFact, others: Iterable[ModelFact]) -> bool:
    return any(
        fact.isVEqualTo(other, numericIntervalConsistency=True)
        for other in others
    )


def _iterContextMatchedFacts(
        modelXbrl: ModelXbrl,
        leftQnames: tuple[QName, ...],
        rightQnames: tuple[QName, ...],
) -> Iterable[tuple[list[ModelFact], list[ModelFact]]]:
    leftByContext = _numericFactsByContext(modelXbrl, leftQnames)
    if not leftByContext:
        return
    rightByContext = _numericFactsByContext(modelXbrl, rightQnames)
    for key, leftFacts in leftByContext.items():
        rightFacts = rightByContext.get(key)
        if rightFacts:
            yield leftFacts, rightFacts


def _mismatchedNumericValues(
        leftFacts: Iterable[ModelFact],
        rightFacts: Iterable[ModelFact],
) -> tuple[Decimal, Decimal] | None:
    """Return one unequal pair, or None when every shared unit is v-equal.

    Facts already share a context. They are compared within one unit
    (``ModelUnit.isEqualTo``); a unit present on only one side is
    skipped. Equality is ``ModelFact.isVEqualTo`` with numeric interval
    consistency, so overlapping ``decimals`` intervals match.
    """
    rightGroups = _groupFactsByUnit(rightFacts)
    for leftUnit, leftGroup in _groupFactsByUnit(leftFacts):
        rightGroup = next(
            (
                group for groupUnit, group in rightGroups
                if leftUnit.isEqualTo(groupUnit)
            ),
            None,
        )
        if not rightGroup:
            continue
        leftUnmatched = next(
            (fact for fact in leftGroup if not _isVEqualToAny(fact, rightGroup)),
            None,
        )
        rightUnmatched = next(
            (fact for fact in rightGroup if not _isVEqualToAny(fact, leftGroup)),
            None,
        )
        if leftUnmatched is None and rightUnmatched is None:
            continue
        leftValue = getNumericValue(leftUnmatched if leftUnmatched is not None else leftGroup[0])
        rightValue = getNumericValue(rightUnmatched if rightUnmatched is not None else rightGroup[0])
        if leftValue is None or rightValue is None:
            continue
        return leftValue, rightValue
    return None


def _numericFactsByContext(
        modelXbrl: ModelXbrl,
        qnames: tuple[QName, ...],
) -> dict[ContextHashKey, list[ModelFact]]:
    grouped: dict[ContextHashKey, list[ModelFact]] = defaultdict(list)
    for qname in qnames:
        for fact in iterValidNonNilFactsByQname(modelXbrl, qname):
            context = fact.context
            if getNumericValue(fact) is None or context is None:
                continue
            grouped[ContextHashKey(context, dimensionalAspectModel=True)].append(fact)
    return grouped


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1290(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1290: BIR51 financial statements must tag total equity.

    Applies only when an FS (or FS-PE) document is in the IXDS, so
    TC-only BIR51 filings are not false-positived. BIR52 filings are
    skipped — total equity is not a named mandatory FS item for
    partnerships. Either ``ird_fs:Equity`` or ``ird_fs_pe:Equity``
    satisfies the requirement.
    """
    modelXbrl = val.modelXbrl
    if pluginData.isBir52(modelXbrl):
        return
    if not _hasFsDocument(modelXbrl, pluginData):
        return
    if not _hasFsEquity(modelXbrl, pluginData):
        yield Validation.error(
            codes="IRD.NVAD-E-1290",
            msg=_(
                "Equity (total equity) must be tagged in the financial "
                "statements data file of a BIR51 filing."
            ),
            modelDocument=modelXbrl.modelDocument,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1291(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1291: FS document must tag Revenue.

    Required for every BIR52 filing with an FS document, and for BIR51
    filings whose ``AccountsPreparedAtConsolidatedLevel`` flag is
    explicitly false. Consolidated BIR51 filings (flag true) and
    FS-only BIR51 filings (flag absent, so the exemption cannot be
    disproven) are skipped. Either ``ird_fs:Revenue`` or
    ``ird_fs_pe:Revenue`` satisfies the requirement.
    """
    modelXbrl = val.modelXbrl
    if not _hasFsDocument(modelXbrl, pluginData):
        return
    if not _fsRevenueAndPbtRequired(modelXbrl, pluginData):
        return
    if not _hasFsRevenue(modelXbrl, pluginData):
        yield Validation.error(
            codes="IRD.NVAD-E-1291",
            msg=_(
                "Revenue must be tagged in the financial statements "
                "data file (BIR52, or BIR51 where accounts are not "
                "prepared at consolidated level)."
            ),
            modelDocument=modelXbrl.modelDocument,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1292(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1292: FS document must tag ProfitLossBeforeTax.

    Same applicability as NVAD-E-1291: required for every BIR52 filing
    with an FS document, and for BIR51 filings whose
    ``AccountsPreparedAtConsolidatedLevel`` flag is explicitly false.
    Checks ``ird_fs:ProfitLossBeforeTax`` / ``ird_fs_pe:ProfitLossBeforeTax``
    rather than the TC-namespace concept, so a paired TC fact does not
    satisfy the FS mandatory-item requirement.
    """
    modelXbrl = val.modelXbrl
    if not _hasFsDocument(modelXbrl, pluginData):
        return
    if not _fsRevenueAndPbtRequired(modelXbrl, pluginData):
        return
    if not _hasFsProfitLossBeforeTax(modelXbrl, pluginData):
        yield Validation.error(
            codes="IRD.NVAD-E-1292",
            msg=_(
                "ProfitLossBeforeTax must be tagged in the financial "
                "statements data file (BIR52, or BIR51 where accounts "
                "are not prepared at consolidated level)."
            ),
            modelDocument=modelXbrl.modelDocument,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1300(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1300: FS Assets must equal EquityAndLiabilities.

    The identity is per statement of financial position. Facts are
    paired by context s-equality (entity, period, and dimensions), not
    by ``contextRef``, then compared within each unit. A context or
    unit tagged on only one side is skipped. Values are v-equal when
    their ``decimals`` intervals overlap. One error is reported when
    both sides are present and a value differs. Full HKFRS and
    private-entity qnames are pooled. Either side entirely untagged is
    skipped.
    """
    modelXbrl = val.modelXbrl
    for assetFacts, equityFacts in _iterContextMatchedFacts(
        modelXbrl,
        (pluginData.fsAssetsQn, pluginData.fsPeAssetsQn),
        (pluginData.fsEquityAndLiabilitiesQn, pluginData.fsPeEquityAndLiabilitiesQn),
    ):
        mismatch = _mismatchedNumericValues(assetFacts, equityFacts)
        if mismatch is None:
            continue
        assetValue, equityValue = mismatch
        yield Validation.error(
            codes="IRD.NVAD-E-1300",
            msg=_(
                "Assets (total assets) must equal EquityAndLiabilities "
                "(total equity and liabilities); found %(assets)s and "
                "%(equityAndLiabilities)s."
            ),
            modelObject=assetFacts + equityFacts,
            assets=assetValue,
            equityAndLiabilities=equityValue,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1390(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1390: ProfitLossBeforeTax must match between TC and FS.

    Combined filings only. Facts are paired by context s-equality
    (entity, period, and dimensions), so a tax-computation context and
    a financial-statements context match when they describe the same
    period even though their ``contextRef`` ids differ, then compared
    within each unit. A prior-year financial-statements figure with no
    tax-computation counterpart is skipped, as is a unit present on
    only one side. Values are v-equal when their ``decimals`` intervals
    overlap. One error is reported when both sides are present and a
    value differs. Accepts ``ird_fs:ProfitLossBeforeTax`` and
    ``ird_fs_pe:ProfitLossBeforeTax``. Either side entirely untagged is
    skipped — TC-only, FS-only, and consolidated BIR51 filings (FS PBT
    waived) are therefore unaffected.
    """
    modelXbrl = val.modelXbrl
    for tcFacts, fsFacts in _iterContextMatchedFacts(
        modelXbrl,
        (pluginData.tcProfitLossBeforeTaxQn,),
        (pluginData.fsProfitLossBeforeTaxQn, pluginData.fsPeProfitLossBeforeTaxQn),
    ):
        mismatch = _mismatchedNumericValues(tcFacts, fsFacts)
        if mismatch is None:
            continue
        tcValue, fsValue = mismatch
        yield Validation.error(
            codes="IRD.NVAD-E-1390",
            msg=_(
                "ProfitLossBeforeTax in the financial statements "
                "(%(fsValue)s) must equal ProfitLossBeforeTax in the "
                "tax computation (%(tcValue)s)."
            ),
            modelObject=tcFacts + fsFacts,
            fsValue=fsValue,
            tcValue=tcValue,
        )
