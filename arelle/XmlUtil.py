'''
Created on Oct 22, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import re, datetime, xml.dom.minidom, xml.dom
from arelle import XbrlConst
from arelle.ModelObject import ModelObject

datetimePattern = re.compile('\s*([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})\s*|'
                             '\s*([0-9]{4})-([0-9]{2})-([0-9]{2})\s*')
xmlEncodingPattern = re.compile(r"\s*<\?xml\s.*encoding=['\"]([^'\"]*)['\"].*\?>")
xpointerFragmentIdentifierPattern = re.compile(r"([\w.]+)(\(([^)]*)\))?")

def xmlns(element, prefix):
    return element.nsmap.get(prefix)
    '''
    if prefix is None or prefix == "":
        xmlnsattr = "xmlns"
    elif prefix == "xml":  # never declared explicitly
        return XbrlConst.xml
    else:
        xmlnsattr = "xmlns:" + prefix
    ns = None
    treeElt = element
    while treeElt.nodeType == 1:
        if treeElt.hasAttribute(xmlnsattr):
            ns = treeElt.getAttribute(xmlnsattr)
            # xmlns="" returns None instead of ""
            break
        treeElt = treeElt.parentNode
    return ns
    '''

def xmlnsprefix(element, ns):
    if ns is None:
        return None
    if ns == XbrlConst.xml: # never declared explicitly
        return 'xml'
    for prefix, NS in element.nsmap.items():
        if NS == ns:
            return prefix
    return None
    '''
    treeElt = element
    while treeElt.nodeType == 1:
        for i in range(len(treeElt.attributes)):
            attribute = treeElt.attributes.item(i)
            if attribute.value == ns:
                if attribute.name == "xmlns":
                    return ""
                elif attribute.prefix:  # no prefix is accessible on just-created xmlns attributes
                    if attribute.prefix == "xmlns":
                        return attribute.localName
                elif attribute.name.startswith("xmlns:"):   # xlower than previx comparison, needed for new xmlns additions
                    return attribute.localName
        treeElt = treeElt.parentNode
    return None
    '''

def targetNamespace(element):
    treeElt = element
    while treeElt is not None:
        if treeElt.localName == "schema" and treeElt.namespaceURI == XbrlConst.xsd and treeElt.get("targetNamespace"):
            return treeElt.get("targetNamespace")
        treeElt = treeElt.getparent()
    return None

def schemaLocation(element, namespace):
    treeElt = element
    while treeElt is not None:
        sl = treeElt.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation")
        if sl:
            isNs = True
            for entry in sl.split():
                if isNs:
                    if entry == namespace:
                        return treeElt
                    isNs = False
                else:
                    isNs = True
        treeElt = treeElt.getparent()
    return None

# provide python-style QName, e.g., {namespaceURI}localName
def prefixedNameToNamespaceLocalname(element, prefixedName):
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
        if prefix: return None  # error, prefix not found
    return (ns, localName, prefix)

# provide python-style QName, e.g., {namespaceURI}localName
def prefixedNameToPyQname(element, prefixedName):
    nsLocalname = prefixedNameToNamespaceLocalname(element, prefixedName)
    if nsLocalname is None: return None
    ns, localname, prefix = nsLocalname
    if ns is None: return localname
    return "{{{0}}}{1}".format(ns, localname)

def pyQnameToNamespaceLocalname(pyQname):
    if pyQname[0] == "{":
        ns,sep,name = pyQname[1:].partition("}")
        return (ns,name)
    return None

def pyQname(element):
    return "{{{0}}}{1}".format(element.namespaceURI, element.localName)
    

def encoding(xml):
    if isinstance(xml,bytes):
        str = xml[0:80].decode("latin-1")
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
    return textNotStripped(element).strip() if element else None

def textNotStripped(element):
    if element is None: return ""   
    return element.text

def innerText(element, ixExclude=False):   
    try:
        return "".join(child.nodeValue for child in innerTextNodes(element, ixExclude, [])).strip()
    except TypeError:
        return ""

def innerTextList(element, ixExclude=False):   
    try:
        return ", ".join(child.text.strip() for child in innerTextNodes(element, ixExclude) if len(child.text.strip()) > 0)
    except TypeError:
        return ""

def innerTextNodes(element, ixExclude):
    return [child
            for child in element.iterdescendants()
            if isinstance(child,ModelObject) and (
               not ixExclude or (child.localName != "exclude" and child.namespaceURI != "http://www.xbrl.org/2008/inlineXBRL"))]

def parentId(element, parentNamespaceURI, parentLocalName):
    while element is not None:
        if element.namespaceURI == parentNamespaceURI and element.localName == parentLocalName:
            return element.get("id")
        element = element.getparent()
    return None
    
def hasChild(element, childNamespaceURI, childLocalNames):
    if not isinstance(childLocalNames,tuple): childLocalNames = (childLocalNames ,)
    wildLocalName = childLocalNames == ('*',)
    for child in element.iterchildren():
        if isinstance(child,ModelObject) and \
            child.elementNamespaceURI == childNamespaceURI and \
            (wildLocalName or child.localName in childLocalNames):
            return True
    return False
    
def hasDescendant(element, childNamespaceURI, childLocalNames):
    for childLocalName in childLocalNames if isinstance(childLocalNames,tuple) else (childLocalNames,):
        for child in element.getElementsByTagNameNS(childNamespaceURI, childLocalName):
            if isinstance(child,ModelObject):
                return True
    return False
    
def hasAncestor(element, ancestorNamespaceURI, ancestorLocalNames):
    treeElt = element.getparent()
    while treeElt is not None:
        if treeElt.elementNamespaceURI == ancestorNamespaceURI:
            if isinstance(ancestorLocalNames,tuple):
                if treeElt.localName in ancestorLocalNames:
                    return True
            elif treeElt.localName == ancestorLocalNames:
                return True
        treeElt = treeElt.getparent()
    return False
    
def ancestor(element, ancestorNamespaceURI, ancestorLocalNames):
    treeElt = element.getparent()
    while treeElt is not None:
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
    ancestors = []
    ancestor = element.getparent()
    while ancestor is not None:
        ancestors.append(ancestor)
        ancestor = ancestor.getparent()
    return ancestors
    
def childAttr(element, childNamespaceURI, childLocalNames, attrLocalName):
    childElt = child(element, childNamespaceURI, childLocalNames)
    return childElt.get(attrLocalName) if childElt else None

def descendantAttr(element, childNamespaceURI, childLocalNames, attrLocalName, attrName=None, attrValue=None):
    descendantElt = descendant(element, childNamespaceURI, childLocalNames, attrName, attrValue)
    return descendantElt.get(attrLocalName) if (descendantElt is not None) else None

def children(element, childNamespaceURI, childLocalNames):
    children = []
    if not isinstance(childLocalNames,tuple): childLocalNames = (childLocalNames ,)
    wildLocalName = childLocalNames == ('*',)
    wildNamespaceURI = not childNamespaceURI or childNamespaceURI == '*'
    if element is not None:
        for child in element.iterchildren():
            if isinstance(child,ModelObject) and \
                (wildNamespaceURI or child.elementNamespaceURI == childNamespaceURI) and \
                (wildLocalName or child.localName in childLocalNames):
                children.append(child)
    return children

def child(element, childNamespaceURI, childLocalNames):
    result = children(element, childNamespaceURI, childLocalNames)
    if result and len(result) > 0:
        return result[0]
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
    
# call with parent, childNamespaceURI, childLocalName, or just childQName object
# attributes can be (localName, value) or (QName, value)
def addChild(parent, childName1, childName2=None, attributes=None, text=None, afterSibling=None):
    from arelle.ModelValue import (QName)
    from arelle.FunctionXs import (string)
    document = parent.ownerDocument
    documentElement = document.documentElement
    if isinstance(childName1, QName):
        child = document.createElementNS(childName1.namespaceURI, 
                                         addQnameValue(documentElement, childName1))
    else:   # called with namespaceURI, localName
        existingPrefix = xmlnsprefix(documentElement, childName1)
        if existingPrefix is None:  # assume prefix is used consistently and doesn't need cross-checking
            prefix, sep, localName = childName2.partition(":")
            if sep and localName:
                setXmlns(documentElement, prefix, childName1)
        child = document.createElementNS(childName1, childName2)
    if afterSibling:
        parent.insertBefore(child, afterSibling.nextSibling)
    else:
        parent.appendChild(child)
    if attributes:
        for name, value in (attributes if len(attributes) > 0 and isinstance(attributes[0],tuple) else (attributes,)):
            if isinstance(name,QName):
                child.setAttributeNS(name.namespaceURI,
                                     addQnameValue(document.documentElement, name),
                                     str(value))
            else:
                child.setAttribute(name, string(None, value) )
    if text:
        textNode = document.createTextNode(string(None, text))
        child.appendChild(textNode)
    return child

def copyNodes(parent, elts):
    from arelle.ModelValue import (qname)
    document = parent.ownerDocument
    xmlnsElement = document.documentElement
    for origElt in elts if hasattr(elts, '__iter__') else (elts,):
        copyElt = document.createElementNS(origElt.namespaceURI, 
                                           addQnameValue(document.documentElement, qname(origElt)))
        parent.appendChild(copyElt)
        for i in range(len(origElt.attributes)):
            origAttr = origElt.attributes.item(i)
            if origAttr.prefix and origAttr.namespaceURI:
                copyElt.setAttributeNS(origAttr.namespaceURI,
                                       addQnameValue(document.documentElement, qname(origAttr.namespaceURI,origAttr.name)),
                                       origAttr.value)
            else:
                copyElt.setAttribute(origAttr.name, origAttr.value)
        textContentSet = False
        if hasattr(origElt, "xValue"):
            from arelle.ModelValue import (QName)
            if isinstance(origElt.xValue,QName):
                copyElt.appendChild(document.createTextNode(
                           addQnameValue(document.documentElement, origElt.xValue)))
                textContentSet = True
        for childNode in origElt.childNodes:
            if (childNode.nodeType == 3 or childNode.nodeType == 4) and not textContentSet:
                copyElt.appendChild(document.createTextNode(childNode.nodeValue))
            elif childNode.nodeType == 1:
                copyNodes(copyElt,childNode)
                
def copyChildren(parent, elt):
    for childNode in elt.childNodes:
        if childNode.nodeType == 1:
            copyNodes(parent, childNode)

def addComment(parent, commentText):
    document = parent.ownerDocument
    child = document.createComment( str(commentText) )
    parent.appendChild(child)
    
def addQnameValue(xmlnsElement, qnameValue):
    from arelle.ModelValue import (qname)
    existingPrefix = xmlnsprefix(xmlnsElement, qnameValue.namespaceURI)
    if existingPrefix is not None:  # namespace is already declared, use that for qnameValue's prefix
        return qnameValue.localName if len(existingPrefix) == 0 else existingPrefix + ':' + qnameValue.localName
    prefix = qnameValue.prefix
    dupNum = 2 # start with _2 being 'second' use of same prefix, etc.
    while (dupNum < 10000): # check if another namespace has prefix already (but don't die if running away)
        if xmlns(xmlnsElement, prefix) is None:
            break   # ok to use this prefix
        prefix = "{0}_{1}".format(qnameValue.prefix if qnameValue.prefix else '', dupNum)
        dupNum += 1
    setXmlns(xmlnsElement, prefix, qnameValue.namespaceURI)
    return qnameValue.localName if len(prefix) == 0 else prefix + ':' + qnameValue.localName

def setXmlns(xmlnsElement, prefix, namespaceURI):
    xmlnsElement.setAttribute('xmlns' if len(prefix) == 0 else 'xmlns:' + prefix, namespaceURI )

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
    if element is not None:
        for child in element.iterdescendants():
            if isinstance(child,ModelObject) and \
                (wildNamespaceURI or child.elementNamespaceURI == descendantNamespaceURI) and \
                (wildLocalName or child.localName in descendantLocalNames):
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
    from arelle.ModelValue import (qname)
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
    from arelle.ModelValue import (qname,QName)
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

def sortKey(parentElement, childNamespaceUri, childLocalNames, childAttributeName=None, qnames=False):
    list = []
    if parentElement:
        for childLocalName in childLocalNames if isinstance(childLocalNames,tuple) else (childLocalNames,):
            for child in parentElement.iterdescendants(tag="{{{0}}}{1}".format(childNamespaceUri,childLocalName)):
                value = text(child)
                if qnames:
                    value = prefixedNameToPyQname(child, value)
                if childAttributeName is not None:
                    list.append((child.tagName, value, child.get(childAttributeName)))
                else:
                    list.append((child.tagName, value))
        list.sort()
    return list

def datetimeValue(element, addOneDay=False, none=None):
    if element is None:
        if none == "minyear":
            return datetime.datetime(datetime.MINYEAR,1,1)
        elif none == "maxyear":
            return datetime.datetime(datetime.MAXYEAR,12,31)
        return None
    match = datetimePattern.match(text(element).strip())
    if match is None:
        return None
    if match.lastindex == 6:
        result = datetime.datetime(int(match.group(1)),int(match.group(2)),int(match.group(3)),int(match.group(4)),int(match.group(5)),int(match.group(6)))
    else:
        result = datetime.datetime(int(match.group(7)),int(match.group(8)),int(match.group(9)))
    if addOneDay and match.lastindex == 9:
        result += datetime.timedelta(1)   #add one day
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
                node = modelDocument.idObjects.get(scheme).element
            else:
                node = modelDocument.xmlDocument.getElementById(scheme)
            if node:
                return node    # this scheme fails
        elif scheme == "element" and parenPart and path:
            pathParts = path.split("/")
            if len(pathParts) >= 1 and len(pathParts[0]) > 0 and not pathParts[0].isnumeric():
                id = pathParts[0]
                if id in modelDocument.idObjects:
                    node = modelDocument.idObjects.get(id).element
                else:
                    node = modelDocument.xmlDocument.getElementById(id)
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
                    if isinstance(child,ModelObject):
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
    if element.id:
        location = element.id
    else:
        childSequence = [""] # "" represents document element for / on the join below
        while element:
            if element.nodeType == 1:
                sibling = element
                siblingPosition = 0
                while sibling:
                    if sibling.nodeType == 1:
                        siblingPosition += 1
                    sibling = sibling.previousSibling
                childSequence.insert(1, str(siblingPosition))
            element = element.parentNode
        location = "/".join(childSequence)
    return "element({0})".format(location)

def writexml(writer, node, encoding=None, indent=''):
    # customized from xml.minidom to provide correct indentation for data items
    if node.nodeType == xml.dom.Node.DOCUMENT_NODE:
        if encoding:
            writer.write('<?xml version="1.0" encoding="%s"?>\n' % (encoding,))
        else:
            writer.write('<?xml version="1.0"?>\n')
        for child in node.childNodes:
            writexml(writer, child, indent=indent)
    elif node.nodeType == xml.dom.Node.ELEMENT_NODE:
        writer.write(indent+"<" + node.tagName)

        attrs = node._get_attributes()
        a_names = sorted(attrs.keys())

        # should attribute names be indented on separate lines?
        numAttrs = 0
        lenAttrs = 0
        for a_name in a_names:
            numAttrs += 1
            lenAttrs += 4 + len(a_name) + len(attrs[a_name].value)
        indentAttrs = ("\n" + indent + "  ") if numAttrs > 1 and lenAttrs > 60 else " "
        for a_name in a_names:
            writer.write("%s%s=\"" % (indentAttrs, a_name))
            if a_name != "xsi:schemaLocation":
                xml.dom.minidom._write_data(writer, attrs[a_name].value)
            else:
                indentUri = "\n" + indent + "                      "
                for i, a_uri in enumerate(attrs[a_name].value.split()):
                    if i & 1:   #odd
                        writer.write(" " + a_uri)
                    elif i > 0:   #even
                        writer.write(indentUri + a_uri)
                    else:
                        writer.write(a_uri)
            writer.write("\"")
        if node.childNodes:
            if len(node.childNodes) == 1 and node.childNodes[0].nodeType == xml.dom.Node.TEXT_NODE:
                # not indented
                writer.write(">%s</%s>\n" % (node.childNodes[0].data, node.tagName))
            else: # ordinary indented child nodes
                writer.write(">\n")
                for child in node.childNodes:
                    writexml(writer, child, indent=indent+'    ')
                writer.write("%s</%s>\n" % (indent, node.tagName))
        else:
            writer.write("/>\n")
    else: # ok to use minidom implementation
        node.writexml(writer, indent=indent, addindent='    ', newl='\n')