'''
BigInstance is an example of a plug-in to both GUI menu and command line/web service
that provides an alternative approach to big instance documents without building a DOM, to save
memory footprint.  SAX is used to parse the big instance.  ModelObjects are specialized by features
for efficiency and to avoid dependency on an underlying DOM.

See COPYRIGHT.md for copyright information.
'''

import xml.sax, io, sys
from collections import defaultdict
from arelle import XbrlConst, XmlUtil, XmlValidate
from arelle.ModelDocument import ModelDocument, Type
from arelle.ModelObject import ModelObject
from arelle.ModelValue import QName
from arelle.ModelInstanceObject import ModelContext, ModelFact, ModelUnit
from arelle.Version import authorLabel, copyrightLabel

class NotInstanceDocumentException(Exception):
    def __init__(self):
        pass

sharedEmptyDict = {}
sharedEmptyList = []

qnIDattr = QName(None, None, "id")
qnContextRefAttr = QName(None, None, "contextRef")
qnUnitRefAttr = QName(None, None, "unitRef")
qnPrecisionAttr = QName(None, None, "precision")
qnDecimalsAttr = QName(None, None, "decimals")

def initModelObject(obj, saxhandler, qname, attrs):
    obj._elementQname = qname
    obj._namespaceURI = qname.namespaceURI
    obj._localName = qname.localName
    obj.modelDocument = saxhandler.modelDocument
    obj._sourceline = saxhandler.saxParser.getLineNumber()
    obj._parent = saxhandler.qnameStack[0] if saxhandler.qnameStack else None
    obj._attrs = dict((('{{{0}}}{1}'.format(*name) if name[0] else name[1]), value)
                      for name, value in attrs.items())
    obj._elementText = ''

class BigInstModelObject(ModelObject):
    def __init__(self, saxhandler, qname, attrs):
        initModelObject(self, saxhandler, qname, attrs)
        super(BigInstModelObject, self).init(saxhandler.modelDocument)

    def getparent(self):
        return self._parent

    def items(self):
        return self._attrs.items()

    def get(self, clarkName):
        return self._attrs.get(clarkName)

    @property
    def sourceline(self):
        return self._sourceline

    @property
    def elementText(self):
        return self._elementText

class BigInstContext(ModelContext):
    def __init__(self, saxhandler, qname, attrs):
        initModelObject(self, saxhandler, qname, attrs)
        super(BigInstContext, self).init(saxhandler.modelDocument)
        self._isStartEndPeriod = self._isInstantPeriod = self._isForeverPeriod = False

    def getparent(self):
        return self._parent

    def items(self):
        return self._attrs.items()

    def get(self, clarkName):
        return self._attrs.get(clarkName)

    @property
    def sourceline(self):
        return self._sourceline

    @property
    def elementText(self):
        return self._elementText

class BigInstUnit(ModelUnit):
    def __init__(self, saxhandler, qname, attrs):
        initModelObject(self, saxhandler, qname, attrs)
        super(BigInstUnit, self).init(saxhandler.modelDocument)
        self._measures = [[],[]]

    def getparent(self):
        return self._parent

    def items(self):
        return self._attrs.items()

    def get(self, clarkName):
        return self._attrs.get(clarkName)

    @property
    def sourceline(self):
        return self._sourceline

    @property
    def elementText(self):
        return self._elementText

class BigInstFact(ModelFact):
    __slots__ = ("_parent", "_concept", "_attrs", "_sourceline", "_elementText",
                 "_context", "_conceptContextUnitLangHash",
                 "_isItem", "_isTuple", "_isNumeric", "_isFraction",
                 "_id", "_decimals", "_precision",
                 "modelDocument", "objectIndex", "modelTupleFacts",
                 "_parentBigInstObj", "_prevObj", "_nextObj",
                 "xValid", "xValue", "sValue", "xAttributes")

    # reimplement ancestorQnames, parentQname

    def __init__(self, saxhandler, qname, attrs):
        self._concept = saxhandler.modelXbrl.qnameConcepts.get(qname) # use the qname object of the DTS, not parser
        self.modelDocument = saxhandler.modelDocument
        self._sourceline = saxhandler.saxParser.getLineNumber()
        self._parent = saxhandler.qnameStack[0] if saxhandler.qnameStack else None
        self._context = self._unit = self._decimals = self._precision = self._id = None
        self.xValid = 0 # unvalidated
        self._attrs = sharedEmptyDict  # try with common shared emptyDict if no separate attributes
        self._parentBigInstObj = self._prevObj = self._nextObj = 1234
        for names, value in attrs.items():
            attrNameURI, attrLocalName= names
            if not attrNameURI:
                if attrLocalName == "id":
                    self._id = value
                elif attrLocalName == "decimals":
                    self._decimals = value
                elif attrLocalName == "precision":
                    self._precision = value
                elif attrLocalName == "contextRef":
                    self._context =  saxhandler.modelXbrl.contexts.get(value, 0)
                    if self._context == 0: # provide dummmy non-none so attribute is present for validation
                        saxhandler.contextRefedFacts[value].append(self)
                elif attrLocalName == "unitRef":
                    self._unit =  saxhandler.modelXbrl.units.get(value, 0)
                    if self._unit == 0:
                        saxhandler.unitRefedFacts[value].append(self)
                else:
                    if not self._attrs: self.attrs = {}  # stop using common shared emptyDict
                    self._attrs[attrLocalName] = value
            else:
                if not self._attrs: self.attrs = {}  # stop using common shared emptyDict
                self._attrs['{{{0}}}{1}'.format(attrNameURI, attrLocalName)] = value
        self._elementText = ''
        self.modelTupleFacts = sharedEmptyList
        super(ModelFact, self).init(saxhandler.modelDocument)

    def getparent(self):
        return self._parent

    def items(self):
        return self._attrs.items()

    def get(self, clarkName):
        return self._attrs.get(clarkName)

    @property
    def sourceline(self):
        return self._sourceline

    @property
    def concept(self):
        return self._concept

    @property
    def qname(self):
        return self._concept.qname

    @property
    def elementQname(self):
        return self._concept.qname

    @property
    def namespaceURI(self):
        return self._concept.qname.namespaceURI

    @property
    def localName(self):
        return self._concept.qname.localName

    @property
    def elementText(self):
        return self._elementText

    @property
    def contextID(self):
        if self._context is not None:
            return self._context.id
        return None

    @property
    def slottedAttributesNames(self):
        names = set()
        if self._id: names.add(qnIDattr)
        if self._context is not None: names.add(qnContextRefAttr)
        if self._unit is not None: names.add(qnUnitRefAttr)
        if self._decimals is not None: names.add(qnDecimalsAttr)
        if self._precision is not None: names.add(qnPrecisionAttr)
        return names

    @property
    def unitID(self):
        if self._unit is not None:
            return self._unit.id
        return None

class saxHandler(xml.sax.ContentHandler):
    def __init__(self, saxParser, modelXbrl, mappedUri, filepath):
        self.saxParser = saxParser
        self.modelXbrl = modelXbrl
        self.mappedUri = mappedUri
        self.filepath = filepath
        self.nsmap = {}
        self.prefixmap = {}
        self.qnameStack = []
        self.currentNamespaceURI = None
        self.modelDocument = None
        self.contextRefedFacts = defaultdict(list)
        self.unitRefedFacts = defaultdict(list)

    def qname(self, prefixedName):
        prefix, sep, localName = prefixedName.rpartition(":")
        return QName(prefix, self.nsmap.get(prefix,None), localName)

    def startPrefixMapping(self, prefix, uri):
        self.nsmap[prefix] = uri
        self.prefixmap[uri] = prefix

    def endPrefixMapping(self, prefix):
        if prefix in self.nsmap:
            self.prefixmap.pop(self.nsmap[prefix], None)
        self.nsmap.pop(prefix, None)

    def startElementNS(self, name, qname, attrs):
        namespaceURI, localName = name
        prefix = self.prefixmap.get(namespaceURI, None)
        thisQname = QName(prefix, namespaceURI, localName)
        if not self.qnameStack:
            if thisQname != XbrlConst.qnXbrliXbrl:  # not an instance document
                self.modelXbrl = None # dereference
                self.saxParser = None
                raise NotInstanceDocumentException()
            if self.modelDocument is None:
                self.modelDocument = ModelDocument(self.modelXbrl, Type.INSTANCE, self.mappedUri, self.filepath, None)
            parentQname = None
        elif self.qnameStack:
            parentElement = self.qnameStack[0]
            parentQname = parentElement.elementQname
        if namespaceURI in (XbrlConst.xbrli, XbrlConst.link):
            if parentQname == XbrlConst.qnXbrliContext:
                if localName == "identifier":
                    parentElement._entityIdentifier = (attrs.get(None,"scheme"), "")
                elif localName == "forever":
                    parentElement._isForeverPeriod = True
            else:
                if localName == "context":
                    thisModelObject = BigInstContext(self, thisQname, attrs)
                    self.modelXbrl.contexts[thisModelObject.id] = thisModelObject
                elif localName == "unit":
                    thisModelObject = BigInstUnit(self, thisQname, attrs)
                    self.modelXbrl.units[thisModelObject.id] = thisModelObject
                else:
                    thisModelObject = BigInstModelObject(self, thisQname, attrs)
                if localName in ("schemaRef", "linkbaseRef"):
                    self.modelDocument.discoverHref(thisModelObject)
                else:
                    self.qnameStack.insert(0, thisModelObject)
        elif parentQname:
            if parentQname == XbrlConst.qnXbrliContext:
                if namespaceURI == XbrlConst.xbrldi:
                    if localName == "explicitMember":
                        self.dimensionPrefixedName = attrs.get(None,"dimension")
            else: # might be a fact
                thisModelObject = BigInstFact(self, thisQname, attrs)
                if len(self.qnameStack) > 1:
                    tuple = self.qnameStack[0]
                    if not tuple.modelTupleFacts:
                        tuple.modelTupleFacts = [] # allocate unshared list
                    tuple.modelTupleFacts.append(thisModelObject)
                else:
                    self.modelXbrl.facts.append(thisModelObject)
                self.qnameStack.insert(0, thisModelObject)  # build content
        self.currentNamespaceURI = namespaceURI
        self.currentLocalName = localName

    def endElementNS(self, name, qname):
        thisQname = QName(None, *name)
        if self.qnameStack and self.qnameStack[0].elementQname == thisQname:
            elt = self.qnameStack.pop(0)
            if elt.namespaceURI == XbrlConst.xbrli:
                if elt.localName == "unit":
                    elt._measures = (sorted(elt._measures[0]), sorted(elt._measures[1]))
                    if elt.id in self.unitRefedFacts:
                        for fact in self.unitRefedFacts[elt.id]:
                            fact._unit = elt
                        del self.unitRefedFacts[elt.id]
                elif elt.localName == "context":
                    if elt.id in self.contextRefedFacts:
                        for fact in self.contextRefedFacts[elt.id]:
                            fact._context = elt
                        del self.contextRefedFacts[elt.id]
            self.currentNamespaceURI = None
            self.currentLocalName = None
            XmlValidate.validate(self.modelXbrl, elt, recurse=False)
            pass

    def characters(self, content):
        if self.currentNamespaceURI:
            elt = self.qnameStack[0]
            if self.currentNamespaceURI == XbrlConst.xbrli:
                s = content.strip()
                if s:
                    if self.currentLocalName == "identifier":
                        elt._entityIdentifier = (elt._entityIdentifier[0], elt._entityIdentifier[1] + content)
                    elif self.currentLocalName == "startDate":
                        elt._startDatetime = XmlUtil.datetimeValue(s)
                        elt._isStartEndPeriod = True
                    elif self.currentLocalName == "endDate":
                        elt._endDatetime = XmlUtil.datetimeValue(s, addOneDay=True)
                        elt._isStartEndPeriod = True
                    elif self.currentLocalName == "instant":
                        elt._endDatetime = elt._instantDatetime = XmlUtil.datetimeValue(s, addOneDay=True)
                        elt._isInstantPeriod = True
                    elif self.currentLocalName == "measure":
                        m = self.qname(content)
                        parentEltLocalName = self.qnameStack[1].localName
                        if parentEltLocalName == "unit":
                            self.qnameStack[1]._measures[0].append(m)
                        elif parentEltLocalName == "unitNumerator" and self.qnameStack[2].localName == "unit":
                            self.qnameStack[2]._measures[0].append(m)
                        elif parentEltLocalName == "unitDenominator" and self.qnameStack[2].localName == "unit":
                            self.qnameStack[2]._measures[1].append(m)
            elif self.currentNamespaceURI == XbrlConst.xbrldi:
                s = content.strip()
                if s:
                    if self.currentLocalName == "explicitMember" and self.dimensionPrefixedName:
                        dimQname = self.qname(self.currentLocalName)
                        memQname = self.qname(s)
                        dimConcept = self.modelXbrl.qnameConcepts.get(dimQname)
                        memConcept = self.modelXbrl.qnameConcepts.get(memQname)
            elif elt is not None:
                elt._elementText += content

    def skippedEntity(self, name):
        print ("skipped entity={0}".format(name))

class BigInstDocument:
    def __init__(self, file, xbrlParser, saxParser, saxHandler):
        self.file = file
        self.xbrlParser = xbrlParser
        self.saxParser = saxParser
        self.saxHandler = saxHandler

    def getroot(self):
        return self.saxHandler.qnameStack[-1]

def bigInstLoader(modelXbrl, file, mappedUri, filepath):
    saxParser = xml.sax.make_parser()
    saxParser.setFeature("http://xml.org/sax/features/namespaces", True)
    saxParser.setFeature("http://xml.org/sax/features/external-general-entities", True)
    saxhandler = saxHandler(saxParser, modelXbrl, mappedUri, filepath)
    saxParser.setContentHandler(saxhandler)
    try:
        saxParser.parse(file)
        return saxhandler.modelDocument
    except NotInstanceDocumentException:
        file.seek(0,io.SEEK_SET) # allow reparsing
        return None

'''
   Do not use _( ) in pluginInfo itself (it is applied later, after loading
'''

__pluginInfo__ = {
    'name': 'Big Instance Loader',
    'version': '0.9',
    'description': "This plug-in loads big XBRL instances without building a DOM in memory.  "
                    "SAX parses XBRL directly into an object model without a DOM.  ",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'ModelDocument.CustomLoader': bigInstLoader,
}
