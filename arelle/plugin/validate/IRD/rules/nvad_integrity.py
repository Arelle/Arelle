"""
See COPYRIGHT.md for copyright information.

NVAD Integrity rules — tagged-value and document-integrity checks.

Rules implemented here:
  NVAD-E-1340  Tagged stringItemType / textBlockItemType facts must have
               a non-empty value
  NVAD-E-1360  Mandatory visible facts must not be placed in ix:hidden

The following codes are NOT implemented. They describe conditions that
cannot be observed from a loaded iXBRL document.

  NVAD-E-1320  Uploaded file is corrupted. Arelle never reaches
               XBRL_FINALLY if the file is unparseable; this is an
               eTAX upload-pipeline check, not an iXBRL content rule.
  NVAD-E-1330  Uploaded file cannot be decrypted. Decryption fails
               (or succeeds) before Arelle loads the document.
  NVAD-E-1331  eTAX validation job timed out. An operational timeout
               of the IRD's server-side job, not a property of the
               iXBRL content.
  NVAD-E-1332  Invalid file structure / container (wrong type,
               malformed ZIP). The file never becomes a loaded
               document, so this plugin is not invoked. In-document
               schemaRef issues after load are covered by 553-E.
  NVAD-E-1440  Template Tool used for the FS file while gross income
               exceeds HK$5 million. Template Tool provenance is not
               present in raw iXBRL.
  NVAD-E-1441  Same Template Tool restriction for the TC file.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle.ModelInstanceObject import ModelFact
from arelle.ValidateXbrl import ValidateXbrl
from arelle.XbrlConst import qnIXbrl11Hidden
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import ALL_IRD_DISCLOSURE_SYSTEMS
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText

# Declared concept type local names covered by NVAD-E-1340.
STRING_OR_TEXT_BLOCK_TYPES = frozenset({
    "stringItemType",
    "textBlockItemType",
})


def _isStringOrTextBlock(fact: ModelFact) -> bool:
    """True when *fact*'s concept is declared as string or text-block."""
    concept = fact.concept
    if concept is None:
        return False
    if concept.typeQname is None:
        return False
    return concept.typeQname.localName in STRING_OR_TEXT_BLOCK_TYPES


def _isInIxHidden(fact: ModelFact) -> bool:
    """True when *fact* is nested inside an ``<ix:hidden>`` element."""
    parent = fact.getparent()
    while parent is not None:
        if parent.tag == qnIXbrl11Hidden.clarkNotation:
            return True
        parent = parent.getparent()
    return False


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1340(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1340: string and text-block facts must have a non-empty value.

    The IRD fires this when a tagged fact whose data type is
    ``stringItemType`` or ``textBlockItemType`` has an empty (or
    whitespace-only) value. Nil facts are skipped — nil is a distinct
    XBRL state from an empty string. One error is yielded per empty
    fact, with the concept local name substituted into the message.
    """
    for fact in val.modelXbrl.facts:
        if fact.isNil:
            continue
        if not _isStringOrTextBlock(fact):
            continue
        if (fact.value or "").strip():
            continue
        localName = (
            fact.qname.localName if fact.qname is not None else "unknown"
        )
        yield Validation.error(
            codes="IRD.NVAD-E-1340",
            msg=_('Fact value of "%(qname)s" is not found.'),
            modelObject=fact,
            qname=localName,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1360(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1360: mandatory facts must not be tagged inside ix:hidden.

    The IRD requires mandatory items to appear on the face of the
    document (or a visible cover page), not in ``<ix:hidden>``. Optional
    facts in ``ix:hidden`` are allowed. Matching is by concept *local
    name* against the union of BIR51 and BIR52 mandatory TC sets so
    the same local name in an FS namespace (e.g. ProfitLossBeforeTax)
    is also covered. One error is yielded per hidden mandatory fact.
    """
    mandatoryQns = pluginData.mandatoryTcBir51Qns | pluginData.mandatoryTcBir52Qns
    for mandatoryQn in mandatoryQns:
        for fact in val.modelXbrl.factsByQname.get(mandatoryQn, set()):
            if not _isInIxHidden(fact):
                continue
            yield Validation.error(
                codes="IRD.NVAD-E-1360",
                msg=_('Invalid use of hidden tag for "%(qname)s".'),
                modelObject=fact,
                qname=mandatoryQn,
            )
