'''
Created on Oct 5, 2010
Refactored on Jun 11, 2011 to ModelDtsObject, ModelInstanceObject, ModelTestcaseObject

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from lxml import etree
from collections import namedtuple
from arelle import Locale
XmlUtil = None
VALID_NO_CONTENT = None

emptySet = set()

def init(): # init globals
    global XmlUtil, VALID_NO_CONTENT
    if XmlUtil is None:
        from arelle import XmlUtil
        from arelle.XmlValidate import VALID_NO_CONTENT
        
class ModelObject(etree.ElementBase):
    """ModelObjects represent the XML elements within a document, and are implemented as custom 
    lxml proxy objects.  Each modelDocument has a parser with the parser objects in ModelObjectFactory.py, 
    to determine the type of model object to correspond to a proxied lxml XML element.  
    Both static assignment of class, by namespace and local name, and dynamic assignment, by dynamic 
    resolution of element namespace and local name according to the dynamically loaded schemas, are 
    used in the ModelObjectFactory.
    
    ModelObjects are grouped into Python modules to ensure minimal inter-package references 
    (which causes a performance impact).  ModelDtsObjects collects DTS objects (schema and linkbase), 
    ModelInstanceObjects collects instance objects (facts, contexts, dimensions, and units), 
    ModelTestcaseObject collects testcase and variation objects, ModelVersioningObject has specialized 
    objects representing versioning report contents, and ModelRssItem represents the item objects in an 
    RSS feed.   
    
    The ModelObject custom lxml proxy object is implemented as a specialization of etree.ElementBase, 
    and used as the superclass of discovered and created objects in XML-based objects in Arelle.  
    ModelObject is also used as a phantom proxy object, for non-XML objects that are resolved 
    from modelDocument objects, such as the ModelRelationship object.  ModelObjects persistent 
    with their owning ModelDocument, due to reference by modelObject list in modelDocument object.
    
    (The attributes and methods for ModelObject are in addition to those for lxml base class, _ElementBase.)


        .. attribute:: modelDocument        
        Owning ModelDocument object
        
        .. attribute:: modelXbrl
        modelDocument's owning ModelXbrl object
        
        .. attribute:: localName
        W3C DOM localName
        
        .. attribute:: prefixedName
        Prefix by ancestor xmlns and localName of element
        
        .. attribute:: namespaceURI
        W3C DOM namespaceURI (overridden for schema elements)
        
        .. attribute:: elementNamespaceURI
        W3C DOM namespaceURI (not overridden by subclasses)
        
        .. attribute:: qname
        QName of element (overridden for schema elements)
        
        .. attribute:: elementQname
        QName of element (not overridden by subclasses)
        
        .. attribute:: parentQname
        QName of parent element
        
        .. attribute:: id
        Id attribute or None
        
        .. attribute:: elementAttributesTuple
        Python tuple of (tag, value) of specified attributes of element, where tag is in Clark notation
        
        .. attribute:: elementAttributesStr
        String of tag=value[,tag=value...] of specified attributes of element
        
        .. attribute:: xValid
        XmlValidation.py validation state enumeration
        
        .. attribute:: xValue
        PSVI value (for formula processing)
        
        .. attribute:: sValue
        s-equals value (for s-equality)
        
        .. attribute:: xAttributes
        Dict by attrTag of ModelAttribute objects (see below) of specified and default attributes of this element.
    """
    def _init(self):
        self.isChanged = False
        parent = self.getparent()
        if parent is not None and hasattr(parent, "modelDocument"):
            self.init(parent.modelDocument)
            
    def clear(self):
        self.__dict__.clear()  # delete local attributes
        super(ModelObject, self).clear()  # delete children
                   
    def init(self, modelDocument):
        self.modelDocument = modelDocument
        self.objectIndex = len(modelDocument.modelXbrl.modelObjects)
        modelDocument.modelXbrl.modelObjects.append(self)
        id = self.get("id")
        if id:
            modelDocument.idObjects[id] = self
                
    def objectId(self,refId=""):
        """Returns a string surrogate representing the object index of the model document, 
        prepended by the refId string.
        :param refId: A string to prefix the refId for uniqueless (such as to use in tags for tkinter)
        :type refId: str
        """
        return "_{0}_{1}".format(refId, self.objectIndex)
    
    @property
    def modelXbrl(self):
        try:
            return self.modelDocument.modelXbrl
        except AttributeError:
            return None
        
    def attr(self, attrname):
        return self.get(attrname)
    
    @property
    def slottedAttributesNames(self):
        return emptySet

    def setNamespaceLocalName(self):
        ns, sep, self._localName = self.tag.rpartition("}")
        if sep:
            self._namespaceURI = ns[1:]
        else:
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
            self._elementQname = QName(self.prefix, self.namespaceURI, self.localName)
            return self._elementQname
        
    # qname is overridden for concept, type, attribute, and formula parameter, elementQname is unambiguous
    @property
    def elementQname(self):
        try:
            return self._elementQname
        except AttributeError:
            self._elementQname = qname(self)
            return self._elementQname
        
    def vQname(self, validationModelXbrl=None):
        if validationModelXbrl is not None and validationModelXbrl != self.modelXbrl:
            # use physical element declaration in specified modelXbrl
            return self.elementQname
        # use logical qname (inline element's fact qname, or concept's qname)
        return self.qname
             
    
    def elementDeclaration(self, validationModelXbrl=None):
        elementModelXbrl = self.modelXbrl
        if validationModelXbrl is not None and validationModelXbrl != elementModelXbrl: 
            # use physical element declaration in specified modelXbrl
            return validationModelXbrl.qnameConcepts.get(self.elementQname)
        # use logical element declaration in element's own modelXbrl
        return elementModelXbrl.qnameConcepts.get(self.qname)
    
    @property
    def parentQname(self):
        try:
            return self._parentQname
        except AttributeError:
            parentObj = self.getparent()
            self._parentQname = parentObj.elementQname if parentObj is not None else None
            return self._parentQname

    
    @property
    def id(self):
        return self.get("id")
    
    @property
    def stringValue(self):    # "string value" of node, text of all Element descendants
        return ''.join(self._textNodes(recurse=True))  # return text of Element descendants
    
    @property
    def textValue(self):  # xml axis text() differs from string value, no descendant element text
        return ''.join(self._textNodes())  # no text nodes returns ''
    
    def _textNodes(self, recurse=False):
        if self.text and getattr(self,"xValid", 0) != VALID_NO_CONTENT: # skip tuple whitespaces
                yield self.text
        for c in self.iterchildren():
            if recurse and isinstance(c, ModelObject):
                for nestedText in c._textNodes(recurse):
                    yield nestedText
            if c.tail and getattr(self,"xValid", 0) != VALID_NO_CONTENT: # skip tuple whitespaces 
                yield c.tail  # get tail of nested element, comment or processor nodes

    @property
    def document(self):
        return self.modelDocument
    
    def prefixedNameQname(self, prefixedName):
        """Returns ModelValue.QName of prefixedName using this element and its ancestors' xmlns.
        
        :param prefixedName: A prefixed name string
        :type prefixedName: str
        :returns: QName -- the resolved prefixed name, or None if no prefixed name was provided
        """
        if prefixedName:    # passing None would return element qname, not prefixedName None Qname
            return qnameEltPfxName(self, prefixedName)
        else:
            return None
    
    @property
    def elementAttributesTuple(self):
        return tuple((name,value) for name,value in self.items())
    
    @property
    def elementAttributesStr(self):
        return ', '.join(["{0}='{1}'".format(name,value) for name,value in self.items()])

    def resolveUri(self, hrefObject=None, uri=None, dtsModelXbrl=None):
        """Returns the modelObject within modelDocment that resolves a URI based on arguments relative
        to this element
        
        :param hrefObject: an optional tuple of (hrefElement, modelDocument, id), or
        :param uri: An (element scheme pointer), and dtsModelXbrl (both required together if for a multi-instance href)
        :type uri: str
        :param dtsModelXbrl: DTS of href resolution (default is the element's own modelXbrl)
        :type dtsModelXbrl: ModelXbrl
        :returns: ModelObject -- Document node corresponding to the href or resolved uri
        """
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
                for docModelObject in doc.xmlRootElement.iter():
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
                return Locale.rtlString(label, lang=lang)
        if fallbackToQname:
            return str(self.qname)
        elif fallbackToXlinkLabel and hasattr(self,"xlinkLabel"):
            return self.xlinkLabel
        else:
            return None

    def viewText(self, labelrole=None, lang=None):
        return self.stringValue
    
    @property
    def propertyView(self):
        return (("QName", self.elementQname),) + tuple(
                (XmlUtil.clarkNotationToPrefixedName(self, _tag, isAttribute=True), _value)
                for _tag, _value in self.items())
        
    def __repr__(self):
        return ("{0}[{1}, {2} line {3})".format(type(self).__name__, self.objectIndex, self.modelDocument.basename, self.sourceline))

from arelle.ModelValue import qname, qnameEltPfxName, QName
    
class ModelComment(etree.CommentBase):
    """ModelConcept is a custom proxy objects for etree.
    """
    def _init(self):
        self.isChanged = False
        parent = self.getparent()
        if parent is not None and hasattr(parent, "modelDocument"):
            self.init(parent.modelDocument)

    def init(self, modelDocument):
        self.modelDocument = modelDocument
                    
class ModelProcessingInstruction(etree.PIBase):
    """ModelProcessingInstruction is a custom proxy object for etree.
    """
    def _init(self):
        pass

class ModelAttribute:
    """
    .. class:: ModelAttribute(modelElement, attrTag, xValid, xValue, sValue, text)
    
    ModelAttribute is a class of slot-based instances to store PSVI attribute values for each ModelObject
    that has been validated.  It does not correspond to, or proxy, any lxml object.
    
    :param modelElement: owner element of attribute node
    :type modelElement: ModelObject
    :param attrTag: Clark notation attribute tag (from lxml)
    :type attrTag: str
    :param xValid: XmlValidation.py validation state enumeration
    :param xValue: PSVI value (for formula processing)
    :param sValue: s-equals value (for s-equality)
    """
    __slots__ = ("modelElement", "attrTag", "xValid", "xValue", "sValue", "text")
    def __init__(self, modelElement, attrTag, xValid, xValue, sValue, text):
        self.modelElement = modelElement
        self.attrTag = attrTag
        self.xValid = xValid
        self.xValue = xValue
        self.sValue = sValue
        self.text = text

class ObjectPropertyViewWrapper:  # extraProperties = ( (p1, v1), (p2, v2), ... )
    __slots__ = ("modelObject", "extraProperties")
    def __init__(self, modelObject, extraProperties=()):
        self.modelObject = modelObject
        self.extraProperties = extraProperties
        
    @property
    def propertyView(self):
        return self.modelObject.propertyView + self.extraProperties
    
    def __repr__(self):
        return "objectPropertyViewWrapper({}, extraProperties={})".format(self.modelObject, self.extraProperties)

                
