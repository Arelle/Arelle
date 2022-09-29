'''
See COPYRIGHT.md for copyright information.
'''
from arelle import XmlUtil, XbrlConst
from arelle.ModelValue import QName
from arelle.XmlValidate import VALID
from collections import defaultdict
import decimal, os
ModelDocument = None

class PrototypeObject():
    def __init__(self, modelDocument, sourceElement=None):
        self.modelDocument = modelDocument
        self.sourceElement = sourceElement
        self.attributes = {}

    @property
    def sourceline(self):
        return self.sourceElement.sourceline if self.sourceElement is not None else None

    def get(self, key, default=None):
        return self.attributes.get(key, default)

    def itersiblings(self, **kwargs):
        """Method proxy for itersiblings() of lxml arc element"""
        return self.sourceElement.itersiblings(**kwargs) if self.sourceElement is not None else ()

    def getparent(self):
        """(_ElementBase) -- Method proxy for getparent() of lxml arc element"""
        return self.sourceElement.getparent() if self.sourceElement is not None else None

    def iterchildren(self):
        yield from () # no children

    def iterdescendants(self):
        for elt in self.iterchildren():
            yield elt
            for e in elt.iterdescendants():
                yield e

class LinkPrototype(PrototypeObject):      # behaves like a ModelLink for relationship prototyping
    def __init__(self, modelDocument, parent, qname, role, sourceElement=None):
        super(LinkPrototype, self).__init__(modelDocument, sourceElement)
        self._parent = parent
        self.modelXbrl = modelDocument.modelXbrl
        self.qname = self.elementQname = qname
        self.namespaceURI = qname.namespaceURI
        self.localName = qname.localName
        self.role = role
        # children are arc and loc elements or prototypes
        self.childElements = []
        self.text = self.textValue = None
        self.attributes = {"{http://www.w3.org/1999/xlink}type":"extended"}
        if role:
            self.attributes["{http://www.w3.org/1999/xlink}role"] = role
        self.labeledResources = defaultdict(list)

    def clear(self):
        self.__dict__.clear() # dereference here, not an lxml object, don't use superclass clear()

    def __iter__(self):
        return iter(self.childElements)

    def getparent(self):
        return self._parent

    def iterchildren(self):
        return iter(self.childElements)

    def __getitem(self, key):
        return self.attributes[key]

class LocPrototype(PrototypeObject):
    def __init__(self, modelDocument, parent, label, locObject, role=None, sourceElement=None):
        super(LocPrototype, self).__init__(modelDocument, sourceElement)
        self._parent = parent
        self.modelXbrl = modelDocument.modelXbrl
        self.qname = self.elementQname = XbrlConst.qnLinkLoc
        self.namespaceURI = self.qname.namespaceURI
        self.localName = self.qname.localName
        self.text = self.textValue = None
        # children are arc and loc elements or prototypes
        self.attributes = {"{http://www.w3.org/1999/xlink}type":"locator",
                           "{http://www.w3.org/1999/xlink}label":label}
        # add an href if it is a 1.1 id
        if isinstance(locObject,str): # it is an id
            self.attributes["{http://www.w3.org/1999/xlink}href"] = "#" + locObject
        if role:
            self.attributes["{http://www.w3.org/1999/xlink}role"] = role
        self.locObject = locObject

    def clear(self):
        self.__dict__.clear() # dereference here, not an lxml object, don't use superclass clear()

    @property
    def xlinkLabel(self):
        return self.attributes.get("{http://www.w3.org/1999/xlink}label")

    def dereference(self):
        if isinstance(self.locObject,str): # dereference by ID
            return self.modelDocument.idObjects.get(self.locObject,None) # id may not exist
        else: # it's an object pointer
            return self.locObject

    def getparent(self):
        return self._parent

    def get(self, key, default=None):
        return self.attributes.get(key, default)

    def __getitem(self, key):
        return self.attributes[key]

class ArcPrototype(PrototypeObject):
    def __init__(self, modelDocument, parent, qname, fromLabel, toLabel, linkrole, arcrole, order="1", sourceElement=None):
        super(ArcPrototype, self).__init__(modelDocument, sourceElement)
        self._parent = parent
        self.modelXbrl = modelDocument.modelXbrl
        self.qname = self.elementQname = qname
        self.namespaceURI = qname.namespaceURI
        self.localName = qname.localName
        self.linkrole = linkrole
        self.arcrole = arcrole
        self.order = order
        self.text = self.textValue = None
        # children are arc and loc elements or prototypes
        self.attributes = {"{http://www.w3.org/1999/xlink}type":"arc",
                           "{http://www.w3.org/1999/xlink}from": fromLabel,
                           "{http://www.w3.org/1999/xlink}to": toLabel,
                           "{http://www.w3.org/1999/xlink}arcrole": arcrole}
        # must look validated (because it can't really be validated)
        self.xValid = VALID
        self.xValue = self.sValue = None
        self.xAttributes = {}

    @property
    def orderDecimal(self):
        return decimal.Decimal(self.order)

    def clear(self):
        self.__dict__.clear() # dereference here, not an lxml object, don't use superclass clear()

    @property
    def arcElement(self):
        return self.sourceElement if self.sourceElement is not None else None

    def getparent(self):
        return self._parent

    def get(self, key, default=None):
        return self.attributes.get(key, default)

    def items(self):
        return self.attributes.items()

    def __getitem(self, key):
        return self.attributes[key]

class DocumentPrototype():
    def __init__(self, modelXbrl, uri, base=None, referringElement=None, isEntry=False, isDiscovered=False, isIncluded=None, namespace=None, reloadCache=False, **kwargs):
        global ModelDocument
        if ModelDocument is None:
            from arelle import ModelDocument
        self.modelXbrl = modelXbrl
        self.skipDTS = modelXbrl.skipDTS
        self.modelDocument = self
        if referringElement is not None:
            if referringElement.localName == "schemaRef":
                self.type = ModelDocument.Type.SCHEMA
            elif referringElement.localName == "linkbaseRef":
                self.type = ModelDocument.Type.LINKBASE
            else:
                self.type = ModelDocument.Type.UnknownXML
        else:
            self.type = ModelDocument.Type.UnknownXML
        normalizedUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(uri, base)
        self.filepath = modelXbrl.modelManager.cntlr.webCache.getfilename(normalizedUri, filenameOnly=True)
        self.uri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(self.filepath)
        self.basename = os.path.basename(self.filepath)
        self.targetNamespace = None
        self.referencesDocument = {}
        self.hrefObjects = []
        self.schemaLocationElements = set()
        self.referencedNamespaces = set()
        self.inDTS = False
        self.xmlRootElement = None


    def clear(self):
        self.__dict__.clear() # dereference here, not an lxml object, don't use superclass clear()

class PrototypeElementTree(): # equivalent to _ElementTree for parenting root element in non-lxml situations
    def __init__(self, rootElement):
        self.rootElement = rootElement

    def getroot(self):
        return self.rootElement

    def iter(self):
        yield self.rootElement
        for e in self.rootElement.iterdescendants():
            yield e

    def ixIter(self, childOnly=False):
        yield self.rootElement
        if not childOnly:
            for e in self.rootElement.ixIter(childOnly):
                yield e
