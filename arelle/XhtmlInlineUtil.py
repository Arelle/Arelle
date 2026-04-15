"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urljoin

from arelle import XbrlConst

if TYPE_CHECKING:
    from arelle.ModelObject import ModelObject

INLINE_1_0_SCHEMA = "http://www.xbrl.org/2008/inlineXBRL/xhtml-inlinexbrl-1_0.xsd"
INLINE_1_1_SCHEMA = "http://www.xbrl.org/2013/inlineXBRL/xhtml-inlinexbrl-1_1.xsd"

htmlEltUriAttrs: dict[str, set[str]] = { # attributes with URI content (for relative correction and %20 canonicalization
    "a": {"href"},
    "area": {"href"},
    "blockquote": {"cite"},
    "del": {"cite"},
    "form": {"action"},
    "input": {"src", "usemap"},
    "ins": {"cite"},
    "img": {"src", "longdesc", "usemap"},
    "object": {"codebase", "classid", "data", "archive", "usemap"}, # codebase must be first to reolve others
    "q": {"cite"},
}

_IX10_ENTRIES: tuple[tuple[str, dict[str, str]], ...] = (
    ("footnote",    {"constraint": "ix10.5.1.1",  "validation": "ix10.5.1.2"}),
    ("fraction",    {"constraint": "ix10.6.1.1",  "validation": "ix10.6.1.2"}),
    ("denominator", {"constraint": "ix10.6.1.1",  "validation": "ix10.6.1.2"}),
    ("numerator",   {"constraint": "ix10.6.1.1",  "validation": "ix10.6.1.2"}),
    ("header",      {"constraint": "ix10.7.1.1",  "validation": "ix10.7.1.3",  "non-validatable": "ix10.7.1.2"}),
    ("hidden",      {"constraint": "ix10.8.1.1",  "validation": "ix10.8.1.2"}),
    ("nonFraction", {"constraint": "ix10.9.1.1",  "validation": "ix10.9.1.2"}),
    ("nonNumeric",  {"constraint": "ix10.10.1.1", "validation": "ix10.10.1.2"}),
    ("references",  {"constraint": "ix10.11.1.1", "validation": "ix10.11.1.2"}),
    ("resources",   {"constraint": "ix10.12.1.1", "validation": "ix10.12.1.2"}),
    ("tuple",       {"constraint": "ix10.13.1.1", "validation": "ix10.13.1.2"}),
    ("other",       {"constraint": "ix10",        "validation": "ix10"}),
)

_IX11_ENTRIES: tuple[tuple[str, dict[str, str]], ...] = (
    ("continuation",  {"constraint": "ix11.4.1.1",  "validation": "ix11.4.1.2"}),
    ("exclude",       {"constraint": "ix11.5.1.1",  "validation": "ix11.5.1.2"}),
    ("footnote",      {"constraint": "ix11.6.1.1",  "validation": "ix11.6.1.2"}),
    ("fraction",      {"constraint": "ix11.7.1.2",  "validation": "ix11.7.1.3"}),
    ("denominator",   {"constraint": "ix11.7.1.1",  "validation": "ix11.7.1.3"}),
    ("numerator",     {"constraint": "ix11.7.1.1",  "validation": "ix11.7.1.3"}),
    ("header",        {"constraint": "ix11.8.1.1",  "validation": "ix11.8.1.3",  "non-validatable": "ix11.8.1.2"}),
    ("hidden",        {"constraint": "ix11.9.1.1",  "validation": "ix11.9.1.2"}),
    ("nonFraction",   {"constraint": "ix11.10.1.1", "validation": "ix11.10.1.2"}),
    ("nonNumeric",    {"constraint": "ix11.11.1.1", "validation": "ix11.11.1.2"}),
    ("references",    {"constraint": "ix11.12.1.1", "validation": "ix11.12.1.2"}),
    ("relationship",  {"constraint": "ix11.13.1.1", "validation": "ix11.13.1.2"}),
    ("resources",     {"constraint": "ix11.14.1.1", "validation": "ix11.14.1.2"}),
    ("tuple",         {"constraint": "ix11.15.1.1", "validation": "ix11.15.1.2"}),
    ("other",         {"constraint": "ix11",        "validation": "ix11"}),
)

_ixSectIndex: dict[tuple[str, str, str], str] = {
    (ns, name, sect): value
    for ns, entries in ((XbrlConst.ixbrl, _IX10_ENTRIES), (XbrlConst.ixbrl11, _IX11_ENTRIES))
    for name, sects in entries
    for sect, value in sects.items()
}


def ixMsgCode(
    codeName: str,
    elt: ModelObject | None = None,
    sect: str = "constraint",
    ns: str | None = None,
    name: str | None = None,
) -> str:
    if elt is not None and ns is not None:
        raise ValueError(f"{ns=} must not be provided when {elt=}arelle is provided")

    if elt is not None:
        if elt.namespaceURI in XbrlConst.ixbrlAll:
            ns = elt.namespaceURI
        else:
            ns = str(getattr(elt.modelDocument, "ixNS", XbrlConst.ixbrl11))

        if name is None:
            name = "resources" if (ln := elt.localName) in ("context", "unit") else ln

    if ns is None:
        ns = XbrlConst.ixbrl11

    if name is None:
        name = "other"

    ixSection = _ixSectIndex.get((ns, name, sect)) or _ixSectIndex[(ns, "other", sect)]
    return f"{ixSection}:{codeName}"


def resolveHtmlUri(elt: ModelObject, name: str, value: str) -> str:
    if name == "archive":
        # URILIST
        return " ".join(
            resolveHtmlUri(elt, "archiveListElement", v) for v in value.split(" ")
        )

    if (
        elt.localName == "object"
        and name in ("classid", "data", "archiveListElement")
        and (base := elt.get("codebase")) is not None
    ):
        base = base + "/"
    else:
        base = str(
            getattr(elt.modelDocument, "htmlBase", "")
        )

    _uri = urljoin(base, value)
    return _uri
