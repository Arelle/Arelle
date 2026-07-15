"""
See XbrlModel/COPYRIGHT.md for copyright information.

THIS IS A PROOF OF CONCEPT.

inlineXbrlToPdf — convert an Inline XBRL (1.1) report into a structurally
tagged PDF whose PDF marked-content identifiers (MCIDs) are traceable back to
the original inline facts, and rewrite an OIM-Taxonomy (XBRL Model) facts file
so that each fact value's ``valueSources`` point at the PDF (page + MCID)
instead of the HTML element id.

Motivation
----------
Large SEC / ESEF inline-XBRL HTML reports (tens of MB) can exceed the DOM
budget of browser-based inline viewers. A structurally tagged PDF renders and
pages efficiently in any PDF viewer, and — because we capture the mapping from
each inline fact's HTML ``id`` to the PDF ``(page, mcid)`` at render time — the
fact-to-location traceability that the inline viewer provided is preserved.

Pipeline (this tool performs steps 2-4; step 1 is ``saveOIMFacts``)
-------------------------------------------------------------------
1. ``saveOIMFacts`` loads the inline document through Arelle and writes an
   OIM-Taxonomy facts file whose fact values carry ``valueSources`` using the
   ``xbrl:htmlElementId`` locator (the inline fact element's ``id``).
2. Render the same HTML to a tagged PDF with WeasyPrint, hooking its
   structure-tree builder to record ``htmlId -> [(page, mcid), ...]`` in
   document order. (A future extension can also set each PDF structure
   element's ``/ID`` to the HTML id so the ``xbrl:pdfElementId`` locator
   resolves directly; the current tool emits ``xbrl:pdfPage`` + ``xbrl:pdfMcid``
   sources, which round-trip 100% for numeric facts.)
3. Rewrite the facts file: swap each ``xbrl:htmlElementId`` value source for
   ``xbrl:pdfPage`` + ``xbrl:pdfMcid`` sources, retarget ``sourceMappings`` to
   the PDF, and switch the fact map to ``xbrl:pdfContentLocatorType``.
4. Embed the rewritten facts file inside the PDF as an attachment so the report
   travels as a single file (mirrors ``loadFromPDF`` in reverse).

The output PDF + embedded facts can be read back with
``arelle/plugin/loadFromPDF.py`` and the ``PdfTextExtractor`` /
``FactValueResolver`` PDF locator path.

Usage
-----
    DYLD_LIBRARY_PATH=/opt/homebrew/lib \
    python3 inlineXbrlToPdf.py --html report.xhtml --facts report-facts.json \
            --pdf report.pdf [--out-facts report-pdf-facts.json]

WeasyPrint (>=69) and its native Pango stack must be importable.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Set, Tuple

# --------------------------------------------------------------------------
# Locator property / object QNames (oim-taxonomy.md "Fact locator types")
# --------------------------------------------------------------------------
HTML_ELEMENT_ID = "xbrl:htmlElementId"
PDF_PAGE = "xbrl:pdfPage"
PDF_MCID = "xbrl:pdfMcid"
PDF_ELEMENT_ID = "xbrl:pdfElementId"
PDF_CONTENT_LOCATOR_TYPE = "xbrl:pdfContentLocatorType"

# ix elements that carry no rendered display content and must be hidden so
# WeasyPrint does not lay them out (mirrors what inline viewers do via CSS).
_HIDE_IX_CSS = r"""
ix\:header, ix\:hidden, ix\:references, ix\:resources,
ix\:relationship, ix\:exclude { display: none !important; }
"""

# Last-resort layout linearizer, used only if even the crash-guarded render
# fails. Degrades fidelity (collapses grid/flex, reverts tables to UA default),
# so it is NOT applied unless the guarded high-fidelity render still raises.
_SAFE_LAYOUT_CSS = r"""
* { float: none !important; }
[style*="grid"], [style*="flex"] { display: block !important; }
table, thead, tbody, tr, td, th { display: revert !important; }
"""


def _installGridCrashGuard() -> None:
    """Patch a WeasyPrint layout bug in-place so high-fidelity rendering
    survives real-world filings.

    During CSS-grid intrinsic track sizing, a table wrapper / formatting-context
    box nested in a grid item is laid out against a *temporary, un-positioned*
    containing block. ``avoid_collisions`` then calls
    ``containing_block.content_box_x()``, which reads ``position_x`` and raises
    ``AttributeError`` (seen on large SEC filings). Collision avoidance is
    meaningless during measurement, so we no-op in exactly that case and defer
    to the original implementation everywhere else. No CSS / layout is altered,
    so grid, flex, floats and tables all render as WeasyPrint intends.
    """
    import importlib
    import weasyprint.layout.float as _float
    orig = _float.avoid_collisions
    if getattr(orig, "_xbrlGuarded", False):
        return

    def guarded(context, box, containing_block, outer=True):
        if not hasattr(containing_block, "position_x"):
            return (getattr(box, "position_x", 0), getattr(box, "position_y", 0),
                    getattr(containing_block, "width", box.margin_width()))
        return orig(context, box, containing_block, outer)

    guarded._xbrlGuarded = True
    # block.py (and others) bind the name via ``from .float import
    # avoid_collisions``, so patch each importing module's namespace too.
    for modName in ("float", "block", "replaced", "inline"):
        mod = importlib.import_module(f"weasyprint.layout.{modName}")
        if hasattr(mod, "avoid_collisions"):
            mod.avoid_collisions = guarded


# --------------------------------------------------------------------------
# WeasyPrint render + tagging capture
# --------------------------------------------------------------------------
def renderTaggedPdf(
    htmlPath: str,
    pdfPath: str,
    factIds: Set[str],
    baseUrl: Optional[str] = None,
) -> Dict[str, List[Tuple[int, int]]]:
    """Render ``htmlPath`` to a PDF/UA tagged PDF at ``pdfPath`` and return a
    mapping ``htmlId -> [(page, mcid), ...]`` in document order for every id in
    ``factIds`` that produced marked content.

    The capture works by wrapping WeasyPrint's ``add_tags`` (the structure-tree
    builder): before it drains ``stream._tags`` (a per-page ``{box: {mcid}}``
    map) we walk each marked box up to the nearest ancestor element whose ``id``
    is a known fact id, and record ``(1-based page, mcid)``.
    """
    import weasyprint
    import weasyprint.pdf as wp_pdf
    import pydyf

    _installGridCrashGuard()  # survive grid/table layout bug on real filings
    html = weasyprint.HTML(filename=htmlPath, base_url=baseUrl)

    # Parent map over WeasyPrint's own parsed tree so we can climb from a
    # marked box's element to the nearest fact-id'd ancestor. WeasyPrint uses
    # xml.etree elements (no getparent()), hence an explicit id()-keyed map.
    root = html.etree_element
    parentOf: Dict[int, Any] = {}
    for parent in root.iter():
        for child in parent:
            parentOf[id(child)] = parent

    def nearestFactId(el: Any) -> Optional[str]:
        while el is not None:
            elId = el.attrib.get("id") if el.attrib else None
            if elId and elId in factIds:
                return elId
            el = parentOf.get(id(el))
        return None

    captured: Dict[str, List[Tuple[int, int]]] = OrderedDict()
    origAddTags = wp_pdf.add_tags

    def hookedAddTags(pdf, document, pdf_version, page_streams):
        # stream._tags preserves MCID assignment (== draw == document) order.
        for pageIdx, (page, stream) in enumerate(zip(document.pages, page_streams)):
            for box, info in stream._tags.items():
                el = getattr(box, "element", None)
                if el is None:
                    continue
                fid = nearestFactId(el)
                if fid is not None:
                    captured.setdefault(fid, []).append((pageIdx + 1, info["mcid"]))
        return origAddTags(pdf, document, pdf_version, page_streams)

    wp_pdf.add_tags = hookedAddTags
    try:
        stylesheets = [weasyprint.CSS(string=_HIDE_IX_CSS)]
        try:
            html.write_pdf(pdfPath, pdf_variant="pdf/ua-1", stylesheets=stylesheets)
        except AttributeError as e:
            # WeasyPrint layout-engine crash on unsupported grid/flex/float
            # combination: retry with linearized layout (lower fidelity).
            print(f"      normal layout failed ({e}); retrying with --safe-layout ...",
                  flush=True)
            captured.clear()
            stylesheets.append(weasyprint.CSS(string=_SAFE_LAYOUT_CSS))
            html.write_pdf(pdfPath, pdf_variant="pdf/ua-1", stylesheets=stylesheets)
    finally:
        wp_pdf.add_tags = origAddTags

    return captured


# --------------------------------------------------------------------------
# Chrome engine: token carrier (handles arbitrary fact nesting), XHTML mode
# --------------------------------------------------------------------------
#
# WeasyPrint is deterministic but does not scale (an 11h+ non-finish on a 182MB
# filing). Chrome renders the same file in minutes, so it is the engine for
# large filings. Chrome does NOT carry the HTML id onto PDF structure elements,
# and `<a>` link annotations cannot nest -- which caps coverage at the outermost
# facts (~13% on a deeply-nested N-CSR). The token carrier avoids both limits:
# a transparent inline token is independent text that renders (with its own
# MCID) regardless of nesting. Balanced ⟦N⟧…⟦/N⟧ tokens let a stack scan attribute
# each content MCID to every fact currently open, so nested leaves and their
# containers are all located.
_TOKEN_OPEN = "⟦"   # ⟦
_TOKEN_CLOSE = "⟧"  # ⟧
_TOKEN_RE = re.compile(r"⟦(/?)(\d+)⟧")
_TOKEN_CSS = ".xbrl-tok{font-size:1px;color:transparent;letter-spacing:-0.3px}"
# Reflow so absolutely-positioned "PDF-emulation" content (common: preparers
# emulate a fixed PDF page) is not clipped by print pagination. Faithful mode
# leaves ~87% of facts off-page on such filings; reflow recovers ~100% at the
# cost of the preparer's fixed appearance.
_REFLOW_CSS = ("*{position:static !important;inset:auto !important;"
               "transform:none !important;overflow:visible !important;"
               "float:none !important}")
_CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
)


def _findChrome() -> str:
    for c in _CHROME_CANDIDATES:
        if os.path.isabs(c):
            if os.path.exists(c):
                return c
        else:
            w = shutil.which(c)
            if w:
                return w
    raise RuntimeError("Chrome/Chromium not found for the 'chrome' engine")


def renderTaggedPdfChrome(htmlPath: str, pdfPath: str, factIds: Set[str],
                          reflow: bool = True) -> Dict[str, List[Tuple[int, int]]]:
    """Render ``htmlPath`` to a tagged PDF with Chrome and return
    ``htmlId -> [(page, mcid), ...]``.

    Injects balanced ``⟦N⟧…⟦/N⟧`` token spans inside each fact element, renders
    in XHTML mode (a ``.xhtml`` extension forces Chrome's XML parser, required
    for correct inline-XBRL semantics), then reconstructs locations by a
    balanced-token stack scan over the ordered marked-content stream.
    """
    from lxml import etree
    tree = etree.parse(htmlPath)
    root = tree.getroot()
    NS = root.nsmap.get(None)
    XH = f"{{{NS}}}" if NS else ""

    nToId: Dict[str, str] = {}
    idToN: Dict[str, str] = {}

    def _tok(text: str):
        s = etree.Element(f"{XH}span")
        s.set("class", "xbrl-tok")
        s.text = text
        return s

    for el in root.iter():
        _id = el.get("id")
        if _id in factIds and _id not in idToN:
            N = str(len(idToN))
            idToN[_id] = N
            nToId[N] = _id
            openTok = _tok(f"{_TOKEN_OPEN}{N}{_TOKEN_CLOSE}")
            openTok.tail = el.text   # preserve the element's leading text
            el.text = None
            el.insert(0, openTok)
            el.append(_tok(f"{_TOKEN_OPEN}/{N}{_TOKEN_CLOSE}"))

    head = root.find(f"{XH}head")
    if head is not None:
        style = etree.SubElement(head, f"{XH}style")
        style.text = _TOKEN_CSS + (("\n" + _REFLOW_CSS) if reflow else "")

    # .xhtml extension => Chrome uses the XML parser (correct inline-XBRL mode).
    wrappedPath = os.path.splitext(pdfPath)[0] + ".src.xhtml"
    tree.write(wrappedPath, method="xml", encoding="utf-8", xml_declaration=True)

    chrome = _findChrome()
    subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         "--export-tagged-pdf", f"--print-to-pdf={pdfPath}",
         f"file://{os.path.abspath(wrappedPath)}"],
        check=True, capture_output=True, text=True,
    )

    # Readback: PdfTextExtractor lives one directory up (the XbrlModel package).
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from PdfTextExtractor import PdfTextExtractor
    extractor = PdfTextExtractor(pdfPath)
    cache = extractor._buildMcidCache()      # {(page, mcid): text}, document order by key

    captured: Dict[str, List[Tuple[int, int]]] = {}
    stack: List[str] = []
    for (page, mcid), text in sorted(cache.items()):
        m = _TOKEN_RE.fullmatch(text.strip())
        if m:
            isClose, N = m.group(1), m.group(2)
            if isClose:
                if N in stack:
                    stack.remove(N)
            else:
                stack.append(N)
            continue
        if text.strip():
            for N in stack:                  # attribute content to every open fact
                captured.setdefault(nToId[N], []).append((page, mcid))
    return captured


# --------------------------------------------------------------------------
# Facts-file rewrite: html locator -> pdf locator
# --------------------------------------------------------------------------
def _collectHtmlIds(factsDoc: Dict[str, Any]) -> Set[str]:
    ids: Set[str] = set()
    for fact in factsDoc.get("xbrlModel", {}).get("facts", []):
        for fv in fact.get("factValues", []):
            for vs in fv.get("valueSources", []):
                for prop in vs.get("properties", []):
                    if str(prop.get("property", "")).endswith("htmlElementId"):
                        val = prop.get("value")
                        ids.update(val if isinstance(val, list) else [val])
    return ids


def _pdfValueSources(pageMcids: List[Tuple[int, int]]) -> List[Dict[str, Any]]:
    """Group a fact's ordered ``(page, mcid)`` locations into one
    factValueSource object per page, matching the spec example
    (aapl-10K-...-factset-pdf.json):

        {"properties": [
            {"property": "xbrl:pdfPage", "value": <int>},        # scalar
            {"property": "xbrl:pdfMcid", "value": [<int>, ...]}  # array
        ]}

    ``pdfPage`` is a scalar integer; ``pdfMcid`` is an array of integer MCIDs
    (kept in document order, duplicates preserved). A fact spanning multiple
    pages yields one source object per page, in page order; the sources
    aggregate by concatenation.
    """
    from itertools import groupby
    sources: List[Dict[str, Any]] = []
    # pageMcids is already in document order (page, then mcid), so grouping
    # consecutive entries by page reproduces the per-page grouping.
    for page, group in groupby(pageMcids, key=lambda pm: pm[0]):
        mcids = [int(mcid) for _page, mcid in group]
        sources.append({
            "properties": [
                {"property": PDF_PAGE, "value": int(page)},
                {"property": PDF_MCID, "value": mcids},
            ]
        })
    return sources


def rewriteFacts(
    factsDoc: Dict[str, Any],
    captured: Dict[str, List[Tuple[int, int]]],
    pdfBasename: str,
) -> Dict[str, int]:
    """Rewrite ``factsDoc`` in place so html-element value sources become
    pdf page+mcid value sources. Returns counters for reporting."""
    stats = {"rewritten": 0, "unmapped": 0, "factValues": 0}

    # documentInfo.sourceMappings -> point at the PDF
    for mapping in factsDoc.get("documentInfo", {}).get("sourceMappings", []) or []:
        mapping["url"] = pdfBasename

    # factMaps -> pdf content locator type
    for fm in factsDoc.get("xbrlModel", {}).get("factMaps", []) or []:
        if str(fm.get("factLocatorType", "")).endswith("htmlElementLocatorType"):
            fm["factLocatorType"] = PDF_CONTENT_LOCATOR_TYPE

    for fact in factsDoc.get("xbrlModel", {}).get("facts", []):
        for fv in fact.get("factValues", []):
            valueSources = fv.get("valueSources")
            if not valueSources:
                continue
            stats["factValues"] += 1
            # gather html ids referenced by this factValue, in order
            htmlIds: List[str] = []
            for vs in valueSources:
                for prop in vs.get("properties", []):
                    if str(prop.get("property", "")).endswith("htmlElementId"):
                        val = prop.get("value")
                        htmlIds.extend(val if isinstance(val, list) else [val])
            pageMcids: List[Tuple[int, int]] = []
            for hid in htmlIds:
                pageMcids.extend(captured.get(hid, []))
            if pageMcids:
                fv["valueSources"] = _pdfValueSources(pageMcids)
                stats["rewritten"] += 1
            else:
                # Not rendered (e.g. ix:hidden fact): drop the now-dangling html
                # value source. If a literal ``value`` is present it stays; the
                # fact remains valid without a locator.
                stats["unmapped"] += 1
                if "value" in fv:
                    del fv["valueSources"]
    return stats


# --------------------------------------------------------------------------
# Embed facts JSON into the PDF as an attachment
# --------------------------------------------------------------------------
def embedFactsInPdf(pdfPath: str, factsDoc: Dict[str, Any],
                    attachmentName: str = "xbrl-report.json") -> None:
    from pikepdf import Pdf, AttachedFileSpec
    pdf = Pdf.open(pdfPath, allow_overwriting_input=True)
    pdf.attachments[attachmentName] = AttachedFileSpec(
        pdf,
        json.dumps(factsDoc, indent=1).encode("utf-8"),
        mime_type="application/json",
    )
    pdf.save()


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------
def convert(htmlPath: str, factsPath: str, pdfPath: str,
            outFactsPath: Optional[str] = None, embed: bool = True,
            engine: str = "chrome", reflow: bool = True) -> Dict[str, Any]:
    with open(factsPath, "r", encoding="utf-8") as fh:
        factsDoc = json.load(fh)

    factIds = _collectHtmlIds(factsDoc)
    print(f"[1/3] rendering {os.path.basename(htmlPath)} -> tagged PDF "
          f"(engine={engine}, reflow={reflow}, anchoring {len(factIds)} fact ids) ...",
          flush=True)
    if engine == "chrome":
        captured = renderTaggedPdfChrome(htmlPath, pdfPath, factIds, reflow=reflow)
    elif engine == "weasyprint":
        captured = renderTaggedPdf(htmlPath, pdfPath, factIds,
                                   baseUrl=os.path.dirname(os.path.abspath(htmlPath)))
    else:
        raise ValueError(f"unknown engine {engine!r} (use 'chrome' or 'weasyprint')")
    print(f"      captured {len(captured)}/{len(factIds)} ids to PDF marked content")

    print("[2/3] rewriting fact valueSources html -> pdf ...", flush=True)
    stats = rewriteFacts(factsDoc, captured, os.path.basename(pdfPath))
    print(f"      factValues={stats['factValues']} rewritten={stats['rewritten']} "
          f"unmapped={stats['unmapped']}")

    outFactsPath = outFactsPath or (os.path.splitext(pdfPath)[0] + "-pdf-facts.json")
    with open(outFactsPath, "w", encoding="utf-8") as fh:
        json.dump(factsDoc, fh, indent=1)

    if embed:
        print("[3/3] embedding facts JSON into PDF ...", flush=True)
        embedFactsInPdf(pdfPath, factsDoc)

    return {"captured": captured, "stats": stats, "outFacts": outFactsPath}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Convert inline XBRL to a traceable tagged PDF.")
    ap.add_argument("--html", required=True, help="inline XBRL .xhtml/.html source")
    ap.add_argument("--facts", required=True, help="OIM-Taxonomy facts JSON from saveOIMFacts")
    ap.add_argument("--pdf", required=True, help="output tagged PDF path")
    ap.add_argument("--out-facts", default=None, help="output rewritten facts JSON path")
    ap.add_argument("--no-embed", action="store_true", help="do not embed facts JSON in the PDF")
    ap.add_argument("--engine", choices=("chrome", "weasyprint"), default="chrome",
                    help="render engine (default chrome; weasyprint is deterministic but does not scale)")
    ap.add_argument("--no-reflow", action="store_true",
                    help="chrome engine: keep the preparer's fixed (absolute) layout instead of "
                         "reflowing; faithful appearance but clipped facts are unlocatable")
    args = ap.parse_args(argv)
    result = convert(args.html, args.facts, args.pdf, args.out_facts,
                     embed=not args.no_embed, engine=args.engine, reflow=not args.no_reflow)
    print(f"done: {args.pdf}  facts: {result['outFacts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
