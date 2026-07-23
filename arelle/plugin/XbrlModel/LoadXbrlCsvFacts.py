"""
See COPYRIGHT.md for copyright information.

xBRL-CSV built-in fact map.

Implements the ``xbrl:xBRL-CSV`` built-in fact map: it loads a standalone
xBRL-CSV *report* (an xBRL-CSV metadata JSON document plus its companion CSV
data files) into ``XbrlFact`` / ``XbrlFactValue`` objects, mirroring the
xBRL-XML ([LoadXbrlXmlFacts.py](LoadXbrlXmlFacts.py)) and xBRL-JSON
([LoadOimJsonFacts.py](LoadOimJsonFacts.py)) built-in maps.

Unlike the OIM ``XbrlTableTemplate`` CSV path -- where the tableTemplates are
taxonomy objects and the CSV url comes from ``documentInfo.sourceMappings`` (see
[FactPipeline.py](FactPipeline.py) ``CsvFactsLoader``) -- an xBRL-CSV report
carries its own ``tableTemplates`` (native shape: ``columns`` dict, table
``dimensions`` dict) and ``tables`` (``{url, template, parameters}``) in the
metadata document. Both share the CSV row-reading core
``LoadCsvTable.csvTableRowFacts``; this module is its native-metadata front-end.

The report's taxonomy is discovered from ``documentInfo.taxonomy`` by the caller
(``FactPipeline.materializeFactSourceFacts`` -> ``pocCompileLegacyDts``) before
this parser runs, so concepts / dimensions / members resolve against the compiled
model.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from arelle.ModelValue import QName, qname

if TYPE_CHECKING:
    from .XbrlModule import XbrlModule
    from .XbrlModel import XbrlCompiledModel
    from .XbrlFact import XbrlFactSource


class _NativeTableTemplate:
    """A native xBRL-CSV tableTemplate presented in the internal shape the CSV
    core consumes (``columns`` dict keyed by column id with a ``dimensions`` key,
    table-level ``dimensions`` dict, ``decimals``, ``rowIdColumn``)."""
    def __init__(self, name, columns, dimensions, decimals, rowIdColumn):
        self.name = name
        self.columns = columns
        self.dimensions = dimensions
        self.decimals = decimals
        self.rowIdColumn = rowIdColumn


def _openJson(compMdl, url):
    """Open + parse the xBRL-CSV metadata JSON, tolerating a BOM. Mirrors
    LoadOimJsonFacts._openJson (fileSource.file returns a 1-tuple for binary)."""
    modelXbrl = compMdl.modelXbrl
    mgr = modelXbrl.modelManager
    normalizedUri = mgr.cntlr.webCache.normalizeUrl(url)
    filepath = mgr.cntlr.webCache.getfilename(normalizedUri)
    if filepath is None:
        compMdl.error("arelle:factSourceNotFound",
                      _("The xBRL-CSV metadata document could not be retrieved: %(url)s"),
                      url=url)
        return None
    try:
        result = modelXbrl.fileSource.file(filepath, binary=True)
        _file = result[0]
        with _file:
            content = _file.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8-sig")
        return json.loads(content)
    except (OSError, ValueError) as ex:
        compMdl.error("arelle:factSourceLoadError",
                      _("Error loading xBRL-CSV metadata document %(url)s: %(error)s"),
                      url=url, error=str(ex))
        return None


def parseXbrlCsvFacts(compMdl, module, factSource, url):
    """Parse the xBRL-CSV report whose metadata document is at ``url`` and return
    ``(facts, footnotes)`` lists of unregistered objects for the caller to
    materialize. Footnotes are not yet mapped from xBRL-CSV (returns [])."""
    facts: list = []
    footnotes: list = []
    doc = _openJson(compMdl, url)
    if not isinstance(doc, dict):
        return facts, footnotes

    docInfo = doc.get("documentInfo") or {}
    docNamespaces = docInfo.get("namespaces") or {}

    # Bring the report's namespaces into the (disposable) driver module's prefix
    # map so concept / dimension / member SQNames resolve. The report wins on its
    # own prefixes: the entry-point driver binds a synthetic "ex" that would
    # otherwise shadow a report prefix of the same name.
    prefixNs = module._prefixNamespaces
    for p, u in docNamespaces.items():
        prefixNs[p] = u
    # Ensure generated fact SQNames (which are unprefixed local ids) resolve to a
    # namespace: fall back to the module's own document namespace when the report
    # declares no default namespace. (getattr guards an internal attr that is not
    # guaranteed set on every module shape.)
    if prefixNs.get(None) is None:
        prefixNs[None] = getattr(module, "_documentNamespaceURI", None)

    tableTemplates = doc.get("tableTemplates") or {}
    tables = doc.get("tables") or {}
    reportParameters = doc.get("parameters") or {}

    from .FactPipeline import _CsvTableSpec
    from .LoadCsvTable import csvTableRowFacts

    for tableId, tableObj in tables.items():
        if not isinstance(tableObj, dict):
            continue
        templateName = tableObj.get("template")
        tt = tableTemplates.get(templateName)
        if not isinstance(tt, dict):
            compMdl.error("xbrlce:unknownTableTemplate",
                          _("The xBRL-CSV table %(table)s references table template %(name)s "
                            "which is not present in the metadata document."),
                          table=tableId, name=templateName)
            continue
        template = _NativeTableTemplate(
            name=QName(None, prefixNs.get(None), templateName),
            columns=tt.get("columns") or {},
            dimensions=tt.get("dimensions") or {},
            decimals=tt.get("decimals"),
            rowIdColumn=tt.get("rowIdColumn"))
        tableSpec = _CsvTableSpec(
            name=QName(None, prefixNs.get(None), tableId),
            url=tableObj.get("url"),
            template=templateName,
            optional=bool(tableObj.get("optional", False)),
            parameters=tableObj.get("parameters") or {},
            tableTemplate=template,
            reportParameters=reportParameters)
        for _rowIndex, rowFactObjs in csvTableRowFacts(
                tableSpec, compMdl, compMdl.error, compMdl.warning, module, reportUrl=url):
            facts.extend(rowFactObjs)

    return facts, footnotes
