"""
:mod:`arelle.ModelDtsObjuect`
~~~~~~~~~~~~~~~~~~~

.. module:: arelle.ModelDtsObject
   :copyright: See COPYRIGHT.md for copyright information.
   :license: Apache-2.
   :synopsis: This module contains DTS-specialized ModelObject classes: ModelRoleType (role and arcrole types), ModelSchemaObject (parent class for top-level named schema element, attribute, attribute groups, etc), ModelConcept (xs:elements that may be concepts, typed dimension elements, or just plain XML definitions), ModelAttribute (xs:attribute), ModelAttributeGroup, ModelType (both top level named and anonymous simple and complex types), ModelEnumeration, ModelLink (xlink link elements), ModelResource (xlink resource elements), ModelLocator (subclass of ModelResource for xlink locators), and ModelRelationship (not an lxml proxy object, but a resolved relationship that reflects an effective arc between one source and one target).

XBRL processing requires element-level access to schema elements.  Traditional XML processors, such as
lxml (based on libxml), and Xerces (not available in the Python environment), provide opaque schema
models that cannot be used by an XML processor.  Arelle implements its own elment, attribute, and
type processing, in order to provide PSVI-validated element and attribute contents, and in order to
access XBRL features that would otherwise be inaccessible in the XML library opaque schema models.

ModelConcept represents a schema element, regardless whether an XBRL item or tuple, or non-concept
schema element.  The common XBRL and schema element attributes are provided by Python properties,
cached when needed for efficiency, somewhat isolating from the XML level implementation.

There is thought that a future SQL-based implementation may be able to utilize ModelObject proxy
objects to interface to SQL-obtained data.

ModelType represents an anonymous or explicit element type.  It includes methods that determine
the base XBRL type (such as monetaryItemType), the base XML type (such as decimal), substitution
group chains, facits, and attributes.

ModelAttributeGroup and ModelAttribute provide sufficient mechanism to identify element attributes,
their types, and their default or fixed values.

There is also an inherently different model, modelRelationshipSet, which represents an individual
base or dimensional-relationship set, or a collection of them (such as labels independent of
extended link role), based on the semantics of XLink arcs.

PSVI-validated instance data are determined during loading for instance documents, and on demand
for any other objects (such as when formula operations may access linkbase contents and need
PSVI-validated contents of some linkbase elements).  These validated items are added to the
ModelObject lxml custom proxy objects.

Linkbase objects include modelLink, representing extended link objects, modelResource,
representing resource objects, and modelRelationship, which is not a lxml proxy object, but
represents a resolved and effective arc in a relationship set.

ModelRelationshipSets are populated on demand according to specific or general characteristics.
A relationship set can be a fully-specified base set, including arcrole, linkrole, link element
qname, and arc element qname.  However by not specifying linkrole, link, or arc, a composite
relationship set can be produced for an arcrole accumulating relationships across all extended
link linkroles that have contributing arcs, which may be needed in building indexing or graphical
topology top levels.

Relationship sets for dimensional arcroles will honor and traverse targetrole attributes across
linkroles.  There is a pseudo-arcrole for dimensions that allows accumulating all dimensional
relationships regardless of arcrole, which is useful for constructing certain graphic tree views.

Relationship sets for table linkbases likewise have a pseudo-arcrole to accumulate all table
relationships regardless of arcrole, for the same purpose.

Relationship sets can identify ineffective arcroles, which is a requirement for SEC and GFM
validation.
"""
from __future__ import annotations
from collections import defaultdict
import os, sys
from typing import TYPE_CHECKING, Any, cast
from lxml import etree
import decimal
from arelle import (XmlUtil, XbrlConst, XbrlUtil, UrlUtil, Locale, ModelValue, XmlValidate)
from arelle.XmlValidate import UNVALIDATED, VALID
from arelle.ModelObject import ModelObject
from arelle.ModelValue import AnyURI, QName, TypeXValue
from lxml.etree import _Element

if TYPE_CHECKING:
    from arelle.ModelDocument import ModelDocument

ModelFact = None

class ModelRoleType(ModelObject):
    """
    .. class:: ModelRoleType(modelDocument)

    ModelRoleType represents both role type and arcrole type definitions

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """

    _definition: str | None
    _maxOccurs: int
    _minOccurs: int
    _tableCode: str | None
    _typeQname: QName
    _usedOns: set[TypeXValue]

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelRoleType, self).init(modelDocument)

    @property
    def isArcrole(self) -> bool:
        """(bool) -- True if ModelRoleType declares an arcrole type"""
        return self.localName == "arcroleType"

    @property
    def roleURI(self) -> str | None:
        """(str) -- Value of roleURI attribute"""
        return self.get("roleURI")

    @property
    def arcroleURI(self) -> str | None:
        """(str) -- Value of arcroleURI attribute"""
        return self.get("arcroleURI")

    @property
    def cyclesAllowed(self) -> str | None:
        """(str) -- Value of cyclesAllowed attribute"""
        return self.get("cyclesAllowed")

    @property
    def definition(self) -> str | None:
        """(str) -- Text of child definition element (stripped)"""
        try:
            return cast(str, self._definition)
        except AttributeError:
            definition = XmlUtil.child(self, XbrlConst.link, "definition")
            self._definition = definition.textValue.strip() if definition is not None else None
            return self._definition

    @property
    def definitionNotStripped(self) -> str | None:
        """(str) -- Text of child definition element (not stripped)"""
        definition = XmlUtil.child(self, XbrlConst.link, "definition")
        return definition.textValue if definition is not None else None

    @property
    def usedOns(self) -> set[TypeXValue]:
        """( {QName} ) -- Set of PSVI QNames of descendant usedOn elements"""
        try:
            return self._usedOns
        except AttributeError:
            XmlValidate.validate(self.modelXbrl, self)
            self._usedOns = set(usedOn.xValue
                                for usedOn in self.iterdescendants("{http://www.xbrl.org/2003/linkbase}usedOn")
                                if isinstance(usedOn,ModelObject))
            return self._usedOns

    @property
    def tableCode(self) -> str | None:
        """ table code from structural model for presentable table by ELR"""
        if self.isArcrole:
            return None
        try:
            return self._tableCode
        except AttributeError:
            from arelle import TableStructure
            TableStructure.evaluateRoleTypesTableCodes(self.modelXbrl)
            return self._tableCode

    @property
    def propertyView(self) -> tuple[Any, ...]:
        if self.isArcrole:
            return (("arcrole Uri", self.arcroleURI),
                    ("definition", self.definition),
                    ("used on", self.usedOns),
                    ("defined in", self.modelDocument.uri))
        else:
            return (("role Uri", self.roleURI),
                    ("definition", self.definition),
                    ("used on", self.usedOns),
                    ("defined in", self.modelDocument.uri))

    def __repr__(self) -> str:
        return ("{0}[{1}, uri: {2}, definition: {3}, {4} line {5}])"
                .format('modelArcroleType' if self.isArcrole else 'modelRoleType',
                        self.objectIndex,
                        self.arcroleURI if self.isArcrole else self.roleURI,
                        self.definition,
                        self.modelDocument.basename, self.sourceline))

    @property
    def viewConcept(self) -> ModelRoleType:  # concept trees view roles as themselves
        return self

class ModelNamableTerm(ModelObject):
    """
    .. class:: ModelNamableTerm(modelDocument)

    Particle Model namable term (can have @name attribute)

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """

    _attributeWildcards: set[_Element]
    _defaultAttributeQnames: set[QName]
    _xsdQname: QName | None
    isQualifiedForm: bool
    namespaceURI: str

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelNamableTerm, self).init(modelDocument)

    @property
    def name(self) -> str | None:
        return self.getStripped("name")

    @property
    def qname(self) -> QName:
        try:
            return cast(QName, self._xsdQname)
        except AttributeError:
            name = self.name
            if self.name:
                if self.parentQname == XbrlConst.qnXsdSchema or self.isQualifiedForm:
                #if self.isQualifiedForm:
                    prefix = XmlUtil.xmlnsprefix(self.modelDocument.xmlRootElement,self.modelDocument.targetNamespace)
                    self._xsdQname = ModelValue.QName(prefix, self.modelDocument.targetNamespace, name)
                else:
                    self._xsdQname = ModelValue.QName(None, None, name)
            else:
                self._xsdQname = None
            return self._xsdQname

    @property
    def isGlobalDeclaration(self) -> bool:
        parent = self.getparent()
        assert parent is not None
        return parent.namespaceURI == XbrlConst.xsd and parent.localName == "schema"  # type: ignore[attr-defined]

    def schemaNameQname(self, prefixedName: str, isQualifiedForm: bool = True, prefixException: type[Exception] | None = None) -> QName | None:
        """Returns ModelValue.QName of prefixedName using this element and its ancestors' xmlns.

        :param prefixedName: A prefixed name string
        :type prefixedName: str
        :returns: QName -- the resolved prefixed name, or None if no prefixed name was provided
        """
        if prefixedName:    # passing None would return element qname, not prefixedName None Qname
            qn = ModelValue.qnameEltPfxName(self, prefixedName, prefixException=prefixException)
            # may be in an included file with no target namespace
            # a ref to local attribute or element wihich is qualified MAY need to assume targetNamespace
            if qn and not qn.namespaceURI and self.modelDocument.noTargetNamespace and not isQualifiedForm:
                qn = ModelValue.qname(self.modelDocument.targetNamespace, prefixedName)
            return qn
        else:
            return None
class ParticlesList(list):
    """List of particles which can provide string representation of contained particles"""
    def __repr__(self) -> str:
        particlesList = []
        for particle in self:
            if isinstance(particle, ModelConcept):
                mdlObj = particle.dereference()
                if isinstance(mdlObj, ModelObject):
                    p = str(mdlObj.qname)
                else:
                    p = 'None'
            elif isinstance(particle, ModelAny):
                p = "any"
            else:
                p = "{0}({1})".format(particle.localName, getattr(particle.dereference(), "particles", ""))
            particlesList.append(p + ("" if particle.minOccurs == particle.maxOccurs == 1 else
                                      "{{{0}:{1}}}".format(particle.minOccursStr, particle.maxOccursStr)))
        return ", ".join(particlesList)

class ModelParticle():

    _maxOccurs: int
    _minOccurs: int

    """Represents a particle (for multi-inheritance subclasses of particles)"""
    def addToParticles(self) -> None:
        """Finds particle parent (in xml element ancestry) and appends self to parent particlesList"""
        parent = self.getparent()  # type: ignore[attr-defined]
        while parent is not None:  # find a parent with particles list
            try:
                parent.particlesList.append(self)
                break
            except AttributeError:
                parent = parent.getparent()

    @property
    def maxOccurs(self) -> int:
        """(int) -- Value of maxOccurs attribute, sys.maxsize of unbounded, or 1 if absent"""
        try:
            return self._maxOccurs
        except AttributeError:
            m = self.get("maxOccurs")  # type: ignore[attr-defined]
            if m:
                if m == "unbounded":
                    self._maxOccurs = sys.maxsize
                else:
                    self._maxOccurs = int(m)
                    if self._maxOccurs < 0:
                        raise ValueError(_("maxOccurs must be positive").format(m))
            else:
                self._maxOccurs = 1
            return self._maxOccurs

    @property
    def maxOccursStr(self) -> str:
        """(str) -- String value of maxOccurs attribute"""
        if self.maxOccurs == sys.maxsize:
            return "unbounded"
        return str(self.maxOccurs)

    @property
    def minOccurs(self) -> int:
        """(int) -- Value of minOccurs attribute or 1 if absent"""
        try:
            return self._minOccurs
        except AttributeError:
            m = self.get("minOccurs")  # type: ignore[attr-defined]
            if m:
                self._minOccurs = int(m)
                if self._minOccurs < 0:
                    raise ValueError(_("minOccurs must be positive").format(m))
            else:
                self._minOccurs = 1
            return self._minOccurs

    @property
    def minOccursStr(self) -> str:
        """(str) -- String value of minOccurs attribute"""
        return str(self.minOccurs)

anonymousTypeSuffix = "@anonymousType"

class ModelConcept(ModelNamableTerm, ModelParticle):
    """
    .. class:: ModelConcept(modelDocument)

    Particle Model element term

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """

    _baseXbrliType: str | None
    _baseXbrliTypeQname: QName | None
    _baseXsdType: str
    _enumDomain: ModelConcept | None
    _isDimensionItem: bool
    _isEnum: bool
    _isEnumDomainUsable: bool
    _isFraction: bool
    _isHypercubeItem: bool
    _isInteger: bool
    _isItem: bool
    _isLanguage: bool
    _isMonetary: bool
    _isNumeric: bool
    _typedDomainElement: bool
    _isLinkPart: bool
    _isPrimaryItem: bool
    _isShares: bool
    _isTuple: bool
    _isTypedDimension: bool
    _type: ModelType | None
    _substitutionGroupQname: QName | None
    _typeQname: QName | None

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelConcept, self).init(modelDocument)

        assert self.modelXbrl is not None

        if self.name:  # don't index elements with ref and no name
            self.modelXbrl.qnameConcepts[self.qname] = self
            if not self.isQualifiedForm:
                self.modelXbrl.qnameConcepts[ModelValue.QName(None, None, self.name)] = self
            self.modelXbrl.nameConcepts[self.name].append(self)
        if not self.isGlobalDeclaration:
            self.addToParticles()
        self._baseXsdAttrType = {}

    @property
    def abstract(self) -> str:
        """(str) -- Value of abstract attribute or 'false' if absent"""
        return self.get("abstract", 'false')

    @property
    def isAbstract(self) -> bool:
        """(bool) -- True if abstract"""
        return self.abstract in ("true", "1")

    @property
    def periodType(self) -> str | None:
        """(str) -- Value of periodType attribute"""
        return self.get("{http://www.xbrl.org/2003/instance}periodType")

    @property
    def balance(self) -> str | None:
        """(str) -- Value of balance attribute"""
        return self.get("{http://www.xbrl.org/2003/instance}balance")

    @property
    def typeQname(self) -> QName | None:
        """(QName) -- Value of type attribute, if any, or if type contains an annonymously-named
        type definition (as sub-elements), then QName formed of element QName with anonymousTypeSuffix
        appended to localName.  If neither type attribute or nested type definition, then attempts
        to get type definition in turn from substitution group element."""
        try:
            return self._typeQname
        except AttributeError:
            if self.get("type"):
                self._typeQname = self.schemaNameQname(self.get("type"))
            else:
                # check if anonymous type exists (clark qname tag + suffix)
                qn = self.qname
                if qn is not None:
                    typeQname = ModelValue.QName(qn.prefix, qn.namespaceURI, qn.localName + anonymousTypeSuffix)
                else:
                    typeQname = None

                assert self.modelXbrl is not None

                if typeQname in self.modelXbrl.qnameTypes:
                    self._typeQname = typeQname
                else:
                    # try substitution group for type
                    subs = self.substitutionGroup
                    if subs is not None:
                        self._typeQname = subs.typeQname
                    else:
                        self._typeQname =  XbrlConst.qnXsdDefaultType
            return self._typeQname

    @property
    def niceType(self) -> str | None:
        """Provides a type name suited for user interfaces: hypercubes as Table, dimensions as Axis,
        types ending in ItemType have ItemType removed and first letter capitalized (e.g.,
        stringItemType as String).  Otherwise returns the type's localName portion.
        """
        if self.isHypercubeItem: return "Table"
        if self.isDimensionItem: return "Axis"
        if self.typeQname:
            if self.typeQname.localName.endswith("ItemType"):
                return self.typeQname.localName[0].upper() + self.typeQname.localName[1:-8]
            return self.typeQname.localName
        return None

    @property
    def baseXsdType(self) -> str:
        """(str) -- Value of localname of type (e.g., monetary for monetaryItemType)"""
        try:
            return self._baseXsdType
        except AttributeError:
            typeqname = self.typeQname
            if typeqname is not None and typeqname.namespaceURI == XbrlConst.xsd:
                self._baseXsdType = typeqname.localName
            else:
                type = self.type
                self._baseXsdType = type.baseXsdType if type is not None else "anyType"
            return self._baseXsdType

    @property
    def facets(self) -> dict[str, TypeXValue]:
        """(dict) -- Facets declared for element type"""
        return self.type.facets if self.type is not None else None

    ''' unused, remove???
    def baseXsdAttrType(self,attrName):
        try:
            return self._baseXsdAttrType[attrName]
        except KeyError:
            if self.type is not None:
                attrType = self.type.baseXsdAttrType(attrName)
            else:
                attrType = "anyType"
            self._baseXsdAttrType[attrName] = attrType
            return attrType
    '''

    @property
    def baseXbrliType(self) -> str:
        """(str) -- Attempts to return the base xsd type localName that this concept's type
        is derived from.  If not determinable anyType is returned.  E.g., for monetaryItemType,
        decimal is returned."""
        try:
            return cast(str, self._baseXbrliType)
        except AttributeError:
            typeqname = self.typeQname
            if typeqname is not None and typeqname.namespaceURI == XbrlConst.xbrli:
                self._baseXbrliType =  typeqname.localName
            else:
                self._baseXbrliType = self.type.baseXbrliType if self.type is not None else None
            return self._baseXbrliType

    @property
    def baseXbrliTypeQname(self) -> QName:
        """(qname) -- Attempts to return the base xsd type QName that this concept's type
        is derived from.  If not determinable anyType is returned.  E.g., for monetaryItemType,
        decimal is returned."""
        try:
            return cast(QName, self._baseXbrliTypeQname)
        except AttributeError:
            typeqname = self.typeQname
            if typeqname is not None and typeqname.namespaceURI == XbrlConst.xbrli:
                self._baseXbrliTypeQname = typeqname
            else:
                self._baseXbrliTypeQname = self.type.baseXbrliTypeQname if self.type is not None else None
            return self._baseXbrliTypeQname

    def instanceOfType(self, typeqname: Any) -> bool:
        """(bool) -- True if element is declared by, or derived from type of given qname or list of qnames"""
        if isinstance(typeqname, (tuple,list,set)): # union
            if self.typeQname in typeqname:
                return True
        else: # not union, single type
            if self.typeQname == typeqname:
                return True
        type = self.type
        if type is not None and type.isDerivedFrom(typeqname): # allows list or single type name
            return True
        subs = self.substitutionGroup
        if subs is not None:
            return subs.instanceOfType(typeqname)
        return False

    @property
    def isNumeric(self) -> bool:
        """(bool) -- True for elements of, or derived from, numeric base type (not including fractionItemType)"""
        try:
            return self._isNumeric
        except AttributeError:
            self._isNumeric = XbrlConst.isNumericXsdType(self.baseXsdType)
            return self._isNumeric

    @property
    def isInteger(self) -> bool:
        """(bool) -- True for elements of, or derived from, integer base type (not including fractionItemType)"""
        try:
            return self._isInteger
        except AttributeError:
            self._isInteger = XbrlConst.isIntegerXsdType(self.baseXsdType)
            return self._isInteger

    @property
    def isFraction(self) -> bool:
        """(bool) -- True if the baseXbrliType is fractionItemType"""
        try:
            return self._isFraction
        except AttributeError:
            self._isFraction = self.baseXbrliType == "fractionItemType"
            return self._isFraction

    @property
    def isMonetary(self) -> bool:
        """(bool) -- True if the baseXbrliType is monetaryItemType"""
        try:
            return self._isMonetary
        except AttributeError:
            self._isMonetary = self.baseXbrliType == "monetaryItemType"
            return self._isMonetary

    @property
    def isShares(self) -> bool:
        """(bool) -- True if the baseXbrliType is sharesItemType"""
        try:
            return self._isShares
        except AttributeError:
            self._isShares = self.baseXbrliType == "sharesItemType"
            return self._isShares

    @property
    def isTextBlock(self) -> bool:
        """(bool) -- Element's type.isTextBlock."""
        return self.type is not None and self.type.isTextBlock

    @property
    def isLanguage(self) -> bool:
        """(bool) -- True if the baseXbrliType is languageItemType"""
        try:
            return self._isLanguage
        except AttributeError:
            self._isLanguage = self.baseXbrliType == "languageItemType"
            return self._isLanguage

    @property
    def type(self) -> ModelType | None:
        """Element's modelType object (if any)"""
        try:
            return self._type
        except AttributeError:
            assert self.modelXbrl is not None
            self._type = self.modelXbrl.qnameTypes.get(self.typeQname)
            return self._type

    @property
    def substitutionGroup(self) -> ModelConcept | None:
        """modelConcept object for substitution group (or None)"""
        subsgroupqname = self.substitutionGroupQname
        if subsgroupqname is not None:
            assert self.modelXbrl is not None
            return self.modelXbrl.qnameConcepts.get(subsgroupqname)
        return None

    @property
    def substitutionGroupQname(self) -> QName | None:
        """(QName) -- substitution group"""
        try:
            return self._substitutionGroupQname
        except AttributeError:
            self._substitutionGroupQname = None
            if self.get("substitutionGroup"):
                self._substitutionGroupQname = self.schemaNameQname(self.get("substitutionGroup"))
            return self._substitutionGroupQname

    @property
    def substitutionGroupQnames(self) -> list[QName]:   # ordered list of all substitution group qnames
        """([QName]) -- Ordered list of QNames of substitution groups (recursively)"""
        qnames = []
        subs = self
        subNext = subs.substitutionGroup
        while subNext is not None:
            qnames.append(subNext.qname)
            subs = subNext
            subNext = subs.substitutionGroup
        return qnames

    @property
    def isQualifiedForm(self) -> bool: # used only in determining qname, which itself is cached
        """(bool) -- True if element has form attribute qualified or its document default"""
        if self.get("form") is not None: # form is almost never used
            return self.get("form") == "qualified"
        return getattr(self.modelDocument, "isQualifiedElementFormDefault", False) # parent might not be a schema document

    @property
    def nillable(self) -> str | None:
        """(str) --Value of the nillable attribute or its default"""
        return self.get("nillable", 'false')

    @property
    def isNillable(self) -> bool:
        """(bool) -- True if nillable"""
        return self.get("nillable") == 'true'

    @property
    def block(self) -> str | None:
        """(str) -- block attribute"""
        return self.get("block")

    @property
    def default(self) -> str | None:
        """(str) -- default attribute"""
        return self.get("default")

    @property
    def fixed(self) -> str | None:
        """(str) -- fixed attribute"""
        return self.get("fixed")

    @property
    def final(self) -> str | None:
        """(str) -- final attribute"""
        return self.get("final")

    @property
    def isRoot(self) -> bool:
        """(bool) -- True if parent of element definition is xsd schema element"""
        return self.getparent().localName == "schema"  # type: ignore[union-attr]

    def label(
        self,
        preferredLabel: str | None = None,
        fallbackToQname: bool = True,
        lang: str | tuple | list | None = None,
        strip: bool=False,
        linkrole: str | None = None,
        linkroleHint: str | None = None,
    ) -> str | None:
        """Returns effective label for concept, using preferredLabel role (or standard label if None),
        absent label falls back to element qname (prefixed name) if specified, lang falls back to
        tool-config language if none, leading/trailing whitespace stripped (trimmed) if specified.
        Does not look for generic labels (use superclass genLabel for generic label).

        :param preferredLabel: label role (standard label if not specified)
        :type preferredLabel: str
        :param fallbackToQname: if True and no matching label, then element qname is returned
        :type fallbackToQname: bool
        :param lang: language code(s) requested (otherwise configuration specified language is returned).  If multiple the order represents priority of label lang.
        :type lang: str, tuple or list
        :param strip: specifies removal of leading/trailing whitespace from returned label
        :type strip: bool
        :param linkrole: specifies linkrole desired (wild card if not specified)
        :type linkrole: str
        :returns: label matching parameters, or element qname if fallbackToQname requested and no matching label
        """
        if preferredLabel is None: preferredLabel = XbrlConst.standardLabel
        if preferredLabel == XbrlConst.conceptNameLabelRole: return str(self.qname)

        assert self.modelXbrl is not None

        labelsRelationshipSet = self.modelXbrl.relationshipSet(XbrlConst.conceptLabel,linkrole)
        if labelsRelationshipSet:
            for _lang in (lang if isinstance(lang, (tuple,list)) else (lang,)):
                label = labelsRelationshipSet.label(self, preferredLabel, _lang, linkroleHint=linkroleHint)
                if label is not None:
                    if strip: return label.strip()
                    return Locale.rtlString(label, lang=_lang)
        return str(self.qname) if fallbackToQname else None

    def relationshipToResource(self, resourceObject: ModelObject, arcrole: str) -> ModelRelationship:
        """For specified object and resource (all link roles), returns first
        modelRelationshipObject that relates from this element to specified resourceObject.

        :param resourceObject: resource to find relationship to
        :type resourceObject: ModelObject
        :param arcrole: specifies arcrole for search
        :type arcrole: str
        :returns: ModelRelationship
        """
        assert self.modelXbrl is not None

        relationshipSet = self.modelXbrl.relationshipSet(arcrole)
        if relationshipSet:
            for modelRel in relationshipSet.fromModelObject(self):
                if modelRel.toModelObject == resourceObject:
                    return modelRel
        return None

    @property
    def isItem(self) -> bool:
        """(bool) -- True for a substitution for xbrli:item but not xbrli:item itself"""
        try:
            return self._isItem
        except AttributeError:
            self._isItem = self.subGroupHeadQname == XbrlConst.qnXbrliItem and self.namespaceURI != XbrlConst.xbrli
            return self._isItem

    @property
    def isTuple(self) -> bool:
        """(bool) -- True for a substitution for xbrli:tuple but not xbrli:tuple itself"""
        try:
            return self._isTuple
        except AttributeError:
            self._isTuple = self.subGroupHeadQname == XbrlConst.qnXbrliTuple and self.namespaceURI != XbrlConst.xbrli
            return self._isTuple

    @property
    def isLinkPart(self) -> bool:
        """(bool) -- True for a substitution for link:part but not link:part itself"""
        try:
            return self._isLinkPart
        except AttributeError:
            self._isLinkPart = self.subGroupHeadQname == XbrlConst.qnLinkPart and self.namespaceURI != XbrlConst.link
            return self._isLinkPart

    @property
    def isPrimaryItem(self) -> bool:
        """(bool) -- True for a concept definition that is not a hypercube or dimension"""
        try:
            return self._isPrimaryItem
        except AttributeError:
            self._isPrimaryItem = self.isItem and not \
            (self.substitutesForQname(XbrlConst.qnXbrldtHypercubeItem) or self.substitutesForQname(XbrlConst.qnXbrldtDimensionItem))
            return self._isPrimaryItem

    @property
    def isDomainMember(self) -> bool:
        """(bool) -- Same as isPrimaryItem (same definition in XDT)"""
        return self.isPrimaryItem   # same definition in XDT

    @property
    def isHypercubeItem(self) -> bool:
        """(bool) -- True for a concept definition that is a hypercube"""
        try:
            return self._isHypercubeItem
        except AttributeError:
            self._isHypercubeItem = self.substitutesForQname(XbrlConst.qnXbrldtHypercubeItem)
            return self._isHypercubeItem

    @property
    def isDimensionItem(self) -> bool:
        """(bool) -- True for a concept definition that is a dimension"""
        try:
            return self._isDimensionItem
        except AttributeError:
            self._isDimensionItem = self.substitutesForQname(XbrlConst.qnXbrldtDimensionItem)
            return self._isDimensionItem

    @property
    def isTypedDimension(self) -> bool:
        """(bool) -- True for a concept definition that is a typed dimension"""
        try:
            return self._isTypedDimension
        except AttributeError:
            self._isTypedDimension = self.isDimensionItem and self.get("{http://xbrl.org/2005/xbrldt}typedDomainRef") is not None
            return self._isTypedDimension

    @property
    def isExplicitDimension(self) -> bool:
        """(bool) -- True for a concept definition that is an explicit dimension"""
        return self.isDimensionItem and not self.isTypedDimension

    @property
    def typedDomainRef(self) -> str | None:
        """(str) -- typedDomainRef attribute"""
        return self.get("{http://xbrl.org/2005/xbrldt}typedDomainRef")

    @property
    def typedDomainElement(self) -> ModelObject | None:
        """(ModelConcept) -- the element definition for a typedDomainRef attribute (of a typed dimension element)"""
        try:
            return self._typedDomainElement
        except AttributeError:
            self._typedDomainElement = self.resolveUri(uri=self.typedDomainRef)
            return self._typedDomainElement

    @property
    def isEnumeration(self) -> bool:
        """(bool) -- True if derived from enum:enumerationItemType or enum:enumerationsItemType or enum2:setValueDimensionType"""
        try:
            return self._isEnum
        except AttributeError:
            self._isEnum = self.instanceOfType(XbrlConst.qnEnumerationTypes)
            return self._isEnum

    @property
    def isEnumeration2Item(self) -> bool:
        """(bool) -- True if derived from enum2 item types"""
        try:
            return self._isEnum
        except AttributeError:
            self._isEnum = self.instanceOfType(XbrlConst.qnEnumeration2ItemTypes)
            return self._isEnum

    @property
    def enumDomainQname(self) -> QName | None:
        """(QName) -- enumeration domain qname """
        return self.schemaNameQname(self.get(XbrlConst.attrEnumerationDomain2014) or self.get(XbrlConst.attrEnumerationDomain2020) or self.get(XbrlConst.attrEnumerationDomainYYYY) or self.get(XbrlConst.attrEnumerationDomain11YYYY) or self.get(XbrlConst.attrEnumerationDomain2016))

    @property
    def enumDomain(self) -> ModelConcept | None:
        """(ModelConcept) -- enumeration domain """
        try:
            return self._enumDomain
        except AttributeError:
            assert self.modelXbrl is not None

            self._enumDomain = self.modelXbrl.qnameConcepts.get(self.enumDomainQname)
            return self._enumDomain

    @property
    def enumLinkrole(self) -> str | None:
        """(anyURI) -- enumeration linkrole """
        return self.get(XbrlConst.attrEnumerationLinkrole2014) or self.get(XbrlConst.attrEnumerationLinkrole2020) or self.get(XbrlConst.attrEnumerationLinkroleYYYY) or self.get(XbrlConst.attrEnumerationLinkrole11YYYY) or self.get(XbrlConst.attrEnumerationLinkrole2016)

    @property
    def enumDomainUsable(self) -> str | None:
        """(string) -- enumeration usable attribute """
        return self.get(XbrlConst.attrEnumerationUsable2014) or self.get(XbrlConst.attrEnumerationUsable2020) or self.get(XbrlConst.attrEnumerationUsableYYYY) or self.get(XbrlConst.attrEnumerationUsable11YYYY) or self.get(XbrlConst.attrEnumerationUsable2016) or "false"

    @property
    def isEnumDomainUsable(self) -> bool:
        """(bool) -- enumeration domain usability """
        try:
            return self._isEnumDomainUsable
        except AttributeError:
            self._isEnumDomainUsable = self.enumDomainUsable == "true"
            return self._isEnumDomainUsable

    def substitutesForQname(self, subsQname: QName) -> bool:
        """(bool) -- True if element substitutes for specified qname"""
        subs = self
        subNext = subs.substitutionGroup
        while subNext is not None:
            if subsQname == subs.substitutionGroupQname:
                return True
            subs = subNext
            subNext = subs.substitutionGroup
        return False

    @property
    def subGroupHeadQname(self) -> QName:
        """(QName) -- Head of substitution lineage of element (e.g., xbrli:item)"""
        subs = self
        subNext = subs.substitutionGroup
        while subNext is not None:
            subs = subNext
            subNext = subs.substitutionGroup
        return subs.qname

    def dereference(self) -> ModelConcept | None:
        """(ModelConcept) -- If element is a ref (instead of name), provides referenced modelConcept object, else self"""
        ref = self.get("ref")
        if ref:
            qn = self.schemaNameQname(ref, isQualifiedForm=self.isQualifiedForm)

            assert self.modelXbrl is not None

            return self.modelXbrl.qnameConcepts.get(qn)
        return self

    @property
    def propertyView(self) -> tuple[Any, ...]:
        # find default and other labels
        assert self.modelXbrl is not None
        _lang = self.modelXbrl.modelManager.defaultLang
        _labelDefault = self.label(lang=_lang)
        _labels = tuple(("{} ({})".format(os.path.basename(label.role or "no-role"), label.xmlLang), label.stringValue)
                        for labelRel in self.modelXbrl.relationshipSet(XbrlConst.conceptLabel).fromModelObject(self)
                        for label in (labelRel.toModelObject,))
        if _labels:
            _labelProperty = ("label", _labelDefault, sorted(_labels))
        else:
            _labelProperty = ("label", _labelDefault)
        _refT = tuple((self.modelXbrl.roleTypeDefinition(_ref.role, _lang), " ",
                       tuple((_refPart.localName, _refPart.stringValue.strip())
                             for _refPart in _ref.iterchildren()))
                      for _refRel in sorted(self.modelXbrl.relationshipSet(XbrlConst.conceptReference).fromModelObject(self),
                                            key=lambda r:r.toModelObject.roleRefPartSortKey())
                      for _ref in (_refRel.toModelObject,))
        _refsStrung = " ".join(_refPart.stringValue.strip()
                               for _refRel in self.modelXbrl.relationshipSet(XbrlConst.conceptReference).fromModelObject(self)
                               for _refPart in _refRel.toModelObject.iterchildren())
        _refProperty = ("references", _refsStrung, _refT) if _refT else ()
        _facets = ("facets", ", ".join(sorted(self.facets.keys())), tuple(
                    (_name, sorted(_value.keys()),
                     tuple((eVal,eElt.genLabel())  # type: ignore[attr-defined]
                           for eVal, eElt in sorted(_value.items(), key=lambda i:i[0]))
                     ) if isinstance(_value,dict)
                    else (_name, _value)
                    for _name, _value in sorted(self.facets.items(), key=lambda i:i[0]))
                   ) if self.facets else ()
        return (_labelProperty,
                ("namespace", self.qname.namespaceURI),
                ("name", self.name),
                ("QName", self.qname),
                ("id", self.id),
                ("abstract", self.abstract),
                ("type", self.typeQname),
                ("subst grp", self.substitutionGroupQname),
                ("period type", self.periodType) if self.periodType else (),
                ("balance", self.balance) if self.balance else (),
                _facets,
                _refProperty)

    def __repr__(self) -> str:
        return ("modelConcept[{0}, qname: {1}, type: {2}, abstract: {3}, {4}, line {5}]"
                .format(self.objectIndex, self.qname, self.typeQname, self.abstract,
                        self.modelDocument.basename, self.sourceline))

    @property
    def viewConcept(self) -> ModelConcept:
        return self

class ModelAttribute(ModelNamableTerm):
    """
    .. class:: ModelAttribute(modelDocument)

    Attribute term

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """

    _baseXsdType: str | None
    _isNumeric: bool
    _facets: dict[str, Any] | None
    _type: ModelType | None

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelAttribute, self).init(modelDocument)
        if self.isGlobalDeclaration:
            assert self.modelXbrl is not None
            self.modelXbrl.qnameAttributes[self.qname] = self
            if not self.isQualifiedForm:
                self.modelXbrl.qnameAttributes[ModelValue.QName(None, None, self.name)] = self

    @property
    def typeQname(self) -> QName:
        """(QName) -- QName of type of attribute"""
        if self.get("type"):
            return self.schemaNameQname(self.get("type"))
        # check derivation
        typeOrUnion = XmlUtil.schemaBaseTypeDerivedFrom(self)
        if not isinstance(typeOrUnion,list): # not a union
            return self.schemaNameQname(typeOrUnion)
        if getattr(self,"xValid", 0) >= 4:
            # check if anonymous type exists
            typeqname = ModelValue.qname(self.qname.clarkNotation +  anonymousTypeSuffix)
            assert self.modelXbrl is not None
            if typeqname in self.modelXbrl.qnameTypes:
                return typeqname
            # try substitution group for type
            ''' HF: I don't think attributes can have a substitution group ??
            subs = self.substitutionGroup
            if subs:
                return subs.typeQname
            '''
        return None

    @property
    def type(self) -> ModelType:
        """(ModelType) -- Attribute's modelType object (if any)"""
        try:
            return self._type
        except AttributeError:
            assert self.modelXbrl is not None
            self._type = self.modelXbrl.qnameTypes.get(self.typeQname)
            return self._type

    @property
    def baseXsdType(self) -> str:
        """(str) -- Attempts to return the base xsd type localName that this attribute's type
        is derived from.  If not determinable *anyType* is returned"""
        try:
            return self._baseXsdType
        except AttributeError:
            typeqname = self.typeQname
            if typeqname is None:   # anyType is default type
                return "anyType"
            if typeqname.namespaceURI == XbrlConst.xsd:
                return typeqname.localName
            type = self.type
            self._baseXsdType = type.baseXsdType if type is not None else None
            return self._baseXsdType

    @property
    def facets(self) -> dict[Any, Any] | None:
        """(dict) -- Returns self.type.facets or None (if type indeterminate)"""
        try:
            return self._facets
        except AttributeError:
            type = self.type
            self._facets = type.facets if type is not None else None
            return self._facets

    @property
    def isNumeric(self) -> bool:
        """(bool) -- True for a numeric xsd base type (not including xbrl fractions)"""
        try:
            return self._isNumeric
        except AttributeError:
            self._isNumeric = XbrlConst.isNumericXsdType(self.baseXsdType)
            return self._isNumeric

    @property
    def isQualifiedForm(self) -> bool: # used only in determining qname, which itself is cached
        """(bool) -- True if attribute has form attribute qualified or its document default"""
        if self.get("form") is not None: # form is almost never used
            return self.get("form") == "qualified"
        return self.modelDocument.isQualifiedAttributeFormDefault

    @property
    def isRequired(self) -> bool:
        """(bool) -- True if use is required"""
        return self.get("use") == "required"

    @property
    def default(self) -> str | None:
        """(str) -- default attribute"""
        return self.get("default")

    @property
    def fixed(self) -> str | None:
        """(str) -- fixed attribute or None"""
        return self.get("fixed")

    def dereference(self) -> ModelAttribute:
        """(ModelAttribute) -- If element is a ref (instead of name), provides referenced modelAttribute object, else self"""
        ref = self.get("ref")
        if ref:
            qn = self.schemaNameQname(ref, isQualifiedForm=self.isQualifiedForm)
            assert self.modelXbrl is not None
            return self.modelXbrl.qnameAttributes.get(qn)
        return self

class ModelAttributeGroup(ModelNamableTerm):
    """
    .. class:: ModelAttributeGroup(modelDocument)

    Attribute Group term

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """

    _attributes: dict[QName, ModelAttribute]

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelAttributeGroup, self).init(modelDocument)
        if self.isGlobalDeclaration:
            assert self.modelXbrl is not None
            self.modelXbrl.qnameAttributeGroups[self.qname] = self

    @property
    def isQualifiedForm(self) -> bool:
        """(bool) -- True, always qualified"""
        return True

    @property
    def attributes(self) -> dict[QName, ModelAttribute]:
        """(dict) -- Dict by attribute QName of ModelAttributes"""
        try:
            return self._attributes
        except AttributeError:
            self._attributes = {}
            attrs, attrWildcardElts, attrGroups = XmlUtil.schemaAttributesGroups(self)
            self._attributeWildcards = set(attrWildcardElts)
            for attrGroupRef in attrGroups:
                attrGroupDecl = attrGroupRef.dereference()  # type: ignore[attr-defined]
                if attrGroupDecl is not None:
                    for attrRef in attrGroupDecl.attributes.values():
                        attrDecl = attrRef.dereference()
                        if attrDecl is not None:
                            self._attributes[attrDecl.qname] = attrDecl
                    self._attributeWildcards.update(attrGroupDecl.attributeWildcards)
            for attrRef in attrs:
                attrDecl = attrRef.dereference()
                if attrDecl is not None:
                    self._attributes[attrDecl.qname] = attrDecl
            return self._attributes

    @property
    def attributeWildcards(self) -> set[_Element]:
        try:
            return self._attributeWildcards
        except AttributeError:
            self.attributes # loads attrWildcards
            return self._attributeWildcards

    def dereference(self) -> ModelAttributeGroup:
        """(ModelAttributeGroup) -- If element is a ref (instead of name), provides referenced modelAttributeGroup object, else self"""
        ref = self.get("ref")
        if ref:
            qn = self.schemaNameQname(ref)
            assert self.modelXbrl is not None
            return self.modelXbrl.qnameAttributeGroups.get(ModelValue.qname(self, ref))
        return self

class ModelType(ModelNamableTerm):
    """
    .. class:: ModelType(modelDocument)

    Type definition term

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """

    _attributes: dict[QName, ModelAttribute]
    _attributeWildcards: list[str]
    _baseXbrliType: str | None
    _baseXbrliTypeQname: Any
    _baseXsdType: str
    _facets: dict[str, TypeXValue] | None
    _elements: set[QName | None]
    _requiredAttributeQnames: set[QName]

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelType, self).init(modelDocument)
        assert self.modelXbrl is not None
        self.modelXbrl.qnameTypes.setdefault(self.qname, self) # don't redefine types nested in anonymous types
        self.particlesList = ParticlesList()

    @property
    def name(self) -> str | None:
        nameAttr = self.getStripped("name")
        if nameAttr:
            return nameAttr
        # may be anonymous type of parent
        element = self.getparent()
        while element is not None:
            nameAttr = element.getStripped("name")  # type: ignore[attr-defined]
            if nameAttr:
                return nameAttr + anonymousTypeSuffix
            element = element.getparent()
        return None

    @property
    def isQualifiedForm(self) -> bool:
        """(bool) -- True (for compatibility with other schema objects)"""
        return True

    @property
    def qnameDerivedFrom(self) -> QName:
        """(QName) -- the type that this type is derived from"""
        typeOrUnion = XmlUtil.schemaBaseTypeDerivedFrom(self)
        if isinstance(typeOrUnion,list): # union
            return [self.schemaNameQname(t) for t in typeOrUnion]
        return self.schemaNameQname(typeOrUnion)

    @property
    def typeDerivedFrom(self) -> ModelType:
        """(ModelType) -- type that this type is derived from"""
        qnameDerivedFrom = self.qnameDerivedFrom
        assert self.modelXbrl is not None
        if isinstance(qnameDerivedFrom, list):
            return [self.modelXbrl.qnameTypes.get(qn) for qn in qnameDerivedFrom]
        elif isinstance(qnameDerivedFrom, ModelValue.QName):
            return self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
        return None

    @property
    def particles(self) -> list[ModelParticle]:
        """([ModelParticles]) -- Particles of this type"""
        if self.particlesList:  # if non empty list, use it
            return self.particlesList
        typeDerivedFrom = self.typeDerivedFrom  # else try to get derived from list
        if isinstance(typeDerivedFrom, ModelType):
            return typeDerivedFrom.particlesList
        return self.particlesList  # empty list

    @property
    def baseXsdType(self) -> str:
        """(str) -- The xsd type localName that this type is derived from or:
        *noContent* for an element that may not have text nodes,
        *anyType* for an element that may have text nodes but their type is not specified,
        or one of several union types for schema validation purposes: *XBRLI_DATEUNION*,
        *XBRLI_DECIMALSUNION*, *XBRLI_PRECISIONUNION*, *XBRLI_NONZERODECIMAL*.
        """
        try:
            return self._baseXsdType
        except AttributeError:
            if self.qname == XbrlConst.qnXbrliDateUnion:
                self._baseXsdType = "XBRLI_DATEUNION"
            elif self.qname == XbrlConst.qnXbrliDecimalsUnion:
                self._baseXsdType = "XBRLI_DECIMALSUNION"
            elif self.qname == XbrlConst.qnXbrliPrecisionUnion:
                self._baseXsdType = "XBRLI_PRECISIONUNION"
            elif self.qname == XbrlConst.qnXbrliNonZeroDecimalUnion:
                self._baseXsdType = "XBRLI_NONZERODECIMAL"
            else:
                assert self.modelXbrl is not None

                qnameDerivedFrom = self.qnameDerivedFrom
                if qnameDerivedFrom is None:
                    # want None if base type has no content (not mixed content, TBD)
                    #self._baseXsdType =  "anyType"
                    self._baseXsdType =  "noContent"
                elif isinstance(qnameDerivedFrom,list): # union
                    if qnameDerivedFrom == XbrlConst.qnDateUnionXsdTypes:
                        self._baseXsdType = "XBRLI_DATEUNION"
                    elif len(qnameDerivedFrom) == 1:
                        qn0 = qnameDerivedFrom[0]
                        if qn0.namespaceURI == XbrlConst.xsd:
                            self._baseXsdType = qn0.localName
                        else:
                            typeDerivedFrom = self.modelXbrl.qnameTypes.get(qn0)
                            self._baseXsdType = typeDerivedFrom.baseXsdType if typeDerivedFrom is not None else "anyType"
                    # TBD implement union types
                    else:
                        self._baseXsdType = "anyType"
                elif qnameDerivedFrom.namespaceURI == XbrlConst.xsd:
                    self._baseXsdType = qnameDerivedFrom.localName
                else:
                    typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
                    #assert typeDerivedFrom is not None, _("Unable to determine derivation of {0}").format(qnameDerivedFrom)
                    self._baseXsdType = typeDerivedFrom.baseXsdType if typeDerivedFrom is not None else "anyType"
                if self._baseXsdType == "anyType" and XmlUtil.emptyContentModel(self):
                    self._baseXsdType = "noContent"
            return self._baseXsdType

    @property
    def baseXbrliTypeQname(self) -> QName:
        """(qname) -- The qname of the parent type in the xbrli namespace, if any, otherwise the localName of the parent in the xsd namespace."""
        try:
            return self._baseXbrliTypeQname
        except AttributeError:
            self._baseXbrliTypeQname = None
            if self.qname == XbrlConst.qnXbrliDateUnion:
                self._baseXbrliTypeQname = self.qname
            else:
                assert self.modelXbrl is not None

                qnameDerivedFrom = self.qnameDerivedFrom
                if isinstance(qnameDerivedFrom,list): # union
                    if qnameDerivedFrom == XbrlConst.qnDateUnionXsdTypes:
                        self._baseXbrliTypeQname = qnameDerivedFrom
                    # TBD implement union types
                    elif len(qnameDerivedFrom) == 1:
                        qn0 = qnameDerivedFrom[0]
                        if qn0.namespaceURI in (XbrlConst.xbrli, XbrlConst.xsd):
                            self._baseXbrliTypeQname = qn0
                        else:
                            typeDerivedFrom = self.modelXbrl.qnameTypes.get(qn0)
                            self._baseXbrliTypeQname = typeDerivedFrom.baseXbrliTypeQname if typeDerivedFrom is not None else None
                elif isinstance(qnameDerivedFrom, ModelValue.QName):
                    if qnameDerivedFrom.namespaceURI == XbrlConst.xbrli:  # xbrli type
                        self._baseXbrliTypeQname = qnameDerivedFrom
                    elif qnameDerivedFrom.namespaceURI == XbrlConst.xsd:    # xsd type
                        self._baseXbrliTypeQname = qnameDerivedFrom
                    else:
                        typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
                        self._baseXbrliTypeQname = typeDerivedFrom.baseXbrliTypeQname if typeDerivedFrom is not None else None
                else:
                    self._baseXbrliType = None
            return self._baseXbrliTypeQname

    @property
    def baseXbrliType(self) -> str:
        """(str) -- The localName of the parent type in the xbrli namespace, if any, otherwise the localName of the parent in the xsd namespace."""
        try:
            return self._baseXbrliType
        except AttributeError:
            baseXbrliTypeQname = self.baseXbrliTypeQname
            if isinstance(baseXbrliTypeQname,list): # union
                if baseXbrliTypeQname == XbrlConst.qnDateUnionXsdTypes:
                    self._baseXbrliType = "XBRLI_DATEUNION"
                # TBD implement union types
                else:
                    self._baseXbrliType = "anyType"
            elif baseXbrliTypeQname is not None:
                self._baseXbrliType = baseXbrliTypeQname.localName
            else:
                self._baseXbrliType = None
            return self._baseXbrliType

    @property
    def isTextBlock(self) -> bool:
        """(str) -- True if type is, or is derived from, us-types:textBlockItemType or dtr-types:escapedItemType"""
        assert self.modelDocument.targetNamespace is not None
        if self.name == "textBlockItemType" and "/us-types/" in self.modelDocument.targetNamespace:
            return True
        if self.name == "escapedItemType" and self.modelDocument.targetNamespace.startswith(XbrlConst.dtrTypesStartsWith):
            return True
        qnameDerivedFrom = self.qnameDerivedFrom
        if (not isinstance(qnameDerivedFrom, ModelValue.QName) or # textblock not a union type
            (qnameDerivedFrom.namespaceURI in(XbrlConst.xsd,XbrlConst.xbrli))):
            return False

        assert self.modelXbrl is not None
        typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
        return typeDerivedFrom.isTextBlock if typeDerivedFrom is not None else False

    @property
    def isOimTextFactType(self) -> bool:
        """(str) -- True if type meets OIM requirements to be a text fact"""
        assert self.modelDocument.targetNamespace is not None
        if self.modelDocument.targetNamespace.startswith(XbrlConst.dtrTypesStartsWith):
            return self.name not in XbrlConst.dtrNoLangItemTypeNames and self.baseXsdType in XbrlConst.xsdStringTypeNames
        if self.modelDocument.targetNamespace == XbrlConst.xbrli:
            return self.baseXsdType not in XbrlConst.xsdNoLangTypeNames and self.baseXsdType in XbrlConst.xsdStringTypeNames
        qnameDerivedFrom = self.qnameDerivedFrom
        if not isinstance(qnameDerivedFrom, ModelValue.QName): # textblock not a union type
            return False

        assert self.modelXbrl is not None
        typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
        return typeDerivedFrom.isOimTextFactType if typeDerivedFrom is not None else False

    @property
    def isWgnStringFactType(self) -> bool:
        """(str) -- True if type meets WGN String Fact Type requirements"""
        assert self.modelDocument.targetNamespace is not None
        if self.modelDocument.targetNamespace == XbrlConst.xbrli:
            return self.name in XbrlConst.wgnStringItemTypeNames
        qnameDerivedFrom = self.qnameDerivedFrom
        if not isinstance(qnameDerivedFrom, ModelValue.QName): # textblock not a union type
            return False

        assert self.modelXbrl is not None
        typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
        return typeDerivedFrom.isWgnStringFactType if typeDerivedFrom is not None else False

    @property
    def isDomainItemType(self) -> bool:
        """(bool) -- True if type is, or is derived from, domainItemType in either a us-types or a dtr-types namespace."""
        assert self.modelDocument.targetNamespace is not None
        if self.name == "domainItemType" and \
           ("/us-types/" in self.modelDocument.targetNamespace or
            self.modelDocument.targetNamespace.startswith(XbrlConst.dtrTypesStartsWith)):
            return True
        qnameDerivedFrom = self.qnameDerivedFrom
        if (not isinstance(qnameDerivedFrom, ModelValue.QName) or # domainItemType not a union type
            (qnameDerivedFrom.namespaceURI in(XbrlConst.xsd,XbrlConst.xbrli))):
            return False

        assert self.modelXbrl is not None
        typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
        return typeDerivedFrom.isDomainItemType if typeDerivedFrom is not None else False

    @property
    def isMultiLanguage(self) -> bool:
        """(bool) -- True if type is, or is derived from, stringItemType or normalizedStringItemType."""
        return self.baseXbrliType in {"stringItemType", "normalizedStringItemType", "string", "normalizedString"}

    def isDerivedFrom(self, typeqname: list[QName] | QName | None) -> bool:
        """(bool) -- True if type is derived from type specified by QName.  Type can be a single type QName or list of QNames"""
        qnamesDerivedFrom = self.qnameDerivedFrom # can be single qname or list of qnames if union
        if qnamesDerivedFrom is None:    # not derived from anything
            return typeqname is None or not typeqname # may be none or empty list
        if isinstance(qnamesDerivedFrom, (tuple,list)): # union
            if isinstance(typeqname, (tuple,list,set)):
                if any(t in qnamesDerivedFrom for t in typeqname):
                    return True
            else:
                if typeqname in qnamesDerivedFrom:
                    return True
        else: # not union, single type
            if isinstance(typeqname, (tuple,list,set)):
                if qnamesDerivedFrom in typeqname:
                    return True
            else:
                if qnamesDerivedFrom == typeqname:
                    return True
            qnamesDerivedFrom = (qnamesDerivedFrom,)
        for qnameDerivedFrom in qnamesDerivedFrom:  # type: ignore[attr-defined]
            assert self.modelXbrl is not None
            typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
            if typeDerivedFrom is not None and typeDerivedFrom.isDerivedFrom(typeqname):
                return True
        return False


    @property
    def attributes(self) -> dict[QName, ModelAttribute]:
        """(dict) -- Dict of ModelAttribute attribute declarations keyed by attribute QName"""
        try:
            return self._attributes
        except AttributeError:
            self._attributes = {}
            attrs, attrWildcardElts, attrGroups = XmlUtil.schemaAttributesGroups(self)
            self._attributeWildcards = attrWildcardElts
            for attrRef in attrs:
                attrDecl = attrRef.dereference()  # type: ignore[attr-defined]
                if attrDecl is not None:
                    self._attributes[attrDecl.qname] = attrDecl
            for attrGroupRef in attrGroups:
                attrGroupDecl = attrGroupRef.dereference()  # type: ignore[attr-defined]
                if attrGroupDecl is not None:
                    for attrRef in attrGroupDecl.attributes.values():
                        attrDecl = attrRef.dereference()  # type: ignore[attr-defined]
                        if attrDecl is not None:
                            self._attributes[attrDecl.qname] = attrDecl
                    self._attributeWildcards.extend(attrGroupDecl.attributeWildcards)
            typeDerivedFrom = self.typeDerivedFrom
            for t in typeDerivedFrom if isinstance(typeDerivedFrom, list) else [typeDerivedFrom]:
                if isinstance(t, ModelType):
                    self._attributes.update(t.attributes)
                    self._attributeWildcards.extend(t.attributeWildcards)
            return self._attributes

    @property
    def attributeWildcards(self) -> dict[str, str]:
        """(dict) -- List of wildcard namespace strings (e.g., ##other)"""
        try:
            return self._attributeWildcards
        except AttributeError:
            self.attributes # loads attrWildcards
            return self._attributeWildcards

    @property
    def requiredAttributeQnames(self) -> set[QName]:
        """(set) -- Set of attribute QNames which have use=required."""
        try:
            return self._requiredAttributeQnames
        except AttributeError:
            self._requiredAttributeQnames = set(a.qname for a in self.attributes.values() if a.isRequired)
            return self._requiredAttributeQnames

    @property
    def defaultAttributeQnames(self) -> set[QName]:
        """(set) -- Set of attribute QNames which have a default specified"""
        try:
            return self._defaultAttributeQnames
        except AttributeError:
            self._defaultAttributeQnames = set(a.qname for a in self.attributes.values() if a.default is not None)
            return self._defaultAttributeQnames

    @property
    def elements(self) -> list[QName]:
        """([QName]) -- List of element QNames that are descendants (content elements)"""
        try:
            return self._elements
        except AttributeError:
            self._elements = XmlUtil.schemaDescendantsNames(self, XbrlConst.xsd, "element")
            return self._elements

    @property
    def facets(self) -> dict[str, Any]:
        """(dict) -- Dict of facets by their facet name, all are strings except enumeration, which is a set of enumeration values."""
        try:
            return self._facets
        except AttributeError:
            facets = self.constrainingFacets()
            self._facets = facets if facets else None
            return self._facets

    def constrainingFacets(self, facetValues: dict[str, TypeXValue] | None = None) -> dict[str, TypeXValue]:
        """helper function for facets discovery"""
        if facetValues is None: facetValues = {}
        for facetElt in XmlUtil.schemaFacets(self, (
                    "{http://www.w3.org/2001/XMLSchema}length", "{http://www.w3.org/2001/XMLSchema}minLength",
                    "{http://www.w3.org/2001/XMLSchema}maxLength",
                    "{http://www.w3.org/2001/XMLSchema}pattern", "{http://www.w3.org/2001/XMLSchema}whiteSpace",
                    "{http://www.w3.org/2001/XMLSchema}maxInclusive", "{http://www.w3.org/2001/XMLSchema}minInclusive",
                    "{http://www.w3.org/2001/XMLSchema}maxExclusive", "{http://www.w3.org/2001/XMLSchema}minExclusive",
                    "{http://www.w3.org/2001/XMLSchema}totalDigits", "{http://www.w3.org/2001/XMLSchema}fractionDigits")):
            facetValue = XmlValidate.validateFacet(self, facetElt)
            assert facetElt is not None
            facetName = facetElt.localName  # type: ignore[attr-defined]
            if facetName not in facetValues and facetValue is not None:  # facetValue can be zero but not None
                facetValues[facetName] = facetValue
        if "enumeration" not in facetValues:
            for facetElt in XmlUtil.schemaFacets(self, ("{http://www.w3.org/2001/XMLSchema}enumeration",)):
                # Note 2023-01-29:
                # Not sure about this one. facetElt must not be None for there to be a
                # get-method. Should we assert instead?
                if facetElt is not None:
                    facetValues.setdefault("enumeration",{})[facetElt.get("value")] = facetElt
        typeDerivedFrom = self.typeDerivedFrom
        if isinstance(typeDerivedFrom, ModelType):
            typeDerivedFrom.constrainingFacets(facetValues)
        return facetValues

    def fixedOrDefaultAttrValue(self, attrName: str) -> str:
        """(str) -- Descendant attribute declaration value if fixed or default, argument is attribute name (string), e.g., 'precision'."""
        attr = XmlUtil.schemaDescendant(self, XbrlConst.xsd, "attribute", attrName)
        if attr is not None:
            if attr.get("fixed"):
                return attr.get("fixed")
            elif attr.get("default"):
                return attr.get("default")
        return None

    def dereference(self) -> ModelType:
        """(ModelType) -- If element is a ref (instead of name), provides referenced modelType object, else self"""
        return self

    @property
    def propertyView(self) -> tuple[Any, ...]:
        return (("namespace", self.qname.namespaceURI),
                ("name", self.name),
                ("QName", self.qname),
                ("xsd type", self.baseXsdType),
                ("derived from", self.qnameDerivedFrom),
                ("facits", self.facets))

    def __repr__(self) -> str:
        return ("modelType[{0}, qname: {1}, derivedFrom: {2}, {3}, line {4}]"
                .format(self.objectIndex, self.qname, self.qnameDerivedFrom,
                        self.modelDocument.basename, self.sourceline))

class ModelGroupDefinition(ModelNamableTerm, ModelParticle):
    """
    .. class:: ModelGroupDefinition(modelDocument)

    Group definition particle term

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelGroupDefinition, self).init(modelDocument)
        if self.isGlobalDeclaration:
            assert self.modelXbrl is not None
            self.modelXbrl.qnameGroupDefinitions[self.qname] = self
        else:
            self.addToParticles()
        self.particlesList = self.particles = ParticlesList()

    def dereference(self) -> ModelGroupDefinition:
        """(ModelGroupDefinition) -- If element is a ref (instead of name), provides referenced modelGroupDefinition object, else self"""
        ref = self.get("ref")
        if ref:
            qn = self.schemaNameQname(ref)
            assert self.modelXbrl is not None
            return self.modelXbrl.qnameGroupDefinitions.get(qn)
        return self

    @property
    def isQualifiedForm(self) -> bool:
        """(bool) -- True (for compatibility with other schema objects)"""
        return True

class ModelGroupCompositor(ModelObject, ModelParticle):
    """
    .. class:: ModelGroupCompositor(modelDocument)

    Particle Model group compositor term (sequence, choice, or all)

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelGroupCompositor, self).init(modelDocument)
        self.addToParticles()
        self.particlesList = self.particles = ParticlesList()

    def dereference(self) -> ModelGroupCompositor:
        """(ModelGroupCompositor) -- If element is a ref (instead of name), provides referenced ModelGroupCompositor object, else self"""
        return self

class ModelAll(ModelGroupCompositor):
    """
    .. class:: ModelAll(modelDocument)

    Particle Model all term

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelAll, self).init(modelDocument)

class ModelChoice(ModelGroupCompositor):
    """
    .. class:: ModelChoice(modelDocument)

    Particle Model choice term

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelChoice, self).init(modelDocument)

class ModelSequence(ModelGroupCompositor):
    """
    .. class:: ModelSequence(modelDocument)

    Particle Model sequence term

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelSequence, self).init(modelDocument)

class ModelAny(ModelObject, ModelParticle):
    """
    .. class:: ModelAny(modelDocument)

    Particle Model any term

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """

    _isAny: bool
    _namespaces: list[str]

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelAny, self).init(modelDocument)
        self.addToParticles()

    def dereference(self) -> ModelAny:
        return self

    def allowsNamespace(self, namespaceURI: str) -> bool:
        try:
            if self._isAny:
                return True
            if not namespaceURI:
                return "##local" in self._namespaces
            if namespaceURI in self._namespaces:
                return True
            if namespaceURI == self.modelDocument.targetNamespace:
                if "##targetNamespace" in self._namespaces:
                    return True
            else: # not equal namespaces
                if "##other" in self._namespaces:
                    return True
            return False
        except AttributeError:
            self._namespaces = self.get("namespace", '').split()
            self._isAny = (not self._namespaces) or "##any" in self._namespaces
            return self.allowsNamespace(namespaceURI)

class ModelAnyAttribute(ModelObject):
    """
    .. class:: ModelAnyAttribute(modelDocument)

    Any attribute definition term

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """

    _isAny: bool
    _namespaces: list[str]

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelAnyAttribute, self).init(modelDocument)

    def allowsNamespace(self, namespaceURI: str) -> bool:
        try:
            if self._isAny:
                return True
            if not namespaceURI:
                return "##local" in self._namespaces
            if namespaceURI in self._namespaces:
                return True
            if namespaceURI == self.modelDocument.targetNamespace:
                if "##targetNamespace" in self._namespaces:
                    return True
            else: # not equal namespaces
                if "##other" in self._namespaces:
                    return True
            return False
        except AttributeError:
            self._namespaces = self.get("namespace", '').split()
            self._isAny = (not self._namespaces) or "##any" in self._namespaces
            return self.allowsNamespace(namespaceURI)

class ModelEnumeration(ModelNamableTerm):
    """
    .. class:: ModelEnumeration(modelDocument)

    Facet enumeration term

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelEnumeration, self).init(modelDocument)

    @property
    def value(self) -> str | None:
        return self.get("value")

class ModelLink(ModelObject):
    """
    .. class:: ModelLink(modelDocument)

    XLink extended link element

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelLink, self).init(modelDocument)
        self.labeledResources = defaultdict(list)

    @property
    def role(self) -> str | None:
        return self.get("{http://www.w3.org/1999/xlink}role")

class ModelResource(ModelObject):
    """
    .. class:: ModelResource(modelDocument)

    XLink resource element

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelResource, self).init(modelDocument)
        assert self.modelXbrl is not None
        if self.xmlLang:
            self.modelXbrl.langs.add(self.xmlLang)
        if self.localName == "label":
            self.modelXbrl.labelroles.add(self.role)

    @property
    def role(self) -> str | None:
        """(str) -- xlink:role attribute"""
        return self.get("{http://www.w3.org/1999/xlink}role")

    @property
    def xlinkLabel(self) -> str | None:
        """(str) -- xlink:label attribute"""
        return self.get("{http://www.w3.org/1999/xlink}label")

    @property
    def xmlLang(self) -> str:
        """(str) -- xml:lang attribute
        Note that xml.xsd specifies that an empty string xml:lang attribute is an un-declaration of the
        attribute, as if the attribute were not present.  When absent or un-declared, returns None."""
        return XmlUtil.ancestorOrSelfAttr(self, "{http://www.w3.org/XML/1998/namespace}lang") or None

    def viewText(self, labelrole: str | None = None, lang: str | None = None) -> str:
        """(str) -- Text of contained (inner) text nodes except for any whose localName
        starts with URI, for label and reference parts displaying purposes.
        (Footnotes, which return serialized html content of footnote.)"""
        if self.qname == XbrlConst.qnLinkFootnote:
            return XmlUtil.innerText(self, ixEscape="html", strip=True) # include HTML construct
        return " ".join([XmlUtil.text(resourceElt)
                           for resourceElt in self.iter()
                              if isinstance(resourceElt,ModelObject) and
                                  not resourceElt.localName.startswith("URI")])

    def roleRefPartSortKey(self) -> str:
        return "{} {}".format(self.role,
                              " ".join("{} {}".format(_refPart.localName, _refPart.stringValue.strip())  # type: ignore[attr-defined]
                                       for _refPart in self.iterchildren()))[:200] # limit length of sort

    def dereference(self) -> ModelResource:
        return self

class ModelLocator(ModelResource):
    """
    .. class:: ModelLocator(modelDocument)

    XLink locator element

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """

    modelHref: tuple[str, ModelDocument, str]

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelLocator, self).init(modelDocument)

    def dereference(self) -> ModelObject:
        """(ModelObject) -- Resolve loc's href if resource is a loc with href document and id modelHref a tuple with
        href's element, modelDocument, id"""
        return self.resolveUri(self.modelHref)

    @property
    def propertyView(self) -> tuple[Any, ...]:
        global ModelFact
        if ModelFact is None:
            from arelle.ModelInstanceObject import ModelFact
        hrefObj = self.dereference()
        if isinstance(hrefObj,(ModelFact,ModelConcept)):
            return (("href", hrefObj.qname ), )
        elif isinstance(hrefObj, ModelResource):
            return (("href", hrefObj.viewText()),)
        else:
            return hrefObj.propertyView

class RelationStatus:
    Unknown = 0
    EFFECTIVE = 1
    OVERRIDDEN = 2
    PROHIBITED = 3
    INEFFECTIVE = 4

arcCustAttrsExclusions = {XbrlConst.xlink, "use","priority","order","weight","preferredLabel"}

class ModelRelationship(ModelObject):
    """
    .. class:: ModelRelationship(modelDocument, arcElement, fromModelObject, toModelObject)

    ModelRelationship is a ModelObject that does not proxy an lxml object (but instead references
    ModelObject arc elements, and the from and to ModelObject elements.

    :param modelDocument: Owning modelDocument object
    :type modelDocument: ModelDocument
    :param arcElement: lxml arc element that was resolved into this relationship object
    :type arcElement: ModelObject
    :param fromModelObject: the from lxml resource element of the source of the relationship
    :type fromModelObject: ModelObject
    :param toModelObject: the to lxml resource element of the target of the relationship
    :type toModelObject: ModelObject

    Includes properties that proxy the referenced modelArc: localName, namespaceURI, prefixedName, sourceline, tag, elementQname, qname,
    and methods that proxy methods of modelArc: get() and itersiblings()

        .. attribute:: arcElement

        ModelObject arc element of the effective relationship

        .. attribute:: fromModelObject

        ModelObject of the xlink:from (dereferenced if via xlink:locator)

        .. attribute:: toModelObject

        ModelObject of the xlink:to (dereferenced if via xlink:locator)
    """

    _isComplemented: bool
    _isCovered: bool
    _isClosed: bool
    _tableAxis: str
    _usable: str | None

    def __init__(self, modelDocument: ModelDocument, arcElement: ModelDocument, fromModelObject: ModelDocument, toModelObject: ModelDocument) -> None:
        # copy model object properties from arcElement
        self.arcElement: ModelDocument = arcElement
        self.init(modelDocument)
        self.fromModelObject: ModelDocument = fromModelObject
        self.toModelObject: ModelDocument = toModelObject

    def clear(self) -> None:
        self.__dict__.clear() # dereference here, not an lxml object, don't use superclass clear()

    # simulate etree operations
    def get(self, attrname: str) -> Any:
        """Method proxy for the arc element of the effective relationship so that the non-proxy
        """
        return self.arcElement.get(attrname) # type: ignore[attr-defined]

    @property
    def localName(self) -> str:
        """(str) -- Property proxy for localName of arc element"""
        return cast(str, self.arcElement.localName) # type: ignore[attr-defined]

    @property
    def namespaceURI(self) -> str:
        """(str) -- Property proxy for namespaceURI of arc element"""
        return cast(str, self.arcElement.namespaceURI) # type: ignore[attr-defined]

    @property
    def prefixedName(self) -> str:
        """(str) -- Property proxy for prefixedName of arc element"""
        return cast(str, self.arcElement.prefixedName) # type: ignore[attr-defined]

    @property
    def sourceline(self) -> int:
        """(int) -- Property proxy for sourceline of arc element"""
        return self.arcElement.sourceline # type: ignore[attr-defined]

    @property
    def tag(self) -> str:
        """(str) -- Property proxy for tag of arc element (clark notation)"""
        return self.arcElement.tag # type: ignore[attr-defined]

    @property
    def elementQname(self) -> QName:
        """(QName) -- Property proxy for elementQName of arc element"""
        return self.arcElement.elementQname # type: ignore[attr-defined]

    @property
    def qname(self) -> QName:
        """(QName) -- Property proxy for qname of arc element"""
        return self.arcElement.qname

    def itersiblings(self, **kwargs: Any) -> Any:
        """Method proxy for itersiblings() of lxml arc element"""
        return self.arcElement.itersiblings(**kwargs) # type: ignore[attr-defined]

    def getparent(self) -> ModelObject:
        """(_ElementBase) -- Method proxy for getparent() of lxml arc element"""
        return self.arcElement.getparent() # type: ignore[attr-defined]

    @property
    def fromLabel(self) -> str | None:
        """(str) -- Value of xlink:from attribute"""
        return self.arcElement.get("{http://www.w3.org/1999/xlink}from") # type: ignore[attr-defined]

    @property
    def toLabel(self) -> str | None:
        """(str) -- Value of xlink:to attribute"""
        return self.arcElement.get("{http://www.w3.org/1999/xlink}to") # type: ignore[attr-defined]

    @property
    def fromLocator(self) -> ModelLocator | None:
        """(ModelLocator) -- Value of locator surrogate of relationship source, if any"""
        for fromResource in self.arcElement.getparent().labeledResources[self.fromLabel]: # type: ignore[attr-defined]
            if isinstance(fromResource, ModelLocator) and self.fromModelObject is fromResource.dereference():
                return fromResource
        return None

    @property
    def toLocator(self) -> ModelLocator | None:
        """(ModelLocator) -- Value of locator surrogate of relationship target, if any"""
        for toResource in self.arcElement.getparent().labeledResources[self.toLabel]: # type: ignore[attr-defined]
            if isinstance(toResource, ModelLocator) and self.toModelObject is toResource.dereference():
                return toResource
        return None

    def locatorOf(self, dereferencedObject: ModelObject) -> ModelLocator | None:
        """(ModelLocator) -- Value of locator surrogate of relationship target, if any"""
        fromLocator = self.fromLocator
        if fromLocator is not None and fromLocator.dereference() == dereferencedObject:
            return fromLocator
        toLocator = self.toLocator
        if toLocator is not None and toLocator.dereference() == dereferencedObject:
            return toLocator
        return None

    @property
    def arcrole(self) -> str:
        """(str) -- Value of xlink:arcrole attribute"""
        return self.arcElement.get("{http://www.w3.org/1999/xlink}arcrole")  # type: ignore[attr-defined]

    @property
    def order(self) -> float:
        """(float) -- Value of xlink:order attribute, or 1.0 if not specified"""
        try:
            return self.arcElement._order # type: ignore[attr-defined]
        except AttributeError:
            o = self.arcElement.get("order") # type: ignore[attr-defined]
            if o is None:
                order = 1.0
            else:
                try:
                    order = float(o)
                except (TypeError,ValueError) :
                    order = float("nan")
            self.arcElement._order = order # type: ignore[attr-defined]
            return order

    @property
    def orderDecimal(self) -> decimal.Decimal:
        """(decimal) -- Value of xlink:order attribute, NaN if not convertable to float, or None if not specified"""
        try:
            return decimal.Decimal(self.order)
        except decimal.InvalidOperation:
            return decimal.Decimal("NaN")

    @property
    def priority(self) -> int:
        """(int) -- Value of xlink:order attribute, or 0 if not specified"""
        try:
            return self.arcElement._priority # type: ignore[attr-defined]
        except AttributeError:
            p = self.arcElement.get("priority") # type: ignore[attr-defined]
            if p is None:
                priority = 0
            else:
                try:
                    priority = int(p)
                except (TypeError,ValueError) :
                    # XBRL validation error needed
                    priority = 0
            self.arcElement._priority = priority # type: ignore[attr-defined]
            return priority

    @property
    def weight(self) -> float | None:
        """(float) -- Value of xlink:weight attribute, NaN if not convertable to float, or None if not specified"""
        try:
            return self.arcElement._weight # type: ignore[attr-defined]
        except AttributeError:
            w = self.arcElement.get("weight") # type: ignore[attr-defined]
            if w is None:
                weight = None
            else:
                try:
                    weight = float(w)
                except (TypeError,ValueError) :
                    # XBRL validation error needed
                    weight = float("nan")
            self.arcElement._weight = weight # type: ignore[attr-defined]
            return weight

    @property
    def weightDecimal(self) -> decimal.Decimal | None:
        """(decimal) -- Value of xlink:weight attribute, NaN if not convertable to float, or None if not specified"""
        try:
            return self.arcElement._weightDecimal # type: ignore[attr-defined]
        except AttributeError:
            w = self.arcElement.get("weight") # type: ignore[attr-defined]
            if w is None:
                weight = None
            else:
                try:
                    weight = decimal.Decimal(w)
                except (TypeError,ValueError,decimal.InvalidOperation) :
                    # XBRL validation error needed
                    weight = decimal.Decimal("nan")
            self.arcElement._weightDecimal = weight # type: ignore[attr-defined]
            return weight

    @property
    def use(self) -> str | None:
        """(str) -- Value of use attribute"""
        return self.get("use")

    @property
    def isProhibited(self) -> bool:
        """(bool) -- True if use is prohibited"""
        return self.use == "prohibited"

    @property
    def prohibitedUseSortKey(self) -> int:
        """(int) -- 2 if use is prohibited, else 1, for use in sorting effective arcs before prohibited arcs"""
        return 2 if self.isProhibited else 1

    @property
    def preferredLabel(self) -> str | None:
        """(str) -- preferredLabel attribute or None if absent"""
        return self.get("preferredLabel")

    @property
    def variablename(self) -> str | None:
        """(str) -- name attribute"""
        return self.getStripped("name")

    @property
    def variableQname(self) -> QName:
        """(QName) -- resolved name for a formula (or other arc) having a QName name attribute"""
        varName = self.variablename
        return ModelValue.qname(self.arcElement, varName, noPrefixIsNoNamespace=True) if varName else None

    @property
    def linkrole(self) -> str:
        """(str) -- Value of xlink:role attribute of parent extended link element"""
        return self.arcElement.getparent().get("{http://www.w3.org/1999/xlink}role") # type: ignore[attr-defined]

    @property
    def linkQname(self) -> QName:
        """(QName) -- qname of the parent extended link element"""
        return self.arcElement.getparent().elementQname # type: ignore[attr-defined]

    @property
    def contextElement(self) -> str:
        """(str) -- Value of xbrldt:contextElement attribute (on applicable XDT arcs)"""
        return self.get("{http://xbrl.org/2005/xbrldt}contextElement")

    @property
    def targetRole(self) -> str:
        """(str) -- Value of xbrldt:targetRole attribute (on applicable XDT arcs)"""
        return self.get("{http://xbrl.org/2005/xbrldt}targetRole")

    @property
    def consecutiveLinkrole(self) -> str:
        """(str) -- Value of xbrldt:targetRole attribute, if provided, else parent linkRole (on applicable XDT arcs)"""
        return self.targetRole or self.linkrole

    @property
    def isUsable(self) -> bool:
        """(bool) -- True if xbrldt:usable is true (on applicable XDT arcs, defaults to True if absent)"""
        return self.get("{http://xbrl.org/2005/xbrldt}usable") in ("true","1", None)

    @property
    def closed(self) -> str:
        """(str) -- Value of xbrldt:closed (on applicable XDT arcs, defaults to 'false' if absent)"""
        return self.get("{http://xbrl.org/2005/xbrldt}closed") or "false"

    @property
    def isClosed(self) -> bool:
        """(bool) -- True if xbrldt:closed is true (on applicable XDT arcs, defaults to False if absent)"""
        try:
            return self._isClosed
        except AttributeError:
            self._isClosed = self.get("{http://xbrl.org/2005/xbrldt}closed") in ("true","1")
            return self._isClosed

    @property
    def usable(self) -> str:
        """(str) -- Value of xbrldt:usable (on applicable XDT arcs, defaults to 'true' if absent)"""
        try:
            return self._usable
        except AttributeError:
            if self.arcrole in (XbrlConst.dimensionDomain, XbrlConst.domainMember):
                self._usable = cast(str, self.get("{http://xbrl.org/2005/xbrldt}usable")) or "true"
            else:
                self._usable = None
            return self._usable

    @property
    def isComplemented(self) -> bool:
        """(bool) -- True if complemented is true (on applicable formula/rendering arcs, defaults to False if absent)"""
        try:
            return self._isComplemented
        except AttributeError:
            self._isComplemented = self.get("complement") in ("true","1")
            return self._isComplemented

    @property
    def isCovered(self) -> bool:
        """(bool) -- True if cover is true (on applicable formula/rendering arcs, defaults to False if absent)"""
        try:
            return self._isCovered
        except AttributeError:
            self._isCovered = self.get("cover") in ("true","1")
            return self._isCovered

    @property
    def axisDisposition(self) -> str:
        """(str) -- Value of axisDisposition (on applicable table linkbase arcs"""
        try:
            return self._tableAxis
        except AttributeError:
            aType = (self.get("axis") or # XII 2013
                     self.get("axisDisposition") or # XII 2011
                     self.get("axisType"))  # Eurofiling
            if aType in ("xAxis","x"): self._axisDisposition = "x"
            elif aType in ("yAxis","y"): self._axisDisposition = "y"
            elif aType in ("zAxis","z"): self._axisDisposition = "z"
            else: self._axisDisposition = None
            return self._axisDisposition

    @property
    def equivalenceHash(self) -> int: # not exact, use equivalenceKey if hashes are the same
        return hash((self.qname,
                     self.linkQname,
                     self.linkrole,  # needed when linkrole=None merges multiple links
                     self.fromModelObject.objectIndex if isinstance(self.fromModelObject, ModelObject) else -1,
                     self.toModelObject.objectIndex if isinstance(self.toModelObject, ModelObject) else -1,
                     self.order,
                     self.weight,
                     self.preferredLabel))

    @property
    def equivalenceKey(self) -> tuple[Any, ...]:
        """(tuple) -- Key to determine relationship equivalence per 2.1 spec"""
        # cannot be cached because this is unique per relationship
        assert self.modelXbrl is not None
        return (self.qname,
                self.linkQname,
                self.linkrole,  # needed when linkrole=None merges multiple links
                self.fromModelObject.objectIndex if isinstance(self.fromModelObject, ModelObject) else -1,
                self.toModelObject.objectIndex if isinstance(self.toModelObject, ModelObject) else -1,
                self.order,
                self.weight,
                self.preferredLabel) + \
                XbrlUtil.attributes(self.modelXbrl, self.arcElement,
                    exclusions=arcCustAttrsExclusions, keyByTag=True) # use clark tag for key instead of qname

    def isIdenticalTo(self, otherModelRelationship: ModelRelationship) -> bool:
        """(bool) -- Determines if relationship is identical to another, based on arc and identical from and to objects"""
        return (otherModelRelationship is not None and
                self.arcElement == otherModelRelationship.arcElement and
                self.fromModelObject is not None and otherModelRelationship.fromModelObject is not None and
                self.toModelObject is not None and otherModelRelationship.toModelObject is not None and
                self.fromModelObject == otherModelRelationship.fromModelObject and
                self.toModelObject == otherModelRelationship.toModelObject)

    def priorityOver(self, otherModelRelationship: ModelRelationship) -> bool:
        """(bool) -- True if this relationship has priority over other relationship"""
        if otherModelRelationship is None:
            return True
        priority = self.priority
        otherPriority = otherModelRelationship.priority
        if priority > otherPriority:
            return True
        elif priority < otherPriority:
            return False
        if otherModelRelationship.isProhibited:
            return False
        return True

    @property
    def propertyView(self) -> tuple[Any, ...]:
        return self.toModelObject.propertyView + \
               (("arcrole", self.arcrole),
                ("weight", self.weight) if self.arcrole == XbrlConst.summationItem else (),
                ("preferredLabel", self.preferredLabel)  if self.arcrole == XbrlConst.parentChild and self.preferredLabel else (),
                ("contextElement", self.contextElement)  if self.arcrole in (XbrlConst.all, XbrlConst.notAll)  else (),
                ("typedDomain", self.toModelObject.typedDomainElement.qname)  # type: ignore[attr-defined]
                  if self.arcrole == XbrlConst.hypercubeDimension and
                     isinstance(self.toModelObject,ModelConcept) and
                     self.toModelObject.isTypedDimension and
                     self.toModelObject.typedDomainElement is not None  else (),
                ("closed", self.closed) if self.arcrole in (XbrlConst.all, XbrlConst.notAll)  else (),
                ("usable", self.usable) if self.arcrole == XbrlConst.domainMember  else (),
                ("targetRole", self.targetRole) if self.arcrole.startswith(XbrlConst.dimStartsWith) else (),
                ("order", self.order),
                ("priority", self.priority)) + \
               (("from", self.fromModelObject.qname),) if isinstance(self.fromModelObject,ModelObject) else ()

    def __repr__(self) -> str:
        return ("modelRelationship[{0}, linkrole: {1}, arcrole: {2}, from: {3}, to: {4}, {5}, line {6}]"
                .format(self.objectIndex, os.path.basename(self.linkrole), os.path.basename(self.arcrole),
                        self.fromModelObject.qname if isinstance(self.fromModelObject, ModelObject) else "??",
                        self.toModelObject.qname if isinstance(self.toModelObject, ModelObject) else "??",
                        self.modelDocument.basename, self.sourceline))

    @property
    def viewConcept(self) -> ModelConcept | None:
        if isinstance(self.toModelObject, ModelConcept):
            return self.toModelObject
        elif isinstance(self.fromModelObject, ModelConcept):
            return self.fromModelObject
        return None

from arelle.ModelObjectFactory import elementSubstitutionModelClass
elementSubstitutionModelClass.update((
     (XbrlConst.qnXlExtended, ModelLink),
     (XbrlConst.qnXlLocator, ModelLocator),
     (XbrlConst.qnXlResource, ModelResource),
     (XbrlConst.qnLinkLabelLink, ModelLink), # needed for dynamic object creation (e.g., loadFromExcel, OIM)
     (XbrlConst.qnLinkReferenceLink, ModelLink),
     (XbrlConst.qnLinkFootnoteLink, ModelLink),
     (XbrlConst.qnLinkPresentationLink, ModelLink),
     (XbrlConst.qnLinkCalculationLink, ModelLink),
     (XbrlConst.qnLinkDefinitionLink, ModelLink),
     (XbrlConst.qnGenLink, ModelLink),
    ))
