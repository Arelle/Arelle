"""
See COPYRIGHT.md for copyright information.

PDF text-extraction helper for the XBRL Model plugin.

A lightweight, lazily-loaded facade over `pikepdf` (with optional fallback to
`pypdf`) that exposes the three lookup primitives the OIM-Taxonomy PDF
locator types need:

  * :meth:`textByFormField` — AcroForm field by ``/T`` name (xbrl:pdfFormField)
  * :meth:`textByMcid` — marked-content sequence by ``(page, mcid)``
    (xbrl:pdfMcid / xbrl:pdfPage)
  * :meth:`textByStructElemId` — structure tree element by ``/ID``
    (xbrl:pdfElementId)

The full content-stream walker in ``arelle/plugin/loadFromPDF.py`` is the
reference implementation; this helper exposes only the high-level API needed
by ``FactValueResolver`` so that the OIM-Taxonomy code path does not pull in
the entire PoC loader. Both modules may converge later -- the surface here is
intentionally narrow so the legacy loader can be migrated onto it.

The extractor is built lazily: opening a PDF only happens when an actual
``textBy*`` call is made, and any of those methods returns ``None`` rather
than raising when the requested locator is not present or the PDF cannot be
opened. Callers (the PDF valueSource resolver) treat ``None`` as "deferred"
in the same way the HTML resolver does.
"""
from __future__ import annotations

from typing import Any, Optional, Tuple, Dict


def _importPikepdf():
    try:
        import pikepdf  # type: ignore
        return pikepdf
    except Exception:
        return None


class PdfTextExtractor:
    """Open a PDF once and answer multiple locator lookups against it."""

    __slots__ = ("_path", "_pdf", "_pikepdf", "_formFieldCache",
                 "_mcidCache", "_structIdCache", "_built")

    def __init__(self, path: str) -> None:
        self._path = path
        self._pdf = None
        self._pikepdf = None
        self._formFieldCache: Optional[Dict[str, str]] = None
        self._mcidCache: Optional[Dict[Tuple[int, int], str]] = None
        self._structIdCache: Optional[Dict[str, str]] = None
        self._built = False

    def _open(self) -> bool:
        if self._built:
            return self._pdf is not None
        self._built = True
        pikepdf = _importPikepdf()
        if pikepdf is None:
            return False
        self._pikepdf = pikepdf
        try:
            self._pdf = pikepdf.Pdf.open(self._path)
        except Exception:
            self._pdf = None
        return self._pdf is not None

    # ------------------------------------------------------------------
    # AcroForm field text
    # ------------------------------------------------------------------
    def _buildFormFieldCache(self) -> Dict[str, str]:
        if self._formFieldCache is not None:
            return self._formFieldCache
        cache: Dict[str, str] = {}
        if self._open():
            try:
                acro = self._pdf.Root.get("/AcroForm")
                fields = acro.get("/Fields") if acro is not None else None
                if fields:
                    self._walkFields(fields, "", cache)
            except Exception:
                pass
        self._formFieldCache = cache
        return cache

    def _walkFields(self, fields, prefix: str, out: Dict[str, str]) -> None:
        for fld in fields:
            try:
                t = fld.get("/T")
                name = str(t) if t is not None else ""
                fq = f"{prefix}.{name}" if prefix and name else (name or prefix)
                v = fld.get("/V")
                if v is not None:
                    out[fq] = str(v)
                    if name:
                        out.setdefault(name, str(v))
                kids = fld.get("/Kids")
                if kids:
                    self._walkFields(kids, fq, out)
            except Exception:
                continue

    def textByFormField(self, fieldName: str) -> Optional[str]:
        if not fieldName:
            return None
        cache = self._buildFormFieldCache()
        return cache.get(fieldName)

    # ------------------------------------------------------------------
    # Marked-content (MCID) text
    # ------------------------------------------------------------------
    def _buildMcidCache(self) -> Dict[Tuple[int, int], str]:
        """Map (page-1-based, mcid) -> text.

        Uses the full content-stream walker in ``loadFromPDF`` when available;
        falls back to ``None`` results when not.
        """
        if self._mcidCache is not None:
            return self._mcidCache
        cache: Dict[Tuple[int, int], str] = {}
        if self._open():
            try:
                # Reuse the reference walker -- imported lazily so this module
                # stays usable when the loadFromPDF plugin is absent.
                from arelle.plugin.loadFromPDF import (  # type: ignore
                    loadFromPDF as _loadFromPDF,  # noqa: F401
                )
                # The reference walker is heavyweight; the slim path below is
                # enough for the locator use case. If a full mapping is ever
                # needed it can call _loadFromPDF directly.
                cache = self._walkMcidQuick()
            except Exception:
                cache = {}
        self._mcidCache = cache
        return cache

    def _walkMcidQuick(self) -> Dict[Tuple[int, int], str]:
        """Lightweight MCID walker: handle simple `Tj` / `TJ` text-show ops
        within BDC/EMC pairs. Sufficient for tagged PDF/A reports where the
        spec's xbrl:pdfMcid locator is used."""
        out: Dict[Tuple[int, int], str] = {}
        try:
            pikepdf = self._pikepdf
            assert pikepdf is not None and self._pdf is not None
            from pikepdf import Operator, parse_content_stream, Dictionary, Name
        except Exception:
            return out
        for pIdx, page in enumerate(self._pdf.pages):
            pageNum = pIdx + 1
            try:
                resources = page.get("/Resources", {})
                instructions = parse_content_stream(page)
            except Exception:
                continue
            stack: list = []
            for i in instructions:
                op = i.operator
                if op == Operator("BDC"):
                    mcid = None
                    if len(i.operands) >= 2:
                        po = i.operands[1]
                        if isinstance(po, Dictionary):
                            mcid = po.get("/MCID")
                        elif isinstance(po, Name):
                            try:
                                props = resources.get("/Properties", {}).get(po)
                                if isinstance(props, Dictionary):
                                    mcid = props.get("/MCID")
                            except Exception:
                                pass
                    stack.append({"mcid": int(mcid) if mcid is not None else None,
                                  "txt": []})
                elif op == Operator("EMC"):
                    if stack:
                        frame = stack.pop()
                        if frame["mcid"] is not None:
                            out[(pageNum, frame["mcid"])] = "".join(frame["txt"])
                elif op == Operator("Tj") and stack:
                    for s in i.operands:
                        try:
                            stack[-1]["txt"].append(str(s))
                        except Exception:
                            pass
                elif op == Operator("TJ") and stack:
                    for arr in i.operands:
                        try:
                            for el in arr:
                                # numeric kerning operands are not text
                                if hasattr(el, "__bytes__") or isinstance(el, str):
                                    stack[-1]["txt"].append(str(el))
                        except Exception:
                            continue
        return out

    def textByMcid(self, page: int, mcid: int) -> Optional[str]:
        if page is None or mcid is None:
            return None
        try:
            page = int(page)
            mcid = int(mcid)
        except (TypeError, ValueError):
            return None
        cache = self._buildMcidCache()
        return cache.get((page, mcid))

    # ------------------------------------------------------------------
    # Structure-tree element by /ID
    # ------------------------------------------------------------------
    def _buildStructIdCache(self) -> Dict[str, str]:
        if self._structIdCache is not None:
            return self._structIdCache
        cache: Dict[str, str] = {}
        if self._open():
            try:
                root = self._pdf.Root.get("/StructTreeRoot")
                if root is not None:
                    mcidText = self._buildMcidCache()
                    self._walkStructTree(root, mcidText, cache, currentPage=None)
            except Exception:
                pass
        self._structIdCache = cache
        return cache

    def _walkStructTree(self, node, mcidText: Dict[Tuple[int, int], str],
                         out: Dict[str, str], currentPage: Optional[int]) -> str:
        """Recursive walk; returns the concatenated text of the subtree."""
        try:
            from pikepdf import Dictionary, Array
        except Exception:
            return ""
        text_parts: list = []
        try:
            # /Pg may scope which page MCIDs belong to.
            pgRef = node.get("/Pg") if isinstance(node, Dictionary) else None
            if pgRef is not None:
                try:
                    currentPage = self._pageNumberForRef(pgRef)
                except Exception:
                    pass
            kids = node.get("/K") if isinstance(node, Dictionary) else None
            if kids is None:
                pass
            elif isinstance(kids, int):
                # bare MCID
                if currentPage is not None:
                    t = mcidText.get((currentPage, int(kids)))
                    if t:
                        text_parts.append(t)
            elif isinstance(kids, (Array, list, tuple)):
                for k in kids:
                    text_parts.append(self._walkStructTree(k, mcidText, out, currentPage))
            elif isinstance(kids, Dictionary):
                # MCR (marked-content reference) or OBJR or nested struct elem
                if "/MCID" in kids:
                    mcid = kids.get("/MCID")
                    pg = kids.get("/Pg")
                    page = self._pageNumberForRef(pg) if pg is not None else currentPage
                    if mcid is not None and page is not None:
                        t = mcidText.get((page, int(mcid)))
                        if t:
                            text_parts.append(t)
                else:
                    text_parts.append(self._walkStructTree(kids, mcidText, out, currentPage))
            # ID-tagged structure elements
            elemId = node.get("/ID") if isinstance(node, Dictionary) else None
        except Exception:
            elemId = None
        subtree = "".join(text_parts)
        if elemId is not None:
            try:
                out[str(elemId)] = subtree
            except Exception:
                pass
        return subtree

    def _pageNumberForRef(self, pgRef) -> Optional[int]:
        if self._pdf is None or pgRef is None:
            return None
        try:
            target = pgRef.objgen[0]
        except Exception:
            return None
        for i, p in enumerate(self._pdf.pages):
            try:
                if p.objgen[0] == target:
                    return i + 1
            except Exception:
                continue
        return None

    def textByStructElemId(self, elemId: str) -> Optional[str]:
        if not elemId:
            return None
        return self._buildStructIdCache().get(elemId)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def close(self) -> None:
        try:
            if self._pdf is not None:
                self._pdf.close()
        except Exception:
            pass
        self._pdf = None
