"""XPointer element() scheme child sequences, for locating facts in HTML that
cannot be modified.

A Python port of the viewer's reference implementation,
``iXBRLViewerPlugin/viewer/src/js/xbrlModel/tagging/elementPointer.js``. The
browser tagger and the fact aligner generate pointers for the SAME documents, so
the two implementations must agree exactly: every way a pointer goes wrong is
silent -- it resolves to a real but different element and yields a plausible
value from the wrong place. Keep this file and the JavaScript in step, and assert
both against a shared corpus rather than trusting that they match.

Pointers are written WITHOUT the ``element(...)`` wrapper -- ``f1``, ``/1/14``,
``currentAssets/2/1``. The wrapper exists in XBRL 2.1 because the fragment
identifier after ``#`` is a slot shared by several pointer schemes; a dedicated
property is not a shared slot.

Integers are 1-based and count ELEMENT children only. In lxml, iterating an
element also yields comments and processing instructions, whose ``tag`` is not a
string -- counting those would shift every index after them, exactly the failure
this addressing scheme cannot tolerate. Every traversal here filters them.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

# An id usable as an anchor must be an NCName, so it is expressible as a
# shorthand pointer. Matches the reference implementation's pattern exactly.
_NCNAME = re.compile(r"^[A-Za-z_][\w.\-]*$")


def buildIdIndex(root) -> Dict[str, List[Any]]:
    """Map id -> [elements] in one pass.

    Built once per document rather than searched per pointer: a child-index path
    and an id lookup are indistinguishable in cost once either is resolved
    through a single indexing pass, and searching per lookup is what makes
    positional addressing appear slow.

    The value is a LIST, not an element, because duplicate ids are invalid but
    occur in real filings and the count is what decides usability.
    """
    index: Dict[str, List[Any]] = {}
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        elementId = el.get("id")
        if elementId:
            index.setdefault(elementId, []).append(el)
    return index


def _elementChildren(el) -> List[Any]:
    return [c for c in el if isinstance(c.tag, str)]


def _isUsableAnchor(el, idIndex: Dict[str, List[Any]]) -> bool:
    """True if the element's id addresses exactly one element.

    A duplicate id is silently resolved to the first match by every DOM API, so
    anchoring to one would point a fact at the wrong element with no error.
    Anchoring is skipped in that case and the sequence continues upward.
    """
    elementId = el.get("id")
    if not elementId or not _NCNAME.match(elementId):
        return False
    return len(idIndex.get(elementId) or ()) == 1


def _childIndex(el) -> int:
    """1-based position among the element children of the parent."""
    parent = el.getparent()
    if parent is None:
        return 1
    n = 0
    for c in parent:
        if isinstance(c.tag, str):
            n += 1
            if c is el:
                return n
    return n


def elementPointer(el, root, idIndex: Dict[str, List[Any]]) -> Optional[str]:
    """Build the pointer for an element, or None if it is not in this tree.

    Prefers the shortest robust form: the element's own id, else a sequence from
    the nearest usable ancestor id, else a full sequence from the document. The
    hybrid form is preferred where it exists because it is unaffected by
    structural change anywhere outside its anchor -- which is the failure a bare
    sequence handles worst, and the likely one when the document is regenerated
    independently of the model.
    """
    if el is None or not isinstance(el.tag, str):
        return None
    if _isUsableAnchor(el, idIndex):
        return el.get("id")
    steps: List[str] = []
    cur = el
    while cur is not None and cur is not root:
        if _isUsableAnchor(cur, idIndex):
            return cur.get("id") + "/" + "/".join(steps)
        steps.insert(0, str(_childIndex(cur)))
        cur = cur.getparent()
    if cur is not root:
        return None
    # The document element is /1: the sequence is rooted at the document, not at
    # the root element, so the root's own position is the leading step.
    return "/1" + ("/" + "/".join(steps) if steps else "")


def resolvePointer(pointer: Optional[str], root, idIndex: Dict[str, List[Any]]):
    """Resolve a pointer back to an element, or None.

    Failure is silent by design in the element() scheme -- "failure to identify
    an element results simply in no subresource being identified" -- so callers
    should treat None as a finding to report, never as an absent value.
    """
    if not isinstance(pointer, str):
        return None
    text = pointer.strip()
    if not text:
        return None
    if text.startswith("/"):
        steps = text[1:].split("/")
        first = steps.pop(0) if steps else ""
        if not first.isdigit() or int(first) < 1:
            return None
        # the leading step selects among the document's element children, of
        # which there is exactly one: the root element
        cur = root if int(first) == 1 else None
    else:
        slash = text.find("/")
        anchorId = text if slash == -1 else text[:slash]
        steps = [] if slash == -1 else text[slash + 1:].split("/")
        matches = idIndex.get(anchorId) or []
        cur = matches[0] if matches else None    # first match, as getElementById does
    for step in steps:
        if cur is None:
            return None
        if not step.isdigit() or int(step) < 1:
            return None
        children = _elementChildren(cur)
        n = int(step)
        cur = children[n - 1] if n - 1 < len(children) else None
    return cur


def verifiedPointer(el, root, idIndex: Dict[str, List[Any]]) -> Tuple[Optional[str], bool, Optional[str]]:
    """Generate a pointer and check it resolves back to the element it came from.

    Verification happens at generation time because every failure mode is silent.
    Within one tree this catches generation bugs; the stronger check -- resolving
    through a different parser -- is what the media-type branch in the aligner
    exists to make unnecessary.

    Returns (pointer, verified, reason).
    """
    pointer = elementPointer(el, root, idIndex)
    if pointer is None:
        return None, False, "could not generate a pointer"
    back = resolvePointer(pointer, root, idIndex)
    if back is el:
        return pointer, True, None
    return pointer, False, ("pointer resolves to a different element" if back is not None
                            else "pointer does not resolve")
