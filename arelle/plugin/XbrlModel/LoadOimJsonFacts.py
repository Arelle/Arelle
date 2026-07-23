"""
See COPYRIGHT.md for copyright information.

OIM-JSON (xBRL-JSON) built-in fact map.

Implements the ``xbrl:OIM-JSON`` built-in fact map defined in the OIM Taxonomy
specification ("OIM JSON fact map" section). It maps the facts of an xBRL-JSON
report document into ``XbrlFact`` / ``XbrlFactValue`` objects, and facts whose
``dimensions.concept`` is ``xbrl:note`` into ``XbrlFootnote`` objects.

There are no conformance tests exercising this map yet, so this is a best-effort
implementation that mirrors the structure of the xBRL-XML map
([LoadXbrlXmlFacts.py](LoadXbrlXmlFacts.py)); the produced objects are
materialized by the caller.
"""
from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Optional

from arelle.ModelValue import QName, qname

from .ModelValueMore import SQName
from .XbrlConst import xbrl as xbrlNs
from .XbrlConcept import XbrlConcept
from .XbrlCube import (conceptCoreDim, periodCoreDim, entityCoreDim,
                       unitCoreDim, languageCoreDim)
from .XbrlFact import XbrlFact, XbrlFactValue, XbrlFootnote
from .XbrlProperty import XbrlProperty
from .LoadFactsCommon import qnNil, qnUnknownNilReason

if TYPE_CHECKING:
    from .XbrlModule import XbrlModule
    from .XbrlModel import XbrlCompiledModel
    from .XbrlFact import XbrlFactSource

_coreByJsonName = {
    "concept": conceptCoreDim,
    "period": periodCoreDim,
    "entity": entityCoreDim,
    "unit": unitCoreDim,
    "language": languageCoreDim,
}

_qnNote = QName("xbrl", xbrlNs, "note")


def _openJson(compMdl, url):
    modelXbrl = compMdl.modelXbrl
    mgr = modelXbrl.modelManager
    normalizedUri = mgr.cntlr.webCache.normalizeUrl(url)
    filepath = mgr.cntlr.webCache.getfilename(normalizedUri)
    if filepath is None:
        compMdl.error("arelle:factSourceNotFound",
                      _("The OIM-JSON fact source could not be retrieved: %(url)s"),
                      url=url)
        return None
    try:
        # fileSource.file returns a (handle,) 1-tuple for binary and (handle, encoding)
        # for text; read binary and decode utf-8-sig so a BOM is tolerated regardless.
        result = modelXbrl.fileSource.file(filepath, binary=True)
        _file = result[0]
        with _file:
            content = _file.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8-sig")
        return json.loads(content)
    except (OSError, ValueError) as ex:
        compMdl.error("arelle:factSourceLoadError",
                      _("Error loading OIM-JSON fact source %(url)s: %(error)s"),
                      url=url, error=str(ex))
        return None


def parseOimJsonFacts(compMdl, module, factSource, url):
    """Parse the xBRL-JSON report at ``url`` and return ``(facts, footnotes)``."""
    facts: list = []
    footnotes: list = []
    doc = _openJson(compMdl, url)
    if not isinstance(doc, dict):
        return facts, footnotes
    jsonFacts = doc.get("facts")
    if not isinstance(jsonFacts, dict):
        return facts, footnotes

    docNamespaces = {}
    docInfo = doc.get("documentInfo")
    if isinstance(docInfo, dict) and isinstance(docInfo.get("namespaces"), dict):
        docNamespaces = docInfo["namespaces"]

    prefixNs = getattr(module, "_prefixNamespaces", {}) or {}
    _factPrefix = getattr(factSource, "factIdentifierNamespacePrefix", None)
    factNs = prefixNs.get(_factPrefix) if _factPrefix else getattr(module, "_documentNamespaceURI", None)
    # bring the report's own namespaces into scope for member/unit resolution
    for p, u in docNamespaces.items():
        if p not in prefixNs:
            prefixNs[p] = u
    factPrefix = next((p for p, u in prefixNs.items() if u == factNs), None)

    # namespaceMaps redirection (fromNamespacePrefix -> toNamespacePrefix) for XBRL-format sources;
    # prefixes are resolved to their declared namespace URIs (declared in the module document namespaces).
    # When a namespaceMap omits fromNamespacePrefix, the toNamespacePrefix namespace is applied
    # irrespective of the namespace in the source (oim-taxonomy namespace map object). Mirrors the
    # xBRL-XML fact map (LoadXbrlXmlFacts.py): applied to the concept and to taxonomy-defined dimension /
    # member QNames, not to the core entity / period / unit dimensions.
    nsRedirect = {}
    nsRedirectAll = None
    for nsMap in (getattr(factSource, "namespaceMaps", None) or ()):
        frm = prefixNs.get(getattr(nsMap, "fromNamespacePrefix", None))
        to = prefixNs.get(getattr(nsMap, "toNamespacePrefix", None))
        if to:
            if frm:
                nsRedirect[str(frm)] = str(to)
            elif getattr(nsMap, "fromNamespacePrefix", None) is None:
                nsRedirectAll = str(to)

    def redirect(qn: Optional[QName]) -> Optional[QName]:
        if qn is not None:
            if qn.namespaceURI in nsRedirect:
                return QName(qn.prefix, nsRedirect[qn.namespaceURI], qn.localName)
            if nsRedirectAll is not None and qn.namespaceURI != nsRedirectAll:
                return QName(qn.prefix, nsRedirectAll, qn.localName)
        return qn

    for factId, factObj in jsonFacts.items():
        if not isinstance(factObj, dict):
            continue
        dimensions = factObj.get("dimensions") or {}
        conceptStr = dimensions.get("concept")
        conceptQn = qname(conceptStr, docNamespaces) if conceptStr else None

        if conceptQn == _qnNote:
            fnObj = XbrlFootnote()
            fnObj.name = SQName(factPrefix, factNs, str(dimensions.get("noteId") or factId))
            fnObj.forObjects = []
            fnObj.content = factObj.get("value")
            fnObj.language = dimensions.get("language")
            footnotes.append(fnObj)
            continue

        # migrate the source concept namespace (note detection above uses the un-redirected QName so a
        # no-fromNamespacePrefix remap-all cannot swallow the reserved xbrl:note concept)
        conceptQn = redirect(conceptQn)
        conceptObj = compMdl.namedObjects.get(conceptQn)
        if not isinstance(conceptObj, XbrlConcept):
            continue

        fact = XbrlFact()
        fact.module = module
        fact.parent = module
        fact.name = SQName(factPrefix, factNs, factId)
        fact.extends = None
        fact.factQualifier = None
        fact.factDimensions = {}
        fact.properties = None
        for dimName, dimVal in dimensions.items():
            if dimName in _coreByJsonName:
                coreQn = _coreByJsonName[dimName]
                if dimName == "concept":  # migrated like the concept above; entity/unit are not redirected
                    fact.factDimensions[coreQn] = redirect(qname(dimVal, docNamespaces)) or dimVal
                elif dimName in ("entity", "unit"):
                    fact.factDimensions[coreQn] = qname(dimVal, docNamespaces) or dimVal
                else:
                    fact.factDimensions[coreQn] = dimVal
            else:  # taxonomy-defined dimension, mapped directly
                dQn = qname(dimName, docNamespaces)
                if dQn is not None:
                    memQn = qname(dimVal, docNamespaces) if isinstance(dimVal, str) and ':' in dimVal else dimVal
                    fact.factDimensions[redirect(dQn)] = redirect(memQn) if isinstance(memQn, QName) else memQn

        fv = XbrlFactValue()
        fv.fact = fact
        fv.name = SQName(factPrefix, factNs, f"{factId}_fv")
        fv.value = factObj.get("value")
        fv.decimals = factObj.get("decimals")
        fv.language = dimensions.get("language")
        fv.valueSources = None
        fv.valueAnchors = None
        # An xBRL-JSON nil fact has value: null; mark it with the xbrl:nil property so it is recognised
        # as nil (matching native-OIM facts and the xBRL-XML / inline loaders).
        if fv.value is None:
            nilProp = XbrlProperty()
            nilProp.property = qnNil
            nilProp.value = qnUnknownNilReason
            fact.properties = [nilProp]
        fact.factValues = [fv]
        facts.append(fact)

    return facts, footnotes
