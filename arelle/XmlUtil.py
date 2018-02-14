'''
Created on Oct 22, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import datetime
try:
    import regex as re
except ImportError:
    import re
from lxml import etree
from arelle.XbrlConst import ixbrlAll, qnLinkFootnote, xhtml, xml, xsd, xhtml
from arelle.ModelObject import ModelObject, ModelComment
from arelle.ModelValue import qname, QName

datetimePattern = re.compile(r"\s*([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})\s*|"
                             r"\s*([0-9]{4})-([0-9]{2})-([0-9]{2})\s*")
xmlEncodingPattern = re.compile(r"\s*<\?xml\s.*encoding=['\"]([^'\"]*)['\"].*\?>")
xpointerFragmentIdentifierPattern = re.compile(r"([\w.]+)(\(([^)]*)\))?")
xmlnsStripPattern = re.compile(r'\s*xmlns(:[\w.-]+)?="[^"]*"')
nonSpacePattern = re.compile(r"\S+")

def xmlns(element, prefix):
    ns = element.nsmap.get(prefix)
    if ns:
        return ns
    if prefix == 'xml': # not normally declared explicitly
        return xml
    return ns # return results of get (which may be no namespace

def xmlnsprefix(element, ns):
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
    
def targetNamespace(element):
    treeElt = element
    while treeElt is not None:
        if treeElt.localName == "schema" and treeElt.namespaceURI == xsd and treeElt.get("targetNamespace"):
            return treeElt.get("targetNamespace")
        treeElt = treeElt.getparent()
    return None

def schemaLocation(element, namespace, returnElement=False):
    treeElt = element
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

def clarkNotationToPrefixNsLocalname(element, clarkName, isAttribute=False):
    ns, sep, localName = clarkName[1:].partition('}')
    if sep:
        prefix = xmlnsprefix(element, ns)
        if prefix is None and isAttribute:
            return (None, None, clarkName) # don't use default xmlns on unqualified attribute name
        return (prefix, ns, localName)
    return (None, None, clarkName)

def clarkNotationToPrefixedName(element, clarkName, isAttribute=False):
    prefix, ns, localName = clarkNotationToPrefixNsLocalname(element, clarkName, isAttribute)
    if prefix:
        return prefix + ":" + localName
    else:
        return localName

def prefixedNameToNamespaceLocalname(element, prefixedName, defaultNsmap=None):
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
            if prefix in defaultNsmap:
                ns = defaultNsmap[prefix]
            else:
                return None  # error, prefix not found
    return (ns, localName, prefix)

def prefixedNameToClarkNotation(element, prefixedName):
    nsLocalname = prefixedNameToNamespaceLocalname(element, prefixedName)
    if nsLocalname is None: return None
    ns, localname, prefix = nsLocalname
    if ns is None: return localname
    return "{{{0}}}{1}".format(ns, localname)

def encoding(xml, default="utf-8"):
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

def text(element):   
    return textNotStripped(element).strip()

def childText(element, childNamespaceURIs, childLocalNames):   
    element = child(element, childNamespaceURIs, childLocalNames)
    return textNotStripped(element).strip() if element is not None else None

def textNotStripped(element):
    if element is None: 
        return ""
    return element.textValue  # allows embedded comment nodes, returns '' if None

# ixEscape can be None, "html" (xhtml namespace becomes default), "xhtml", or "xml"
def innerText(element, ixExclude=False, ixEscape=None, ixContinuation=False, strip=True):   
    try:
        text = "".join(text for text in innerTextNodes(element, ixExclude, ixEscape, ixContinuation))
        if strip:
            return text.strip()
        return text
    except (AttributeError, TypeError):
        return ""

def innerTextList(element, ixExclude=False, ixEscape=None, ixContinuation=False):   
    try:
        return ", ".join(text.strip() for text in innerTextNodes(element, ixExclude, ixEscape, ixContinuation) if len(text.strip()) > 0)
    except (AttributeError, TypeError):
        return ""

def innerTextNodes(element, ixExclude, ixEscape, ixContinuation):
    if element.text:
        yield escapedText(element.text) if ixEscape else element.text
    for child in element.iterchildren():
        if isinstance(child,ModelObject) and (
           not ixExclude or 
           not ((child.localName == "exclude" or ixExclude == "tuple") and child.namespaceURI in ixbrlAll)):
            firstChild = True
            for nestedText in innerTextNodes(child, ixExclude, ixEscape, False): # nested elements don't participate in continuation chain
                if firstChild and ixEscape:
                    yield escapedNode(child, True, False, ixEscape)
                    firstChild = False
                yield nestedText
            if ixEscape:
                yield escapedNode(child, False, firstChild, ixEscape)
        if child.tail:
            yield escapedText(child.tail) if ixEscape else child.tail
    if ixContinuation:
        contAt = getattr(element, "_continuationElement", None)
        if contAt is not None:
            for contText in innerTextNodes(contAt, ixExclude, ixEscape, ixContinuation):
                yield contText
            
def escapedNode(elt, start, empty, ixEscape):
    if elt.namespaceURI in ixbrlAll:
        return ''  # do not yield XML for nested facts
    s = ['<']
    if not start and not empty:
        s.append('/')
    if ixEscape == "html" and elt.qname.namespaceURI == xhtml:
        s.append(elt.qname.localName) # force xhtml prefix to be default
    else:
        s.append(str(elt.qname))
    if start or empty:
        for n,v in sorted(elt.items(), key=lambda item: item[0]):
            s.append(' {0}="{1}"'.format(qname(elt,n),
                                         v.replace("&","&amp;").replace('"','&quot;')))
    if not start and empty:
        s.append('/')
    s.append('>')
    return ''.join(s)

def escapedText(text):
    return ''.join("&amp;" if c == "&"
                   else "&lt;" if c == "<"
                   else "&gt;" if c == ">"
                   else c
                   for c in text)

def collapseWhitespace(s):
    return ' '.join( nonSpacePattern.findall(s) ) 
                                         
def parentId(element, parentNamespaceURI, parentLocalName):
    while element is not None:
        if element.namespaceURI == parentNamespaceURI and element.localName == parentLocalName:
            return element.get("id")
        element = element.getparent()
    return None
    
def hasChild(element, childNamespaceURI, childLocalNames):
    result = children(element, childNamespaceURI, childLocalNames)
    return bool(result)
    
def hasDescendant(element, descendantNamespaceURI, descendantLocalNames):
    d = descendants(element, descendantNamespaceURI, descendantLocalNames)
    return bool(d)
    
def hasAncestor(element, ancestorNamespaceURI, ancestorLocalNames):
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
    
def ancestor(element, ancestorNamespaceURI, ancestorLocalNames):
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
    
def parent(element, parentNamespaceURI=None, parentLocalNames=None):
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
    return p

def ancestors(element, ancestorNamespaceURI=None, ancestorLocalNames=None):
    if ancestorNamespaceURI is None and ancestorLocalNames is None:
        return [ancestor for ancestor in element.iterancestors()]
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
    
def ancestorOrSelfAttr(element, attrClarkName):
    treeElt = element
    while isinstance(treeElt,ModelObject):
        attr = treeElt.get(attrClarkName)
        if attr is not None:
            return attr
        treeElt = treeElt.getparent()
    return None

def childAttr(element, childNamespaceURI, childLocalNames, attrClarkName):
    childElt = child(element, childNamespaceURI, childLocalNames)
    return childElt.get(attrClarkName) if childElt is not None else None

def descendantAttr(element, childNamespaceURI, childLocalNames, attrClarkName, attrName=None, attrValue=None):
    descendantElt = descendant(element, childNamespaceURI, childLocalNames, attrName, attrValue)
    return descendantElt.get(attrClarkName) if (descendantElt is not None) else None

def children(element, childNamespaceURIs, childLocalNames):
    children = []
    if not isinstance(childLocalNames,tuple): childLocalNames = (childLocalNames ,)
    wildLocalName = childLocalNames == ('*',)
    wildNamespaceURI = not childNamespaceURIs or childNamespaceURIs == '*'
    if not isinstance(childNamespaceURIs,tuple): childNamespaceURIs = (childNamespaceURIs ,)
    if isinstance(element,ModelObject):
        for child in element.iterchildren():
            if isinstance(child,ModelObject) and \
                (wildNamespaceURI or child.elementNamespaceURI in childNamespaceURIs) and \
                (wildLocalName or child.localName in childLocalNames):
                children.append(child)
    elif isinstance(element,etree._ElementTree): # document root
        child = element.getroot()
        if (wildNamespaceURI or child.elementNamespaceURI in childNamespaceURIs) and \
           (wildLocalName or child.localName in childLocalNames):
            children.append(child)
    return children

def child(element, childNamespaceURI=None, childLocalNames=("*",)):
    result = children(element, childNamespaceURI, childLocalNames)
    if result and len(result) > 0:
        return result[0]
    return None

def lastChild(element, childNamespaceURI=None, childLocalNames=("*",)):
    result = children(element, childNamespaceURI, childLocalNames)
    if result and len(result) > 0:
        return result[-1]
    return None

def previousSiblingElement(element):
    for result in element.itersiblings(preceding=True):
        if isinstance(result,ModelObject):
            return result
    return None
    
def nextSiblingElement(element):
    for result in element.itersiblings(preceding=False):
        if isinstance(result,ModelObject):
            return result
    return None
    
def childrenAttrs(element, childNamespaceURI, childLocalNames, attrLocalName):
    childrenElts = children(element, childNamespaceURI, childLocalNames)
    childrenAttrs = []
    for childElt in childrenElts:
        if childElt.get(attrLocalName):
            childrenAttrs.append(childElt.get(attrLocalName))
    childrenAttrs.sort()
    return childrenAttrs

def descendant(element, descendantNamespaceURI, descendantLocalNames, attrName=None, attrValue=None):
    d = descendants(element, descendantNamespaceURI, descendantLocalNames, attrName, attrValue, breakOnFirst=True)
    if d:
        return d[0]
    return None
    
def descendants(element, descendantNamespaceURI, descendantLocalNames, attrName=None, attrValue=None, breakOnFirst=False):
    descendants = []
    if not isinstance(descendantLocalNames,tuple): descendantLocalNames = (descendantLocalNames ,)
    wildLocalName = descendantLocalNames == ('*',)
    wildNamespaceURI = not descendantNamespaceURI or descendantNamespaceURI == '*'
    if isinstance(element,(ModelObject,etree._ElementTree)):
        for child in (element.iterdescendants() if isinstance(element,ModelObject) else element.iter()):
            if isinstance(child,ModelObject) and \
                (wildNamespaceURI or child.elementNamespaceURI == descendantNamespaceURI) and \
                (wildLocalName or child.localName in descendantLocalNames):
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
    
def isDescendantOf(element, ancestorElement):
    while element is not None:
        if element == ancestorElement:
            return True
        element = element.getparent()
    return False

def schemaDescendantsNames(element, descendantNamespaceURI, descendantLocalName, qnames=None):
    if qnames is None: qnames = set()
    for child in element.iterdescendants(tag="{{{0}}}{1}".format(descendantNamespaceURI,descendantLocalName)):
        if isinstance(child,ModelObject):
            if child.get("name"):
                # need to honor attribute/element form default
                qnames.add(qname(targetNamespace(element), child.get("name")))
            elif child.get("ref"):
                qnames.add(qname(element, child.get("ref")))
    return qnames

def schemaDescendant(element, descendantNamespaceURI, descendantLocalName, name):
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

def schemaBaseTypeDerivedFrom(element):
    for child in element.iterchildren():
        if child.tag in ("{http://www.w3.org/2001/XMLSchema}extension","{http://www.w3.org/2001/XMLSchema}restriction"):
            return child.get("base") 
        elif child.tag == "{http://www.w3.org/2001/XMLSchema}union":
            return (child.get("memberTypes") or "").split() + [
                    schemaBaseTypeDerivedFrom(child)
                    for child in element.iterchildren(tag="{http://www.w3.org/2001/XMLSchema}simpleType")]
        elif child.tag in ("{http://www.w3.org/2001/XMLSchema}complexType",
                           "{http://www.w3.org/2001/XMLSchema}simpleType",
                           "{http://www.w3.org/2001/XMLSchema}complexContent",
                           "{http://www.w3.org/2001/XMLSchema}simpleContent"):
            qn = schemaBaseTypeDerivedFrom(child)
            if qn is not None:
                return qn
    return None

def schemaFacets(element, facetTags, facets=None):
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

def schemaAttributesGroups(element, attributes=None, attributeWildcards=None, attributeGroups=None):
    if attributes is None: attributes = []; attributeWildcards = []; attributeGroups = []
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

def emptyContentModel(element):
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
def addChild(parent, childName1, childName2=None, attributes=None, text=None, afterSibling=None, beforeSibling=None, appendChild=True):
    from arelle.FunctionXs import xsString
    modelDocument = parent.modelDocument
                    
    if isinstance(childName1, QName):
        addQnameValue(modelDocument, childName1)
        if childName1.prefix:
            child = modelDocument.parser.makeelement(childName1.clarkNotation, nsmap={childName1.prefix:childName1.namespaceURI}) 
        else:
            child = modelDocument.parser.makeelement(childName1.clarkNotation)
    else:   # called with namespaceURI, localName
        existingPrefix = xmlnsprefix(parent, childName1)
        prefix, sep, localName = childName2.partition(":")
        if localName:
            if existingPrefix is None:
                setXmlns(modelDocument, prefix, childName1)
        else:
            localName = prefix
        child = modelDocument.parser.makeelement("{{{0}}}{1}".format(childName1, localName))
    if afterSibling is not None and afterSibling.getparent() == parent:  # sibling is a hint, parent prevails
        afterSibling.addnext(child)
    elif beforeSibling is not None and beforeSibling.getparent() == parent:  # sibling is a hint, parent prevails
        beforeSibling.addprevious(child)
    elif appendChild:
        parent.append(child)
    if attributes:
        for name, value in (attributes.items() if isinstance(attributes, dict) else
                            attributes if len(attributes) > 0 and isinstance(attributes[0],(tuple,list)) else (attributes,)):
            if isinstance(name,QName):
                if name.namespaceURI:
                    addQnameValue(modelDocument, name)
                child.set(name.clarkNotation, str(value))
            else:
                child.set(name, xsString(None, None, value) )
    if text is not None:
        child.text = xsString(None, None, text)
        # check if the text is a QName and add the namespace if needed!
        if isinstance(text, QName):
            addQnameValue(modelDocument, text)
    child.init(modelDocument)
    return child

def copyNodes(parent, elts):
    modelDocument = parent.modelDocument
    for origElt in elts if isinstance(elts, (tuple,list,set)) else (elts,):
        addQnameValue(modelDocument, origElt.elementQname)
        copyElt = modelDocument.parser.makeelement(origElt.tag)
        copyElt.init(modelDocument)
        parent.append(copyElt)
        for attrTag, attrValue in origElt.items():
            qn = qname(attrTag, noPrefixIsNoNamespace=True)
            prefix = xmlnsprefix(origElt, qn.namespaceURI)
            if prefix:
                setXmlns(modelDocument, prefix, qn.namespaceURI)
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
                
def copyChildren(parent, elt):
    for childNode in elt:
        if isinstance(childNode,ModelObject):
            copyNodes(parent, childNode)

def copyIxFootnoteHtml(srcXml, tgtHtml, targetModelDocument=None, withText=False, isContinChainElt=True, tgtStack=None, srcLevel=0):
    if tgtStack is None:
        tgtStack = [[tgtHtml, "text"]] # stack of current targetStack element, and current text attribute
    if not (isinstance(srcXml,ModelObject) and srcXml.localName == "exclude" and srcXml.namespaceURI in ixbrlAll):
        tgtStackLen = len(tgtStack)
        if withText:
            _tx = srcXml.text            
            if _tx:
                tgtElt, tgtNode = tgtStack[-1]
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
            setattr(tgtElt, tgtNode, (getattr(tgtElt, tgtNode) or "") + _tl)
    if isContinChainElt: # for inline continuation chain elements, follow chain (but not for nested elements)
        contAt = getattr(srcXml, "_continuationElement", None)
        if contAt is not None:
            copyIxFootnoteHtml(contAt, tgtHtml, targetModelDocument, withText=withText, isContinChainElt=True, tgtStack=tgtStack, srcLevel=0)
        
def addComment(parent, commentText):
    comment = str(commentText)
    if '--' in comment: # replace -- with - - (twice, in case more than 3 '-' together)
        comment = comment.replace('--', '- -').replace('--', '- -')
    child = etree.Comment( comment )
    parent.append(child)
    
def addProcessingInstruction(parent, piTarget, piText, insertBeforeChildElements=True, insertBeforeParentElement=False):
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
    
def addQnameValue(modelDocument, qnameValue):
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
        return qnameValue.localName if len(existingPrefix) == 0 else existingPrefix + ':' + qnameValue.localName
    prefix = qnameValue.prefix
    dupNum = 2 # start with _2 being 'second' use of same prefix, etc.
    while (dupNum < 10000): # check if another namespace has prefix already (but don't die if running away)
        if xmlns(xmlRootElement, prefix) is None:
            break   # ok to use this prefix
        prefix = "{0}_{1}".format(qnameValue.prefix if qnameValue.prefix else '', dupNum)
        dupNum += 1
    setXmlns(modelDocument, prefix, ns)
    return qnameValue.localName if len(prefix) == 0 else prefix + ':' + qnameValue.localName

def setXmlns(modelDocument, prefix, namespaceURI):
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
            newroot = etree.Element('nsmap', nsmap=newmap)
            newroot.extend(root)
        else:  # new xmlns-extension root
            newroot = etree.Element('nsmap', nsmap={prefix: namespaceURI})
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

def sortKey(parentElement, childNamespaceUri, childLocalNames, childAttributeName=None, qnames=False):
    list = []
    if parentElement is not None:
        for childLocalName in childLocalNames if isinstance(childLocalNames,tuple) else (childLocalNames,):
            for child in parentElement.iterdescendants(tag="{{{0}}}{1}".format(childNamespaceUri,childLocalName)):
                value = text(child)
                if qnames:
                    value = prefixedNameToClarkNotation(child, value)
                if childAttributeName is not None:
                    list.append((child.tag, value, child.get(childAttributeName)))
                else:
                    list.append((child.tag, value))
        list.sort()
    return list

DATETIME_MINYEAR = datetime.datetime(datetime.MINYEAR,1,1)
DATETIME_MAXYEAR = datetime.datetime(datetime.MAXYEAR,12,31)
def datetimeValue(element, addOneDay=False, none=None):
    if element is None:
        if none == "minyear":
            return DATETIME_MINYEAR
        elif none == "maxyear":
            return DATETIME_MAXYEAR
        return None
    match = datetimePattern.match(element if isinstance(element,_STR_BASE) else text(element).strip())
    if match is None:
        return None
    hour24 = False
    try:
        if match.lastindex == 6:
            hour = int(match.group(4))
            min = int(match.group(5))
            sec = int(match.group(6))
            if hour == 24 and min == 0 and sec == 0:
                hour24 = True
                hour = 0
            result = datetime.datetime(int(match.group(1)),int(match.group(2)),int(match.group(3)),hour,min,sec)
        else:
            result = datetime.datetime(int(match.group(7)),int(match.group(8)),int(match.group(9)))
        if addOneDay and match.lastindex == 9:
            result += datetime.timedelta(1) 
        if hour24:  #add one day
            result += datetime.timedelta(1) 
    except (ValueError, OverflowError, IndexError, AttributeError):
        if not "result" in locals(): # if not set yet, punt with max datetime
            result = DATETIME_MAXYEAR
    return result

def dateunionValue(datetimeValue, subtractOneDay=False, dateOnlyHour=None):
    if not isinstance(datetimeValue, (datetime.datetime, datetime.date)):
        return "INVALID"
    isDate = (hasattr(datetimeValue,'dateOnly') and datetimeValue.dateOnly) or not hasattr(datetimeValue, 'hour')
    if isDate or (datetimeValue.hour == 0 and datetimeValue.minute == 0 and datetimeValue.second == 0):
        d = datetimeValue
        if subtractOneDay and not isDate: d -= datetime.timedelta(1)
        if dateOnlyHour is None:
            return "{0:04n}-{1:02n}-{2:02n}".format(d.year, d.month, d.day)
        else: # show explicit hour on date-only value (e.g., 24:00:00 for end date)
            return "{0:04n}-{1:02n}-{2:02n}T{3:02n}:00:00".format(d.year, d.month, d.day, dateOnlyHour)
    else:
        return "{0:04n}-{1:02n}-{2:02n}T{3:02n}:{4:02n}:{5:02n}".format(datetimeValue.year, datetimeValue.month, datetimeValue.day, datetimeValue.hour, datetimeValue.minute, datetimeValue.second)

def xpointerSchemes(fragmentIdentifier):
    matches = xpointerFragmentIdentifierPattern.findall(fragmentIdentifier)
    schemes = []
    for scheme, parenPart, path in matches:
        if parenPart is not None and len(parenPart) > 0:   # don't accumulate shorthand id's
            schemes.append((scheme,path))
    return schemes

def xpointerElement(modelDocument, fragmentIdentifier):
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
            else:
                node = modelDocument.xmlDocument
                iter = (node.getroot(),)
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

def elementFragmentIdentifier(element):
    if getattr(element, "sourceElement", None) is not None: # prototype element
        return elementFragmentIdentifier(element.sourceElement)
    if isinstance(element,etree.ElementBase) and element.get('id'):
        return element.get('id')  # "short hand pointer" for element fragment identifier
    else:
        childSequence = [""] # "" represents document element for / (root) on the join below
        while element is not None:
            if isinstance(element,etree.ElementBase):
                if element.get('id'):  # has ID, use as start of path instead of root
                    childSequence[0] = element.get('id')
                    break
                try:
                    siblingPosition = element._elementSequence # set by loader in some element hierarchies
                except AttributeError:
                    siblingPosition = 1
                    for sibling in element.itersiblings(preceding=True):
                        if isinstance(sibling,etree.ElementBase):
                            siblingPosition += 1
                childSequence.insert(1, str(siblingPosition))
            element = element.getparent()
        location = "/".join(childSequence)
        return "element({0})".format(location)
    
def elementIndex(element):
    if isinstance(element,etree.ElementBase):
        try:
            return element._elementSequence # set by loader in some element hierarchies
        except AttributeError:
            siblingPosition = 1
            for sibling in element.itersiblings(preceding=True):
                if isinstance(sibling,etree.ElementBase):
                    siblingPosition += 1
            return siblingPosition
    return 0
    
def elementChildSequence(element):
    childSequence = [""] # "" represents document element for / (root) on the join below
    while element is not None:
        if isinstance(element,etree.ElementBase):
            try:
                siblingPosition = element._elementSequence # set by loader in some element hierarchies
            except AttributeError:
                siblingPosition = 1
                for sibling in element.itersiblings(preceding=True):
                    if isinstance(sibling,etree.ElementBase):
                        siblingPosition += 1
            childSequence.insert(1, str(siblingPosition))
        element = element.getparent()
    return "/".join(childSequence)
                        
def xmlstring(elt, stripXmlns=False, prettyPrint=False, contentsOnly=False, includeText=False):
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
    xml = etree.tostring(elt, encoding=_STR_UNICODE, pretty_print=prettyPrint)
    if not prettyPrint:
        xml = xml.strip()
    if stripXmlns:
        return xmlnsStripPattern.sub('', xml)
    else:
        return xml

def writexml(writer, node, encoding=None, indent='', xmlcharrefreplace=False, parentNsmap=None):
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
                    writexml(writer, nsmapChild, indent=indent, xmlcharrefreplace=xmlcharrefreplace, parentNsmap={}) # force all xmlns in next element
            else:
                writexml(writer, child, indent=indent, xmlcharrefreplace=xmlcharrefreplace, parentNsmap={})
    elif isinstance(node,etree._Comment): # ok to use minidom implementation
        writer.write(indent+"<!--" + node.text + "-->\n")
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
                                 for k, v in (_DICT_SET(node.nsmap.items()) - _DICT_SET(parentNsmap.items()))):
            if prefix:
                attrs["xmlns:" + prefix] = ns
            else:
                attrs["xmlns"] = ns
        for aTag,aValue in node.items():
            ns, sep, localName = aTag.partition('}')
            if sep:
                prefix = xmlnsprefix(node,ns[1:])
                if prefix:
                    prefixedName = prefix + ":" + localName
                else:
                    prefixedName = localName
            else:
                prefixedName = ns
            attrs[prefixedName] = aValue
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
                     indent=indent+'    ' if indent is not None and not isFootnote else None, 
                     xmlcharrefreplace=xmlcharrefreplace)
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
