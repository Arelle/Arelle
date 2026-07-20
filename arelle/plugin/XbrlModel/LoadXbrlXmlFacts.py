"""
See COPYRIGHT.md for copyright information.

xBRL-XML built-in fact map.

Implements the ``xbrl:xBRL-XML`` built-in fact map defined in the OIM Taxonomy
specification ("xBRL-XML fact map" section). It maps the fact and footnote
elements of an XBRL 2.1 XML instance document into ``XbrlFact`` / ``XbrlFactValue``
/ ``XbrlFootnote`` model objects.

Design (see plan calm-floating-blanket.md):

* This is a custom, lxml-based parser for the subset of XBRL 2.1 that xBRL-XML
  permits (no tuples, no fraction items, no custom HTML in contexts). It does
  NOT load the instance's ``schemaRef`` DTS -- concept / dimension / datatype
  metadata is resolved from the already-loaded compiled OIM taxonomy
  (``compMdl.namedObjects``). Fact elements are identified by looking their
  QName up in that taxonomy, not by XML-schema validation.
* URL resolution, caching, zip/archive access and remapping are delegated to the
  Arelle ``fileSource`` / ``webCache`` infrastructure, and the hardened lxml
  parser (and, when a disclosure system is active, the malicious-content checks
  in ``ValidateFilingText``) are reused from ``ModelDocument``.

The produced facts are *materialized* (registered in the compiled model) by the
caller in ``FactPipeline.materializeFactSourceFacts`` so that the existing
resolveFact / cube / vector-search / duplicate passes run over them unchanged.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

from lxml import etree

from arelle.ModelValue import QName
from arelle.ModelObjectFactory import parser as xmlParser
from arelle import ValidateFilingText

from .ModelValueMore import SQName
from .XbrlConcept import XbrlConcept
from .XbrlCube import conceptCoreDim, periodCoreDim, entityCoreDim, unitCoreDim, languageCoreDim
from .XbrlFact import XbrlFact, XbrlFactValue, XbrlFootnote
from .XbrlProperty import XbrlProperty
# Shared XBRL 2.1 -> OIM converters (also used by LoadInlineFacts); imported under
# underscore aliases so this module's body reads unchanged after the extraction.
from .LoadFactsCommon import (
    XBRLI, LINK, XLINK, XSI, XMLNS,
    clark as _clark,
    eltQName as _eltQName,
    innerText as _innerText,
    inheritedLang as _inheritedLang,
    mergeInstanceNamespaces as _mergeInstanceNamespaces,
    parseContexts as _parseContexts,
    parseUnits as _parseUnits,
    factLocalName as _factLocalName,
    decimalsValue as _decimalsValue,
    factIdentity,
    qnNil as _qnNil,
    qnUnknownNilReason as _qnUnknownNilReason,
)

if TYPE_CHECKING:
    from .XbrlModule import XbrlModule
    from .XbrlModel import XbrlCompiledModel
    from .XbrlFact import XbrlFactSource


def _openInstance(compMdl, url):
    """Open and parse the instance URL into an lxml element tree root, reusing
    Arelle's fileSource / webCache and hardened parser. Returns the root element
    or None (after emitting a diagnostic)."""
    modelXbrl = compMdl.modelXbrl
    mgr = modelXbrl.modelManager
    normalizedUri = mgr.cntlr.webCache.normalizeUrl(url)
    filepath = mgr.cntlr.webCache.getfilename(normalizedUri)
    if filepath is None:
        compMdl.error("arelle:factSourceNotFound",
                      _("The xBRL-XML fact source could not be retrieved: %(url)s"),
                      url=url)
        return None
    _file = None
    try:
        if (mgr.validateDisclosureSystem and (
                mgr.disclosureSystem.validateFileText and
                normalizedUri not in mgr.disclosureSystem.standardTaxonomiesDict)):
            _file, _encoding = ValidateFilingText.checkfile(modelXbrl, filepath)
        else:
            _file, _encoding = modelXbrl.fileSource.file(filepath, stripDeclaration=True)
        _parser, _lookupName, _lookupClass = xmlParser(modelXbrl, normalizedUri)
        xmlDocument = etree.parse(_file, parser=_parser, base_url=filepath)
        for err in _parser.error_log:
            compMdl.error("xmlSchema:syntax",
                          _("%(error)s, %(fileName)s, line %(line)s, column %(column)s"),
                          fileName=os.path.basename(url), error=err.message,
                          line=err.line, column=err.column)
        return xmlDocument.getroot()
    except (OSError, etree.LxmlError) as ex:
        compMdl.error("arelle:factSourceLoadError",
                      _("Error loading xBRL-XML fact source %(url)s: %(error)s"),
                      url=url, error=str(ex))
        return None
    finally:
        if _file is not None:
            try:
                _file.close()
            except Exception:
                pass


def parseXbrlXmlFacts(compMdl, module, factSource, url):
    """Parse the XBRL 2.1 instance at ``url`` and return ``(facts, footnotes)``
    lists of unregistered ``XbrlFact`` / ``XbrlFootnote`` objects. The caller is
    responsible for materializing (indexing / registering) them.
    """
    facts: list = []
    footnotes: list = []
    root = _openInstance(compMdl, url)
    if root is None:
        return facts, footnotes

    nsmap = dict(root.nsmap or {})
    _mergeInstanceNamespaces(module, nsmap)

    # Namespace prefix / URI for generated fact QNames, plus the namespaceMaps
    # redirect -- shared with LoadInlineFacts (see LoadFactsCommon.factIdentity).
    factPrefix, factNs, redirect = factIdentity(module, factSource)

    contexts = _parseContexts(root)
    units = _parseUnits(root, module)

    factIdByElt = {}  # element -> generated fact SQName local part (for footnotes)
    position = 0
    for elt in root:
        if not isinstance(elt.tag, str) or elt.tag.startswith('{' + XBRLI + '}') \
                or elt.tag.startswith('{' + LINK + '}'):
            continue  # skip contexts, units, footnoteLinks, comments/PIs
        conceptQn = redirect(_eltQName(elt, nsmap))
        if conceptQn is None:
            continue
        conceptObj = compMdl.namedObjects.get(conceptQn)
        if not isinstance(conceptObj, XbrlConcept):
            continue  # not a taxonomy-defined fact element; skip
        position += 1
        localName = _factLocalName(elt, f"e.{position}")

        fact = XbrlFact()
        fact.module = module
        fact.parent = module
        fact.name = SQName(factPrefix, factNs, localName)
        fact.extends = None
        fact.factQualifier = None
        fact.factDimensions = {conceptCoreDim: conceptQn}
        fact.properties = None

        ctxRef = elt.get("contextRef")
        ctx = contexts.get(ctxRef)
        if ctx is not None:
            entityQn, oimPer, dims = ctx
            if entityQn is not None:
                fact.factDimensions[entityCoreDim] = entityQn
            if oimPer is not None:
                fact.factDimensions[periodCoreDim] = oimPer
            for dQn, dVal in dims.items():
                fact.factDimensions[redirect(dQn)] = redirect(dVal) if isinstance(dVal, QName) else dVal

        isNumeric = conceptObj.isNumeric(compMdl)
        unitRef = elt.get("unitRef")
        if unitRef is not None:
            uStr = units.get(unitRef)
            if uStr is not None:
                fact.factDimensions[unitCoreDim] = uStr

        lang = elt.get(_clark(XMLNS, "lang")) or _inheritedLang(elt)
        if lang and conceptObj.isOimTextFactType(compMdl):
            fact.factDimensions[languageCoreDim] = lang

        # nil facts carry no value and a xbrl:nil = xbrl:unknownNilReason property.
        isNil = (elt.get(_clark(XSI, "nil")) in ("true", "1"))

        fv = XbrlFactValue()
        fv.fact = fact
        fv.name = SQName(factPrefix, factNs, f"{localName}_fv")
        fv.decimals = None
        fv.language = lang if (lang and conceptObj.isOimTextFactType(compMdl)) else None
        fv.valueSources = None
        fv.valueAnchors = None
        if isNil:
            fv.value = None
            nilProp = XbrlProperty()
            nilProp.property = _qnNil
            nilProp.value = _qnUnknownNilReason
            fact.properties = [nilProp]
        else:
            text = elt.text if elt.text is not None else ""
            fv.value = text
            if isNumeric:
                fv.decimals = _decimalsValue(elt)
        fact.factValues = [fv]

        facts.append(fact)
        factIdByElt[elt] = localName

    _parseFootnotes(compMdl, root, nsmap, factPrefix, factNs, factIdByElt, footnotes)
    return facts, footnotes


def _parseFootnotes(compMdl, root, nsmap, factPrefix, factNs, factIdByElt, footnotes) -> None:
    """Map XBRL 2.1 link:footnoteLink footnotes to XbrlFootnote objects.

    Footnotes are linked to facts through link:loc + link:footnoteArc. The
    generated footnote SQName is ``fn_`` + the related fact's local name, with an
    incrementing suffix when a fact carries more than one footnote.
    """
    # id -> fact element (for loc resolution)
    idToElt = {}
    for elt, _ln in factIdByElt.items():
        fid = elt.get("id")
        if fid:
            idToElt[fid] = elt
    perFactCount = {}
    for fnLink in root.findall(_clark(LINK, "footnoteLink")):
        # collect locators: xlink:label -> fact local name
        labelToFactLocal = {}
        for loc in fnLink.findall(_clark(LINK, "loc")):
            href = loc.get(_clark(XLINK, "href")) or ""
            label = loc.get(_clark(XLINK, "label"))
            fid = href.rpartition('#')[2]
            elt = idToElt.get(fid)
            if elt is not None and label is not None:
                labelToFactLocal.setdefault(label, factIdByElt.get(elt))
        # collect footnote resources: xlink:label -> (content, lang)
        labelToFootnote = {}
        for fn in fnLink.findall(_clark(LINK, "footnote")):
            label = fn.get(_clark(XLINK, "label"))
            if label is None:
                continue
            lang = fn.get(_clark(XMLNS, "lang")) or _inheritedLang(fn)
            content = _innerText(fn)
            labelToFootnote[label] = (content, lang)
        # walk footnoteArcs from fact-locator label to footnote-resource label
        for arc in fnLink.findall(_clark(LINK, "footnoteArc")):
            frm = arc.get(_clark(XLINK, "from"))
            to = arc.get(_clark(XLINK, "to"))
            factLocal = labelToFactLocal.get(frm)
            fnInfo = labelToFootnote.get(to)
            if factLocal is None or fnInfo is None:
                continue
            content, lang = fnInfo
            n = perFactCount.get(factLocal, 0) + 1
            perFactCount[factLocal] = n
            suffix = f"_{n}" if n > 1 else ""
            fnObj = XbrlFootnote()
            fnObj.name = SQName(factPrefix, factNs, f"fn_{factLocal}{suffix}")
            fnObj.forObjects = [SQName(factPrefix, factNs, factLocal)]
            fnObj.content = content
            fnObj.language = lang
            footnotes.append(fnObj)
