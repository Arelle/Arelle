"""
See XbrlModel/COPYRIGHT.md for copyright information.

THIS IS A PROOF OF CONCEPT.

alignFactsToPdf — locate inline-XBRL facts inside an EXISTING (filer- or
Acrobat-produced) tagged PDF, instead of generating a PDF from the HTML.

Motivation
----------
Generating a PDF from the inline document (see ``inlineXbrlToPdf.py``) never
looks as good as the filer's own PDF or an Acrobat conversion. This tool takes
the good-looking PDF as given and *matches* the facts onto it, producing PDF
``valueSources`` without any rendering:

1. **Visible facts** (fees, returns, prose) are matched by aligning the
   document-order word-token streams of the HTML and of the PDF marked content,
   then mapping each fact's html token range to the covering ``(page, mcid)``
   set — emitted with ``xbrl:pdfContentLocatorType`` (page + mcid).
   The alignment is a recursive *patience* alignment (anchor on tokens locally
   unique within each gap, recurse, difflib only on tiny base gaps) so it runs
   in well under a second on ~360k-token streams where a global difflib never
   finishes.

2. **Chart-series facts** — the SEC "Tailored Shareholder Report" pattern where
   the visual is an ``<img>`` chart and the ~85% of facts are in a
   ``clip:rect(0,0,0,0)`` visually-hidden data table beside it — have no visible
   tagged text to align to. Each such hidden data table is paired to its sibling
   chart ``<img>``; the image is matched to the PDF by content hash and its
   placement (page + bounding box) is recovered from the content-stream CTM.
   Those facts are emitted with ``xbrl:pdfImageLocatorType`` (page + bbox +
   imageHash) so a viewer can highlight the chart when any of them is selected.

Clip-hidden subtrees are excluded from the text alignment (they are not in the
PDF); including them is what otherwise collapses alignment quality on these
filings.

Usage
-----
    python3 alignFactsToPdf.py --html report.xhtml \
            --facts report-html-facts.json --pdf filer.pdf \
            [--out-facts report-pdf-facts.json]

``--facts`` is the OIM-Taxonomy facts file from ``saveOIMFacts`` (html
``valueSources``). The PDF must be tagged (marked content) for the text path;
the image path additionally needs the filing's image files next to the HTML.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
import re
import sys
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

IXNS = "http://www.xbrl.org/2013/inlineXBRL"
HTML_ELEMENT_ID = "xbrl:htmlElementId"
PDF_PAGE, PDF_MCID = "xbrl:pdfPage", "xbrl:pdfMcid"
PDF_BBOX, PDF_IMAGE_HASH = "xbrl:pdfBBox", "xbrl:pdfImageHash"
PDF_CONTENT_LOCATOR = "xbrl:pdfContentLocatorType"
PDF_IMAGE_LOCATOR = "xbrl:pdfImageLocatorType"

_WORD = re.compile(r"\w+|[^\w\s]")
def _toks(s: Optional[str]) -> List[str]:
    return [w.lower() for w in _WORD.findall(s)] if s else []

_SKIP_TAGS = {f"{{{IXNS}}}header", f"{{{IXNS}}}hidden", f"{{{IXNS}}}references",
              f"{{{IXNS}}}resources", f"{{{IXNS}}}relationship"}
def _skip_tag(tag) -> bool:
    if not isinstance(tag, str):
        return True
    return (tag in _SKIP_TAGS or tag.endswith("}head") or tag.endswith("}script")
            or tag.endswith("}style") or tag in ("head", "script", "style"))

def _local(tag) -> str:
    return tag.split("}")[-1] if isinstance(tag, str) else str(tag)

def _is_clip_hidden(style: Optional[str]) -> bool:
    """True for the visually-hidden `clip: rect(0,0,0,0)` pattern (any units)."""
    if not style:
        return False
    s = style.replace(" ", "").lower()
    return bool(re.search(r"clip:rect\(0\w*,0\w*,0\w*,0\w*\)", s))


# --------------------------------------------------------------------------
# HTML: document-order token stream + fact ranges + clip-hidden fact tables
# --------------------------------------------------------------------------
class HtmlModel:
    def __init__(self, root, tokens, idRange, clipHiddenFactIds, chartByFactId, chartTokenPos):
        self.root = root
        self.tokens = tokens                    # visible word tokens, doc order
        self.idRange = idRange                  # htmlId -> [start, end) in tokens
        self.clipHiddenFactIds = clipHiddenFactIds   # set of html ids in clip-hidden tables
        self.chartByFactId = chartByFactId      # html id -> chart <img> element
        self.chartTokenPos = chartTokenPos      # id(img element) -> visible-token position


def _build_html_model(htmlPath: str, factIds: Set[str]) -> HtmlModel:
    from lxml import etree
    root = etree.parse(htmlPath).getroot()
    tokens: List[str] = []
    idRange: Dict[str, List[Optional[int]]] = {}
    clipHiddenFactIds: Set[str] = set()
    chartByFactId: Dict[str, Any] = {}
    chartTokenPos: Dict[int, int] = {}
    sys.setrecursionlimit(200000)

    def collect_ids(el, out):
        if el.get("id") in factIds:
            out.add(el.get("id"))
        for c in el:
            collect_ids(c, out)

    def walk(el):
        tag = el.tag
        # clip-hidden subtree: not in the PDF text. Record its facts + chart img
        # (sibling <img> under the same parent), then do NOT emit its tokens.
        if _is_clip_hidden(el.get("style")):
            ids: Set[str] = set()
            collect_ids(el, ids)
            if ids:
                clipHiddenFactIds.update(ids)
                img = _find_sibling_chart(el)
                if img is not None:
                    chartTokenPos.setdefault(id(img), len(tokens))  # doc position
                    for i in ids:
                        chartByFactId[i] = img
            tokens.extend(_toks(el.tail))
            return
        if _skip_tag(tag):
            tokens.extend(_toks(el.tail))
            return
        _id = el.get("id")
        if _id in factIds:
            idRange.setdefault(_id, [len(tokens), None])
        tokens.extend(_toks(el.text))
        for c in el:
            walk(c)
        if _id in factIds and idRange.get(_id)[1] is None:
            idRange[_id][1] = len(tokens)
        tokens.extend(_toks(el.tail))

    # parent map for sibling-chart lookup
    global _PARENT
    _PARENT = {c: p for p in root.iter() for c in p}
    walk(root)
    return HtmlModel(root, tokens, idRange, clipHiddenFactIds, chartByFactId, chartTokenPos)


_PARENT: Dict[Any, Any] = {}
def _find_sibling_chart(clipTable):
    """The chart <img> is a sibling of the clip-hidden data table under the
    wrapping element (typically the enclosing ix:nonNumeric). Search the parent
    and grandparent subtrees for an <img> outside the clip-hidden table."""
    inside = set(id(d) for d in clipTable.iter())
    node = clipTable
    for _lvl in range(3):
        node = _PARENT.get(node)
        if node is None:
            break
        for d in node.iter():
            if _local(d.tag).lower() == "img" and id(d) not in inside:
                return d
    return None


# --------------------------------------------------------------------------
# HTML table rows (row-granular alignment)
# --------------------------------------------------------------------------
# The html DOM is well-formed (inline XBRL), so its TR/TH/TD structure is
# TRUSTED: a fact's row = its enclosing <tr>, with a label (leading non-fact
# cells) and value cells in document order. The row signature (label + value
# sequence) is far more distinctive than a bare value, which is what defeats
# repeated-value / 2-vs-3-period mismatches. The PDF side (built separately from
# glyph geometry, NOT its structure tags) is matched against these rows.
def _cell_tokens_ids(cell, factIds):
    """Tokens and fact ids contained in one table cell (excludes the cell's own
    tail, which belongs to the row)."""
    toks: List[str] = []
    ids: List[str] = []

    def rec(el):
        if el.get("id") in factIds:
            ids.append(el.get("id"))
        toks.extend(_toks(el.text))
        for c in el:
            rec(c)
        toks.extend(_toks(el.tail))

    toks.extend(_toks(cell.text))
    for c in cell:
        rec(c)
    return toks, ids


def _build_html_rows(root, factIds):
    """Rows in document order. Each row: ``{tokens, label, cells, factIds}`` where
    ``cells`` is the ordered list of fact-bearing value cells
    (``{factIds, tokens, col}``). Also returns ``factRow``: factId -> (rowIndex,
    cellIndex) so a fact can be placed within its matched PDF row."""
    rows: List[Dict[str, Any]] = []
    factRow: Dict[str, Tuple[int, int]] = {}
    for tr in root.iter():
        if _local(tr.tag).lower() != "tr":
            continue
        cells = [c for c in tr if _local(c.tag).lower() in ("td", "th")]
        if not cells:
            continue
        rowToks: List[str] = []
        label: List[str] = []
        valueCells: List[Dict[str, Any]] = []
        rowFactIds: List[str] = []
        for col, cell in enumerate(cells):
            ctoks, cids = _cell_tokens_ids(cell, factIds)
            rowToks.extend(ctoks)
            if cids:
                for fid in cids:
                    factRow[fid] = (len(rows), len(valueCells))
                valueCells.append({"factIds": cids, "tokens": ctoks, "col": col})
                rowFactIds.extend(cids)
            elif not valueCells:
                # leading non-fact cell(s) form the row label
                label.extend(ctoks)
        if valueCells:  # only rows that carry a fact are alignment units
            rows.append({"tokens": rowToks, "label": label,
                         "cells": valueCells, "factIds": rowFactIds})
    return rows, factRow


# --------------------------------------------------------------------------
# PDF: marked-content token stream (page, mcid)
# --------------------------------------------------------------------------
def _build_pdf_text_stream(pdfPath: str):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from PdfTextExtractor import PdfTextExtractor
    ex = PdfTextExtractor(pdfPath)
    cache = ex._buildMcidCache()               # {(page, mcid): text}
    tokens: List[str] = []
    src: List[Tuple[int, int]] = []
    for (pg, mc), text in sorted(cache.items()):
        for w in _toks(text):
            tokens.append(w); src.append((pg, mc))
    return tokens, src, cache


# --------------------------------------------------------------------------
# Recursive patience alignment: html-token-index -> pdf-token-index
# --------------------------------------------------------------------------
def _lis(pairs: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    tails: List[int] = []
    idx: List[int] = []
    prev = [-1] * len(pairs)
    for i, (_a, b) in enumerate(pairs):
        j = bisect.bisect_left(tails, b)
        if j == len(tails):
            tails.append(b); idx.append(i)
        else:
            tails[j] = b; idx[j] = i
        prev[i] = idx[j - 1] if j > 0 else -1
    if not idx:
        return []
    out: List[Tuple[int, int]] = []
    k = idx[-1]
    while k != -1:
        out.append(pairs[k]); k = prev[k]
    return out[::-1]


def _patience_align(H: List[str], P: List[str], base: int = 2500) -> Dict[int, int]:
    h2p: Dict[int, int] = {}
    work = [(0, len(H), 0, len(P))]
    while work:
        hlo, hhi, plo, phi = work.pop()
        hn, pn = hhi - hlo, phi - plo
        if hn <= 0 or pn <= 0:
            continue
        if hn * pn <= base:
            sm = SequenceMatcher(None, H[hlo:hhi], P[plo:phi], autojunk=False)
            for a, b, sz in sm.get_matching_blocks():
                for k in range(sz):
                    h2p[hlo + a + k] = plo + b + k
            continue
        hcount: Dict[str, int] = {}
        for i in range(hlo, hhi):
            hcount[H[i]] = hcount.get(H[i], 0) + 1
        pcount: Dict[str, int] = {}
        for i in range(plo, phi):
            pcount[P[i]] = pcount.get(P[i], 0) + 1
        hpos: Dict[str, int] = {}
        for i in range(hlo, hhi):
            if hcount[H[i]] == 1:
                hpos[H[i]] = i
        anchors: List[Tuple[int, int]] = []
        for i in range(plo, phi):
            t = P[i]
            if pcount.get(t) == 1 and t in hpos:
                anchors.append((hpos[t], i))
        anchors.sort()
        mono = _lis(anchors)
        if not mono:
            sm = SequenceMatcher(None, H[hlo:hhi], P[plo:phi], autojunk=True)
            for a, b, sz in sm.get_matching_blocks():
                for k in range(sz):
                    h2p[hlo + a + k] = plo + b + k
            continue
        prevh, prevp = hlo, plo
        for ah, ap in mono:
            h2p[ah] = ap
            work.append((prevh, ah, prevp, ap))
            prevh, prevp = ah + 1, ap + 1
        work.append((prevh, hhi, prevp, phi))
    return h2p


# --------------------------------------------------------------------------
# PDF image placements: contentHash -> [(page, bbox)], via content-stream CTM
# --------------------------------------------------------------------------
def _matmul(a, b):
    return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
            a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]

def _pdf_image_placements(pdfPath: str) -> Dict[str, List[Tuple[int, List[float]]]]:
    from pikepdf import Pdf, parse_content_stream, Operator
    from decimal import Decimal
    def f(x):
        return float(x) if isinstance(x, (Decimal, int, float)) else 0.0
    pdf = Pdf.open(pdfPath)
    byHash: Dict[str, List[Tuple[int, List[float]]]] = {}
    hashOfName: Dict[Tuple[int, str], Optional[str]] = {}
    for pi, page in enumerate(pdf.pages):
        xo = page.get("/Resources", {}).get("/XObject", {}) or {}
        imgnames = {}
        for name, obj in xo.items():
            if str(obj.get("/Subtype")) != "/Image":
                continue
            key = (pi, str(name))
            h = hashOfName.get(key)
            if h is None:
                try:
                    h = hashlib.md5(obj.read_raw_bytes()).hexdigest()
                except Exception:
                    h = ""
                hashOfName[key] = h
            imgnames[name] = h
        if not imgnames:
            continue
        try:
            instrs = parse_content_stream(page, "cm q Q Do")
        except Exception:
            continue
        ctm = [1, 0, 0, 1, 0, 0]
        stack: List[list] = []
        for instr in instrs:
            op = instr.operator
            if op == Operator("cm"):
                ctm = _matmul([f(x) for x in instr.operands], ctm)
            elif op == Operator("q"):
                stack.append(ctm[:])
            elif op == Operator("Q"):
                ctm = stack.pop() if stack else [1, 0, 0, 1, 0, 0]
            elif op == Operator("Do") and instr.operands and instr.operands[0] in imgnames:
                h = imgnames[instr.operands[0]]
                if not h:
                    continue
                xs = [ctm[4], ctm[0] + ctm[4], ctm[2] + ctm[4], ctm[0] + ctm[2] + ctm[4]]
                ys = [ctm[5], ctm[1] + ctm[5], ctm[3] + ctm[5], ctm[1] + ctm[3] + ctm[5]]
                bbox = [round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)]
                byHash.setdefault(h, []).append((pi + 1, bbox))
    return byHash


def _html_image_hash(imgEl, htmlDir: str) -> Optional[str]:
    src = imgEl.get("src")
    if not src or src.startswith("data:"):
        return None
    path = os.path.join(htmlDir, os.path.basename(src))
    if not os.path.exists(path):
        return None
    try:
        return hashlib.md5(open(path, "rb").read()).hexdigest()
    except Exception:
        return None


# --------------------------------------------------------------------------
# Perceptual-hash (dHash) fallback: pairs an HTML chart image to a PDF image
# when Acrobat re-encoded the JPEG so their exact bytes differ. This is only a
# pairing aid at authoring time -- the value stored in xbrl:pdfImageHash is
# still the matched PDF image's EXACT md5 (which a resolver verifies exactly).
# --------------------------------------------------------------------------
_PHASH_THRESHOLD = 10   # max Hamming distance (64-bit dHash) to accept a match

def _dhash(im, size: int = 8) -> int:
    from PIL import Image
    data = im.convert("L").resize((size + 1, size), Image.LANCZOS).tobytes()
    bits = 0
    for r in range(size):
        base = r * (size + 1)
        for c in range(size):
            bits = (bits << 1) | (1 if data[base + c] < data[base + c + 1] else 0)
    return bits

def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")

def _pil_from_pdf_image(obj):
    try:
        from pikepdf import PdfImage
        return PdfImage(obj).as_pil_image()
    except Exception:
        return None

def _html_image_phash(imgEl, htmlDir: str) -> Optional[int]:
    src = imgEl.get("src")
    if not src or src.startswith("data:"):
        return None
    path = os.path.join(htmlDir, os.path.basename(src))
    if not os.path.exists(path):
        return None
    try:
        from PIL import Image
        with Image.open(path) as im:
            return _dhash(im)
    except Exception:
        return None

def _pdf_image_phashes(pdfPath: str, wantMd5s: Set[str]) -> Dict[str, int]:
    """dHash of each PDF image XObject whose md5 is in wantMd5s (decode once)."""
    from pikepdf import Pdf
    pdf = Pdf.open(pdfPath)
    out: Dict[str, int] = {}
    for page in pdf.pages:
        xo = page.get("/Resources", {}).get("/XObject", {}) or {}
        for _name, obj in xo.items():
            if str(obj.get("/Subtype")) != "/Image":
                continue
            try:
                h = hashlib.md5(obj.read_raw_bytes()).hexdigest()
            except Exception:
                continue
            if h not in wantMd5s or h in out:
                continue
            im = _pil_from_pdf_image(obj)
            if im is not None:
                try:
                    out[h] = _dhash(im)
                except Exception:
                    pass
    return out


# --------------------------------------------------------------------------
# Locator builders (spec format)
# --------------------------------------------------------------------------
def _content_sources(pageMcids: List[Tuple[int, int]]) -> List[Dict[str, Any]]:
    from itertools import groupby
    out = []
    for page, group in groupby(pageMcids, key=lambda pm: pm[0]):
        out.append({"properties": [
            {"property": PDF_PAGE, "value": int(page)},
            {"property": PDF_MCID, "value": [int(mc) for _p, mc in group]},
        ]})
    return out

def _image_source(page: int, bbox: List[float], imgHash: str) -> List[Dict[str, Any]]:
    return [{"properties": [
        {"property": PDF_PAGE, "value": int(page)},
        {"property": PDF_BBOX, "value": " ".join(str(x) for x in bbox)},
        {"property": PDF_IMAGE_HASH, "value": f"md5:{imgHash}"},
    ]}]


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------
def _collect_fact_html_ids(factsDoc):
    perFactValue: Dict[int, List[str]] = {}
    allIds: Set[str] = set()
    for fact in factsDoc.get("xbrlModel", {}).get("facts", []):
        for fv in fact.get("factValues", []):
            ids: List[str] = []
            for vs in fv.get("valueSources", []) or []:
                for p in vs.get("properties", []):
                    if str(p.get("property", "")).endswith("htmlElementId"):
                        v = p.get("value"); ids += v if isinstance(v, list) else [v]
            if ids:
                perFactValue[id(fv)] = ids
                allIds.update(ids)
    return perFactValue, allIds


def align(htmlPath: str, factsPath: str, pdfPath: str,
          outFactsPath: Optional[str] = None) -> Dict[str, Any]:
    with open(factsPath, "r", encoding="utf-8") as fh:
        factsDoc = json.load(fh)
    perFV, allIds = _collect_fact_html_ids(factsDoc)
    print(f"[facts] {len(perFV)} factValues, {len(allIds)} html ids", flush=True)

    hm = _build_html_model(htmlPath, allIds)
    print(f"[html] visible tokens={len(hm.tokens)}  clip-hidden facts={len(hm.clipHiddenFactIds)}"
          f"  charts paired={len(set(id(v) for v in hm.chartByFactId.values()))}", flush=True)

    Ptok, Psrc, mcidCache = _build_pdf_text_stream(pdfPath)
    print(f"[pdf] text tokens={len(Ptok)}", flush=True)

    h2p = _patience_align(hm.tokens, Ptok)
    print(f"[align] {len(h2p)}/{len(hm.tokens)} tokens "
          f"({100*len(h2p)//max(1,len(hm.tokens))}%)", flush=True)

    # per-fact content locators (also serve as page anchors for image
    # multi-placement disambiguation), computed once and reused by the rewrite.
    pmsByFV: Dict[int, List[Tuple[int, int]]] = {}
    valueTextByFV: Dict[int, str] = {}           # the fact's own displayed html text
    contentAnchors: List[Tuple[int, int]] = []   # (html token pos, pdf page)
    for fact in factsDoc.get("xbrlModel", {}).get("facts", []):
        for fv in fact.get("factValues", []):
            ids = perFV.get(id(fv))
            if not ids:
                continue
            pms = _fact_pms(ids, hm, h2p, Psrc)
            pmsByFV[id(fv)] = pms
            parts: List[str] = []
            for hid in ids:
                r = hm.idRange.get(hid)
                if r and r[1] is not None:
                    parts.extend(hm.tokens[r[0]:r[1]])
            valueTextByFV[id(fv)] = " ".join(parts)
            if pms:
                r = hm.idRange.get(ids[0])
                if r and r[1] is not None:
                    contentAnchors.append((r[0], pms[0][0]))
    contentAnchors.sort()
    _anchorPos = [a[0] for a in contentAnchors]

    def _nearest_page(tokenPos: Optional[int]) -> Optional[int]:
        """Page of the nearest content-located fact to a document position;
        used to disambiguate an image placed on several pages."""
        if tokenPos is None or not contentAnchors:
            return None
        j = bisect.bisect_left(_anchorPos, tokenPos)
        cands = []
        if j < len(contentAnchors):
            cands.append(contentAnchors[j])
        if j > 0:
            cands.append(contentAnchors[j - 1])
        return min(cands, key=lambda a: abs(a[0] - tokenPos))[1] if cands else None

    # image placements only if there are clip-hidden facts with charts
    imgLocByFactId: Dict[str, Tuple[int, List[float], str]] = {}
    if hm.chartByFactId:
        print("[image] extracting PDF image placements ...", flush=True)
        placements = _pdf_image_placements(pdfPath)
        htmlDir = os.path.dirname(os.path.abspath(htmlPath))
        distinctCharts = {id(e): e for e in hm.chartByFactId.values()}

        def _pick(h, chartKey):
            """Choose a placement for image md5 ``h``; if placed on several
            pages, pick the one nearest this chart's document position."""
            pls = placements.get(h)
            if not pls:
                return None
            if len(pls) == 1:
                pg, bbox = pls[0]
                return (pg, bbox, h)
            want = _nearest_page(hm.chartTokenPos.get(chartKey))
            if want is None:
                return None
            pg, bbox = min(pls, key=lambda pb: abs(pb[0] - want))
            return (pg, bbox, h)

        chartPdf: Dict[int, Optional[Tuple[int, List[float], str]]] = {}
        unpaired: List[Tuple[int, Any]] = []
        multi = 0
        # pass 1: exact content hash (with multi-placement disambiguation)
        for key, imgEl in distinctCharts.items():
            h = _html_image_hash(imgEl, htmlDir)
            loc = _pick(h, key) if h else None
            chartPdf[key] = loc
            if loc is None:
                unpaired.append((key, imgEl))
            elif h in placements and len(placements[h]) > 1:
                multi += 1
        exactCharts = sum(1 for v in chartPdf.values() if v)
        # pass 2: perceptual (dHash) fallback for re-encoded charts (all
        # candidate images, single- or multi-placement)
        phashRecovered = 0
        if unpaired:
            print(f"[image] {len(unpaired)} charts unmatched by exact hash; trying dHash ...", flush=True)
            pdfPh = _pdf_image_phashes(pdfPath, set(placements.keys()))
            for key, imgEl in unpaired:
                ph = _html_image_phash(imgEl, htmlDir)
                if ph is None:
                    continue
                best, bestD = None, 1 << 30
                for h, pph in pdfPh.items():
                    d = _hamming(ph, pph)
                    if d < bestD:
                        bestD, best = d, h
                if best is not None and bestD <= _PHASH_THRESHOLD:
                    loc = _pick(best, key)
                    if loc is not None:
                        chartPdf[key] = loc
                        phashRecovered += 1
        for fid, imgEl in hm.chartByFactId.items():
            loc = chartPdf.get(id(imgEl))
            if loc is not None:
                imgLocByFactId[fid] = loc
        print(f"[image] charts matched: exact={exactCharts} (multi-placement disambiguated={multi}) "
              f"+dHash={phashRecovered}; chart facts located: {len(imgLocByFactId)}", flush=True)

    # ---- rewrite -----------------------------------------------------------
    # Sub-MCID glyph geometry (optional): lets a fact that is only a portion of a
    # coarse row-grained MCID be located by a tight glyph bbox of its own value.
    geom = None
    try:
        geom = _PdfGeometry(pdfPath)
    except Exception as e:
        print(f"[bbox] pypdfium2 geometry unavailable ({e}); portion facts keep pdfMcid", flush=True)

    # Row-granular alignment (primary): match the trusted html table rows against
    # the geometry-built PDF rows, monotone top-to-bottom, keyed on the row
    # signature. Fills the wrong/unmapped cases the global token alignment can't
    # disambiguate (repeated value, 2- vs 3-period). Facts not in a table row --
    # or in rows that did not match -- fall back to the token-alignment hybrid.
    rowPlacement: Dict[str, Tuple[int, Any, str]] = {}
    if geom is not None:
        htmlRows, _factRow = _build_html_rows(hm.root, set(allIds))
        rowPlacement = _row_align(htmlRows, geom, len(geom._doc))
        print(f"[rows] html rows={len(htmlRows)}  facts placed by row signature={len(rowPlacement)}", flush=True)

    # Phrase-locate fallback for facts still unmapped by row + token alignment
    # (prose text blocks, addresses): match the fact's distinctive text as a
    # phrase against the MCID cache. Expected page (nearest located neighbour)
    # breaks ties between repeated occurrences.
    phraseByFV: Dict[int, List[Tuple[int, int]]] = {}
    unmappedFVs = [fv for fact in factsDoc.get("xbrlModel", {}).get("facts", [])
                   for fv in fact.get("factValues", [])
                   if perFV.get(id(fv))
                   and not pmsByFV.get(id(fv))
                   and not any(i in rowPlacement for i in perFV[id(fv)])]
    if unmappedFVs:
        wordIdx, mcidWords = _build_mcid_word_index(mcidCache)
        for fv in unmappedFVs:
            ids = perFV[id(fv)]
            r = hm.idRange.get(ids[0])
            expected = _nearest_page(r[0]) if (r and r[1] is not None) else None
            hit = _phrase_locate(valueTextByFV.get(id(fv), ""), wordIdx, mcidWords, expected)
            if hit:
                phraseByFV[id(fv)] = hit
        print(f"[phrase] unmapped after row+token={len(unmappedFVs)}  located by phrase={len(phraseByFV)}", flush=True)

    stats = _rewrite(factsDoc, perFV, pmsByFV, imgLocByFactId,
                     os.path.basename(pdfPath),
                     valueTextByFV=valueTextByFV, mcidCache=mcidCache, geom=geom,
                     rowPlacement=rowPlacement, phraseByFV=phraseByFV)
    total = stats["total"]
    located = total - stats["unmapped"]
    pct = (100 * located // total) if total else 0
    print("[summary] fact locators in the PDF"
          f"\n    total facts ................. {total}"
          f"\n    located in PDF .............. {located}  ({pct}%)"
          f"\n      by method:  row-granular={stats['row']}  token={stats['token']}"
          f"  phrase={stats['phrase']}  image={stats['image']}"
          f"\n      by locator: pdfMcid={stats['content']}  pdfBBox={stats['bbox']}"
          f"  pdfImage={stats['image']}"
          f"\n    unlocated in PDF ........... {stats['unmapped']}  (kept html-element-id"
          " fallback; not resolvable while viewing the PDF)", flush=True)

    dropped = _sanitize_reserved_aliases(factsDoc)
    if dropped:
        print(f"[namespaces] dropped mis-bound reserved alias(es): {', '.join(dropped)}", flush=True)

    outFactsPath = outFactsPath or (os.path.splitext(pdfPath)[0] + "-pdf-facts.json")
    with open(outFactsPath, "w", encoding="utf-8") as fh:
        json.dump(factsDoc, fh, indent=1)
    print(f"done: {outFactsPath}")
    return {"stats": stats, "outFacts": outFactsPath}


def _fact_pms(ids, hm, h2p, Psrc):
    pms: List[Tuple[int, int]] = []
    for hid in ids:
        rng = hm.idRange.get(hid)
        if not rng or rng[1] is None:
            continue
        for hi in range(rng[0], rng[1]):
            pi = h2p.get(hi)
            if pi is not None:
                pm = Psrc[pi]
                if not pms or pms[-1] != pm:
                    pms.append(pm)
    return pms


def _sanitize_reserved_aliases(factsDoc):
    """Drop documentInfo.namespaces bindings for reserved OIM aliases whose URI does not match
    the reserved value (e.g. an upstream extractor emitting the legacy xbrli->2003/instance
    binding). A reserved alias bound to the wrong URI is invalid per oim-common
    (oimce:invalidURIForReservedAlias) whether or not it is used, so normalising it here keeps
    the produced module loadable. The year is taken from the xbrl namespace (https://xbrl.org/YYYY).
    Returns the list of dropped prefixes."""
    di = factsDoc.get("documentInfo") or {}
    namespaces = di.get("namespaces")
    if not isinstance(namespaces, dict):
        return []
    reserved = {
        "xs": "http://www.w3.org/2001/XMLSchema",
        "iso4217": "http://www.xbrl.org/2003/iso4217",
        "oimce": "https://xbrl.org/2021/oim-common/error",
        "oime": "http://www.xbrl.org/2021/oim/error",
    }
    year = None
    xbrlNs = namespaces.get("xbrl")
    if isinstance(xbrlNs, str):
        m = re.match(r"https://xbrl\.org/(\d{4})(?:/|$)", xbrlNs)
        if m:
            year = m.group(1)
    if year:
        reserved.update({
            "xbrl": f"https://xbrl.org/{year}",
            "xbrli": f"https://xbrl.org/{year}/instance",
            "ref": f"https://xbrl.org/{year}/ref",
            "utr": f"https://xbrl.org/{year}/utr",
            "xbrltt": f"https://xbrl.org/{year}/transform-types",
            "oimte": f"https://xbrl.org/{year}/oimtaxonomy/error",
        })
    dropped = [pfx for pfx, uri in list(namespaces.items())
               if pfx in reserved and uri != reserved[pfx]]
    for pfx in dropped:
        del namespaces[pfx]
    return dropped


# --------------------------------------------------------------------------
# POC: sub-MCID glyph geometry (pypdfium2). A content fact that occupies only a
# PORTION of a coarse (row-grained) MCID -- e.g. one figure in a whole-row MCID
# "TOTAL GROUPE 41 182,5 43 486,8 44 052,0 ..." -- is located by a pdfBBox (the
# glyph rectangle of its own value) instead of the shared MCID, so a viewer
# highlights just the value. A fact that IS its whole MCID(s) keeps pdfMcid
# (structural, reflow-robust). "The bbox we already have" = the image locator.
# --------------------------------------------------------------------------
_WS = re.compile(r"\s+")
def _norm(s: str) -> str:
    # Drop whitespace (a French thousands separator may be a space, nbsp, or
    # absent) and lower-case, so tokenisation differences don't defeat matching.
    return _WS.sub("", s or "").lower()


_NONNUM = re.compile(r"[^\d.,]")
def _valkey(s: str) -> str:
    """Magnitude key for a numeric cell: keep only digits and the decimal/group
    separators, dropping sign, spaces, parentheses, currency and percent. The
    html and the PDF often show negativity differently -- ``ix:nonFraction
    sign="-"`` omits the sign from the tagged text, while the PDF renders ``-``,
    ``- `` or ``(...)`` -- so matching on magnitude keeps the row signature
    aligned regardless of convention. Placement still uses the PDF glyph box,
    i.e. whatever the PDF actually shows (sign included)."""
    return _NONNUM.sub("", s or "")


class _PdfGeometry:
    """Lazy per-page character geometry (unicode + glyph boxes) via pypdfium2."""
    def __init__(self, pdfPath: str):
        import pypdfium2 as pdfium
        self._doc = pdfium.PdfDocument(pdfPath)
        self._pages: Dict[int, Any] = {}

    def _raw(self, page: int):
        key = ("raw", page)
        if key not in self._pages:
            tp = self._doc[page - 1].get_textpage()
            n = tp.count_chars()
            text = tp.get_text_range()
            boxes = [tp.get_charbox(i) for i in range(n)]  # (l,b,r,t), PDF pts, LL origin
            self._pages[key] = (text, boxes)
        return self._pages[key]

    def _page(self, page: int):
        if page not in self._pages:
            text, boxes = self._raw(page)
            norm, n2o = [], []
            for i in range(len(boxes)):
                ch = text[i]
                if not ch.isspace():
                    norm.append(ch.lower())
                    n2o.append(i)
            self._pages[page] = ("".join(norm), n2o, boxes)
        return self._pages[page]

    def rows(self, page: int):
        """Visual rows of the page from GLYPH GEOMETRY (structure tags ignored):
        cluster chars into rows by y-band, then segment each row into tokens by
        x-gap. Robust to the cell merges (horizontal/vertical) that corrupt a
        PDF's structure tree, because it reads where the ink physically sits.
        Returns a list of rows, each a list of ``(text, (x0,y0,x1,y1))`` tokens
        left-to-right."""
        key = ("rows", page)
        if key in self._pages:
            return self._pages[key]
        try:
            text, boxes = self._raw(page)
        except Exception:
            self._pages[key] = []
            return []
        chars = []
        for i in range(len(boxes)):
            ch = text[i]
            if ch.isspace():
                continue
            l, b, r, t = boxes[i]
            chars.append((l, b, r, t, ch))
        if not chars:
            self._pages[key] = []
            return []
        heights = sorted(t - b for l, b, r, t, _c in chars if t > b)
        medH = heights[len(heights) // 2] if heights else 8.0
        chars.sort(key=lambda c: (-(c[1] + c[3]) / 2, c[0]))  # top-to-bottom, then left
        bands, cur, curY = [], [], None
        for c in chars:
            cy = (c[1] + c[3]) / 2
            if curY is None or abs(cy - curY) <= medH * 0.6:
                cur.append(c)
                curY = cy if curY is None else (curY * (len(cur) - 1) + cy) / len(cur)
            else:
                bands.append(cur)
                cur, curY = [c], cy
        if cur:
            bands.append(cur)
        out = []
        for band in bands:
            band.sort(key=lambda c: c[0])
            widths = sorted(c[2] - c[0] for c in band if c[2] > c[0])
            medW = widths[len(widths) // 2] if widths else 4.0
            # Split into cells at COLUMN gaps only, not the small digit-group
            # (thousands) space -- otherwise "8 687,5" fragments into "8"+"687,5"
            # and won't match the html value "8687,5". A column gap is ~1.5+ char
            # widths; the thousands space is well under that.
            toks, tk = [], []
            for c in band:
                if tk and c[0] - tk[-1][2] > medW * 1.5:  # x-gap -> cell boundary
                    toks.append(tk)
                    tk = [c]
                else:
                    tk.append(c)
            if tk:
                toks.append(tk)
            rowToks = []
            for t in toks:
                s = "".join(c[4] for c in t)
                xs = [c[0] for c in t] + [c[2] for c in t]
                ys = [c[1] for c in t] + [c[3] for c in t]
                rowToks.append((s, (round(min(xs), 2), round(min(ys), 2),
                                    round(max(xs), 2), round(max(ys), 2))))
            out.append(rowToks)
        self._pages[key] = out
        return out

    def locate(self, page: int, contextText: str, valueText: str):
        """Union bbox (x0,y0,x1,y1) of valueText on the page. contextText (the
        MCID/row text) disambiguates which occurrence when the value repeats."""
        try:
            norm, n2o, boxes = self._page(page)
        except Exception:
            return None
        vn, cn = _norm(valueText), _norm(contextText)
        if not vn:
            return None
        pos = -1
        if cn:                                  # find the value inside its row
            ci = norm.find(cn)
            if ci >= 0:
                vi = norm.find(vn, ci, ci + len(cn) + len(vn))
                if vi >= 0:
                    pos = vi
        if pos < 0:
            # No context match: only trust the value when it is UNIQUE on the
            # page. A repeated value with no located row is ambiguous -- return
            # None so the fact keeps its (correct-row) pdfMcid rather than risk
            # highlighting the wrong occurrence.
            first = norm.find(vn)
            if first < 0 or norm.find(vn, first + 1) >= 0:
                return None
            pos = first
        rects = [boxes[n2o[k]] for k in range(pos, pos + len(vn)) if k < len(n2o)]
        if not rects:
            return None
        xs = [r[0] for r in rects] + [r[2] for r in rects]
        ys = [r[1] for r in rects] + [r[3] for r in rects]
        return (round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2))


def _bbox_source(page: int, bbox) -> List[Dict[str, Any]]:
    # A content fact located by a glyph bbox (no image hash), rendered by the
    # viewer's existing pdfBBox (image-region) path.
    return [{"properties": [
        {"property": PDF_PAGE, "value": int(page)},
        {"property": PDF_BBOX, "value": " ".join(str(x) for x in bbox)},
    ]}]


# --------------------------------------------------------------------------
# Row-granular alignment: monotone (top-to-bottom, both documents) match of the
# trusted html table rows against the geometry-built PDF rows, keyed on the row
# SIGNATURE (label + ordered value sequence). The signature is far more
# distinctive than a bare value, and the monotone order is an independent
# disambiguator, so a value repeated across statements / 2- vs 3-period
# presentations lands in its correct row. Returns factId -> (page, bbox,
# valueNorm) for every fact placed in a matched row.
# --------------------------------------------------------------------------
def _row_align(htmlRows, geom, npages: int):
    import difflib
    for r in htmlRows:
        r["vnorm"] = [_valkey("".join(c["tokens"])) for c in r["cells"]]
        r["lnorm"] = _norm("".join(r["label"]))
    # PDF rows flattened in reading order (page asc, rows already top-to-bottom)
    flat: List[Dict[str, Any]] = []
    for pg in range(1, npages + 1):
        for tokens in geom.rows(pg):
            vals, label = [], []
            for text, bbox in tokens:
                if any(ch.isdigit() for ch in text):
                    k = _valkey(text)          # magnitude key (sign-insensitive)
                    if k:
                        vals.append((k, bbox))
                else:
                    n = _norm(text)
                    if n:
                        label.append(n)
            flat.append({"page": pg, "vals": vals, "label": "".join(label)})
    val2rows: Dict[str, Set[int]] = {}
    for ri, pr in enumerate(flat):
        for n, _b in pr["vals"]:
            val2rows.setdefault(n, set()).add(ri)
    # candidate (htmlRow, pdfRow, score); score = value-subsequence coverage +
    # label similarity (label matched as a normalised string, since geometry may
    # merge label words into one token).
    cands: List[Tuple[int, int, float]] = []
    for hi, r in enumerate(htmlRows):
        hv = r["vnorm"]
        if not hv:
            continue
        rowset: Set[int] = set()
        for v in hv:
            rowset |= val2rows.get(v, set())
        scored = []
        for ri in rowset:
            pv = [n for n, _b in flat[ri]["vals"]]
            j = 0
            for x in pv:
                if j < len(hv) and x == hv[j]:
                    j += 1
            vscore = j / len(hv)
            if vscore < 0.6:
                continue
            lscore = (difflib.SequenceMatcher(None, r["lnorm"], flat[ri]["label"]).ratio()
                      if r["lnorm"] else 0.0)
            scored.append((vscore + 0.4 * lscore, ri))
        scored.sort(reverse=True)
        for score, ri in scored[:5]:
            cands.append((hi, ri, score))
    # weighted monotone chain: hi and ri both strictly increasing (top-to-bottom
    # in both documents), maximising total score. A CONTIGUITY bonus rewards
    # consecutive html rows landing on the same/adjacent PDF page: when a value
    # (a whole statement, even) is duplicated in the report -- e.g. the condensed
    # income statement in the management commentary AND the official one in the
    # financial statements -- the table must map as one contiguous block to its
    # real occurrence, not split across the duplicates (which the plain monotone
    # chain scores equally).
    _CONTIG = 0.6
    cands.sort(key=lambda c: (c[0], c[1]))
    m = len(cands)
    dp = [c[2] for c in cands]
    prev = [-1] * m
    for k in range(m):
        hi, ri, sc = cands[k]
        pk = flat[ri]["page"]
        for j in range(k):
            hj, rj, _s = cands[j]
            if hj < hi and rj < ri:
                bonus = _CONTIG if abs(pk - flat[rj]["page"]) <= 1 else 0.0
                v = dp[j] + sc + bonus
                if v > dp[k]:
                    dp[k] = v
                    prev[k] = j
    assign: Dict[int, int] = {}
    if m:
        k = max(range(m), key=lambda i: dp[i])
        while k != -1:
            hi, ri, _s = cands[k]
            assign[hi] = ri
            k = prev[k]
    # place each html value cell onto its pdf token (ordered), in the matched row
    placement: Dict[str, Tuple[int, Any, str]] = {}
    for hi, ri in assign.items():
        r = htmlRows[hi]
        pv = flat[ri]["vals"]
        j = 0
        for ci, cell in enumerate(r["cells"]):
            target = r["vnorm"][ci]
            while j < len(pv) and pv[j][0] != target:
                j += 1
            if j < len(pv):
                _n, bbox = pv[j]
                for fid in cell["factIds"]:
                    placement[fid] = (flat[ri]["page"], bbox, target)
                j += 1
    return placement


# --------------------------------------------------------------------------
# Phrase-locate fallback: for facts still unmapped after row-granular + token
# alignment (typically prose text blocks and addresses), find the fact's
# distinctive TEXT as a phrase in the MCID cache. Patience alignment anchors on
# UNIQUE tokens, so anchor-less prose (all common words) is skipped even when the
# text is present as one clean MCID -- a phrase (a contiguous run of common
# words) is distinctive where its individual words are not.
# --------------------------------------------------------------------------
_PW = re.compile(r"\w+", re.UNICODE)
def _phrase_toks(s: str) -> List[str]:
    return _PW.findall((s or "").lower())


def _build_mcid_word_index(mcidCache):
    """word -> [(page, mcid)] and (page, mcid) -> word list, over the MCID cache."""
    wordIdx: Dict[str, List[Tuple[int, int]]] = {}
    mcidWords: Dict[Tuple[int, int], List[str]] = {}
    for key, txt in mcidCache.items():
        ws = _phrase_toks(txt)
        mcidWords[key] = ws
        for w in set(ws):
            wordIdx.setdefault(w, []).append(key)
    return wordIdx, mcidWords


def _longest_run(a: List[str], b: List[str]) -> int:
    """Length of the longest common CONTIGUOUS word run between a and b (a is
    capped short; b is guarded against very long MCIDs by the caller)."""
    best = 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        bi = 0
        for j in range(1, len(b) + 1):
            if ai == b[j - 1]:
                bi = prev[j - 1] + 1
                cur[j] = bi
                if bi > best:
                    best = bi
        prev = cur
    return best


def _phrase_locate(factText, wordIdx, mcidWords, expectedPage=None):
    """Locate a text fact by phrase: return the matched (page, mcid) list (in
    mcid order on the chosen page), or []. A contiguous word run of at least
    ``thr`` words counts as a match; among equally good pages, the one nearest
    the fact's expected (neighbour) page wins."""
    fw = _phrase_toks(factText)
    if len(fw) < 3:
        return []
    fw = fw[:60]
    thr = 3 if len(fw) <= 6 else 5
    rare = sorted(set(fw), key=lambda w: len(wordIdx.get(w, ())))[:6]
    cand: Set[Tuple[int, int]] = set()
    for w in rare:
        cand.update(wordIdx.get(w, ()))
    scored = []
    for key in cand:
        mw = mcidWords[key]
        if len(mw) > 400:            # skip pathologically long MCIDs
            continue
        rl = _longest_run(fw, mw)
        if rl >= thr:
            scored.append((rl, key))
    if not scored:
        return []
    maxrl = max(rl for rl, _k in scored)
    best = [k for rl, k in scored if rl == maxrl]
    if expectedPage is not None:
        anchorPage = min(best, key=lambda k: abs(k[0] - expectedPage))[0]
    else:
        anchorPage = min(best, key=lambda k: k[0])[0]
    return [(anchorPage, mc) for mc in sorted(mc for rl, (pg, mc) in scored if pg == anchorPage)]


def _rewrite(factsDoc, perFV, pmsByFV, imgLocByFactId, pdfBasename,
             valueTextByFV=None, mcidCache=None, geom=None, rowPlacement=None,
             phraseByFV=None):
    rowPlacement = rowPlacement or {}
    phraseByFV = phraseByFV or {}
    di = factsDoc.setdefault("documentInfo", {})
    xm = factsDoc.setdefault("xbrlModel", {})
    # Preserve the original html source so facts not located in the PDF keep a
    # valid (html) locator; add two PDF sources for content and image locators.
    origMappings = di.get("sourceMappings") or []
    origFactSources = xm.get("factSources") or []
    origFactMaps = xm.get("factMaps") or []
    prefix = (origMappings[0]["sourceName"].split(":", 1)[0] if origMappings else "report")
    htmlSrc = origMappings[0]["sourceName"] if origMappings else None
    cSrc, iSrc = f"{prefix}:pdfContentSource", f"{prefix}:pdfImageSource"
    cMap, iMap = f"{prefix}:pdfContentMap", f"{prefix}:pdfImageMap"

    di["sourceMappings"] = list(origMappings) + [
        {"sourceName": cSrc, "url": pdfBasename},
        {"sourceName": iSrc, "url": pdfBasename},
    ]
    xm["factSources"] = list(origFactSources) + [
        {"name": cSrc, "factMapName": cMap},
        {"name": iSrc, "factMapName": iMap},
    ]
    xm["factMaps"] = list(origFactMaps) + [
        {"name": cMap, "factLocatorType": PDF_CONTENT_LOCATOR},
        {"name": iMap, "factLocatorType": PDF_IMAGE_LOCATOR},
    ]
    stats = {"row": 0, "token": 0, "phrase": 0, "content": 0, "bbox": 0, "image": 0, "unmapped": 0, "total": 0}
    # (page, magnitude key) -> [mcids]: lets a row-placed value that is exactly one
    # whole MCID keep the structural, reflow-robust pdfMcid rather than a bbox. Keyed
    # by _valkey so it matches the sign-insensitive row placement; a merged/coarse MCID
    # keys to a longer magnitude string and so won't match (falls to bbox).
    mcByPageVal: Dict[Tuple[int, str], List[int]] = {}
    for (pg, mc), txt in (mcidCache or {}).items():
        k = _valkey(txt)
        if k:
            mcByPageVal.setdefault((pg, k), []).append(mc)
    for fact in xm.get("facts", []):
        for fv in fact.get("factValues", []):
            ids = perFV.get(id(fv))
            if not ids:
                continue
            stats["total"] += 1
            # 1) row-granular placement (preferred): the fact was placed in a matched
            #    table row. Emit a whole-MCID pdfMcid when its value is exactly one MCID,
            #    else the row cell's glyph bbox (handles merged/coarse MCIDs).
            rid = next((i for i in ids if i in rowPlacement), None)
            if rid is not None:
                page, bbox, vnorm = rowPlacement[rid]
                mcs = mcByPageVal.get((page, vnorm))
                if mcs and len(mcs) == 1:
                    fv["reportSource"] = cSrc
                    fv["valueSources"] = _content_sources([(page, mcs[0])])
                    stats["content"] += 1
                else:
                    fv["reportSource"] = iSrc
                    fv["valueSources"] = _bbox_source(page, bbox)
                    stats["bbox"] += 1
                stats["row"] += 1
                continue
            # 2) token-alignment hybrid (fallback for non-table / unmatched-row facts)
            pms = pmsByFV.get(id(fv)) or []
            if pms:
                stats["token"] += 1
                # Hybrid locator: a fact that IS its whole MCID(s) keeps pdfMcid; a fact that is
                # only a PORTION of a coarse (row-grained) MCID -- its value a proper substring of
                # the MCID text -- is located by a glyph bbox of just its value instead.
                bboxLoc = None
                if valueTextByFV is not None and mcidCache is not None and geom is not None:
                    valueText = valueTextByFV.get(id(fv)) or ""
                    mcidText = " ".join(mcidCache.get(pm, "") for pm in pms)
                    vn, mn = _norm(valueText), _norm(mcidText)
                    if vn and mn and vn != mn and vn in mn:  # portion of a shared/coarse MCID
                        bboxLoc = geom.locate(pms[0][0], mcidText, valueText)
                if bboxLoc is not None:
                    fv["reportSource"] = iSrc
                    fv["valueSources"] = _bbox_source(pms[0][0], bboxLoc)
                    stats["bbox"] += 1
                else:
                    fv["reportSource"] = cSrc
                    fv["valueSources"] = _content_sources(pms)
                    stats["content"] += 1
                continue
            # 3) phrase-locate (text blocks / addresses the token aligner skipped)
            phit = phraseByFV.get(id(fv))
            if phit:
                fv["reportSource"] = cSrc
                fv["valueSources"] = _content_sources(phit)
                stats["phrase"] += 1
                stats["content"] += 1
                continue
            # 4) chart image region
            loc = next((imgLocByFactId[i] for i in ids if i in imgLocByFactId), None)
            if loc is not None:
                pg, bbox, h = loc
                fv["reportSource"] = iSrc
                fv["valueSources"] = _image_source(pg, bbox, h)
                stats["image"] += 1
                continue
            # not located in the PDF: fall back to the retained html source
            # (its original htmlElementId valueSources stay unchanged).
            stats["unmapped"] += 1
            if htmlSrc is not None:
                fv["reportSource"] = htmlSrc
    return stats


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Locate inline-XBRL facts in an existing tagged PDF.")
    ap.add_argument("--html", required=True, help="inline XBRL .xhtml/.html source")
    ap.add_argument("--facts", required=True, help="OIM-Taxonomy html-locator facts JSON (saveOIMFacts)")
    ap.add_argument("--pdf", required=True, help="existing tagged PDF to locate facts within")
    ap.add_argument("--out-facts", default=None, help="output rewritten facts JSON path")
    args = ap.parse_args(argv)
    align(args.html, args.facts, args.pdf, args.out_facts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
