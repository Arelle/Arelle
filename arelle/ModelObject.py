'''
Created on Oct 5, 2010
Refactored on Jun 11, 2011 to ModelDtsObject, ModelInstanceObject, ModelTestcaseObject

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from lxml import etree
from collections import namedtuple

class ModelObject(etree.ElementBase):
    
    def _init(self):
        self.isChanged = False
        parent = self.getparent()
        if parent is not None and hasattr(parent, "modelDocument"):
            self.init(parent.modelDocument)
            
    def init(self, modelDocument):
        self.modelDocument = modelDocument
        self.objectIndex = len(modelDocument.modelXbrl.modelObjects)
        modelDocument.modelXbrl.modelObjects.append(self)
        modelDocument.modelObjects.append(self)
        id = self.get("id")
        if id:
            modelDocument.idObjects[id] = self
                
    def objectId(self,refId=""):
        return "_{0}_{1}".format(refId, self.objectIndex)
    
    @property
    def modelXbrl(self):
        try:
            return self.modelDocument.modelXbrl
        except AttributeError:
            return None
        
    def attr(self, attrname):
        return self.get(attrname)

    def setNamespaceLocalName(self):
        ns, sep, ln = self.tag.partition("}")
        if sep:
            self._localName = ln
            self._namespaceURI = ns[1:]
        else:
            self._localName = ns
            self._namespaceURI = None
        if self.prefix:
            self._prefixedName = self.prefix + ":" + self.localName
        else:
            self._prefixedName = self.localName
            
    def getStripped(self, attrName):
        attrValue = self.get(attrName)
        if attrValue is not None:
            return attrValue.strip()
        return attrValue

    @property
    def localName(self):
        try:
            return self._localName
        except AttributeError:
            self.setNamespaceLocalName()
            return self._localName
        
    @property
    def prefixedName(self):
        try:
            return self._prefixedName
        except AttributeError:
            self.setNamespaceLocalName()
            return self._prefixedName
        
    @property
    def namespaceURI(self):
        try:
            return self._namespaceURI
        except AttributeError:
            self.setNamespaceLocalName()
            return self._namespaceURI
    
    @property
    def elementNamespaceURI(self):  # works also for concept elements
        try:
            return self._namespaceURI
        except AttributeError:
            self.setNamespaceLocalName()
            return self._namespaceURI
    
    # qname of concept of fact or element for all but concept element, type, attr, param, override to the name parameter
    @property
    def qname(self):
        try:
            return self._elementQname
        except AttributeError:
            self._elementQname = qname(self)
            return self._elementQname
        
    # qname is overridden for concept, type, attribute, and formula parameter, elementQname is unambiguous
    @property
    def elementQname(self):
        try:
            return self._elementQname
        except AttributeError:
            self._elementQname = qname(self)
            return self._elementQname
    
    @property
    def elementDeclaration(self):
        concept = self.modelXbrl.qnameConcepts.get(self.qname)
        return concept
    
    @property
    def parentQname(self):
        try:
            return self._parentQname
        except AttributeError:
            self._parentQname = qname( self.getparent() )
            return self._parentQname

    
    @property
    def id(self):
        return self.get("id")
    
    @property
    def innerText(self):    # includes text 'around' nested elements and comment nodes nested in value
        return ''.join(self.itertext())  # no text nodes returns ''
    
    @property
    def elementText(self):    # includes text 'around' comment nodes nested in value
        return ''.join(self._elementTextNodes())  # no text nodes returns ''
    
    def _elementTextNodes(self):
        if self.text: yield self.text
        for c in self.iterchildren():
            if not isinstance(c, etree.ElementBase): # skip nested element nodes
                if c.tail: yield c.tail  # get tail of nested comment or processor nodes

    @property
    def document(self):
        return self.modelDocument
    
    def prefixedNameQname(self, prefixedName):
        if prefixedName:    # passing None would return element qname, not prefixedName None Qname
            return qname(self, prefixedName)
        else:
            return None
    
    @property
    def elementAttributesTuple(self):
        return tuple((name,value) for name,value in self.items())
    
    @property
    def elementAttributesStr(self):
        return ', '.join(["{0}='{1}'".format(name,value) for name,value in self.items()])

    def resolveUri(self, hrefObject=None, uri=None, dtsModelXbrl=None):
        if dtsModelXbrl is None:
            dtsModelXbrl = self.modelXbrl
        doc = None
        if hrefObject:
            hrefElt,doc,id = hrefObject
        elif uri:
            from arelle import UrlUtil
            url, id = UrlUtil.splitDecodeFragment(uri)
            if url == "":
                doc = self.modelDocument
            else:
                normalizedUrl = self.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(
                                   url, 
                                   self.modelDocument.baseForElement(self))
                doc = dtsModelXbrl.urlDocs.get(normalizedUrl)
        from arelle import ModelDocument
        if isinstance(doc, ModelDocument.ModelDocument):
            if id is None:
                return doc
            elif id in doc.idObjects:
                return doc.idObjects[id]
            else:
                from arelle.XmlUtil import xpointerElement
                xpointedElement = xpointerElement(doc,id)
                # find element
                for docModelObject in doc.modelObjects:
                    if docModelObject == xpointedElement:
                        doc.idObjects[id] = docModelObject # cache for reuse
                        return docModelObject
        return None

    def genLabel(self,role=None,fallbackToQname=False,fallbackToXlinkLabel=False,lang=None,strip=False,linkrole=None):
        from arelle import XbrlConst
        if role is None: role = XbrlConst.genStandardLabel
        if role == XbrlConst.conceptNameLabelRole: return str(self.qname)
        labelsRelationshipSet = self.modelXbrl.relationshipSet(XbrlConst.elementLabel,linkrole)
        if labelsRelationshipSet:
            label = labelsRelationshipSet.label(self, role, lang)
            if label is not None:
                if strip: return label.strip()
                return label
        if fallbackToQname:
            return str(self.qname)
        elif fallbackToXlinkLabel and hasattr(self,"xlinkLabel"):
            return self.xlinkLabel
        else:
            return None

    
    @property
    def propertyView(self):
        return (("QName", self.qname),
                ("id", self.id))
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))

from arelle.ModelValue import qname
    
class ModelComment(etree.CommentBase):
    def _init(self):
        self.isChanged = False
        parent = self.getparent()
        if parent is not None and hasattr(parent, "modelDocument"):
            self.init(parent.modelDocument)

    def init(self, modelDocument):
        self.modelDocument = modelDocument
                    
class ModelProcessingInstruction(etree.PIBase):
    def _init(self):
        pass

class ModelAttribute:
    __slots__ = ("modelElement", "attrTag", "xValid", "xValue", "sValue", "text")
    def __init__(self, modelElement, attrTag, xValid, xValue, sValue, text):
        self.modelElement = modelElement
        self.attrTag = attrTag
        self.xValid = xValid
        self.xValue = xValue
        self.sValue = sValue
        self.text = text

