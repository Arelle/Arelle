'''
Created on Oct 22, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import re, datetime
from lxml import etree
from arelle import XbrlConst
from arelle.ModelObject import ModelObject, ModelComment
from arelle.ModelValue import qname, QName

datetimePattern = re.compile('\s*([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})\s*|'
                             '\s*([0-9]{4})-([0-9]{2})-([0-9]{2})\s*')
xmlEncodingPattern = re.compile(r"\s*<\?xml\s.*encoding=['\"]([^'\"]*)['\"].*\?>")
xpointerFragmentIdentifierPattern = re.compile(r"([\w.]+)(\(([^)]*)\))?")
xmlnsStripPattern = re.compile(r'\s*xmlns(:\w+)?="[^"]*"')

def xmlns(element, prefix):
    return element.nsmap.get(prefix)

def xmlnsprefix(element, ns):
    if ns is None:
        return None
    if ns == XbrlConst.xml: # never declared explicitly
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
        if treeElt.localName == "schema" and treeElt.namespaceURI == XbrlConst.xsd and treeElt.get("targetNamespace"):
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

def encoding(xml):
    if isinstance(xml,bytes):
        s = xml[0:120]
        if b"x\0m\0l" in s:
            str = s.decode("utf-16")
        else:
            str = s.decode("latin-1")
    else:
        str = xml[0:80]
    match = xmlEncodingPattern.match(str)
    if match and match.lastindex == 1:
        return match.group(1)
    return "utf-8"

def text(element):   
    return textNotStripped(element).strip()

def childText(element, childNamespaceURI, childLocalNames):   
    element = child(element, childNamespaceURI, childLocalNames)
    return textNotStripped(element).strip() if element is not None else None

def textNotStripped(element):
    if element is None: 
        return ""
    return element.elementText  # allows embedded comment nodes, returns '' if None

def innerText(element, ixExclude=False, strip=True):   
    try:
        text = "".join(text for text in innerTextNodes(element, ixExclude))
        if strip:
            return text.strip()
        return text
    except TypeError:
        return ""

def innerTextList(element, ixExclude=False):   
    try:
        return ", ".join(text.strip() for text in innerTextNodes(element, ixExclude) if len(text.strip()) > 0)
    except TypeError:
        return ""

def innerTextNodes(element, ixExclude):
    if element.text:
        yield element.text
    for child in element.iterchildren():
        if isinstance(child,ModelObject) and (
           not ixExclude or 
           (child.localName != "exclude" and child.namespaceURI != "http://www.xbrl.org/2008/inlineXBRL")):
            for nestedText in innerTextNodes(child, ixExclude):
                yield nestedText
        if child.tail:
            yield child.tail

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
    while isinstance(treeElt,ModelObject):
        if treeElt.elementNamespaceURI == ancestorNamespaceURI:
            if isinstance(ancestorLocalNames,tuple):
                if treeElt.localName in ancestorLocalNames:
                    return treeElt
            elif treeElt.localName == ancestorLocalNames:
                return treeElt
        treeElt = treeElt.getparent()
    return None
    
def parent(element):
    return element.getparent()

def ancestors(element):
    return [ancestor for ancestor in element.getancestors()]
    
def childAttr(element, childNamespaceURI, childLocalNames, attrClarkName):
    childElt = child(element, childNamespaceURI, childLocalNames)
    return childElt.get(attrClarkName) if childElt is not None else None

def descendantAttr(element, childNamespaceURI, childLocalNames, attrClarkName, attrName=None, attrValue=None):
    descendantElt = descendant(element, childNamespaceURI, childLocalNames, attrName, attrValue)
    return descendantElt.get(attrClarkName) if (descendantElt is not None) else None

def children(element, childNamespaceURI, childLocalNames):
    children = []
    if not isinstance(childLocalNames,tuple): childLocalNames = (childLocalNames ,)
    wildLocalName = childLocalNames == ('*',)
    wildNamespaceURI = not childNamespaceURI or childNamespaceURI == '*'
    if isinstance(element,ModelObject):
        for child in element.iterchildren():
            if isinstance(child,ModelObject) and \
                (wildNamespaceURI or child.elementNamespaceURI == childNamespaceURI) and \
                (wildLocalName or child.localName in childLocalNames):
                children.append(child)
    elif isinstance(element,etree._ElementTree): # document root
        child = element.getroot()
        if (wildNamespaceURI or child.elementNamespaceURI == childNamespaceURI) and \
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

def schemaAttributesGroups(element, attributes=None, attributeGroups=None):
    if attributes is None: attributes = []; attributeGroups = []
    for child in element.iterchildren():
        if child.tag == "{http://www.w3.org/2001/XMLSchema}attribute":
            attributes.append(child) 
        elif child.tag == "{http://www.w3.org/2001/XMLSchema}attributeGroup":
            attributeGroups.append(child) 
        elif child.tag in {"{http://www.w3.org/2001/XMLSchema}complexType",
                           "{http://www.w3.org/2001/XMLSchema}simpleType",
                           "{http://www.w3.org/2001/XMLSchema}complexContent",
                           "{http://www.w3.org/2001/XMLSchema}simpleContent",
                           "{http://www.w3.org/2001/XMLSchema}restriction",
                           "{http://www.w3.org/2001/XMLSchema}extension"
                           }:
            schemaAttributesGroups(child, attributes=attributes, attributeGroups=attributeGroups)
    return (attributes, attributeGroups)

def emptyContentModel(element):
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
def addChild(parent, childName1, childName2=None, attributes=None, text=None, afterSibling=None, beforeSibling=None):
    from arelle.FunctionXs import xsString
    modelDocument = parent.modelDocument
    if isinstance(childName1, QName):
        addQnameValue(modelDocument, childName1)
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
    child.init(modelDocument)
    if afterSibling is not None and afterSibling.getparent() == parent:  # sibling is a hint, parent prevails
        afterSibling.addnext(child)
    elif beforeSibling is not None and beforeSibling.getparent() == parent:  # sibling is a hint, parent prevails
        beforeSibling.addprevious(child)
    else:
        parent.append(child)
    if attributes:
        for name, value in (attributes if len(attributes) > 0 and isinstance(attributes[0],tuple) else (attributes,)):
            if isinstance(name,QName):
                if name.namespaceURI:
                    addQnameValue(modelDocument, name)
                child.set(name.clarkNotation, str(value))
            else:
                child.set(name, xsString(None, None, value) )
    if text:
        child.text = xsString(None, None, text)
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
            if qn.prefix and qn.namespaceURI:
                setXmlns(modelDocument, qn.prefix, qn.namespaceURI)
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

def addComment(parent, commentText):
    comment = str(commentText)
    if '--' in comment: # replace -- with - - (twice, in case more than 3 '-' together)
        comment = comment.replace('--', '- -').replace('--', '- -')
    child = etree.Comment( comment )
    parent.append(child)
    
def addQnameValue(modelDocument, qnameValue):
    if isinstance(modelDocument, ModelObject): modelDocument = modelDocument.modelDocument
    existingPrefix = xmlnsprefix(modelDocument.xmlRootElement, qnameValue.namespaceURI)
    if existingPrefix is not None:  # namespace is already declared, use that for qnameValue's prefix
        return qnameValue.localName if len(existingPrefix) == 0 else existingPrefix + ':' + qnameValue.localName
    prefix = qnameValue.prefix
    dupNum = 2 # start with _2 being 'second' use of same prefix, etc.
    while (dupNum < 10000): # check if another namespace has prefix already (but don't die if running away)
        if xmlns(modelDocument.xmlRootElement, prefix) is None:
            break   # ok to use this prefix
        prefix = "{0}_{1}".format(qnameValue.prefix if qnameValue.prefix else '', dupNum)
        dupNum += 1
    setXmlns(modelDocument, prefix, qnameValue.namespaceURI)
    return qnameValue.localName if len(prefix) == 0 else prefix + ':' + qnameValue.localName

def setXmlns(modelDocument, prefix, namespaceURI):
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
            newroot.append(root)
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

def datetimeValue(element, addOneDay=False, none=None):
    if element is None:
        if none == "minyear":
            return datetime.datetime(datetime.MINYEAR,1,1)
        elif none == "maxyear":
            return datetime.datetime(datetime.MAXYEAR,12,31)
        return None
    match = datetimePattern.match(element if isinstance(element,_STR_BASE) else text(element).strip())
    if match is None:
        return None
    hour24 = False
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
    return result

def dateunionValue(datetimeValue, subtractOneDay=False):
    isDate = (hasattr(datetimeValue,'dateOnly') and datetimeValue.dateOnly) or not hasattr(datetimeValue, 'hour')
    if isDate or (datetimeValue.hour == 0 and datetimeValue.minute == 0 and datetimeValue.second == 0):
        d = datetimeValue
        if subtractOneDay and not isDate: d -= datetime.timedelta(1)
        return "{0:04n}-{1:02n}-{2:02n}".format(d.year, d.month, d.day)
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
                    if isinstance(child,etree._Element):
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
    if isinstance(element,etree._Element) and element.get('id'):
        return element.get('id')  # "short hand pointer" for element fragment identifier
    else:
        childSequence = [""] # "" represents document element for / (root) on the join below
        while element is not None:
            if isinstance(element,etree._Element):
                if element.get('id'):  # has ID, use as start of path instead of root
                    childSequence[0] = element.get('id')
                    break
                siblingPosition = 1
                for sibling in element.itersiblings(preceding=True):
                    if isinstance(sibling,etree._Element):
                        siblingPosition += 1
                childSequence.insert(1, str(siblingPosition))
            element = element.getparent()
        location = "/".join(childSequence)
        return "element({0})".format(location)
    
def ixToXhtml(fromRoot):
    toRoot = etree.Element(fromRoot.localName)
    copyNonIxChildren(fromRoot, toRoot)
    for attrTag, attrValue in fromRoot.items():
        toRoot.set(attrTag, attrValue)
    return toRoot

def copyNonIxChildren(fromElt, toElt):
    for fromChild in fromElt:
        if isinstance(fromChild, ModelObject):
            fromTag = fromChild.tag
            if fromTag not in {"{http://www.xbrl.org/2008/inlineXBRL}references",
                               "{http://www.xbrl.org/2008/inlineXBRL}resources"}:
                if fromTag in {"{http://www.xbrl.org/2008/inlineXBRL}footnote",
                               "{http://www.xbrl.org/2008/inlineXBRL}nonNumeric"}:
                    toChild = etree.Element("ixNestedContent")
                    toElt.append(toChild)
                    copyNonIxChildren(fromChild, toChild)
                    if fromChild.text is not None:
                        toChild.text = fromChild.text
                    if fromChild.tail is not None:
                        toChild.tail = fromChild.tail
                elif fromTag.startswith("{http://www.xbrl.org/2008/inlineXBRL}"):
                    copyNonIxChildren(fromChild, toElt)
                else:
                    toChild = etree.Element(fromChild.localName)
                    toElt.append(toChild)
                    copyNonIxChildren(fromChild, toChild)
                    for attrTag, attrValue in fromChild.items():
                        toChild.set(attrTag, attrValue)
                    if fromChild.text is not None:
                        toChild.text = fromChild.text
                    if fromChild.tail is not None:
                        toChild.tail = fromChild.tail
                        
def xmlstring(elt, stripXmlns=False, prettyPrint=False):
    xml = etree.tounicode(elt, pretty_print=prettyPrint)
    if stripXmlns:
        return xmlnsStripPattern.sub('', xml)
    else:
        return xml

def writexml(writer, node, encoding=None, indent='', parentNsmap=None):
    # customized from xml.minidom to provide correct indentation for data items
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
                    writexml(writer, nsmapChild, indent=indent, parentNsmap={}) # force all xmlns in next element
            else:
                writexml(writer, child, indent=indent, parentNsmap={})
    elif isinstance(node,etree._Comment): # ok to use minidom implementation
        writer.write(indent+"<!--" + node.text + "-->\n")
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
        else:
            ns, sep, localName = node.tag.partition('}')
            if sep:
                prefix = xmlnsprefix(node,ns[1:])
                if prefix:
                    tag = prefix + ":" + localName
                else:
                    tag = localName
            else:
                tag = ns
        writer.write(indent+"<" + tag)
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
        indentAttrs = ("\n" + indent + "  ") if numAttrs > 1 and lenAttrs > 60 else " "
        for aName in aSortedNames:
            writer.write("%s%s=\"" % (indentAttrs, aName))
            if aName != "xsi:schemaLocation":
                writer.write(attrs[aName].replace("&","&amp;").replace('"','&quot;'))
            else:
                indentUri = "\n" + indent + "                      "
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
            text = text.replace("&","&amp;").replace("\u00A0","&nbsp;").strip().replace("<","&lt;").replace("\u00AD","&shy;")
        for child in node.iterchildren():
            hasChildNodes = True
            if firstChild:
                writer.write(">\n")
                if text:
                    writer.write(text)
                firstChild = False
            writexml(writer, child, indent=indent+'    ')
        if hasChildNodes:
            writer.write("%s</%s>\n" % (indent, tag))
        elif text:
            writer.write(">%s</%s>\n" % (text, tag))
        else:
            writer.write("/>\n")
