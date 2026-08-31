"""The Python half of the cross-language element-pointer corpus.

The browser tagger and the fact aligner generate XPointer child sequences for
the SAME documents -- the tagger in JavaScript
(``iXBRLViewerPlugin/viewer/src/js/xbrlModel/tagging/elementPointer.js``), the
aligner in Python (``arelle/plugin/XbrlModel/HtmlElementPointer.py``). Every way
the two can disagree is silent: both pointers resolve, to different elements, and
a fact ends up addressing a plausible value in the wrong place.

So agreement is asserted rather than assumed. Both languages generate pointers
for every element of the same fixtures and compare against the same
``expected-pointers.json``; ``test_corpus_digest_is_pinned`` pins that file's
digest on each side, so regenerating in one repository without syncing the other
fails instead of drifting.

Two of the fixture cases are live regressions rather than hypotheticals -- an
accented id and a triply-duplicated id; see ``adversarial.html``.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys

import pytest

PLUGIN = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "..",
    "arelle", "plugin", "XbrlModel"))


def _loadLeaf(name, path):
    """Load a module by path, without importing the XbrlModel package.

    ``arelle/plugin/XbrlModel/__init__.py`` is 1,569 lines and pulls in cbor2
    and jsonschema_rs before it will import. Neither module under test needs any
    of it: HtmlElementPointer imports ``re`` and ``typing``, alignFactsToSurface only
    the standard library (lxml and selectolax are imported lazily, inside the
    functions that parse). Loading the package to reach two leaves would tie
    this suite to the whole model runtime and to optional binary dependencies,
    for no coverage.
    """
    spec = importlib.util.spec_from_file_location(name, os.path.join(PLUGIN, path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


hep = _loadLeaf("_xbrlmodel_HtmlElementPointer", "HtmlElementPointer.py")
_parse_source_tree = _loadLeaf(
    "_xbrlmodel_alignFactsToSurface", os.path.join("tools", "alignFactsToSurface.py"))._parse_source_tree

CORPUS = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..",
                      "resources", "html-element-pointer")
CORPUS = os.path.normpath(CORPUS)

# Digest of expected-pointers.json, pinned identically in the viewer's
# elementPointer.corpus.test.js. Regenerate with generate.py and update BOTH.
CORPUS_SHA256 = "190290cee0711622b62c003252be30dcc815cfd9fcc68eaafcd5e60ec6be8fac"


@pytest.fixture(scope="module")
def expected():
    with open(os.path.join(CORPUS, "expected-pointers.json"), encoding="utf-8") as fh:
        return json.load(fh)["documents"]


def _documentIds(docs):
    return [d["name"] for d in docs]


@pytest.fixture(scope="module", autouse=True)
def _deepRecursion():
    # the walk is recursive and real reports nest deeply; the aligner raises the
    # limit for the same reason
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(200000)
    yield
    sys.setrecursionlimit(old)


def test_corpus_digest_is_pinned():
    """The two repositories must be comparing byte-identical expectations.

    Without this, regenerating here and forgetting the viewer copy leaves both
    suites green while the implementations diverge -- which is the whole failure
    this corpus exists to detect, reintroduced one level up.
    """
    with open(os.path.join(CORPUS, "expected-pointers.json"), "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    assert digest == CORPUS_SHA256, (
        "expected-pointers.json changed. Re-run generate.py, copy the corpus "
        "directory into ixbrl-viewer, and update CORPUS_SHA256 in both suites.")


def test_every_document_is_covered(expected):
    assert _documentIds(expected) == ["tiny.xhtml", "tiny-html5.html", "adversarial.html"]


@pytest.mark.parametrize("doc", [pytest.param(i, id=n) for i, n in enumerate(
    ["tiny.xhtml", "tiny-html5.html", "adversarial.html"])])
def test_fixture_is_unmodified(doc, expected):
    """A fixture edited without regenerating would compare stale pointers."""
    d = expected[doc]
    with open(os.path.join(CORPUS, d["name"]), "rb") as fh:
        assert hashlib.sha256(fh.read()).hexdigest() == d["sha256"], (
            f"{d['name']} was modified; re-run generate.py")


@pytest.mark.parametrize("doc", [pytest.param(i, id=n) for i, n in enumerate(
    ["tiny.xhtml", "tiny-html5.html", "adversarial.html"])])
def test_pointers_match_the_corpus(doc, expected):
    d = expected[doc]
    root = _parse_source_tree(os.path.join(CORPUS, d["name"]), d["mediaType"])
    idIndex = hep.buildIdIndex(root)
    got = []
    for el in root.iter():
        if isinstance(el.tag, str):
            got.append([len(got), el.tag.split("}")[-1],
                        hep.elementPointer(el, root, idIndex)])
    assert got == d["pointers"]


@pytest.mark.parametrize("doc", [pytest.param(i, id=n) for i, n in enumerate(
    ["tiny.xhtml", "tiny-html5.html", "adversarial.html"])])
def test_every_pointer_resolves_back(doc, expected):
    """Generation and resolution must be inverse, element for element."""
    d = expected[doc]
    root = _parse_source_tree(os.path.join(CORPUS, d["name"]), d["mediaType"])
    idIndex = hep.buildIdIndex(root)
    for el in root.iter():
        if isinstance(el.tag, str):
            pointer, verified, why = hep.verifiedPointer(el, root, idIndex)
            assert verified, f"{d['name']}: {el.tag}: {why} ({pointer!r})"


def test_html5_parse_synthesizes_tbody():
    """The corpus must actually exercise the parser divergence it claims to.

    tiny-html5.html writes <table><tr>, with no <tbody>. HTML5 tree construction
    inserts one and libxml2 does not, so every pointer below the table differs
    between the two parsers. If this assertion ever fails, the fixture has been
    "tidied" and the corpus has quietly stopped testing the thing that makes the
    conformant parse non-optional.
    """
    with open(os.path.join(CORPUS, "tiny-html5.html"), encoding="utf-8") as fh:
        # comments stripped first: the fixture's header comment says the word
        # "tbody" while explaining why the markup must not contain the tag
        markup = re.sub(r"<!--.*?-->", "", fh.read(), flags=re.S).lower()
    assert "<tbody" not in markup
    assert "<table>\n<tr>" in markup, "the table must open straight onto <tr>"
    root = _parse_source_tree(os.path.join(CORPUS, "tiny-html5.html"), "text/html")
    idIndex = hep.buildIdIndex(root)
    tbodies = [el for el in root.iter() if isinstance(el.tag, str)
               and el.tag.split("}")[-1] == "tbody"]
    assert len(tbodies) == 1
    assert hep.elementPointer(tbodies[0], root, idIndex) == "financial-highlights/4/1"


def test_media_type_is_load_bearing(expected):
    """Reading a document under the wrong parse mode is silently wrong.

    tiny.xhtml writes <table><tr> with no tbody, so it yields 25 elements under
    the XML infoset and 26 under HTML5 tree construction, and the pointers below
    its table differ accordingly. That is why the corpus records a media type per
    document and why _parse_source_tree takes one as a required argument rather
    than sniffing: on Microsoft's filed 10-K only 6.8% of pointers survive the
    swap, and none of the other 93.2% reports an error.
    """
    doc = next(d for d in expected if d["name"] == "tiny.xhtml")
    path = os.path.join(CORPUS, "tiny.xhtml")

    def pointers(mediaType):
        root = _parse_source_tree(path, mediaType)
        idIndex = hep.buildIdIndex(root)
        rows = []
        for el in root.iter():
            if isinstance(el.tag, str):
                rows.append([len(rows), el.tag.split("}")[-1],
                             hep.elementPointer(el, root, idIndex)])
        return rows

    asXml, asHtml = pointers("application/xhtml+xml"), pointers("text/html")
    assert [r[1] for r in asXml].count("tbody") == 0
    assert [r[1] for r in asHtml].count("tbody") == 1
    assert asXml == doc["pointers"]
    assert asHtml != doc["pointers"]


def test_accented_id_is_not_an_anchor():
    """Regression: Python's \\w is Unicode-aware, JavaScript's is not.

    The reference implementation rejects id="résultat-net" as not an NCName, so
    this must too -- otherwise the two emit different pointers for the element,
    both resolving, neither reporting anything.
    """
    root = _parse_source_tree(os.path.join(CORPUS, "adversarial.html"), "text/html")
    idIndex = hep.buildIdIndex(root)
    el = idIndex["résultat-net"][0]
    assert hep.elementPointer(el, root, idIndex) == "/1/2/1"


def test_first_of_a_duplicated_id_is_not_an_anchor():
    """Regression: the FIRST duplicate is the discriminating case.

    getElementById returns it, so a guard implemented as
    ``getElementById(id) === el`` anchors to an id addressing three elements.
    The second and third are refused by any implementation and prove nothing.
    """
    root = _parse_source_tree(os.path.join(CORPUS, "adversarial.html"), "text/html")
    idIndex = hep.buildIdIndex(root)
    dups = idIndex["dup"]
    assert len(dups) == 3
    assert [hep.elementPointer(el, root, idIndex) for el in dups] == \
        ["/1/2/2", "/1/2/3", "/1/2/10"]
