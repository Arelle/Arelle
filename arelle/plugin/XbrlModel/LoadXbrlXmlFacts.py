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
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Optional

from lxml import etree

from arelle.ModelValue import QName, qname
from arelle.ModelObjectFactory import parser as xmlParser
from arelle import ValidateFilingText

from .ModelValueMore import SQName
from .XbrlConst import xbrl as xbrlNs
from .XbrlConcept import XbrlConcept
from .XbrlCube import conceptCoreDim, periodCoreDim, entityCoreDim, unitCoreDim, languageCoreDim
from .XbrlFact import XbrlFact, XbrlFactValue, XbrlFootnote
from .XbrlProperty import XbrlProperty

if TYPE_CHECKING:
    from .XbrlModule import XbrlModule
    from .XbrlModel import XbrlCompiledModel
    from .XbrlFact import XbrlFactSource

# XBRL 2.1 namespaces (fixed by the XBRL 2.1 / dimensions specifications).
XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDI = "http://xbrl.org/2006/xbrldi"
LINK = "http://www.xbrl.org/2003/linkbase"
XLINK = "http://www.w3.org/1999/xlink"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
XMLNS = "http://www.w3.org/XML/1998/namespace"

_qnNil = QName("xbrl", xbrlNs, "nil")
_qnUnknownNilReason = QName("xbrl", xbrlNs, "unknownNilReason")

# xbrli:pure. A unit of pure (the domain value of xbrl:unit) is equivalent to no
# unit, so a lone pure numerator is dropped when building the OIM unit string.
_qnPure = QName("xbrli", XBRLI, "pure")


def _clark(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}"


def _localName(elt) -> str:
    tag = elt.tag
    return tag.rpartition('}')[2] if isinstance(tag, str) else tag


def _eltQName(elt, nsmap) -> Optional[QName]:
    """Resolve an lxml element's tag to a QName, carrying its source prefix."""
    tag = elt.tag
    if not isinstance(tag, str) or not tag.startswith('{'):
        return None
    ns, _b, local = tag[1:].partition('}')
    prefix = None
    for p, u in (nsmap or {}).items():
        if u == ns:
            prefix = p
            break
    return QName(prefix, ns, local)


def _resolvePrefixedName(text: str, nsmap) -> Optional[QName]:
    """Resolve a ``prefix:local`` string against an lxml nsmap into a QName."""
    if not text:
        return None
    text = text.strip()
    prefix, _sep, local = text.rpartition(':')
    if not _sep:  # unprefixed -> default namespace
        ns = (nsmap or {}).get(None)
        return QName(None, ns, local) if ns else None
    ns = (nsmap or {}).get(prefix)
    if ns is None:
        return None
    return QName(prefix, ns, local)


def _dayAfter(dateStr: str) -> str:
    """Return the OIM datetime for the *end* of an XBRL 2.1 date (start of the
    following day). A date without a time component is treated as end-of-day, i.e.
    midnight of the next day (per the xBRL-XML fact map)."""
    if 'T' in dateStr:
        return dateStr  # already a dateTime; carry through unchanged
    y, m, d = (int(p) for p in dateStr.split('-'))
    nxt = date(y, m, d) + timedelta(days=1)
    return nxt.strftime("%Y-%m-%dT00:00:00")


def _startOfDay(dateStr: str) -> str:
    if 'T' in dateStr:
        return dateStr
    return dateStr + "T00:00:00"


def _oimPeriod(periodElt) -> Optional[str]:
    """Map an ``xbrli:period`` element to an OIM period string, or None for forever."""
    instant = periodElt.find(_clark(XBRLI, "instant"))
    if instant is not None and instant.text:
        return _dayAfter(instant.text.strip())
    start = periodElt.find(_clark(XBRLI, "startDate"))
    end = periodElt.find(_clark(XBRLI, "endDate"))
    if start is not None and end is not None and start.text and end.text:
        return f"{_startOfDay(start.text.strip())}/{_dayAfter(end.text.strip())}"
    return None  # xbrli:forever -> no period dimension


def _modulePrefixedName(module, qn) -> str:
    """Serialise a measure QName as an OIM ``prefix:local`` string whose prefix is
    bound in the module's namespace map (registering the namespace if needed), so
    the resulting unit string resolves during fact validation. QName equality
    ignores the prefix, so a measure declared via a default namespace (e.g.
    ``<measure>USD</measure>`` in an xbrli default-namespaced instance) still gets a
    usable prefix here."""
    prefixNs = getattr(module, "_prefixNamespaces", None)
    if prefixNs is None:
        return f"{qn.prefix}:{qn.localName}" if qn.prefix else qn.localName
    for p, u in prefixNs.items():
        if u == qn.namespaceURI and p is not None:
            return f"{p}:{qn.localName}"
    prefix = qn.prefix
    if not prefix or prefix in prefixNs:
        i = 0
        while f"ns{i}" in prefixNs:
            i += 1
        prefix = f"ns{i}"
    prefixNs[prefix] = qn.namespaceURI
    return f"{prefix}:{qn.localName}"


def _oimUnit(unitElt, module) -> Optional[str]:
    """Map an ``xbrli:unit`` element to an OIM unit string representation.

    A single ``xbrli:pure`` numerator with no denominator is dropped (returns
    None): a unit of pure is equivalent to no unit, so such facts are unit-less.
    """
    def measureQNames(parent) -> list:
        qns = []
        for m in parent.findall(_clark(XBRLI, "measure")):
            qn = _resolvePrefixedName((m.text or "").strip(), m.nsmap)
            if qn is not None:
                qns.append(qn)
        return qns

    def emit(qns) -> str:
        # measures serialised as module-valid prefixed names, in alphabetical order
        names = sorted(_modulePrefixedName(module, qn) for qn in qns)
        joined = '*'.join(names)
        return f"({joined})" if len(names) > 1 else joined

    divide = unitElt.find(_clark(XBRLI, "divide"))
    if divide is not None:
        num = divide.find(_clark(XBRLI, "unitNumerator"))
        den = divide.find(_clark(XBRLI, "unitDenominator"))
        nums = measureQNames(num) if num is not None else []
        dens = measureQNames(den) if den is not None else []
        numStr = emit(nums)
        denStr = emit(dens)
        return f"{numStr}/{denStr}" if denStr else numStr
    nums = measureQNames(unitElt)
    if not nums:
        return None
    if len(nums) == 1 and nums[0] == _qnPure:
        return None  # a lone xbrli:pure numerator is equivalent to no unit
    return emit(nums)


def _mergeInstanceNamespaces(module, nsmap) -> None:
    """Merge the instance document's namespace declarations into the module's
    prefix map so that OIM unit strings and member QNames generated from the
    instance (e.g. ``iso4217:USD``, ``utr:bbl``) resolve during fact validation.

    Only prefixes not already bound in the module are added; a prefix already
    bound to a *different* URI is left untouched (the module wins)."""
    prefixNs = getattr(module, "_prefixNamespaces", None)
    if prefixNs is None:
        return
    for prefix, ns in (nsmap or {}).items():
        if prefix is None or not ns:
            continue
        if prefix not in prefixNs:
            prefixNs[prefix] = ns


def _factLocalName(factElt, positionalId: str) -> str:
    """Derive the local part of the generated fact SQName per the fact map spec."""
    fid = factElt.get("id")
    if fid:
        return f"e.{fid}" if fid[0].isdigit() else fid
    return positionalId


def _parseContexts(root):
    """Return {contextId: (entityQName, oimPeriodStr, {dimQName: memberValue})}."""
    contexts = {}
    for ctx in root.findall(_clark(XBRLI, "context")):
        cid = ctx.get("id")
        if not cid:
            continue
        entityQn = None
        ent = ctx.find(_clark(XBRLI, "entity"))
        dims = {}
        if ent is not None:
            ident = ent.find(_clark(XBRLI, "identifier"))
            if ident is not None and ident.text:
                scheme = ident.get("scheme")
                identifier = ident.text.strip()
                # entity value carried as a QName whose namespace is the scheme
                # URI (matching how OIM carries xbrl:entity as scheme:identifier).
                prefix = None
                for p, u in (root.nsmap or {}).items():
                    if u == scheme:
                        prefix = p
                        break
                entityQn = QName(prefix, scheme, identifier)
            # explicit / typed members appear in segment and/or scenario
            for container in ("segment", "scenario"):
                cElt = ent.find(_clark(XBRLI, container))
                if cElt is not None:
                    _parseDimensions(cElt, dims)
        perElt = ctx.find(_clark(XBRLI, "period"))
        oimPer = _oimPeriod(perElt) if perElt is not None else None
        contexts[cid] = (entityQn, oimPer, dims)
    return contexts


def _parseDimensions(container, dims) -> None:
    for dimElt in container:
        ln = _localName(dimElt)
        dimAttr = dimElt.get("dimension")
        if not dimAttr:
            continue
        dimQn = _resolvePrefixedName(dimAttr, dimElt.nsmap)
        if dimQn is None:
            continue
        if ln == "explicitMember":
            memQn = _resolvePrefixedName((dimElt.text or "").strip(), dimElt.nsmap)
            if memQn is not None:
                dims[dimQn] = memQn
        elif ln == "typedMember":
            # typed value: use the concatenated text of the typed member content
            child = next((c for c in dimElt if isinstance(c.tag, str)), None)
            dims[dimQn] = (child.text or "").strip() if child is not None else (dimElt.text or "").strip()


def _parseUnits(root, module):
    units = {}
    for unitElt in root.findall(_clark(XBRLI, "unit")):
        uid = unitElt.get("id")
        if uid:
            units[uid] = _oimUnit(unitElt, module)
    return units


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

    # Namespace prefix (declared in documentInfo.namespaces) for generated fact/factValue/footnote object
    # names, resolved to its namespace URI. If absent, use the model's namespace.
    prefixNs = getattr(module, "_prefixNamespaces", {}) or {}
    factPrefix = getattr(factSource, "factIdentifierNamespacePrefix", None)
    if factPrefix:
        factNs = prefixNs.get(factPrefix)
    else:
        factNs = getattr(module, "_documentNamespaceURI", None)
        factPrefix = next((p for p, u in prefixNs.items() if u == factNs), None)

    # namespaceMaps redirection (fromNamespacePrefix -> toNamespacePrefix) for XBRL sources; prefixes
    # are resolved to their declared namespace URIs.
    nsRedirect = {}
    for nsMap in (getattr(factSource, "namespaceMaps", None) or ()):
        frm = prefixNs.get(getattr(nsMap, "fromNamespacePrefix", None))
        to = prefixNs.get(getattr(nsMap, "toNamespacePrefix", None))
        if frm and to:
            nsRedirect[str(frm)] = str(to)

    def redirect(qn: Optional[QName]) -> Optional[QName]:
        if qn is not None and qn.namespaceURI in nsRedirect:
            return QName(qn.prefix, nsRedirect[qn.namespaceURI], qn.localName)
        return qn

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


def _decimalsValue(elt) -> Optional[int]:
    """Decimals for a numeric fact: @decimals (INF -> None), else inferred from
    @precision, else None."""
    dec = elt.get("decimals")
    if dec is not None:
        dec = dec.strip()
        if dec in ("INF", "INFINITY"):
            return None
        try:
            return int(dec)
        except ValueError:
            return None
    prec = elt.get("precision")
    if prec is not None:
        prec = prec.strip()
        if prec in ("INF", "INFINITY"):
            return None
        # decimals cannot be inferred from precision without the value magnitude;
        # treat as infinitely precise (best-effort) rather than mis-report.
        return None
    return None


def _inheritedLang(elt) -> Optional[str]:
    p = elt.getparent()
    while p is not None:
        lang = p.get(_clark(XMLNS, "lang"))
        if lang:
            return lang
        p = p.getparent()
    return None


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


def _innerText(elt) -> str:
    return ''.join(elt.itertext())
