"""
See COPYRIGHT.md for copyright information.

Fact ingestion pipeline.

Introduces three abstractions used by validation, vector search, cube assignment,
and (in later steps) lazy / streaming fact ingestion from CSV, xBRL-XML, HTML
and PDF value sources:

- `FactSourceLoader` Protocol: each implementation knows how to enumerate
  XbrlFact objects from a single origin (literal `factObject` entries on a
  module, a CSV table, an inline-HTML resolver, a PDF resolver, ...).

- `FactSink`: consumes XbrlFact objects one at a time. Currently drives
  per-fact resolution + cube position validation. Future steps will add
  batched VectorSearch encoding and bounded buffering for incremental
  processing of multi-GB sources without materializing all facts.

- Loader registry: backends register themselves under a key (the template
  class of the factMap, or an explicit media type) so that lazy
  `XbrlFactSource` resolution picks the right reader.

This module deliberately makes NO assumptions about ownership. The OIM-taxonomy
spec places facts directly on `XbrlModule`; the legacy `XbrlReport` object has
been removed.
"""
from __future__ import annotations

import io
from typing import Iterator, Iterable, Protocol, Optional, Callable, Any, TYPE_CHECKING

from arelle.ModelValue import QName
from .XbrlConst import xbrl as xbrlNs

if TYPE_CHECKING:
    from .XbrlFact import XbrlFact, XbrlFactSource
    from .XbrlModule import XbrlModule
    from .XbrlModel import XbrlCompiledModel

# Built-in fact map QNames the spec requires every processor to support without
# any explicit factMap definition in the taxonomy model.
qnXbrlXmlFactMap = QName("xbrl", xbrlNs, "xBRL-XML")
qnXbrlJsonFactMap = QName("xbrl", xbrlNs, "xBRL-JSON")
# POC-INLINE: built-in Inline XBRL 1.1 fact map. NOTE spec casing is inconsistent --
# oim-taxonomy.md uses "inline-XBRL-1.1" (fact-source enumeration) in one place and
# "inline-xbrl-1.1" (fact map section heading) in another; reconcile before finalizing.
qnInlineFactMap = QName("xbrl", xbrlNs, "inline-XBRL-1.1")


# --------------------------------------------------------------------
# Streaming threshold (CLI configurable)
# --------------------------------------------------------------------

# Default fact-count above which a producer SHOULD stream rather than
# materialize. Set via --xbrlModelStreamThreshold or via
# `compMdl.xbrlModelStreamThreshold`. The OIM spec exposes
# `factSourceMetadata.factCount` (when present) which is preferred over
# this default when deciding per-source whether to enforce streaming.
DEFAULT_STREAM_THRESHOLD = 50_000


def streamThresholdFor(compMdl: "XbrlCompiledModel") -> int:
    return int(getattr(compMdl, "xbrlModelStreamThreshold", DEFAULT_STREAM_THRESHOLD) or DEFAULT_STREAM_THRESHOLD)


# --------------------------------------------------------------------
# Loader protocol + registry
# --------------------------------------------------------------------

class FactSourceLoader(Protocol):
    """Yields XbrlFact objects from a single origin."""
    mediaType: str

    def facts(self) -> Iterator["XbrlFact"]:
        ...


# Registry mapping a key (template class, or an explicit string media type)
# to a factory callable. The factory is invoked as
# `factory(factSource, module, compMdl) -> FactSourceLoader`. Loaders register
# themselves at import time via `registerFactSourceLoader`.
_LOADER_FACTORIES: dict[Any, Callable[..., FactSourceLoader]] = {}


def registerFactSourceLoader(key: Any, factory: Callable[..., FactSourceLoader]) -> None:
    """Register a loader factory under a key (template class, or media type)."""
    _LOADER_FACTORIES[key] = factory


def resolveFactSourceLoader(factSource: "XbrlFactSource", module: "XbrlModule",
                            compMdl: "XbrlCompiledModel") -> Optional[FactSourceLoader]:
    """Locate and instantiate a loader for the given factSource, or return None.

    Resolution order:
      1. By template class of the `XbrlFactMap.templateName` target
         (`XbrlTableTemplate` for CSV, `XbrlXMLTemplateMap` for xBRL-XML,
         `XbrlJSONTemplateMap` for JSON, etc.)
      2. By an explicit `mediaType` string registered against the factSource's
         locator.

    Returns `None` if no loader is registered (caller may emit a diagnostic).
    """
    factMap = compMdl.namedObjects.get(getattr(factSource, "factMapName", None))
    template = compMdl.namedObjects.get(getattr(factMap, "templateName", None)) if factMap is not None else None
    if template is not None:
        factory = _LOADER_FACTORIES.get(type(template))
        if factory is not None:
            return factory(factSource, module, compMdl)
    return None


# --------------------------------------------------------------------
# Concrete loaders
# --------------------------------------------------------------------

class InlineFactsLoader:
    """Yields literal `factObject` facts authored directly on an XbrlModule."""
    mediaType = "application/oim-taxonomy+json"

    def __init__(self, module: "XbrlModule") -> None:
        self.module = module

    def facts(self) -> Iterator["XbrlFact"]:
        yield from (self.module.facts or ())


class LazyFactSourceLoader:
    """Wraps an `XbrlFactSource` and defers backend resolution + open() to the
    first `facts()` iteration.

    This is what makes multi-GB CSV/XML companion files safe: nothing is
    opened or read at taxonomy-load time. Validation passes that don't iterate
    facts (e.g. taxonomy-only schema export) pay zero IO cost.
    """
    mediaType = "deferred"

    def __init__(self, factSource: "XbrlFactSource", module: "XbrlModule",
                 compMdl: "XbrlCompiledModel") -> None:
        self.factSource = factSource
        self.module = module
        self.compMdl = compMdl
        self._backend: Optional[FactSourceLoader] = None
        self._resolved = False

    def _resolve(self) -> Optional[FactSourceLoader]:
        if not self._resolved:
            self._backend = resolveFactSourceLoader(self.factSource, self.module, self.compMdl)
            if self._backend is None:
                self.compMdl.error(
                    "arelle:noFactSourceLoader",
                    _("No FactSourceLoader registered for factSource %(name)s (factMap %(map)s). "
                      "The fact source will be skipped."),
                    xbrlObject=self.factSource,
                    name=getattr(self.factSource, "name", None),
                    map=getattr(self.factSource, "factMapName", None),
                )
            self._resolved = True
        return self._backend

    def shouldStream(self) -> bool:
        """Return True if this source's declared factCount exceeds the threshold."""
        metadata = getattr(self.factSource, "metadata", None)
        declared = getattr(metadata, "factCount", None) if metadata is not None else None
        if declared is None:
            return False
        return declared > streamThresholdFor(self.compMdl)

    def facts(self) -> Iterator["XbrlFact"]:
        backend = self._resolve()
        if backend is None:
            return
        yield from backend.facts()


# --------------------------------------------------------------------
# Module-level enumeration
# --------------------------------------------------------------------

def moduleLoaders(module: "XbrlModule",
                  compMdl: Optional["XbrlCompiledModel"] = None) -> Iterable[FactSourceLoader]:
    """Return the set of FactSourceLoaders applicable to a module.

    Always yields the inline loader (for literal `factObject` facts) plus one
    `LazyFactSourceLoader` per declared `XbrlFactSource` on the module. The
    lazy loaders do not touch external files until iterated.
    """
    if getattr(module, "facts", None):
        yield InlineFactsLoader(module)
    if compMdl is not None:
        builtins = _builtinFactMapParsers()
        for factSource in (getattr(module, "factSources", None) or ()):
            factMapQn = getattr(factSource, "factMapName", None)
            # factSources bound to a built-in fact map are materialized eagerly
            # onto module.facts (see materializeFactSourceFacts) and are already
            # covered by InlineFactsLoader.
            if factMapQn in builtins:
                continue
            # A locator-type fact map (factLocatorType, no templateName) only
            # binds a source document for factValue valueSource resolution -- it
            # generates no facts, so there is no loader to run for it. Only
            # template-backed custom maps (tableTemplate / jsonTemplateMap /
            # xmlTemplateMap) produce facts via the streaming lazy loader.
            factMap = compMdl.namedObjects.get(factMapQn)
            if getattr(factMap, "templateName", None) is None:
                continue
            yield LazyFactSourceLoader(factSource, module, compMdl)


# --------------------------------------------------------------------
# Sink
# --------------------------------------------------------------------

class FactSink:
    """Consumes XbrlFact objects and drives validation work for each.

    The sink is intentionally small: callers add side effects (cube assignment,
    vector indexing, completeness tracking) by passing callbacks rather than
    subclassing. This keeps the streaming path explicit and avoids growing a
    framework prematurely.
    """

    def __init__(
        self,
        compMdl: "XbrlCompiledModel",
        resolveFact,
        validateFactPosition,
        skipConcepts: Optional[set] = None,
        callResolveFact: bool = False,
    ) -> None:
        self.compMdl = compMdl
        self._resolveFact = resolveFact
        self._validateFactPosition = validateFactPosition
        self._skipConcepts = skipConcepts or set()
        self._callResolveFact = callResolveFact
        self.factCount = 0

    def accept(self, fact: "XbrlFact") -> None:
        from .XbrlCube import conceptCoreDim  # local import: cube module not needed at plugin import time
        conceptQn = (fact.factDimensions or {}).get(conceptCoreDim) if getattr(fact, "factDimensions", None) else None
        if conceptQn in self._skipConcepts:
            return
        if self._callResolveFact:
            module = getattr(fact, "parent", self.compMdl)
            self._resolveFact(self.compMdl, module, fact)
        self._validateFactPosition(self.compMdl, fact)
        self.factCount += 1


def iterModuleFacts(compMdl: "XbrlCompiledModel") -> Iterator["XbrlFact"]:
    """Yield every fact reachable through every module's loaders, lazily."""
    for module in compMdl.xbrlModels.values():
        for loader in moduleLoaders(module, compMdl):
            yield from loader.facts()


# --------------------------------------------------------------------
# Backend: CSV loader (streaming, registered for XbrlTableTemplate)
# --------------------------------------------------------------------

class CsvFactsLoader:
    """Streams XbrlFact objects out of a CSV-backed `XbrlFactSource`.

    Delegates to `LoadCsvTable.csvTableRowFacts`, which is itself a generator
    that consumes the CSV row-at-a-time. The loader thereby preserves the
    streaming guarantee: only one CSV row's worth of facts is live in
    Python-side memory at a time (modulo the consumer's own buffering).

    Note: full ingestion of `XbrlFactSource` from CSV is not yet exercised by
    the conformance suite. This loader is the wiring point; per-source
    table resolution will be filled in alongside step 6 (HTML resolver), at
    which time the locator-property registry pattern can be reused.
    """
    mediaType = "text/csv"

    def __init__(self, factSource: "XbrlFactSource", module: "XbrlModule",
                 compMdl: "XbrlCompiledModel") -> None:
        self.factSource = factSource
        self.module = module
        self.compMdl = compMdl

    def facts(self) -> Iterator["XbrlFact"]:
        from .LoadCsvTable import csvTableRowFacts
        # The XbrlFactSource references a factMap whose templateName is an
        # XbrlTableTemplate. The concrete `table` object (with `.url`,
        # `.parameters`, `.template`, `.optional`, `.name`) is expected to be
        # discoverable on the factSource via a tableSource attribute; until
        # the spec wires that explicitly we read it from `factSource.tableSource`
        # and skip with a diagnostic if absent.
        table = getattr(self.factSource, "tableSource", None)
        if table is None:
            self.compMdl.warning(
                "arelle:csvFactSourceNotResolved",
                _("XbrlFactSource %(name)s declares a CSV factMap but no resolvable tableSource; "
                  "CSV ingestion skipped."),
                xbrlObject=self.factSource,
                name=getattr(self.factSource, "name", None),
            )
            return
        for _rowIndex, rowFactObjs in csvTableRowFacts(
            table,
            self.compMdl,
            self.compMdl.error,
            self.compMdl.warning,
            self.module,
        ):
            yield from rowFactObjs


def _registerBuiltinLoaders() -> None:
    """Register backend loaders against their template classes.

    Done lazily to avoid import cycles (XbrlReport imports module types that
    transitively reach back here).
    """
    try:
        from .XbrlFact import XbrlTableTemplate
    except Exception:
        return
    registerFactSourceLoader(XbrlTableTemplate, CsvFactsLoader)


_registerBuiltinLoaders()


# --------------------------------------------------------------------
# Built-in fact map materialization (xbrl:xBRL-XML, xbrl:xBRL-JSON)
# --------------------------------------------------------------------

# Parse functions keyed by built-in factMap QName; each returns (facts, footnotes).
_BUILTIN_FACT_MAP_PARSERS: dict[Any, Callable[..., Any]] = {}


def _builtinFactMapParsers() -> dict[Any, Callable[..., Any]]:
    if not _BUILTIN_FACT_MAP_PARSERS:
        from .LoadXbrlXmlFacts import parseXbrlXmlFacts
        from .LoadOimJsonFacts import parseOimJsonFacts
        from .LoadInlineFacts import parseInlineFacts  # POC-INLINE
        _BUILTIN_FACT_MAP_PARSERS[qnXbrlXmlFactMap] = parseXbrlXmlFacts
        _BUILTIN_FACT_MAP_PARSERS[qnXbrlJsonFactMap] = parseOimJsonFacts
        _BUILTIN_FACT_MAP_PARSERS[qnInlineFactMap] = parseInlineFacts  # POC-INLINE
    return _BUILTIN_FACT_MAP_PARSERS


def _sourceUrlForFactSource(module: "XbrlModule", factSource: "XbrlFactSource") -> Optional[str]:
    """Resolve the source document URL for a factSource from the module's
    documentInfo.sourceMappings (matched by sourceName == factSource.name)."""
    for mapping in getattr(module, "_sourceMappings", None) or ():
        if getattr(mapping, "sourceName", None) == getattr(factSource, "name", None):
            return getattr(mapping, "url", None)
    return None


def materializeFactSourceFacts(compMdl: "XbrlCompiledModel", module: "XbrlModule") -> None:
    """Generate facts (and footnotes) from a module's factSources that reference a
    built-in fact map, and register them in the compiled model so the existing
    resolveFact / cube / vector-search / duplicate passes run over them.

    Called from validateXbrlModule before the module's facts are resolved (and, for a
    legacy report opened as an entry point, once at load time -- see
    ``pocLoadReportAsEntry``). Custom (template-backed) fact maps are handled by the
    streaming loader registry and are not materialized here.
    """
    # Idempotency: a report opened as an entry point materializes at load time; the
    # normal validate-time call must then be a no-op (else facts would be doubled).
    done = getattr(compMdl, "_builtinFactsMaterializedModules", None)
    if done is None:
        done = compMdl._builtinFactsMaterializedModules = set()
    if id(module) in done:
        return
    done.add(id(module))
    parsers = _builtinFactMapParsers()
    for factSource in getattr(module, "factSources", None) or ():
        parse = parsers.get(getattr(factSource, "factMapName", None))
        if parse is None:
            continue  # not a built-in map (custom template maps handled elsewhere)
        url = _sourceUrlForFactSource(module, factSource)
        if not url:
            compMdl.error("arelle:factSourceUrlNotFound",
                          _("The factSource %(name)s references factMap %(map)s but no "
                            "sourceMapping provides a source document URL."),
                          xbrlObject=factSource, name=getattr(factSource, "name", None),
                          map=getattr(factSource, "factMapName", None))
            continue
        # POC-LEGACY-DTS: discover the report's own DTS (schemaRef/linkbaseRef) and
        # compile it into the model as if imported, so facts from a legacy XBRL 2.1
        # report resolve against their taxonomy even when it is not otherwise present.
        # Compiled duplicate-tolerance means this is a no-op when the taxonomy is already
        # loaded. Remove this block with the POC.
        # POC-INLINE: the inline map does its OWN single-pass load (facts + DTS) inside
        # parseInlineFacts, so skip this pre-step for it to avoid loading the report twice.
        if getattr(factSource, "factMapName", None) != qnInlineFactMap:
            try:
                from .LoadLegacyTaxonomy import pocCompileLegacyDts
                pocCompileLegacyDts(compMdl.modelManager.cntlr, compMdl,
                                    compMdl.error, compMdl.warning, url)
            except Exception:
                pass  # POC: never let discovery break fact materialization
        facts, footnotes = parse(compMdl, module, factSource, url)
        for fact in facts:
            _registerGeneratedObject(compMdl, module, fact, "facts")
        for footnote in footnotes:
            _registerGeneratedObject(compMdl, module, footnote, "footnotes")


def _registerGeneratedObject(compMdl: "XbrlCompiledModel", module: "XbrlModule",
                             obj: Any, collectionName: str) -> None:
    obj.xbrlMdlObjIndex = len(compMdl.xbrlObjects)
    compMdl.xbrlObjects.append(obj)
    name = getattr(obj, "name", None)
    if name is not None and name not in compMdl.namedObjects:
        compMdl.namedObjects[name] = obj
    coll = getattr(module, collectionName, None)
    if coll is None:
        coll = []
        setattr(module, collectionName, coll)
    coll.append(obj)


# --------------------------------------------------------------------
# Legacy report entry-point loading (POC)
# --------------------------------------------------------------------
# Opening a legacy report (inline XBRL 1.1 .htm/.xhtml, XBRL 2.1 .xml instance, or
# xBRL-JSON .json instance) directly -- via GUI File->Open or CntlrCmdLine --file --
# loads it into the XbrlModel object model instead of the plain infrastructure, by
# synthesizing a driver module whose factSource binds the matching built-in fact map
# to the report. Mirrors the legacy .xsd entry-point loading in LoadLegacyTaxonomy
# (Hook 3). Remove this section with the POC.

_INLINE_XBRL_NS = "http://www.xbrl.org/2013/inlineXBRL"
_XBRLI_XBRL_CLARK = "{http://www.xbrl.org/2003/instance}xbrl"


def _xmlRootClarkName(filepath) -> Optional[str]:
    """Clark name of an XML document's root element, read cheaply (streaming), or None."""
    from lxml import etree
    try:
        for _event, elt in etree.iterparse(filepath, events=("start",)):
            return elt.tag  # first start event is the root element
    except Exception:
        return None
    return None


def pocReportEntryFactMap(filepath) -> Optional[str]:
    """POC: sniff a potential legacy report ENTRY point and return the built-in factMap
    QName string that would load it into the XbrlModel, or None if it is not a
    recognized report entry:

      * inline XBRL 1.1 (.htm/.html/.xhtml carrying the ix namespace) -> xbrl:inline-XBRL-1.1
      * XBRL 2.1 instance (.xml with an xbrli:xbrl root)              -> xbrl:xBRL-XML
      * xBRL-JSON instance (.json with an xbrl-json documentType)     -> xbrl:xBRL-JSON

    Never fires while the compiler is internally re-loading a report's DTS (the legacy
    discovery reentrancy guard), so those sub-loads take the infrastructure path.
    OIM taxonomy .json/.cbor documents are claimed elsewhere and are not report entries.
    """
    from . import LoadLegacyTaxonomy as _legacy
    if _legacy._pocInLegacyDiscovery or not filepath:
        return None
    stem = str(filepath).split("?", 1)[0].split("#", 1)[0]
    ext = stem.rsplit(".", 1)[-1].lower() if "." in stem else ""
    # An inline document inside an archive (report package .xbri / .zip resolves to an
    # archive-member .xhtml path) can't be read with io.open; claim it by extension --
    # an inline doc in a report package is inline XBRL. _loadInlineModel opens the
    # archive (report package) and handles catalog remappings + multi-doc IXDS.
    from arelle.FileSource import archiveFilenameParts
    _parts = archiveFilenameParts(filepath)
    if _parts is not None:
        innerExt = _parts[1].rsplit(".", 1)[-1].lower() if "." in _parts[1] else ""
        if innerExt in ("htm", "html", "xhtml"):
            return "xbrl:inline-XBRL-1.1"
        return None
    try:
        if ext in ("htm", "html", "xhtml"):
            with io.open(filepath, "rt", encoding="utf-8", errors="replace") as f:
                if _INLINE_XBRL_NS in f.read(16384):
                    return "xbrl:inline-XBRL-1.1"
        elif ext == "xml":
            if _xmlRootClarkName(filepath) == _XBRLI_XBRL_CLARK:
                return "xbrl:xBRL-XML"
        elif ext == "json":
            with io.open(filepath, "rt", encoding="utf-8", errors="replace") as f:
                if "xbrl-json" in f.read(4096):  # xBRL-JSON instance documentType
                    return "xbrl:xBRL-JSON"
    except (IOError, OSError, ValueError):
        pass
    return None


def pocLoadReportAsEntry(cntlr, modelXbrl, filepath, mappedUri, factMapName):
    """POC: load a legacy report entry point directly into ``modelXbrl`` as an OIM
    compiled model, by synthesizing a driver module whose factSource binds
    ``factMapName`` (a built-in fact map) to the report. The report's DTS and facts are
    materialized by the normal validate-time pass (``materializeFactSourceFacts``, called
    from validateXbrlModule) -- as for a factSource loaded from a real module document --
    so the model is an XbrlModel on open and fully populated once validated. Returns the
    ModelDocument."""
    url = mappedUri or filepath
    # If the entry resolved to a document inside an archive (report package), bind the
    # factSource to the archive (package) itself so _loadInlineModel applies the report
    # package's catalog remappings and discovers the whole (possibly multi-doc) IXDS.
    from arelle.FileSource import archiveFilenameParts
    _parts = archiveFilenameParts(url)
    if _parts is not None:
        url = _parts[0]
    moduleDict = {
        "documentInfo": {
            "documentType": xbrlNs + "/module",
            "namespaces": {
                "ex": "http://arelle.org/xbrlModel/legacyReport",
                "xbrl": xbrlNs,
                "xbrlm": xbrlNs + "/model",
                "xs": "http://www.w3.org/2001/XMLSchema",
            },
            "documentNamespacePrefix": "ex",
            "sourceMappings": [{"sourceName": "ex:report", "url": url}],
        },
        "xbrlModel": {
            "name": "ex:legacyReport",
            "importedTaxonomies": [{"xbrlModelName": "xbrlm:base"}],
            "factSources": [{"name": "ex:report", "factMapName": factMapName}],
        },
    }
    from . import loadXbrlModule  # lazy: avoid import cycle with the package
    doc = loadXbrlModule(cntlr, modelXbrl.error, modelXbrl.warning, modelXbrl, moduleDict, url)
    # Flag so the GUI view builder validates this model before building views (its DTS +
    # facts materialize at validate time); see xbrlModelViews.
    modelXbrl._xbrlModelReportEntry = True
    return doc
