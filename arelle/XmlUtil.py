'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations
import datetime
import regex as re
from lxml import etree

from arelle.XbrlConst import ixbrlAll, qnLinkFootnote, xhtml, xml, xsd, xhtml
from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname, QName, tzinfoStr
from arelle.PrototypeDtsObject import PrototypeElementTree, PrototypeObject
from arelle.XmlValidateConst import VALID, INVALID
from typing import TYPE_CHECKING
from typing import Any
from typing import cast
from typing import Mapping
from typing import Generator
from typing import Collection
from typing import Callable
from typing import Sequence
from typing import TextIO

if TYPE_CHECKING:
    from arelle.ModelInstanceObject import ModelContext
    from arelle.ModelInstanceObject import ModelUnit
    from arelle.ModelDocument import ModelDocument


htmlEltUriAttrs: dict[str, Collection[str]] | None = None
resolveHtmlUri: Callable[[ModelObject, str | bytes | None, str | bytes | None], str] | None = None
datetimePattern = re.compile(r"\s*([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})?\s*|"
                             r"\s*([0-9]{4})-([0-9]{2})-([0-9]{2})(Z|[+-][0-9]{2}:[0-9]{2})?\s*")
xmlDeclarationPattern = re.compile(r"(\s+)?(<\?xml[^><\?]*\?>)", re.DOTALL)
xmlEncodingPattern = re.compile(r"\s*<\?xml\s.*encoding=['\"]([^'\"]*)['\"].*\?>")
xpointerFragmentIdentifierPattern = re.compile(r"([\w.]+)(\(([^)]*)\))?")
xmlnsStripPattern = re.compile(r'\s*xmlns(:[\w.-]+)?="[^"]*"')
nonSpacePattern = re.compile(r"\S+")

class XmlDeclarationLocationException(Exception):
    def __init__(self) -> None:
        super(XmlDeclarationLocationException, self).__init__("XML declaration is allowed only at the start of the document")

def xmlns(element: ModelObject, prefix: str | None) -> str | None:
    ns = element.nsmap.get(prefix)
    if ns:
        return ns
    if prefix == 'xml': # not normally declared explicitly
        return xml
    return ns # return results of get (which may be no namespace

def xmlnsprefix(element: etree._Element | ModelObject, ns: str | None) -> str | None:
    if ns is None:
        return None
    if ns == xml: # never declared explicitly
        return 'xml'
    for prefix, NS in element.nsmap.items():
        if NS == ns:
            if prefix is not None:
                return prefix
            else:
                return ""   # prefix none but exists, xml process as zero-length string
    return None

def targetNamespace(element: ModelObject) -> str | None:
    treeElt = element
    while treeElt is not None:
        if treeElt.localName == "schema" and treeElt.namespaceURI == xsd and treeElt.get("targetNamespace"):
            return treeElt.get("targetNamespace")
        treeElt = cast(ModelObject, treeElt.getparent())
    return None

def schemaLocation(element: etree._Element, namespace: str, returnElement: bool = False) -> etree._Element | str | None:
    treeElt: etree._Element | None = element
    while treeElt is not None:
        sl = treeElt.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation")
        if sl:
            ns = None
            for entry in sl.split():
                if ns is None:
                    if returnElement and entry == namespace:
                        return treeElt
                    ns = entry
                else:
                    if not returnElement and ns == namespace:
                        return entry
                    ns = None
        treeElt = treeElt.getparent()
    return None

def clarkNotationToPrefixNsLocalname(
    element: ModelObject,
    clarkName: str,
    isAttribute: bool = False
) -> tuple[str | None, str | None, str]:
    ns, sep, localName = clarkName[1:].partition('}')
    if sep:
        prefix = xmlnsprefix(element, ns)
        if prefix is None and isAttribute:
            return (None, None, clarkName) # don't use default xmlns on unqualified attribute name
        return (prefix, ns, localName)
    return (None, None, clarkName)

def clarkNotationToPrefixedName(
    element: ModelObject,
    clarkName: str,
    isAttribute: bool = False
) -> str:
    prefix, ns, localName = clarkNotationToPrefixNsLocalname(element, clarkName, isAttribute)
    if prefix:
        return prefix + ":" + localName
    else:
        return localName

def prefixedNameToNamespaceLocalname(
    element: ModelObject,
    prefixedName: str,
    defaultNsmap: Mapping[str, str] | None = None
) -> tuple[str | None, str, str | None] | None:
    if prefixedName is None or prefixedName == "":
        return None
    names = prefixedName.partition(":")
    if names[2] == "":
        #default namespace
        prefix = None
        localName = names[0]
    else:
        prefix = names[0]
        localName = names[2]
    ns = xmlns(element, prefix)
    if ns is None:
        if prefix:
            assert isinstance(defaultNsmap, Mapping)
            if prefix in defaultNsmap:
                ns = defaultNsmap[prefix]
            else:
                return None  # error, prefix not found
    return (ns, localName, prefix)

def prefixedNameToClarkNotation(element: ModelObject, prefixedName: str) -> str | None:
    nsLocalname = prefixedNameToNamespaceLocalname(element, prefixedName)
    if nsLocalname is None: return None
    ns, localname, prefix = nsLocalname
    if ns is None: return localname
    return "{{{0}}}{1}".format(ns, localname)

def encoding(xml: str | bytes, default: str = "utf-8") -> str:
    if isinstance(xml,bytes):
        s = xml[0:120]
        if s.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'
        if s.startswith(b'\xff\xfe'):
            return 'utf-16'
        if s.startswith(b'\xfe\xff'):
            return 'utf-16'
        if s.startswith(b'\xff\xfe\x00\x00'):
            return 'utf-32'
        if s.startswith(b'\x00\x00\xfe\xff'):
            return 'utf-32'
        if s.startswith(b'# -*- coding: utf-8 -*-'):
            return 'utf-8'  # python utf=encoded
        if b"x\0m\0l" in s:
            str = s.decode("utf-16")
        else:
            str = s.decode("latin-1")
    else:
        str = xml[0:80]
    match = xmlEncodingPattern.match(str)
    if match and match.lastindex == 1:
        return match.group(1)
    return default

def text(element: ModelObject | PrototypeObject) -> str:
    return textNotStripped(element).strip()

def childText(
    element: ModelObject,
    childNamespaceURIs: str | None,
    childLocalNames: tuple[str, ...]
) -> str | None:
    child_element = child(element, childNamespaceURIs, childLocalNames)
    return textNotStripped(child_element).strip() if child_element is not None else None

def textNotStripped(element: ModelObject | PrototypeObject | None) -> str:
    # Note 2022-09-27
    # PrototypeObject has no textValue property
    if element is None or isinstance(element, PrototypeObject):
        return ""
    return element.textValue  # allows embedded comment nodes, returns '' if None

def selfClosable(elt: ModelObject) -> bool:
    return elt.qname.localName in (
        'area', 'base', 'basefont', 'br', 'col', 'frame', 'hr', 'img',
        'input', 'isindex', 'link', 'meta', 'param'
    )

# ixEscape can be None, "html" (xhtml namespace becomes default), "xhtml", or "xml"
def innerText(
    element: ModelObject,
    ixExclude: bool = False,
    ixEscape: str | None = None,
    ixContinuation: bool = False,
    ixResolveUris: bool = False,
    strip: bool = True
) -> str:
    try:
        text = "".join(text for text in innerTextNodes(element, ixExclude, ixEscape, ixContinuation, ixResolveUris))
        if strip:
            return text.strip(" \t\r\n") # strip follows xml whitespace collapse, only blank, tab and newlines
        return text
    except (AttributeError, TypeError):
        return ""

def innerTextList(
    element: ModelObject,
    ixExclude: bool = False,
    ixEscape: str | None = None,
    ixContinuation: bool = False,
    ixResolveUris: bool = False
) -> str:
    try:
        return ", ".join(text.strip() for text in innerTextNodes(element, ixExclude, ixEscape, ixContinuation, ixResolveUris) if len(text.strip()) > 0)
    except (AttributeError, TypeError):
        return ""

def innerTextNodes(
    element: ModelObject | None,
    ixExclude: bool | str,
    ixEscape: str | None,
    ixContinuation: bool,
    ixResolveUris: bool
) -> Generator[str, None, None]:
    global htmlEltUriAttrs, resolveHtmlUri
    if htmlEltUriAttrs is None:
        from arelle.XhtmlValidate import htmlEltUriAttrs, resolveHtmlUri
    while element is not None:
        if element.text:
            yield escapedText(element.text) if ixEscape else element.text
        for child in element.iterchildren():
            if isinstance(child,ModelObject) and (
               not ixExclude or
               not ((child.localName == "exclude" or ixExclude == "tuple") and child.namespaceURI in ixbrlAll)):
                firstChild = True
                for nestedText in innerTextNodes(child, ixExclude, ixEscape, False, ixResolveUris): # nested elements don't participate in continuation chain
                    if firstChild and ixEscape:
                        yield escapedNode(child, True, False, ixEscape, ixResolveUris)
                        firstChild = False
                    yield nestedText
                if ixEscape:
                    yield escapedNode(child, False, firstChild, ixEscape, ixResolveUris)
            if child.tail:
                yield escapedText(child.tail) if ixEscape else child.tail
        if ixContinuation:
            element = getattr(element, "_continuationElement", None)
        else:
            break

def escapedNode(
    elt: ModelObject,
    start: bool,
    empty: bool,
    ixEscape: str,
    ixResolveUris: bool
) -> str:
    if elt.namespaceURI in ixbrlAll:
        return ''  # do not yield XML for nested facts
    if ixResolveUris:
        assert isinstance(htmlEltUriAttrs, dict)
        uriAttrs = htmlEltUriAttrs.get(elt.qname.localName, ())
    else:
        uriAttrs = ()
    s = ['<']
    if not start and not empty:
        s.append('/')
    if ixEscape == "html" and elt.qname.namespaceURI == xhtml:
        tagName = elt.qname.localName # force xhtml prefix to be default
    else:
        tagName = str(elt.qname)
    s.append(tagName)
    if start or empty:
        assert resolveHtmlUri is not None
        if elt.localName == "object" and elt.get("codebase"): # resolve codebase before other element names
            # 2022-09-15: not sure about this one, but seems that
            # elt.get("codebase") should be the value arg for resolveHtmlUri
            elt.set("codebase", resolveHtmlUri(elt, "codebase", elt.get("codebase")))
        for n,v in sorted(elt.items(), key=lambda item: item[0]):
            if n in uriAttrs:
                v = resolveHtmlUri(elt, n, v).replace(" ", "%20") # %20 replacement needed for conformance test passing
            # 2022-09-15: assuming n, v are always strings
            s.append(' {0}="{1}"'.format(qname(elt, cast(str, n)),
                cast(str, v).replace("&","&amp;").replace('"', '&quot;')))
    if not start and empty:
        if selfClosable(elt):
            s.append('/')
        else:
            s.append('></' + tagName)
    s.append('>')
    return ''.join(s)

def escapedText(text: str) -> str:
    return ''.join("&amp;" if c == "&"
                   else "&lt;" if c == "<"
                   else "&gt;" if c == ">"
                   else c
                   for c in text)

def collapseWhitespace(s: str) -> str:
    return ' '.join( nonSpacePattern.findall(s) )

def parentId(
    element: ModelObject,
    parentNamespaceURI: str,
    parentLocalName: str
) -> str | None:
    while element is not None:
        if element.namespaceURI == parentNamespaceURI and element.localName == parentLocalName:
            return element.get("id")
        element = cast(ModelObject, element.getparent())
    return None

def hasChild(
    element: ModelObject,
    childNamespaceURI: str,
    childLocalNames: str
) -> bool:
    result = children(element, childNamespaceURI, childLocalNames)
    return bool(result)

def hasDescendant(
    element: ModelObject,
    descendantNamespaceURI: str,
    descendantLocalNames: str
) -> bool:
    d = descendants(element, descendantNamespaceURI, descendantLocalNames)
    return bool(d)

def hasAncestor(
    element: ModelObject,
    ancestorNamespaceURI: str,
    ancestorLocalNames: str | tuple[str, ...]
) -> bool:
    treeElt = element.getparent()
    while isinstance(treeElt,ModelObject):
        if treeElt.namespaceURI == ancestorNamespaceURI:
            if isinstance(ancestorLocalNames,tuple):
                if treeElt.localName in ancestorLocalNames:
                    return True
            elif treeElt.localName == ancestorLocalNames:
                return True
        treeElt = treeElt.getparent()
    return False

def ancestor(
    element: ModelObject,
    ancestorNamespaceURI: str,
    ancestorLocalNames: str | tuple[str, ...]
) -> ModelObject | None:
    treeElt = element.getparent()
    wildNamespaceURI = not ancestorNamespaceURI or ancestorNamespaceURI == '*'
    if not isinstance(ancestorLocalNames,tuple): ancestorLocalNames = (ancestorLocalNames ,)
    wildLocalName = ancestorLocalNames == ('*',)
    while isinstance(treeElt,ModelObject):
        if wildNamespaceURI or treeElt.elementNamespaceURI == ancestorNamespaceURI:
            if treeElt.localName in ancestorLocalNames or wildLocalName:
                return treeElt
        treeElt = treeElt.getparent()
    return None

def parent(
    element: ModelObject,
    parentNamespaceURI: str | None = None,
    parentLocalNames: str | tuple[str, ...] | None = None,
    ixTarget: bool = False
) -> ModelObject | None:
    if ixTarget and hasattr(element, "parentElement"):
        p = getattr(element, 'parentElement')
    else:
        p = element.getparent()
    if parentNamespaceURI or parentLocalNames:
        wildNamespaceURI = not parentNamespaceURI or parentNamespaceURI == '*'
        if isinstance(p,ModelObject):
            if wildNamespaceURI or p.elementNamespaceURI == parentNamespaceURI:
                if isinstance(parentLocalNames,tuple):
                    if p.localName in parentLocalNames:
                        return p
                elif p.localName == parentLocalNames:
                    return p
        return None
    return cast(ModelObject, p)

def ancestors(
    element: ModelObject,
    ancestorNamespaceURI: str | None = None,
    ancestorLocalNames: str | tuple[str, ...] | None = None
) -> list[ModelObject]:
    if ancestorNamespaceURI is None and ancestorLocalNames is None:
        return [
            cast(ModelObject, ancestor) for ancestor in element.iterancestors()
        ]
    ancestors = []
    wildNamespaceURI = not ancestorNamespaceURI or ancestorNamespaceURI == '*'
    treeElt = element.getparent()
    while isinstance(treeElt,ModelObject):
        if wildNamespaceURI or treeElt.elementNamespaceURI == ancestorNamespaceURI:
            if isinstance(ancestorLocalNames,tuple):
                if treeElt.localName in ancestorLocalNames:
                    ancestors.append(treeElt)
            elif treeElt.localName == ancestorLocalNames:
                ancestors.append(treeElt)
        treeElt = treeElt.getparent()
    return ancestors

def ancestorOrSelfAttr(element: ModelObject, attrClarkName: str) -> str | None:
    treeElt = element
    while isinstance(treeElt,ModelObject):
        attr = treeElt.get(attrClarkName)
        if attr is not None:
            return attr
        treeElt = cast(ModelObject, treeElt.getparent())
    return None

def childAttr(
    element: ModelObject,
    childNamespaceURI: str,
    childLocalNames: str | tuple[str, ...],
    attrClarkName: str
) -> str | None:
    childElt = child(element, childNamespaceURI, childLocalNames)
    return childElt.get(attrClarkName) if childElt is not None else None

def descendantAttr(
    element: ModelObject,
    childNamespaceURI: str,
    childLocalNames: str | tuple[str, ...],
    attrClarkName: str,
    attrName: str | None = None,
    attrValue: str | None = None
) -> str | None:
    descendantElt = descendant(element, childNamespaceURI, childLocalNames, attrName, attrValue)
    return descendantElt.get(attrClarkName) if (descendantElt is not None) else None

def children(
    element: ModelObject | etree._ElementTree | PrototypeElementTree,
    childNamespaceURIs: str | tuple[str, ...] | None,
    childLocalNames: str | tuple[str, ...],
    ixTarget: bool = False
    # 2022-09-15 ModelUnit/Context are model objects,
    # the check in line ~444 below if for ModelObject base class
) -> Sequence[ModelObject]:
    children = []
    if not isinstance(childLocalNames,tuple): childLocalNames = (childLocalNames ,)
    wildLocalName = childLocalNames == ('*',)
    wildNamespaceURI = not childNamespaceURIs or childNamespaceURIs == '*'
    if not isinstance(childNamespaceURIs,tuple) and childNamespaceURIs is not None:
        childNamespaceURIs = (childNamespaceURIs,)
    if childNamespaceURIs is None:
        childNamespaceURIs = tuple() # empty tuple to support `in` operator
    if isinstance(element,ModelObject):
        for child in (getattr(element, 'ixIter')() if ixTarget and hasattr(element, "ixIter") else
                      element.iterchildren()):
            if (isinstance(child,ModelObject) and
                (wildNamespaceURI or (child.qname.namespaceURI if ixTarget else child.elementNamespaceURI) in childNamespaceURIs) and
                (wildLocalName or (child.qname.localName if ixTarget else child.localName) in childLocalNames)):
                children.append(child)
    elif isinstance(element, (etree._ElementTree,PrototypeElementTree)): # document root
        child = element.getroot()
        if (wildNamespaceURI or child.elementNamespaceURI in childNamespaceURIs) and \
           (wildLocalName or child.localName in childLocalNames):
            children.append(child)

    return children

def child(
    element: ModelObject,
    childNamespaceURI: str | tuple[str, ...] | None = None,
    childLocalNames: str | tuple[str, ...] = ("*",)
) -> ModelObject | None:
    result = children(element, childNamespaceURI, childLocalNames)
    if result and len(result) > 0:
        return result[0]
    return None

def lastChild(
    element: ModelObject,
    childNamespaceURI: str | tuple[str, ...] | None = None,
    childLocalNames: str | tuple[str, ...] = ("*",)
) -> ModelObject | ModelContext | ModelUnit | None:
    result = children(element, childNamespaceURI, childLocalNames)
    if result and len(result) > 0:
        return result[-1]
    return None

def previousSiblingElement(element: ModelObject) -> ModelObject | None:
    for result in element.itersiblings(preceding=True):
        if isinstance(result,ModelObject):
            return result
    return None

def nextSiblingElement(element: ModelObject) -> ModelObject | None:
    for result in element.itersiblings(preceding=False):
        if isinstance(result,ModelObject):
            return result
    return None

def childrenAttrs(
    element: ModelObject,
    childNamespaceURI: str,
    childLocalNames: str | tuple[str, ...],
    attrLocalName: str
) -> list[str]:
    childrenElts = children(element, childNamespaceURI, childLocalNames)
    childrenAttrs = []
    for childElt in childrenElts:
        childAt = childElt.get(attrLocalName)
        if childAt:
            childrenAttrs.append(childAt)
    childrenAttrs.sort()
    return childrenAttrs

def descendant(
    element: ModelObject | PrototypeObject,
    descendantNamespaceURI: str | None,
    descendantLocalNames: str | tuple[str, ...],
    attrName: str | None = None,
    attrValue: str | None = None
) -> ModelObject | PrototypeObject | None:
    d = descendants(element, descendantNamespaceURI, descendantLocalNames, attrName, attrValue, breakOnFirst=True)
    if d:
        return d[0]
    return None

def descendants(
    element: ModelObject | PrototypeObject | etree._ElementTree,
    descendantNamespaceURI: str | None,
    descendantLocalNames: str | tuple[str, ...],
    attrName: str | None = None,
    attrValue: str | None = None,
    breakOnFirst: bool = False,
    ixTarget: bool = False
) -> Sequence[ModelObject | PrototypeObject]:
    descendants = []
    if not isinstance(descendantLocalNames,tuple): descendantLocalNames = (descendantLocalNames ,)
    wildLocalName = descendantLocalNames == ('*',)
    wildNamespaceURI = not descendantNamespaceURI or descendantNamespaceURI == '*'
    if isinstance(
        element, (ModelObject, etree._ElementTree, PrototypeElementTree, PrototypeObject)
    ):
        for child in (
            getattr(element, "ixIter")()
            if ixTarget and hasattr(element, "ixIter")
            else element.iterdescendants()
            if isinstance(element, ModelObject)
            # Note 2022-09-27 PrototypeObject has no iter(), ModelObject however has.
            else element.iter()  # type: ignore[union-attr]
        ):
            _childNamespaceURI = getattr(child, 'elementNamespaceURI', None)
            _childLocalName = getattr(child, 'localName', None)
            if isinstance(child, (ModelObject, PrototypeObject)) and ixTarget:
                childQname: QName | None = getattr(child, 'qname', None)
                if childQname:
                    _childNamespaceURI = childQname.namespaceURI
                    _childLocalName = childQname.localName
            if (isinstance(child,(ModelObject,PrototypeObject)) and
                (wildNamespaceURI or _childNamespaceURI == descendantNamespaceURI) and
                (wildLocalName or _childLocalName in descendantLocalNames)):
                if attrName:
                    if child.get(attrName) == attrValue or (attrValue == "*" and child.get(attrName) is not None):
                        descendants.append(child)
                        if breakOnFirst:
                            break
                else:
                    descendants.append(child)
                    if breakOnFirst:
                        break
    return descendants

def isDescendantOf(element: ModelObject, ancestorElement: ModelObject) -> bool:
    while element is not None:
        if element == ancestorElement:
            return True
        element = cast(ModelObject, element.getparent())
    return False

def schemaDescendantsNames(
    element: ModelObject,
    descendantNamespaceURI: str,
    descendantLocalName: str,
    qnames: set[QName | None] | None = None
) -> set[QName | None]:
    if qnames is None: qnames = set()
    for child in element.iterdescendants(tag="{{{0}}}{1}".format(descendantNamespaceURI,descendantLocalName)):
        if isinstance(child,ModelObject):
            if child.get("name"):
                # need to honor attribute/element form default
                qnames.add(qname(targetNamespace(element), child.get("name")))
            elif child.get("ref"):
                qnames.add(qname(element, child.get("ref")))
    return qnames

def schemaDescendant(
    element: ModelObject,
    descendantNamespaceURI: str,
    descendantLocalName: str,
    name: str
) -> ModelObject | None:
    for child in element.iterdescendants(tag="{{{0}}}{1}".format(descendantNamespaceURI,descendantLocalName)):
        if isinstance(child,ModelObject):
            # need to honor attribute/element form default
            if descendantLocalName == "attribute":
                if child.get("name") == (name.localName if isinstance(name,QName) else name):
                    return child
            else:
                if qname(child, child.get("name")) == name:
                    return child
    return None

# 2022-09-15: recursive type alias for schemaBaseTypeDerivedFrom return
# not supported yet as far as I understand, this is for the future.
# see -> https://github.com/python/mypy/issues/731
# from typing import Union
# Nested = Union[str, QName, list['Nested'], None]

def schemaBaseTypeDerivedFrom(
    element: ModelObject
) -> Any:
    for child in element.iterchildren():
        if child.tag in ("{http://www.w3.org/2001/XMLSchema}extension","{http://www.w3.org/2001/XMLSchema}restriction"):
            return child.get("base")  # str | None
        elif child.tag == "{http://www.w3.org/2001/XMLSchema}union":
            return (child.get("memberTypes") or "").split() + [
                    schemaBaseTypeDerivedFrom(cast(ModelObject, _child))
                    for _child in child.iterchildren(tag="{http://www.w3.org/2001/XMLSchema}simpleType")]  # list[str | QName | list[This func return] | None]
        elif child.tag in ("{http://www.w3.org/2001/XMLSchema}complexType",
                           "{http://www.w3.org/2001/XMLSchema}simpleType",
                           "{http://www.w3.org/2001/XMLSchema}complexContent",
                           "{http://www.w3.org/2001/XMLSchema}simpleContent"):
            return schemaBaseTypeDerivedFrom(cast(ModelObject, child))
    return None

def schemaFacets(
    element: etree._Element,
    facetTags: list[str],
    facets: list[etree._Element | None] | None = None
) -> list[etree._Element | None]:
    if facets is None: facets = []
    for child in element.iterchildren():
        if child.tag in facetTags:
            facets.append(child)
        elif child.tag in ("{http://www.w3.org/2001/XMLSchema}complexType",
                           "{http://www.w3.org/2001/XMLSchema}simpleType",
                           "{http://www.w3.org/2001/XMLSchema}restriction",
                           "{http://www.w3.org/2001/XMLSchema}complexContent",
                           "{http://www.w3.org/2001/XMLSchema}simpleContent"):
            schemaFacets(child, facetTags, facets)
    return facets

def schemaAttributesGroups(
    element: etree._Element,
    attributes: list[etree._Element] | None = None,
    attributeWildcards: list[etree._Element] | None = None,
    attributeGroups: list[etree._Element] | None = None
) -> tuple[list[etree._Element], list[etree._Element], list[etree._Element]] :
    if attributes is None: attributes = []; attributeWildcards = []; attributeGroups = []
    assert isinstance(attributes, list) and isinstance(attributeWildcards, list) \
        and isinstance(attributeGroups, list)
    for child in element.iterchildren():
        if child.tag == "{http://www.w3.org/2001/XMLSchema}attribute":
            attributes.append(child)
        elif child.tag == "{http://www.w3.org/2001/XMLSchema}anyAttribute":
            attributeWildcards.append(child)
        elif child.tag == "{http://www.w3.org/2001/XMLSchema}attributeGroup":
            attributeGroups.append(child)
        elif child.tag in {"{http://www.w3.org/2001/XMLSchema}complexType",
                           "{http://www.w3.org/2001/XMLSchema}simpleType",
                           "{http://www.w3.org/2001/XMLSchema}complexContent",
                           "{http://www.w3.org/2001/XMLSchema}simpleContent",
                           "{http://www.w3.org/2001/XMLSchema}restriction",
                           "{http://www.w3.org/2001/XMLSchema}extension"
                           }:
            schemaAttributesGroups(child, attributes, attributeWildcards, attributeGroups)
    return (attributes, attributeWildcards, attributeGroups)

def emptyContentModel(element: etree._Element) -> bool:
    if element.tag in ("{http://www.w3.org/2001/XMLSchema}complexType",
                     "{http://www.w3.org/2001/XMLSchema}complexContent"):
        if element.get("mixed") == "true":
            return False
    for child in element.iterchildren():
        if child.tag in ("{http://www.w3.org/2001/XMLSchema}complexType",
                         "{http://www.w3.org/2001/XMLSchema}complexContent"):
            if child.get("mixed") == "true":
                return False
            for contentChild in child.iterdescendants():
                if contentChild.tag in ("{http://www.w3.org/2001/XMLSchema}sequence",
                                        "{http://www.w3.org/2001/XMLSchema}choice",
                                        "{http://www.w3.org/2001/XMLSchema}all"):
                    return True
        elif child.tag in ("{http://www.w3.org/2001/XMLSchema}simpleType",
                           "{http://www.w3.org/2001/XMLSchema}simpleContent"):
            return False
    return True


# call with parent, childNamespaceURI, childLocalName, or just childQName object
# attributes can be (localName, value) or (QName, value)
def addChild(
    parent: ModelObject,
    childName1: str | QName,
    childName2: str | None = None,
    attributes: Sequence[tuple[str | QName, str]] | dict[str | QName, str] | tuple[str, str] | None = None,
    text: str | None = None,
    afterSibling: ModelObject | None = None,
    beforeSibling: ModelObject | None = None,
    appendChild: bool = True
) -> ModelObject:
    from arelle.FunctionXs import xsString
    modelDocument = parent.modelDocument

    if isinstance(childName1, QName):
        addQnameValue(modelDocument, childName1)
        if childName1.prefix:
            child: ModelObject = modelDocument.parser.makeelement(  # type: ignore[attr-defined] # ModelDocument type hints
                childName1.clarkNotation, nsmap={childName1.prefix:childName1.namespaceURI})
        else:
            child = modelDocument.parser.makeelement(childName1.clarkNotation)  # type: ignore[attr-defined] # ModelDocument type hints
    else:   # called with namespaceURI, localName
        assert isinstance(childName2, str)
        existingPrefix = xmlnsprefix(parent, childName1)
        prefix, sep, localName = childName2.partition(":")
        if localName:
            if existingPrefix is None:
                setXmlns(modelDocument, prefix, childName1)
        else:
            localName = prefix
        child = modelDocument.parser.makeelement("{{{0}}}{1}".format(childName1, localName))  # type: ignore[attr-defined] # ModelDocument type hints
    if afterSibling is not None and afterSibling.getparent() == parent:  # sibling is a hint, parent prevails
        afterSibling.addnext(child)
    elif beforeSibling is not None and beforeSibling.getparent() == parent:  # sibling is a hint, parent prevails
        beforeSibling.addprevious(child)
    elif appendChild:
        parent.append(child)
    if attributes:
        for name, value in (attributes.items() if isinstance(attributes, dict) else  # type: ignore[misc]
                            attributes if len(attributes) > 0 and isinstance(attributes[0],(tuple,list)) else (attributes,)):
            if isinstance(name,QName):
                if name.namespaceURI:
                    addQnameValue(modelDocument, name)
                child.set(name.clarkNotation, str(value)) # ModelValue type hints
            else:
                assert isinstance(name, str)
                child.set(name, xsString(None, None, value) )  # type: ignore[no-untyped-call] # FunctionXs type hints
    if text is not None:
        child.text = xsString(None, None, text)  # type: ignore[no-untyped-call] # FunctionXs type hints
        # check if the text is a QName and add the namespace if needed!
        if isinstance(text, QName):
            addQnameValue(modelDocument, text)
    child.init(modelDocument)
    return child

def copyNodes(parent: ModelObject, elts: Sequence[ModelObject] | ModelObject) -> None:
    modelDocument = parent.modelDocument
    for origElt in elts if isinstance(elts, (tuple,list,set)) else (elts,):
        addQnameValue(modelDocument, origElt.elementQname)
        copyElt = modelDocument.parser.makeelement(origElt.tag)  # type: ignore[attr-defined] # ModelDocument type hints
        copyElt.init(modelDocument)
        parent.append(copyElt)
        for attrTag, attrValue in origElt.items():
            qn = qname(attrTag, noPrefixIsNoNamespace=True)
            prefix = xmlnsprefix(origElt, getattr(qn, 'namespaceURI'))
            if prefix:
                setXmlns(modelDocument, prefix, getattr(qn, 'namespaceURI'))
                copyElt.set(attrTag, attrValue)
            else:
                copyElt.set(attrTag, attrValue)
        textContentSet = False
        if hasattr(origElt, "xValue"):
            if isinstance(origElt.xValue,QName):
                copyElt.text = addQnameValue(modelDocument, origElt.xValue)
                textContentSet = True
        if not textContentSet:
            text = origElt.text
            if text is not None:
                text = text.strip()  # don't copy whitespace text
                if text:
                    copyElt.text = text
        for childNode in origElt:
            if isinstance(childNode,ModelObject):
                copyNodes(copyElt,childNode)

def copyChildren(parent: ModelObject, elt: ModelObject) -> None:
    for childNode in elt:
        if isinstance(childNode,ModelObject):
            copyNodes(parent, childNode)

def copyIxFootnoteHtml(
    srcXml: etree._Element,
    tgtHtml: etree._Element,
    targetModelDocument: ModelDocument | None = None,
    withText: bool = False,
    isContinChainElt: bool = True,
    tgtStack: list[list[etree._Element | str]] | None = None,
    srcLevel: int = 0
) -> None:
    if tgtStack is None:
        tgtStack = [[tgtHtml, "text"]] # stack of current targetStack element, and current text attribute
    if not (isinstance(srcXml,ModelObject) and srcXml.localName == "exclude" and srcXml.namespaceURI in ixbrlAll):
        tgtStackLen = len(tgtStack)
        if withText:
            _tx = srcXml.text
            if _tx:
                tgtElt, tgtNode = tgtStack[-1]
                assert isinstance(tgtNode, str)
                setattr(tgtElt, tgtNode, (getattr(tgtElt, tgtNode) or "") + _tx)
        for srcChild in srcXml.iterchildren():
            if isinstance(srcChild,ModelObject):
                if not srcChild.namespaceURI in ixbrlAll:
                    # ensure xhtml has an xmlns
                    if targetModelDocument is not None and srcChild.namespaceURI == xhtml and xhtml not in tgtHtml.nsmap.values():
                        setXmlns(targetModelDocument, "xhtml", xhtml)
                    tgtChild = etree.SubElement(tgtHtml, srcChild.tag)
                    for attrTag, attrValue in srcChild.items():
                        tgtChild.set(attrTag, attrValue)
                    tgtStack.append([tgtChild, "text"])
                    copyIxFootnoteHtml(srcChild, tgtChild, targetModelDocument, withText=withText, isContinChainElt=False, tgtStack=tgtStack, srcLevel=srcLevel+1)
                    tgtStack[-1][1] = "tail"
                else:
                    copyIxFootnoteHtml(srcChild, tgtHtml, targetModelDocument, withText=withText, isContinChainElt=False, tgtStack=tgtStack, srcLevel=srcLevel+1)
        if not (isinstance(srcXml,ModelObject) and srcXml.namespaceURI in ixbrlAll):
            del tgtStack[tgtStackLen:]
            tgtStack[-1][1] = "tail"
    if withText and srcLevel > 0: # don't take tail of entry level ix:footnote or ix:continuatino
        _tl = srcXml.tail
        if _tl:
            tgtElt, tgtNode = tgtStack[-1]
            assert isinstance(tgtNode, str)
            setattr(tgtElt, tgtNode, (getattr(tgtElt, tgtNode) or "") + _tl)
    if isContinChainElt: # for inline continuation chain elements, follow chain (but not for nested elements)
        contAt = getattr(srcXml, "_continuationElement", None)
        if contAt is not None:
            copyIxFootnoteHtml(contAt, tgtHtml, targetModelDocument, withText=withText, isContinChainElt=True, tgtStack=tgtStack, srcLevel=0)

def addComment(parent: ModelObject, commentText: str) -> None:
    comment = str(commentText)
    if '--' in comment: # replace -- with - - (twice, in case more than 3 '-' together)
        comment = comment.replace('--', '- -').replace('--', '- -')
    child = etree.Comment( comment )
    parent.append(child)

def addProcessingInstruction(
    parent: ModelObject,
    piTarget: str | bytes,
    piText: str,
    insertBeforeChildElements: bool = True,
    insertBeforeParentElement: bool = False
) -> None:
    child = etree.ProcessingInstruction(piTarget, piText)
    if insertBeforeParentElement:
        parent.addprevious(child)
    elif insertBeforeChildElements:
        i = 0 # find position to insert after other comments and PIs but before any element
        for i, _otherChild in enumerate(parent):
            if not isinstance(_otherChild, (etree._Comment, etree._ProcessingInstruction)):
                break # insert before this child
        parent.insert(i, child)
    else: # can go after elements
        parent.append(child)

def addQnameValue(modelDocument: ModelDocument, qnameValue: QName | str) -> str:
    if not isinstance(qnameValue, QName):
        return qnameValue # may be just a string
    if hasattr(modelDocument, "modelDocument"):
        modelDocument = modelDocument.modelDocument
        xmlRootElement = modelDocument.xmlRootElement
    elif isinstance(modelDocument, etree._ElementTree):
        xmlRootElement = modelDocument.getroot()
        if xmlRootElement.tag == "nsmap": xmlRootElement = xmlRootElement[0]
    ns = qnameValue.namespaceURI or '' # None can't be used as a no-namespace prefix
    existingPrefix = xmlnsprefix(xmlRootElement, ns)
    if existingPrefix is not None:  # namespace is already declared, use that for qnameValue's prefix
        return qnameValue.localName if len(existingPrefix) == 0 else existingPrefix + ':' + qnameValue.localName  # ModelValue type hints
    prefix = qnameValue.prefix
    dupNum = 2 # start with _2 being 'second' use of same prefix, etc.
    while (dupNum < 10000): # check if another namespace has prefix already (but don't die if running away)
        if xmlns(xmlRootElement, prefix) is None:
            break   # ok to use this prefix
        prefix = "{0}_{1}".format(qnameValue.prefix if qnameValue.prefix else '', dupNum)
        dupNum += 1
    setXmlns(modelDocument, prefix, ns)
    return f'{prefix}:{qnameValue.localName}' if prefix else qnameValue.localName


def setXmlns(modelDocument: etree._ElementTree | ModelDocument, prefix: str | None, namespaceURI: str) -> None:
    if isinstance(modelDocument, etree._ElementTree):
        elementTree = modelDocument
        root = modelDocument.getroot()
    else:
        elementTree = modelDocument.xmlDocument
        root = elementTree.getroot()
    if prefix == "":
        prefix = None  # default xmlns prefix stores as None
    if prefix not in root.nsmap:
        if root.tag == 'nsmap': # already have an xmlns-extension root element
            newmap = root.nsmap
            newmap[prefix] = namespaceURI
            # 2022-09-16: for some reason prefix is encouraged to always be a str in lxml-stubs,
            # but '' for default ns is not accepted by lxml nsmap arg and lxml produces and error
            # see https://github.com/lxml/lxml-stubs/blob/0a9b6099dd39b298fd0ff897dbcd4fed632d8776/lxml-stubs/etree.pyi#L69
            newroot = etree.Element('nsmap', nsmap=newmap)  # type: ignore[arg-type]  # above note
            newroot.extend(root)
        else:  # new xmlns-extension root
            newroot = etree.Element('nsmap', nsmap={prefix: namespaceURI})  # type: ignore[dict-item]  # above note
            comments = []
            comment = root.getprevious()
            while isinstance(comment, etree._Comment):
                comments.append(comment)
                comment = comment.getprevious()
            newroot.append(root)
            commentAnchor = root # move comment back onto old root (below nsmap) so it can write out later
            for comment in comments:
                commentAnchor.addprevious(comment)
                commentAnchor = comment
        elementTree._setroot(newroot)

def sortKey(
    parentElement: ModelObject,
    childNamespaceUri: str,
    childLocalNames: tuple[str, ...],
    childAttributeName: str | None = None,
    qnames: bool = False
) -> list[tuple[str, str, str | None]]:
    _list = []
    if parentElement is not None:
        for childLocalName in childLocalNames if isinstance(childLocalNames,tuple) else (childLocalNames,):
            for child in parentElement.iterdescendants(tag="{{{0}}}{1}".format(childNamespaceUri,childLocalName)):
                value = text(cast(ModelObject, child))
                if qnames:
                    _value = prefixedNameToClarkNotation(cast(ModelObject, child), value)
                    assert isinstance(_value, str)
                    value = _value
                if childAttributeName is not None:
                    _list.append((child.tag, value, child.get(childAttributeName)))
                else:
                    _list.append((child.tag, value, None))
        _list.sort()
    return _list

DATETIME_MINYEAR = datetime.datetime(datetime.MINYEAR,1,1)
DATETIME_MAXYEAR = datetime.datetime(datetime.MAXYEAR,12,31)
def tzinfo(tz: str | None) -> datetime.timezone | None:
    if tz is None:
        return None
    elif tz == 'Z':
        return datetime.timezone(datetime.timedelta(0))
    else:
        return datetime.timezone(datetime.timedelta(hours=int(tz[0:3]), minutes=int(tz[4:6])))

def datetimeValue(
    element: ModelObject,
    addOneDay: bool = False,
    none: str | None = None,
    subtractOneDay: bool = False,
) -> datetime.datetime | None:
    """
    Parses text value from `element` as a datetime.

    If element is None, returns None, unless `none` is provided:
    "minyear": minimum datetime value
    "maxyear": maximum datetime value

    If the text value does not match a date/datetime pattern, returns None.

    If the text value has a time portion with 24:00:00, the date is rolled forward to it's 00:00:00 equivalent.

    If the text value has a time portion and `subtractOneDay` is True,
    00:00:00 datetimes will cause a day to be subtracted from the result.

    If the text value does not have a time portion and addOneDay is True,
    a day will be added to the result.

    :param element: Element that provides text value to be parsed.
    :param addOneDay: If value does not have a time portion, add one day
    :param none: Determines what to return if element is None. "minyear" or "maxyear"
    :param subtractOneDay: If value has a zero-valued time portion, subtract one day
    :return:
    """
    if element is None:
        if none == "minyear":
            return DATETIME_MINYEAR
        elif none == "maxyear":
            return DATETIME_MAXYEAR
        return None
    match = datetimePattern.match(element if isinstance(element,str) else text(element).strip())
    if match is None:
        return None
    hour24 = False
    try:
        assert isinstance(match.lastindex, int)
        if 6 <= match.lastindex <= 8: # has time portion
            hour = int(match.group(4))
            min = int(match.group(5))
            sec = int(match.group(6))
            fracSec = match.group(7)
            tz = match.group(8)
            if hour == 24 and min == 0 and sec == 0:
                hour24 = True
                hour = 0
            ms = 0
            if fracSec and fracSec[0] == ".":
                ms = int(fracSec[1:7].ljust(6,'0'))
            result = datetime.datetime(int(match.group(1)),int(match.group(2)),int(match.group(3)),hour,min,sec,ms,tzinfo(tz))
            if hour24:  #add one day
                result += datetime.timedelta(1)
            if subtractOneDay and hour == min == sec == ms == 0:
                result += datetime.timedelta(-1)
        else:
            result = datetime.datetime(int(match.group(9)),int(match.group(10)),int(match.group(11)),0,0,0,0,tzinfo(match.group(12)))
            if addOneDay and match.lastindex >= 11:
                result += datetime.timedelta(1)
    except (ValueError, OverflowError, IndexError, AttributeError, AssertionError):
        if not "result" in locals(): # if not set yet, punt with max datetime
            result = DATETIME_MAXYEAR
    return result

def dateunionValue(
    datetimeValue: Any,
    subtractOneDay: bool = False,
    dateOnlyHour: int | None = None
) -> str:
    if not isinstance(datetimeValue, (datetime.datetime, datetime.date)):
        return "INVALID"
    tz = tzinfoStr(datetimeValue)  # type: ignore[arg-type]  # ModelValue type hints
    isDate = getattr(
        datetimeValue, 'dateOnly', False) or not hasattr(datetimeValue, 'hour')
    if isDate or (
        getattr(datetimeValue, 'hour') == 0
        and getattr(datetimeValue, 'minute') == 0
        and getattr(datetimeValue, 'second') == 0
    ):
        d = datetimeValue
        if subtractOneDay and not isDate: d -= datetime.timedelta(1)
        if dateOnlyHour is None:
            return "{0:04}-{1:02}-{2:02}{3}".format(d.year, d.month, d.day, tz)
        else: # show explicit hour on date-only value (e.g., 24:00:00 for end date)
            return "{0:04}-{1:02}-{2:02}T{3:02}:00:00{4}".format(
                d.year, d.month, d.day, dateOnlyHour, tz)
    else:
        return "{0:04}-{1:02}-{2:02}T{3:02}:{4:02}:{5:02}{6}".format(
            datetimeValue.year,
            datetimeValue.month,
            datetimeValue.day,
            getattr(datetimeValue, 'hour'),
            getattr(datetimeValue, 'minute'),
            getattr(datetimeValue, 'second'),
            tz
        )

def xpointerSchemes(fragmentIdentifier: str) -> list[tuple[str, str]]:
    matches = xpointerFragmentIdentifierPattern.findall(fragmentIdentifier)
    schemes = []
    for scheme, parenPart, path in matches:
        if parenPart is not None and len(parenPart) > 0:   # don't accumulate shorthand id's
            schemes.append((scheme, path))
    return schemes

def xpointerElement(modelDocument: ModelDocument, fragmentIdentifier: str) -> etree._Element | ModelObject | None:
    node: etree._Element | ModelObject | None
    matches = xpointerFragmentIdentifierPattern.findall(fragmentIdentifier)
    if matches is None:
        return None
    # try element schemes until one of them works
    for scheme, parenPart, path in matches:
        if scheme and (parenPart is None or len(parenPart) == 0): # shorthand id notation
            if scheme in modelDocument.idObjects:
                node = modelDocument.idObjects.get(scheme)
            else:
                node = modelDocument.xmlDocument.find("//*[@id='{0}']".format(scheme))
            if node is not None:
                return node    # this scheme fails
        elif scheme == "element" and parenPart and path:
            pathParts = path.split("/")
            if len(pathParts) >= 1 and len(pathParts[0]) > 0 and not pathParts[0].isnumeric():
                id = pathParts[0]
                if id in modelDocument.idObjects:
                    node = modelDocument.idObjects.get(id)
                else:
                    node = modelDocument.xmlDocument.find("//*[@id='{0}']".format(id))
                if node is None:
                    continue    # this scheme fails
                elif len(pathParts) > 1:
                    iter = node
            else:
                node = modelDocument.xmlDocument
                iter = (node.getroot(),)  # type: ignore[union-attr] # ModelDocument type hints
            i = 1
            while i < len(pathParts):
                childNbr = int(pathParts[i])
                eltNbr = 1
                parent = node
                node = None
                for child in iter:
                    if isinstance(child,etree.ElementBase):
                        if childNbr == eltNbr:
                            node = child
                            break
                        eltNbr += 1
                if node is None:
                    break   # not found in this scheme, scheme fails
                iter = node.iterchildren()
                i += 1
            if node is not None:    # found
                return node
    return None

def elementFragmentIdentifier(element: etree.ElementBase | etree._Element | ModelObject | None) -> str | None:
    if element is None:
        return None
    if getattr(element, "sourceElement", None) is not None: # prototype element
        return elementFragmentIdentifier(getattr(element, "sourceElement"))
    if isinstance(element, etree.ElementBase) and element.get('id'):
        return element.get('id')  # "short hand pointer" for element fragment identifier
    else:
        childSequence: list[str] = [""] # "" represents document element for / (root) on the join below
        while element is not None:
            if isinstance(element, etree.ElementBase):
                if element.get('id'):  # has ID, use as start of path instead of root
                    _id = element.get('id')
                    assert isinstance(_id, str)
                    childSequence[0] = _id
                    break
                childSequence.insert(1, str(getattr(element, 'elementSequence')))
            element = element.getparent()
        location = "/".join(childSequence)
        return "element({0})".format(location)

def elementIndex(element: Any) -> int:
    if isinstance(element, etree.ElementBase):
        return cast(int, getattr(element, 'elementSequence'))
    return 0

def elementChildSequence(element: etree._Element | etree.ElementBase | ModelObject | None) -> str:
    childSequence = [""] # "" represents document element for / (root) on the join below
    while element is not None:
        if isinstance(element,etree.ElementBase):
            childSequence.insert(1, str(getattr(element, 'elementSequence')))
        element = element.getparent()
    return "/".join(childSequence)

def elementTagnamesPath(element: etree._Element | ModelObject | None) -> str:
    # returns clark notation absolute path without element sequences
    tagnamesPath: list[str] = []
    while (element is not None):
        tagnamesPath.insert(0, element.tag)
        element = element.getparent()
    return "/".join(tagnamesPath)

def xmlstring(
    elt: etree._Element | ModelObject,
    stripXmlns: bool = False,
    prettyPrint: bool = False,
    contentsOnly: bool = False,
    includeText:bool = False
) -> str:
    if elt is None:
        return ""
    if contentsOnly:
        if includeText:
            _text = elt.text or ""
            _tail = elt.tail or ""
        else:
            _text = _tail = ""
        return _text + ('\n' if prettyPrint else '').join(
            xmlstring(child, stripXmlns, prettyPrint)
            for child in elt.iterchildren()) + _tail
    xml = etree.tostring(elt, encoding=str, pretty_print=prettyPrint)
    if not prettyPrint:
        xml = xml.strip()
    if stripXmlns:
        return xmlnsStripPattern.sub('', xml)
    else:
        return xml

def writexml(
    writer: TextIO,
    node: etree._ElementTree | etree._Element | ModelObject,
    encoding: str | None = None,
    indent: str = '',
    xmlcharrefreplace: bool = False,
    edgarcharrefreplace: bool = False,
    skipInvalid: bool = False,
    parentNsmap: dict[str | None, str] | None = None
) -> None:
    # customized from xml.minidom to provide correct indentation for data items
    # when indent is None, preserve original whitespace and don't pretty print
    if isinstance(node,etree._ElementTree):
        if encoding:
            writer.write('<?xml version="1.0" encoding="%s"?>\n' % (encoding,))
        else:
            writer.write('<?xml version="1.0"?>\n')
        for child in node.iter():
            if child.getparent() is not None:
                break   # stop depth first iteration after comment and root node
            if child.tag == 'nsmap':
                for nsmapChild in child:
                    writexml(writer, nsmapChild, indent=indent, xmlcharrefreplace=xmlcharrefreplace, edgarcharrefreplace=edgarcharrefreplace, skipInvalid=skipInvalid, parentNsmap={}) # force all xmlns in next element
            else:
                writexml(writer, child, indent=indent, xmlcharrefreplace=xmlcharrefreplace, edgarcharrefreplace=edgarcharrefreplace, skipInvalid=skipInvalid, parentNsmap={})
    elif isinstance(node,etree._Comment): # ok to use minidom implementation
        commentText = node.text if isinstance(node.text, str) else ''
        writer.write(indent + "<!--" + commentText + "-->\n")
    elif isinstance(node,etree._ProcessingInstruction): # ok to use minidom implementation
        writer.write(indent + str(node) + "\n")
    elif isinstance(node,etree._Element):
        if parentNsmap is None:
            parent = node.getparent()
            if parent is not None:
                parentNsmap = parent.nsmap
            else:
                # first node, no _ElementTree argument, needs document header
                if encoding:
                    writer.write('<?xml version="1.0" encoding="%s"?>\n' % (encoding,))
                else:
                    writer.write('<?xml version="1.0"?>\n')
                parentNsmap = {}
        if isinstance(node,ModelObject):
            tag = node.prefixedName
            isXmlElement = node.namespaceURI != xhtml
            isFootnote = node.qname == qnLinkFootnote
            if skipInvalid and getattr(node, "xValid", VALID) == INVALID:
                return
        else:
            ns, sep, localName = node.tag.partition('}')
            if sep:
                ns = ns[1:]
                prefix = xmlnsprefix(node,ns)
                if prefix:
                    tag = prefix + ":" + localName
                else:
                    tag = localName
            else:
                tag = ns
            isXmlElement = ns != xhtml
            isFootnote = False
        if isXmlElement: writer.write(indent)
        writer.write("<" + tag)
        attrs = {}
        for prefix, ns in sorted((k if k is not None else '', v)
                                 # items wrapped in set for 2.7 compatibility
                                 for k, v in (node.nsmap.items() - parentNsmap.items())):
            if prefix:
                attrs["xmlns:" + prefix] = ns
            else:
                attrs["xmlns"] = ns
        for aTag,aValue in node.items():
            ns, sep, localName = cast(str, aTag).partition('}')
            if sep:
                prefix = xmlnsprefix(node,ns[1:])
                if prefix:
                    prefixedName = prefix + ":" + localName
                else:
                    prefixedName = localName
            else:
                prefixedName = ns
            attrs[prefixedName] = cast(str, aValue)
        aSortedNames = sorted(attrs.keys())

        # should attribute names be indented on separate lines?
        numAttrs = 0
        lenAttrs = 0
        for aName,aValue in attrs.items():
            numAttrs += 1
            lenAttrs += 4 + len(aName) + len(aValue)
        indentAttrs = ("\n" + indent + "  ") if indent is not None and numAttrs > 1 and lenAttrs > 60 and not isFootnote else " "
        for aName in aSortedNames:
            writer.write("%s%s=\"" % (indentAttrs, aName))
            if aName != "xsi:schemaLocation":
                writer.write(''.join("&amp;" if c == "&"
                                     else '&quot;' if c == '"'
                                     else "&#x%x;" % ord(c) if c >= '\x80' and xmlcharrefreplace
                                     else "&#x%x;" % ord(c) if c in ('^', '\x7F') and edgarcharrefreplace
                                     else c
                                     for c in attrs[aName]))
            else:
                indentUri = "\n" + indent + "                      " if indent is not None else " "
                for i, a_uri in enumerate(attrs[aName].split()):
                    if i & 1:   #odd
                        writer.write(" " + a_uri)
                    elif i > 0:   #even
                        writer.write(indentUri + a_uri)
                    else:
                        writer.write(a_uri)
            writer.write("\"")
        hasChildNodes = False
        firstChild = True

        text = node.text
        if text is not None:
            text = ''.join("&amp;" if c == "&"
                           else "&#160;" if c == "\u00A0"
                           else "&lt;" if c == "<"
                           else "&gt;" if c == ">"
                           else "&#173;" if c == "\u00AD"
                           else "&#x%x;" % ord(c) if c >= '\x80' and xmlcharrefreplace
                           else "&#x%x;" % ord(c) if c in ('^', '\x7F') and edgarcharrefreplace
                           else c
                           for c in text)
        tail = node.tail
        if tail is not None:
            tail = ''.join("&amp;" if c == "&"
                           else "&#160;" if c == "\u00A0"
                           else "&lt;" if c == "<"
                           else "&gt;" if c == ">"
                           else "&#173;" if c == "\u00AD"
                           else "&#x%x;" % ord(c) if c >= '\x80' and xmlcharrefreplace
                           else "&#x%x;" % ord(c) if c in ('^', '\x7F') and edgarcharrefreplace
                           else c
                           for c in tail)
        for child in node.iterchildren():
            hasChildNodes = True
            if firstChild:
                writer.write(">")
                if isXmlElement and not isFootnote: writer.write("\n")
                if text and (indent is None or not text.isspace()):
                    writer.write(text)
                firstChild = False
            writexml(writer, child,
                     indent=indent+'    ' if indent is not None and not isFootnote else '',
                     xmlcharrefreplace=xmlcharrefreplace, edgarcharrefreplace=edgarcharrefreplace, skipInvalid=skipInvalid)
        if hasChildNodes:
            if isXmlElement and not isFootnote and indent is not None:
                writer.write("%s</%s>" % (indent, tag))
            else:
                writer.write("</%s>" % (tag,))
        elif text:
            writer.write(">%s</%s>" % (text, tag))
        else:
            writer.write("/>")
        if tail and (indent is None or not tail.isspace()):
            writer.write(tail)
        if isXmlElement and indent is not None: writer.write("\n")
