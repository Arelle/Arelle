"""Regenerate expected-pointers.json from the fixture documents.

Run from anywhere:  python3 tests/resources/html-element-pointer/generate.py

The output is asserted from BOTH languages -- by
tests/unit_tests/arelle/plugin/XbrlModel/test_html_element_pointer.py here, and
by elementPointer.corpus.test.js in the ixbrl-viewer repository, against its own
byte-identical copy of this directory. Regenerating therefore means updating
both copies and the CORPUS_SHA256 literal each side pins; that coupling is the
point, since undetected drift between the two implementations is the failure the
corpus exists to catch.

Expectations are produced by the PYTHON implementation because the fixtures are
also the aligner's inputs. That does not make Python authoritative: the
JavaScript is the reference (see HtmlElementPointer.py), and the JavaScript test
compares against these same bytes. Whichever side generated them, a disagreement
fails on the other.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, REPO)
sys.setrecursionlimit(200000)

from arelle.plugin.XbrlModel import HtmlElementPointer as hep      # noqa: E402
from arelle.plugin.XbrlModel.tools.alignFactsToSurface import _parse_source_tree   # noqa: E402

# (filename, media type). The media type is what selects the parse, and it is
# not sniffed: an XHTML document keeps the XML infoset, an HTML5 document is
# built by the HTML5 tree-construction algorithm, and the two disagree on both
# child indices and ancestry. The corpus covers one document of each.
DOCUMENTS = [
    ("tiny.xhtml", "application/xhtml+xml"),
    ("tiny-html5.html", "text/html"),
    ("adversarial.html", "text/html"),
]


def pointersFor(path, mediaType):
    """Every element in document order, with the pointer generated for it.

    Position in this list IS the element's identity across the two languages --
    both walk the tree preorder from the root element, so index i must be the
    same element in both. The tag travels with it so a structural disagreement
    between the parsers surfaces as a tag mismatch rather than as a confusing
    run of pointer mismatches.
    """
    root = _parse_source_tree(path, mediaType)
    idIndex = hep.buildIdIndex(root)
    rows = []
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue        # comments and PIs are not elements and are not counted
        pointer, verified, why = hep.verifiedPointer(el, root, idIndex)
        if not verified:
            raise SystemExit(f"{os.path.basename(path)}: {el.tag}: {why} ({pointer!r})")
        rows.append([len(rows), el.tag.split("}")[-1], pointer])
    return rows


def main():
    documents = []
    for name, mediaType in DOCUMENTS:
        path = os.path.join(HERE, name)
        with open(path, "rb") as fh:
            raw = fh.read()
        rows = pointersFor(path, mediaType)
        documents.append({
            "name": name,
            "mediaType": mediaType,
            # the fixture's own digest, so a document edited without
            # regenerating fails loudly instead of comparing stale pointers
            "sha256": hashlib.sha256(raw).hexdigest(),
            "elements": len(rows),
            "anchored": sum(1 for r in rows if not r[2].startswith("/")),
            "pointers": rows,
        })
        print(f"{name}: {len(rows)} elements, {documents[-1]['anchored']} anchored to an id")
    out = os.path.join(HERE, "expected-pointers.json")
    text = json.dumps({"documents": documents}, indent=1, ensure_ascii=False) + "\n"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    print(f"\nwrote {out}\nCORPUS_SHA256 = {digest}")
    print("update that literal in BOTH test suites, and copy this directory to\n"
          "  ixbrl-viewer/iXBRLViewerPlugin/viewer/src/js/xbrlModel/tagging/corpus/")


if __name__ == "__main__":
    main()
