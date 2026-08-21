"""Pre-parse normalization of HTML5 source bytes, shared by every producer-side
consumer of an HTML5 document (the fact aligner, and any loader that builds
positional locators).

A positional locator counts element children of a *parsed tree*, so it is only
meaningful if Arelle's parse agrees with the browser's. lexbor (via selectolax)
is the parser that agrees -- but its scripting flag is off and selectolax exposes
no way to set it, which changes how one element is parsed:

Browsers parse ``<noscript>`` content as RAWTEXT because scripting is enabled.
lexbor parses it as elements, and a ``<noscript>`` in ``<head>`` lets that
content escape into ``<body>``, shifting every sibling index after it::

    <head><noscript><p>x</p></noscript></head><body><div id=a><div id=b>

      browser:  body > div#a, div#b
      lexbor:   body > p, div#a, div#b        <-- every later index shifts by 1

``normalizeNoscript`` removes the content while keeping the element, so indices
match the browser's tree. It must run pre-parse: once the ``<p>`` has escaped
into ``<body>``, nothing in the tree records where it came from.

Why this is a scanner and not a regex
-------------------------------------
The obvious ``rb'(<noscript[^>]*>)(.*?)(</noscript\\s*>)'`` corrupts documents,
verified against lexbor in three ways: a ``>`` inside a quoted attribute ends the
"open tag" mid-attribute and eats to the real close; a ``<noscript>`` string
literal inside ``<script>`` (or inside ``<!-- -->``) makes ``.*?`` span from the
literal to a later real close tag, destroying every element between. The last two
are ordinary in uncontrolled documents -- commented-out blocks and analytics JS.

The asymmetry a regex cannot express: with scripting on, noscript content is
RAWTEXT, so comments are not comments and scripts are not scripts *inside* it.
Comment/rawtext context therefore gates whether a ``<noscript>`` START tag is
real, while the matching close is simply the next literal ``</noscript>``.

Provenance and limits
---------------------
Algorithm and validation are from the HTML5 locator investigation; see
``iXBRLViewerPlugin/viewer/src/js/xbrlModel/HTML5-LOCATORS.md``. Measured against
real Safari over the 1,600-case html5lib-tests tree-construction corpus:
lexbor unnormalized 1556/1600, naive regex 1574/1600 (while corrupting
documents), this scanner 1575/1600 -- which is Safari's own agreement rate with
Chrome, with zero noscript residual. The function is idempotent, which matters
because the tagger and the aligner may both run it.

Validated against that synthetic conformance corpus and hand-built adversarial
cases, not against a large body of real-world HTML5. The rawtext element list
below has not been audited against the full HTML5 rawtext/escapable-rawtext set.
"""
import re

_COMMENT = re.compile(rb'<!--')
_RAWTEXT = re.compile(rb'<(script|style|textarea|title)\b(?:[^>"\']|"[^"]*"|\'[^\']*\')*>', re.I)
_NS_OPEN = re.compile(rb'<noscript\b(?:[^>"\']|"[^"]*"|\'[^\']*\')*>', re.I)
_NS_CLOSE = re.compile(rb'</noscript\s*>', re.I)


def normalizeNoscript(data: bytes) -> bytes:
    """Blank the content of every ``<noscript>``, keeping the element itself."""
    out, pos, n = [], 0, len(data)
    while pos < n:
        cand = []
        m = _COMMENT.search(data, pos)
        if m:
            cand.append((m.start(), 'c', m))
        m = _RAWTEXT.search(data, pos)
        if m:
            cand.append((m.start(), 'r', m))
        m = _NS_OPEN.search(data, pos)
        if m:
            cand.append((m.start(), 'n', m))
        if not cand:
            break
        start, kind, m = min(cand, key=lambda t: t[0])
        if kind == 'c':                       # comment: copy through its end
            end = data.find(b'-->', m.end())
            end = n if end < 0 else end + 3
            out.append(data[pos:end])
            pos = end
        elif kind == 'r':                     # rawtext element: copy through its close
            tag = m.group(1)
            close = re.compile(rb'</' + re.escape(tag) + rb'\s*>', re.I).search(data, m.end())
            end = n if close is None else close.end()
            out.append(data[pos:end])
            pos = end
        else:                                 # real noscript: keep tag, drop content
            close = _NS_CLOSE.search(data, m.end())
            if close is None:
                out.append(data[pos:m.end()])   # unclosed: rawtext runs to EOF
                pos = n
            else:
                out.append(data[pos:m.end()])
                pos = close.start()
    out.append(data[pos:])
    return b"".join(out)
