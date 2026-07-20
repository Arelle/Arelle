"""
LoadInlineFacts.py -- built-in ``xbrl:inline-XBRL-1.1`` fact map (SKELETON / POC).

Materializes OIM ``XbrlFact`` / ``XbrlFactValue`` / ``XbrlFootnote`` objects from an
Inline XBRL 1.1 report (or IXDS document set) referenced by a ``factSource`` whose
``factMapName`` is ``xbrl:inline-XBRL-1.1``.

Design (see the session design notes / project memory ``project-factmap`` and
``project_legacy_taxonomy_loader``):

* **Transformer over the infrastructure, not a re-parse.** Unlike
  ``LoadXbrlXmlFacts`` (which reparses a *flat* XBRL 2.1 instance), an inline report
  requires ``ModelDocument.inlineIxdsDiscover`` -- IXDS document-set membership,
  per-``target`` separation, ``ix:continuation`` stitching, transforms, tuples, and
  footnote arcs. We therefore ``ModelXbrl.load`` the inline URL (which runs inline
  discovery *and* discovers the report's own DTS in one pass) and iterate the
  resulting ``ModelInlineFact`` objects, emitting OIM facts.

* **One load does DTS + facts.** Because the inline load also discovers the
  schemaRef / extension taxonomy (in an ESEF Report Package zip, or an SEC
  directory/zip -- both resolved by ``FileSource``), this function compiles that DTS
  into ``compMdl`` itself via ``legacyTaxonomyToOimModule`` and does NOT rely on the
  ``pocCompileLegacyDts`` pre-step that ``FactPipeline`` runs for the XML/JSON maps.

* **Shared converters.** Context / period / dimension / unit / language / decimals
  conversion is shared with ``LoadXbrlXmlFacts`` via ``LoadFactsCommon`` -- a
  ``ModelInlineFact`` exposes the same ``xbrli:context`` / ``xbrli:unit`` elements
  (as ``ModelContext`` / ``ModelUnit``) that inline discovery synthesised.

* **Layered provenance (see design decision).**
    - Value: ``fv.value`` = ``imf.value`` -- the ix-TRANSFORMED value (authoritative,
      computed by the infrastructure's format/scale/sign handling).
    - Durable anchor: ``fv.valueAnchors`` carries an ``xbrl:htmlElementId`` property =
      the ix element's ``@id``, resolved against the element's OWN document. This is
      the spec's "value provided in value property, anchored to document text"
      case -- NOT ``valueSources`` (which would require re-extracting + re-transforming
      from the html, and re-reads the file per fact). Anchors are also cheaper: the
      infrastructure does not re-open the source to validate them. Multi-document IXDS
      binds ``fv.source`` to a per-document sourceMapping URL; the single-document
      default leaves it None.
    - Transient: ``fact._sourceInlineFact = imf`` -- an in-memory, non-serialized
      back-ref to the live ``ModelInlineFact`` for Xule / rich error messages, giving
      lossless access to the already-parsed tree without a file re-parse. Never
      serialized; the xhtml DOM is never reified into OIM objects.

SKELETON STATUS: default (unnamed) ix ``target`` only; footnotes and multi-document
per-fact source binding are stubbed. Non-default targets need a target discriminator
on the factSource/sourceMapping -- deferred, see the HF note in ``oim-taxonomy.md``
under "Inline XBRL 1.1 fact map". ``TODO`` markers flag the parts still to fill in.

NOTE (wiring): a factValue with ``valueAnchors`` requires the factMap to define a
``factLocatorType`` (oim-taxonomy.md, oimte:factValueLocatorRequiredForValueSources).
The built-in ``xbrl:inline-XBRL-1.1`` factMap is registered in resources/xbrlSpec.json
with ``factLocatorType: xbrl:htmlElementLocatorType`` (whose required property
``xbrl:htmlElementId`` the anchors carry). Enforcement of that requirement for the
``valueAnchors`` path is not yet wired: ValidateFacts only runs
``validateAndResolveValueSources`` for ``valueSources`` -- a structure-only anchor
validator (locator-chain + required/allowed properties, no file read) is the
follow-up that would give the registration teeth.
"""
from __future__ import annotations

from typing import Optional

from arelle.ModelValue import QName

from .ModelValueMore import SQName
from .XbrlConst import xbrl as xbrlNs
from .XbrlConcept import XbrlConcept
from .XbrlCube import conceptCoreDim, periodCoreDim, entityCoreDim, unitCoreDim, languageCoreDim
from .XbrlFact import XbrlFact, XbrlFactValue, XbrlFactValueAnchor
from .XbrlProperty import XbrlProperty
from .LoadFactsCommon import (
    XMLNS, clark, inheritedLang, oimContextDimensions, oimUnit,
    factLocalName, factIdentity, qnNil, qnUnknownNilReason,
)

# grep marker for the POC scaffolding (mirrors POC-LEGACY-DTS in LoadLegacyTaxonomy)
# ==== BEGIN POC-INLINE =====================================================

#: Locator property QName written into each factValue's valueAnchors. This is the
#: spec-defined html-element-id property required by the built-in
#: xbrl:htmlElementLocatorType, which the built-in xbrl:inline-XBRL-1.1 factMap
#: references as its factLocatorType (see resources/xbrlSpec.json).
qnHtmlElementId = QName("xbrl", xbrlNs, "htmlElementId")


def parseInlineFacts(compMdl, module, factSource, url):
    """Parse the Inline XBRL 1.1 report (or IXDS) at ``url`` and return
    ``(facts, footnotes)`` lists of *unregistered* ``XbrlFact`` / ``XbrlFootnote``
    objects. Signature matches ``parseXbrlXmlFacts`` so it drops into
    ``FactPipeline._builtinFactMapParsers``; the caller materializes the results.
    """
    facts: list = []
    footnotes: list = []

    # 1. Load the inline document via the infrastructure -- runs inlineIxdsDiscover
    #    (IXDS membership, target separation, continuations, transforms, tuples,
    #    footnote arcs) AND discovers the report's DTS. Default target only for now.
    inlineMx = _loadInlineModel(compMdl, url)
    if inlineMx is None:
        compMdl.error("arelle:inlineReportNotLoaded",
                      _("The factSource %(name)s inline report at %(url)s could not be loaded."),
                      xbrlObject=factSource, name=getattr(factSource, "name", None), url=url)
        return facts, footnotes
    try:
        # 2. Compile the inline report's discovered DTS into compMdl so emitted facts
        #    resolve against their concepts/dimensions/cubes (no-op-safe if present).
        _compileInlineDts(compMdl, inlineMx, url)

        # 3. Namespace prefix + namespaceMaps redirect (shared with LoadXbrlXmlFacts).
        factPrefix, factNs, redirect = factIdentity(module, factSource)

        # 4. Transform each ModelInlineFact -> XbrlFact / XbrlFactValue.
        position = 0
        for imf in _iterTargetFacts(inlineMx):
            conceptQn = redirect(imf.qname)
            if conceptQn is None:
                continue
            conceptObj = compMdl.namedObjects.get(conceptQn)
            if not isinstance(conceptObj, XbrlConcept):
                continue  # not a taxonomy-defined fact element
            position += 1
            facts.append(_emitFact(compMdl, module, imf, conceptQn, conceptObj,
                                   factPrefix, factNs, redirect, position))

        # 5. Footnotes: ModelInlineFootnote + ix:relationship arcs -> XbrlFootnote.
        #    TODO: read the already-resolved footnote relationships from inlineMx and
        #    mirror LoadXbrlXmlFacts._parseFootnotes (footnote text as an html anchor).
        _emitFootnotes(compMdl, module, inlineMx, factPrefix, factNs, footnotes)
    finally:
        # The transient _sourceInlineFact back-refs point into inlineMx's live tree.
        # TODO(decision): if Xule needs the tree to outlive this load, keep inlineMx
        # alive on compMdl instead of discarding it. For value-anchor resolution
        # alone the file is re-opened via FileSource, so it could be closed here.
        pass  # do NOT inlineMx.close() while _sourceInlineFact refs are live

    return facts, footnotes


# --------------------------------------------------------------------------
# Infrastructure load + DTS compile
# --------------------------------------------------------------------------

def _loadInlineModel(compMdl, url):
    """ModelXbrl.load the inline report so inlineIxdsDiscover runs. Sets the legacy
    reentrancy guard so schemaRef .xsd sub-documents are not re-claimed by the
    LoadLegacyTaxonomy entry-point pull-loader (Hook 3)."""
    from arelle import ModelXbrl as _ModelXbrl
    from . import LoadLegacyTaxonomy as _legacy
    # TODO(multi-target): to select a non-default target, set the modelManager /
    #   modelXbrl ixdsTarget before load once the factSource carries a target
    #   discriminator; inlineIxdsDiscover then target-filters facts.
    _legacy._pocInLegacyDiscovery = True
    try:
        return _ModelXbrl.load(compMdl.modelManager, url,
                               _("inline-XBRL-1.1 fact map discovery"))
    except Exception:
        return None
    finally:
        _legacy._pocInLegacyDiscovery = False


def _compileInlineDts(compMdl, inlineMx, url):
    """Compile the inline report's discovered DTS into compMdl (concepts, dimensions,
    cubes) via the legacy transform, so emitted facts resolve. inlineBase=False --
    the host model already carries the base spec objects. No-op-safe when the
    taxonomy is already present (compiled-duplicate tolerance)."""
    from .LoadLegacyTaxonomy import legacyTaxonomyToOimModule
    from . import loadXbrlModule
    if not getattr(inlineMx, "qnameConcepts", None):
        return
    moduleDict = legacyTaxonomyToOimModule(inlineMx, inlineBase=False)
    loadXbrlModule(compMdl.modelManager.cntlr, compMdl.error, compMdl.warning,
                   compMdl, moduleDict, url)


def _iterTargetFacts(inlineMx):
    """Yield the ModelInlineFact objects for the selected target. inlineIxdsDiscover
    has already target-filtered inlineMx.facts. TODO(tuples): tuple parents are
    yielded here too -- decide whether to emit tuple-member facts and skip the tuple
    container. TODO(multi-target): filter by fact.get('target') == target."""
    return getattr(inlineMx, "facts", None) or ()


# --------------------------------------------------------------------------
# Fact emission
# --------------------------------------------------------------------------

def _emitFact(compMdl, module, imf, conceptQn, conceptObj,
              factPrefix, factNs, redirect, position):
    """Build one XbrlFact + XbrlFactValue from a ModelInlineFact.

    ``imf`` is a ModelInlineFact (subclass of ModelFact AND ModelObject): it exposes
    the standard fact API -- ``.qname``, ``.context`` (ModelContext), ``.unit``
    (ModelUnit), ``.value`` (ix-TRANSFORMED), ``.isNil`` -- and, being the live ix
    element, ``.get('id')`` / ``.modelDocument.uri``. Context / unit conversion is
    shared with the XBRL-XML loader via LoadFactsCommon.
    """
    localName = factLocalName(imf, f"e.{position}")

    fact = XbrlFact()
    fact.module = module
    fact.parent = module
    fact.name = SQName(factPrefix, factNs, localName)
    fact.extends = None
    fact.factQualifier = None
    fact.factDimensions = {conceptCoreDim: conceptQn}
    fact.properties = None

    # entity / period / explicit + typed dimensions -- imf.context wraps the same
    # <xbrli:context> element the XML path parses, so reuse the shared converter.
    ctxElt = imf.context
    if ctxElt is not None:
        entityQn, oimPer, dims = oimContextDimensions(ctxElt)
        if entityQn is not None:
            fact.factDimensions[entityCoreDim] = entityQn
        if oimPer is not None:
            fact.factDimensions[periodCoreDim] = oimPer
        for dQn, dVal in dims.items():
            fact.factDimensions[redirect(dQn)] = redirect(dVal) if isinstance(dVal, QName) else dVal

    isNumeric = conceptObj.isNumeric(compMdl)
    unitElt = imf.unit
    if unitElt is not None:
        uStr = oimUnit(unitElt, module)
        if uStr is not None:
            fact.factDimensions[unitCoreDim] = uStr

    lang = imf.get(clark(XMLNS, "lang")) or inheritedLang(imf)
    isText = conceptObj.isOimTextFactType(compMdl)
    if lang and isText:
        fact.factDimensions[languageCoreDim] = lang

    isNil = bool(getattr(imf, "isNil", False))

    fv = XbrlFactValue()
    fv.fact = fact
    fv.name = SQName(factPrefix, factNs, f"{localName}_fv")
    fv.decimals = None
    fv.language = lang if (lang and isText) else None
    fv.valueSources = None
    fv.valueAnchors = None
    fv.source = None  # single-document default target; TODO(multi-doc): set the
    #                   per-document sourceMapping QName for imf.modelDocument.uri.
    if isNil:
        fv.value = None
        nilProp = XbrlProperty()
        nilProp.property = qnNil
        nilProp.value = qnUnknownNilReason
        fact.properties = [nilProp]
    else:
        fv.value = imf.value  # ix-transformed value (authoritative)
        if isNumeric:
            fv.decimals = getattr(imf, "decimals", None)  # TODO: confirm ix decimals/scale
        fv.valueAnchors = _htmlValueAnchor(imf, fv)

    fact.factValues = [fv]

    # Transient, non-serialized back-ref for Xule / error messages (see module docstring).
    fact._sourceInlineFact = imf

    return fact


def _htmlValueAnchor(imf, fv) -> Optional[list]:
    """Build the factValue.valueAnchors list: an ``xbrl:htmlElementId`` property = the
    ix element's ``@id``, correlating the (already-computed) value to its source text
    for highlight / mouse-over. The built-in ``xbrl:inline-XBRL-1.1`` factMap declares
    ``xbrl:htmlElementLocatorType`` as its factLocatorType, which requires this
    property (resources/xbrlSpec.json).

    Returns None when the ix element has no ``@id`` (no durable locator; the value
    still validates from ``fv.value`` and the transient back-ref remains available).

    TODO(multi-doc): the caller must also register a sourceMappings entry binding
    ``fv.source`` to ``imf.modelDocument.uri`` when the IXDS spans multiple documents
    (ids collide across documents); for a single-document report the lone
    sourceMapping already resolves.
    """
    elementId = imf.get("id")
    if not elementId:
        return None
    prop = XbrlProperty()
    prop.property = qnHtmlElementId
    prop.value = elementId
    anchor = XbrlFactValueAnchor()
    anchor.factValue = fv
    anchor.properties = [prop]
    return [anchor]


def _emitFootnotes(compMdl, module, inlineMx, factPrefix, factNs, footnotes):
    """Emit XbrlFootnote objects from the inline report's footnote relationships.
    inlineIxdsDiscover has already resolved ix:footnote / ix:relationship arcs across
    the IXDS. TODO: walk the resolved footnote relationship set -> XbrlFootnote, with
    the footnote text carried as an html anchor like the fact values."""
    return

# ==== END POC-INLINE =======================================================
