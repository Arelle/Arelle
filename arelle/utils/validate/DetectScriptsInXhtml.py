from typing import Any, Collection

from arelle.XbrlConst import xhtml
from lxml.etree import _Element

HTML_EVENT_HANDLER_ATTRIBUTES = frozenset((
    "onabort",
    "onafterprint",
    "onbeforeprint",
    "onbeforeunload",
    "onblur",
    "oncanplay",
    "oncanplaythrough",
    "onchange",
    "onclick",
    "oncontextmenu",
    "oncopy",
    "oncuechange",
    "oncut",
    "ondblclick",
    "ondrag",
    "ondragend",
    "ondragenter",
    "ondragleave",
    "ondragover",
    "ondragstart",
    "ondrop",
    "ondurationchange",
    "onemptied",
    "onended",
    "onerror",
    "onfocus",
    "onhashchange",
    "oninput",
    "oninvalid",
    "onkeydown",
    "onkeypress",
    "onkeyup",
    "onload",
    "onloadeddata",
    "onloadedmetadata",
    "onloadstart",
    "onmessage",
    "onmousedown",
    "onmousemove",
    "onmouseout",
    "onmouseover",
    "onmouseup",
    "onmousewheel",
    "onoffline",
    "ononline",
    "onpagehide",
    "onpageshow",
    "onpaste",
    "onpause",
    "onplay",
    "onplaying",
    "onpopstate",
    "onprogress",
    "onratechange",
    "onreset",
    "onresize",
    "onscroll",
    "onsearch",
    "onseeked",
    "onseeking",
    "onselect",
    "onstalled",
    "onstorage",
    "onsubmit",
    "onsuspend",
    "ontimeupdate",
    "ontoggle",
    "onunload",
    "onvolumechange",
    "onwaiting",
    "onwheel",
))


def hasEventHandlerAttributes(elt: Any) -> bool:
    return _hasEventAttributes(elt, HTML_EVENT_HANDLER_ATTRIBUTES)


def _hasEventAttributes(elt: Any, attributes: Collection[str]) -> bool:
    if isinstance(elt, _Element):
        return any(a in attributes for a in elt.keys())
    return False


def containsScriptMarkers(elt: Any) -> Any:
    _xhtmlNs = "{{{}}}".format(xhtml)
    _xhtmlNsLen = len(_xhtmlNs)
    eltTag = elt.tag.removeprefix(_xhtmlNs)
    if ((eltTag in ("object", "script")) or
            (eltTag == "a" and "javascript:" in elt.get("href","")) or
            (eltTag == "img" and "javascript:" in elt.get("src","")) or
            (hasEventHandlerAttributes(elt))):
        return True
