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

    Ptok, Psrc, _cache = _build_pdf_text_stream(pdfPath)
    print(f"[pdf] text tokens={len(Ptok)}", flush=True)

    h2p = _patience_align(hm.tokens, Ptok)
    print(f"[align] {len(h2p)}/{len(hm.tokens)} tokens "
          f"({100*len(h2p)//max(1,len(hm.tokens))}%)", flush=True)

    # per-fact content locators (also serve as page anchors for image
    # multi-placement disambiguation), computed once and reused by the rewrite.
    pmsByFV: Dict[int, List[Tuple[int, int]]] = {}
    contentAnchors: List[Tuple[int, int]] = []   # (html token pos, pdf page)
    for fact in factsDoc.get("xbrlModel", {}).get("facts", []):
        for fv in fact.get("factValues", []):
            ids = perFV.get(id(fv))
            if not ids:
                continue
            pms = _fact_pms(ids, hm, h2p, Psrc)
            pmsByFV[id(fv)] = pms
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
    stats = _rewrite(factsDoc, perFV, pmsByFV, imgLocByFactId,
                     os.path.basename(pdfPath))
    print(f"[rewrite] content={stats['content']} image={stats['image']} "
          f"unmapped={stats['unmapped']} of {stats['total']}", flush=True)

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


def _rewrite(factsDoc, perFV, pmsByFV, imgLocByFactId, pdfBasename):
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
    stats = {"content": 0, "image": 0, "unmapped": 0, "total": 0}
    for fact in xm.get("facts", []):
        for fv in fact.get("factValues", []):
            ids = perFV.get(id(fv))
            if not ids:
                continue
            stats["total"] += 1
            pms = pmsByFV.get(id(fv)) or []
            if pms:
                fv["source"] = cSrc
                fv["valueSources"] = _content_sources(pms)
                stats["content"] += 1
                continue
            loc = next((imgLocByFactId[i] for i in ids if i in imgLocByFactId), None)
            if loc is not None:
                pg, bbox, h = loc
                fv["source"] = iSrc
                fv["valueSources"] = _image_source(pg, bbox, h)
                stats["image"] += 1
                continue
            # not located in the PDF: fall back to the retained html source
            # (its original htmlElementId valueSources stay unchanged).
            stats["unmapped"] += 1
            if htmlSrc is not None:
                fv["source"] = htmlSrc
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
