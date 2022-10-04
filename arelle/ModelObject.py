'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Generator, Optional, cast
from lxml import etree
from arelle import Locale
from arelle.ModelValue import qname, qnameEltPfxName, QName

if TYPE_CHECKING:
    from arelle.ModelDocument import ModelDocument
    from arelle.ModelXbrl import ModelXbrl
    from arelle.ModelDtsObject import ModelConcept
    from arelle.ModelValue import AnyURI
    from arelle.ModelDtsObject import ModelLink
    from arelle.ModelDtsObject import ModelLocator
    from arelle.ModelDtsObject import ModelResource
    from arelle.ModelInstanceObject import ModelInlineXbrliXbrl
    from arelle.ModelInstanceObject import ModelInlineFootnote
    from arelle.ModelInstanceObject import ModelInlineFact
    from arelle.ModelInstanceObject import ModelDimensionValue

XmlUtil: Any = None
VALID_NO_CONTENT = None

emptySet: set[Any] = set()

def init() -> None: # init globals
    global XmlUtil, VALID_NO_CONTENT
    if XmlUtil is None:
        from arelle import XmlUtil
        from arelle.XmlValidate import VALID_NO_CONTENT  # type: ignore[misc]

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

    _elementQname: QName
    _parentQname: QName | None
    _elementSequence: int
    _namespaceURI: str | None
    _hashSEqual: int
    _hashXpathEqual: int
    sValue = str
    xValue = Any # this can be any thing
    xlinkLabel: str

    def _init(self) -> None:
        self.isChanged = False
        parent = self.getparent()
        if parent is not None and hasattr(parent, "modelDocument"):
            self.init(parent.modelDocument) # type: ignore[attr-defined]

    def clear(self) -> None:
        self.__dict__.clear()  # delete local attributes
        super(ModelObject, self).clear()  # delete children

    def init(self, modelDocument: ModelDocument) -> None:
        self.modelDocument = modelDocument
        self.objectIndex = len(modelDocument.modelXbrl.modelObjects)
        modelDocument.modelXbrl.modelObjects.append(self)
        id = self.get("id")
        if id:
            modelDocument.idObjects[id] = self

    def objectId(self, refId: str = "") -> str:
        """Returns a string surrogate representing the object index of the model document,
        prepended by the refId string.
        :param refId: A string to prefix the refId for uniqueless (such as to use in tags for tkinter)
        :type refId: str
        """
        return "_{0}_{1}".format(refId, self.objectIndex)

    @property
    def modelXbrl(self) -> ModelXbrl | None:
        try:
            return cast("ModelXbrl", self.modelDocument.modelXbrl)
        except AttributeError:
            return None

    def attr(self, attrname: str) -> str | None:
        return self.get(attrname)

    @property
    def slottedAttributesNames(self) -> set[Any]:
        return emptySet

    def setNamespaceLocalName(self) -> None:
        ns, sep, self._localName = self.tag.rpartition("}")
        if sep:
            self._namespaceURI = ns[1:]
        else:
            self._namespaceURI = None
        if self.prefix:
            self._prefixedName = self.prefix + ":" + self.localName
        else:
            self._prefixedName = self.localName

    def getStripped(self, attrName: str) -> str | None:
        attrValue = self.get(attrName)
        if attrValue is not None:
            return attrValue.strip()
        return attrValue

    @property
    def localName(self) -> str:
        try:
            return self._localName
        except AttributeError:
            self.setNamespaceLocalName()
            return self._localName

    @property
    def prefixedName(self) -> str:
        try:
            return self._prefixedName
        except AttributeError:
            self.setNamespaceLocalName()
            return self._prefixedName

    @property
    def namespaceURI(self) -> str | None:
        try:
            return self._namespaceURI
        except AttributeError:
            self.setNamespaceLocalName()
            return self._namespaceURI

    @property
    def elementNamespaceURI(self) -> str | None:  # works also for concept elements
        try:
            return self._namespaceURI
        except AttributeError:
            self.setNamespaceLocalName()
            return self._namespaceURI

    # qname of concept of fact or element for all but concept element, type, attr, param, override to the name parameter
    @property
    def qname(self) -> QName:
        try:
            return self._elementQname
        except AttributeError:
            self._elementQname = QName(self.prefix, self.namespaceURI, self.localName)
            return self._elementQname

    # qname is overridden for concept, type, attribute, and formula parameter, elementQname is unambiguous
    @property
    def elementQname(self) -> QName:
        try:
            return self._elementQname
        except AttributeError:
            self._elementQname = qname(self)
            return self._elementQname

    def vQname(self, validationModelXbrl: ModelXbrl | None = None) -> QName:
        if validationModelXbrl is not None and validationModelXbrl != self.modelXbrl:
            # use physical element declaration in specified modelXbrl
            return self.elementQname
        # use logical qname (inline element's fact qname, or concept's qname)
        return self.qname

    def elementDeclaration(self, validationModelXbrl: ModelXbrl | None = None) -> ModelConcept | None:
        elementModelXbrl = self.modelXbrl
        if validationModelXbrl is not None and validationModelXbrl != elementModelXbrl:
            # use physical element declaration in specified modelXbrl
            return validationModelXbrl.qnameConcepts.get(self.elementQname)
        # use logical element declaration in element's own modelXbrl
        assert elementModelXbrl is not None
        return elementModelXbrl.qnameConcepts.get(self.qname)

    @property
    def elementSequence(self) -> int:
        # ordinal position among siblings, 1 is first position
        try:
            return self._elementSequence
        except AttributeError:
            self._elementSequence = 1 + sum(isinstance(s, etree.ElementBase) for s in self.itersiblings(preceding=True))
            return self._elementSequence

    @property
    def parentQname(self) -> QName | None:
        try:
            return self._parentQname
        except AttributeError:
            parentObj = self.getparent()
            self._parentQname = parentObj.elementQname if parentObj is not None else None # type: ignore[attr-defined]
            return self._parentQname


    @property
    def id(self) -> str | None:
        return self.get("id")

    @property
    def stringValue(self) -> str:    # "string value" of node, text of all Element descendants
        return ''.join(self._textNodes(recurse=True))  # return text of Element descendants

    @property
    def textValue(self) -> str:  # xml axis text() differs from string value, no descendant element text
        return ''.join(self._textNodes())  # no text nodes returns ''

    def _textNodes(self, recurse:bool = False) ->  Generator[str | Any, None, None]:
        if self.text and getattr(self,"xValid", 0) != VALID_NO_CONTENT: # skip tuple whitespaces
                yield self.text
        for c in self.iterchildren():
            if recurse and isinstance(c, ModelObject):
                for nestedText in c._textNodes(recurse):
                    yield nestedText
            if c.tail and getattr(self,"xValid", 0) != VALID_NO_CONTENT: # skip tuple whitespaces
                yield c.tail  # get tail of nested element, comment or processor nodes

    @property
    def document(self) -> ModelDocument:
        return self.modelDocument

    def prefixedNameQname(self, prefixedName: str | None) -> QName | None:
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
    def elementAttributesTuple(self) -> tuple[Any, ...]:
        return tuple((name,value) for name,value in self.items())

    @property
    def elementAttributesStr(self) -> str:
        # Note 2022-09-09:
        # Mypy raises the following error. Not sure why this is the case, this returns a str not binary data?
        # On Python 3 formatting "b'abc'" with "{}" produces "b'abc'", not "abc"; use "{!r}" if this is desired behavior
        return ', '.join(["{0}='{1}'".format(name, value) for name, value in self.items()]) # type: ignore[str-bytes-safe]

    def resolveUri(
        self,
        hrefObject: tuple[str, ModelDocument, str] | None = None,
        uri: str | None = None,
        dtsModelXbrl: ModelXbrl | None = None,
    ) -> ModelObject | None:
        """Returns the modelObject within modelDocment that resolves a URI based on arguments relative
        to this element

        :param hrefObject: an optional tuple of (hrefElement, modelDocument, id), or
        :param uri: An (element scheme pointer), and dtsModelXbrl (both required together if for a multi-instance href)
        :type uri: str
        :param dtsModelXbrl: DTS of href resolution (default is the element's own modelXbrl)
        :type dtsModelXbrl: ModelXbrl
        :returns: ModelObject -- Document node corresponding to the href or resolved uri
        """
        from arelle.ModelDocument import ModelDocument
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
                assert self.modelXbrl is not None
                normalizedUrl = self.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(
                                   url,
                                   self.modelDocument.baseForElement(self)) # type: ignore[no-untyped-call]

                assert dtsModelXbrl is not None
                doc = dtsModelXbrl.urlDocs.get(normalizedUrl)
        if isinstance(doc, ModelDocument):
            if id is None:
                return cast(ModelObject, doc)
            elif id in doc.idObjects:
                return cast(ModelObject, doc.idObjects[id])
            else:
                xpointedElement = XmlUtil.xpointerElement(doc,id)
                # find element
                for docModelObject in doc.xmlRootElement.iter():
                    if docModelObject == xpointedElement:
                        doc.idObjects[id] = docModelObject # cache for reuse
                        return cast(ModelObject, docModelObject)
        return None

    def genLabel(
        self,
        role: str | None = None,
        fallbackToQname: bool = False,
        fallbackToXlinkLabel: bool = False,
        lang: str | None = None,
        strip: bool = False,
        linkrole: str | None = None,
    ) -> str | None:
        from arelle import XbrlConst
        if role is None: role = XbrlConst.genStandardLabel
        if role == XbrlConst.conceptNameLabelRole: return str(self.qname)
        assert self.modelXbrl is not None
        labelsRelationshipSet = self.modelXbrl.relationshipSet(XbrlConst.elementLabel,linkrole)
        if labelsRelationshipSet:
            label = labelsRelationshipSet.label(self, role, lang) # type: ignore[no-untyped-call]
            if label is not None:
                if strip: return cast(str, label.strip())
                return Locale.rtlString(label, lang=lang)
        if fallbackToQname:
            return str(self.qname)
        elif fallbackToXlinkLabel and hasattr(self,"xlinkLabel"):
            return self.xlinkLabel
        else:
            return None

    def viewText(self, labelrole: str | None = None, lang: str | None = None) -> str:
        return self.stringValue

    @property
    def propertyView(self) -> tuple[Any, ...]:
        return (("QName", self.elementQname),) + tuple(
                (XmlUtil.clarkNotationToPrefixedName(self, _tag, isAttribute=True), _value)
                for _tag, _value in self.items())

    def __repr__(self) -> str:
        return ("{0}[{1}, {2} line {3})".format(type(self).__name__, self.objectIndex, self.modelDocument.basename, self.sourceline))

class ModelComment(etree.CommentBase): # type: ignore[misc]
    """ModelConcept is a custom proxy objects for etree.
    """
    def _init(self) -> None:
        self.isChanged = False
        parent = self.getparent()
        if parent is not None and hasattr(parent, "modelDocument"):
            self.init(parent.modelDocument)

    def init(self, modelDocument: ModelDocument) -> None:
        self.modelDocument = modelDocument

class ModelProcessingInstruction(etree.PIBase): # type: ignore[misc]
    """ModelProcessingInstruction is a custom proxy object for etree.
    """
    def _init(self) -> None:
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
    def __init__(
        self,
        modelElement: ModelObject
        | ModelLink
        | ModelLocator
        | ModelResource
        | ModelInlineXbrliXbrl
        | ModelInlineFact
        | ModelDimensionValue
        | ModelInlineFootnote,
        attrTag: str,
        xValid: int,
        xValue: QName | AnyURI | int | str | None,
        sValue: str | None,
        text: str,
    ):
        self.modelElement = modelElement
        self.attrTag = attrTag
        self.xValid = xValid
        self.xValue = xValue
        self.sValue = sValue
        self.text = text

class ObjectPropertyViewWrapper:  # extraProperties = ( (p1, v1), (p2, v2), ... )
    __slots__ = ("modelObject", "extraProperties")
    def __init__(self, modelObject: ModelObject, extraProperties: tuple[Any, ...] = ()) -> None:
        self.modelObject = modelObject
        self.extraProperties = extraProperties

    @property
    def propertyView(self) -> tuple[Any, ...]:
        return self.modelObject.propertyView + self.extraProperties

    def __repr__(self) -> str:
        return "objectPropertyViewWrapper({}, extraProperties={})".format(self.modelObject, self.extraProperties)
