"""
:mod:`arelle.ModelDtsObjuect`
~~~~~~~~~~~~~~~~~~~

.. module:: arelle.ModelDtsObject
   :copyright: Copyright 2010-2012 Mark V Systems Limited, All rights reserved.
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
from collections import defaultdict
import os, sys
from lxml import etree
import decimal
from arelle import (arelle_c, XmlUtil, XbrlConst, XbrlUtil, UrlUtil, Locale, ModelValue, XmlValidate)
from arelle.XmlValidate import UNVALIDATED, VALID
from arelle.ModelObject import ModelObject

ModelFact = None
ModelAttribute = None
anonymousTypeSuffix = None



class ModelConcept(arelle_c.ModelConcept):
    """
    .. class:: ModelConcept(modelDocument)
    
    Particle Model element term
    
    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    def __init__(self, *args):
        #print("pyMdlC init {}".format(args))
        super(ModelConcept, self).__init__(*args) 
        
    def isAttrId(self, attrClarkName):
        """Used by XbrlUtil.py to determine if attribute name is an ID type
        """
        attrkey = "_isAttrId_" + attrClarkName
        try:
            return self.attrs[attrkey]
        except KeyError:
            isId = False
            modelType = self.type
            if modelType is not None:
                attrQn = arelle_c.ModelValue.qname(attrClarkName)
                attrTypes = modelType.attributes
                if attrQn in attrTypes:
                    isId = attrTypes[attrQn].baseXsdType == "ID"
            self.attrs[attrkey] = isId
            return isId
    
    def label(self,preferredLabel=None,fallbackToQname=True,lang=None,strip=False,linkrole=None,linkroleHint=None):
        """Returns effective label for concept, using preferredLabel role (or standard label if None), 
        absent label falls back to element qname (prefixed name) if specified, lang falls back to 
        tool-config language if none, leading/trailing whitespace stripped (trimmed) if specified.  
        Does not look for generic labels (use superclass genLabel for generic label).
        
        :param preferredLabel: label role (standard label if not specified)
        :type preferredLabel: str
        :param fallbackToQname: if True and no matching label, then element qname is returned
        :type fallbackToQname: bool
        :param lang: language code requested (otherwise configuration specified language is returned)
        :type lang: str
        :param strip: specifies removal of leading/trailing whitespace from returned label
        :type strip: bool
        :param linkrole: specifies linkrole desired (wild card if not specified)
        :type linkrole: str
        :returns: label matching parameters, or element qname if fallbackToQname requested and no matching label
        """
        if preferredLabel is None: preferredLabel = XbrlConst.standardLabel
        if preferredLabel == XbrlConst.conceptNameLabelRole: return str(self.qname)
        labelsRelationshipSet = self.modelXbrl.relationshipSet(XbrlConst.conceptLabel,linkrole)
        if labelsRelationshipSet:
            label = labelsRelationshipSet.label(self, preferredLabel, lang, linkroleHint=linkroleHint)
            if label is not None:
                if strip: return label.strip()
                return Locale.rtlString(label, lang=lang)
        return str(self.qname) if fallbackToQname else None
    
    def relationshipToResource(self, resourceObject, arcrole):    
        """For specified object and resource (all link roles), returns first 
        modelRelationshipObject that relates from this element to specified resourceObject. 

        :param resourceObject: resource to find relationship to
        :type resourceObject: ModelObject
        :param arcrole: specifies arcrole for search
        :type arcrole: str
        :returns: ModelRelationship
        """ 
        relationshipSet = self.modelXbrl.relationshipSet(arcrole)
        if relationshipSet:
            for modelRel in relationshipSet.fromModelObject(self):
                if modelRel.toModelObject == resourceObject:
                    return modelRel
        return None
    

    def dereference(self):
        """(ModelConcept) -- If element is a ref (instead of name), provides referenced modelConcept object, else self"""
        ref = self.get("ref")
        if ref:
            qn = self.schemaNameQname(ref, isQualifiedForm=self.isQualifiedForm)
            return self.modelXbrl.qnameConcepts.get(qn)
        return self

    @property
    def propertyView(self):
        # find default and other labels
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
                     tuple((eVal,eElt.genLabel()) 
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
                ("type", self.typeQName),
                ("subst grp", self.substitutionGroupQName),
                ("period type", self.periodType) if self.periodType else (),
                ("balance", self.balance) if self.balance else (),
                _facets,
                _refProperty)
        
    def __repr__(self):
        return ("modelConcept[{0}, qname: {1}, type: {2}, abstract: {3}, {4}, line {5}]"
                .format(self.objectIndex, self.qname, self.typeQName, self.abstract,
                        self.modelDocument.basename, self.sourceline))

    @property
    def viewConcept(self):
        return self
            


class RelationStatus:
    Unknown = 0
    EFFECTIVE = 1
    OVERRIDDEN = 2
    PROHIBITED = 3
    INEFFECTIVE = 4
    
arcCustAttrsExclusions = {XbrlConst.xlink, "use","priority","order","weight","preferredLabel"}
    

