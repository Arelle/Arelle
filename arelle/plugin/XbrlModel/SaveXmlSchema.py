'''
See COPYRIGHT.md for copyright information.

Saves OIM Taxonomy Model into XML Schema (for inline XBRL and XML schema/instance validation)

Formula parameters:
   oimTaxonomySaveSeparateNamespaces = true | yes means to save namespaces in separate files

'''
import os, io, sys
from decimal import Decimal
import tkinter
from collections import OrderedDict
from typing import GenericAlias, Optional, Union, _UnionGenericAlias, get_origin
from arelle.ModelDocument import Type, create as createModelDocument
from arelle.ModelValue import qname, QName, timeInterval
from arelle.PythonUtil import  OrderedSet
from arelle.XmlUtil import addChild
from .ViewXbrlTaxonomyObject import ViewXbrlTxmyObj
from .XbrlAbstract import XbrlAbstract
from .XbrlConcept import XbrlConcept
from .XbrlConst import qnBuiltInCoreObjectsTaxonomy, xbrl
from .XbrlDimension import XbrlDimension, XbrlMember
from .XbrlObject import XbrlModelClass, XbrlObject
from .XbrlModel import XbrlCompiledModel
from .XbrlModule import XbrlModule
from .XbrlTypes import QNameKeyType, XbrlModuleType, DefaultTrue, DefaultFalse, DefaultZero

CLASSES_SAVEABLE_TO_XML_SCHEMA = OrderedSet((
    XbrlAbstract,
    XbrlConcept,
    XbrlDimension,
    XbrlMember))

STANDARD_NAMESPACES = {
    xbrl
    }

xsd = "http://www.w3.org/2001/XMLSchema"
link = "http://www.xbrl.org/2003/linkbase"
xbrli = "http://www.xbrl.org/2003/instance"

QN_ANNOTATION = qname(xsd, "xs:annotation")
QN_APPINFO = qname(xsd, "xs:appinfo")
QN_IMPORT = qname(xsd, "xs:import")
QN_ELEMENT = qname(xsd, "xs:element")
QN_SUBS_GROUP = qname(xsd, "xs:substitutionGroup")
QN_ROLE_TYPE = qname(link, "link:roleType")
QN_ROLE_TYPE = qname(link, "link:roleType")
QN_DEFINITION = qname(link, "link:definition")
QN_USED_ON = qname(link, "link:usedOn")

QN_BALANCE = qname(xbrli, "xbrli:balance")
QN_PERIOD_TYPE = qname(xbrli    , "xbrli:periodType")


def saveXmlSchema(cntlr, txmyMdl, saveXMLSchemaFiles):
    prefixNamespaces = {} # prefix and namespaces of savable objects
    txmyModules = set()

    # identify schema namespaces to save
    for objClass in CLASSES_SAVEABLE_TO_XML_SCHEMA:
        for obj in txmyMdl.filterNamedObjects(objClass):
            if obj.name.namespaceURI not in STANDARD_NAMESPACES:
                prefixNamespaces[obj.name.prefix] = obj.name.namespaceURI
                txmyModules.add(obj.taxonomy)

    taxonomyFiles = dict((f"{pfx}.xsd", ns) for pfx, ns in sorted(prefixNamespaces.items()))

    # create entry point schema
    doc = createModelDocument(
             txmyMdl,
             Type.SCHEMA,
             os.path.join(saveXMLSchemaFiles, "entry.xsd"),
             isEntry=True,
             # initialComment="extracted from OIM {}".format(mappedUri),
             documentEncoding="utf-8",
             base='', # block pathname from becomming absolute
             initialXml='''
<schema
   notargetNamespace
   attributeFormDefault="unqualified"
   elementFormDefault="qualified"
   xmlns="http://www.w3.org/2001/XMLSchema">
'''
            )
    for fileName, ns in taxonomyFiles.items():
        addChild(doc.xmlRootElement, QN_IMPORT, attributes={
            "namespace": ns,
            "schemaLocation": fileName})
    doc.save(doc.filepath)

    # create XSD files
    for fileName, nsURI in taxonomyFiles.items():

        doc = createModelDocument(
             txmyMdl,
             Type.SCHEMA,
             os.path.join(saveXMLSchemaFiles, fileName),
             isEntry=False,
             # initialComment="extracted from OIM {}".format(mappedUri),
             documentEncoding="utf-8",
             base='', # block pathname from becomming absolute
             initialXml=f'''
<schema
   targetNamespace="{nsURI}"
   attributeFormDefault="unqualified"
   elementFormDefault="qualified"
   xmlns="http://www.w3.org/2001/XMLSchema"
   xmlns:{fileName[:-4]}="{nsURI}"
   {''.join(f'xmlns:{prefix}="{namespaceURI}"\n' for prefix, namespaceURI in prefixNamespaces.items())}
   xmlns:dtr-types="http://www.xbrl.org/dtr/type/2024-01-31"
   xmlns:link="http://www.xbrl.org/2003/linkbase"
   xmlns:xbrli="http://www.xbrl.org/2003/instance"
   xmlns:xlink="http://www.w3.org/1999/xlink"
   xmlns:xbrldt="http://xbrl.org/2005/xbrldt"/>
'''
        )
        schemaElt = doc.xmlRootElement
        addChild(schemaElt, QN_IMPORT, attributes={
            "namespace": "http://www.xbrl.org/2003/XLink",
            "schemaLocation": "http://www.xbrl.org/2003/xl-2003-12-31.xsd"})

        # element declarations
        for objClass in CLASSES_SAVEABLE_TO_XML_SCHEMA:
            for obj in txmyMdl.filterNamedObjects(objClass):
                if obj.name.namespaceURI == nsURI:
                    attributes = {"id": f"{obj.name.prefix}_{obj.name.localName}",
                                  "name": obj.name.localName}
                    if objClass == XbrlAbstract:
                        attributes["abstract"] = True
                        conceptElt = addChild(schemaElt,
                                              QN_ELEMENT,
                                              attributes=attributes)
                    elif objClass in (XbrlAbstract, XbrlConcept, XbrlMember):
                        if objClass in (XbrlAbstract, XbrlMember):
                            attributes["abstract"] = "true"
                        if getattr(obj, "nillable", None):
                            attributes["nillable"] = "true"
                        periodType = obj.propertyObjectValue(QN_PERIOD_TYPE)
                        if periodType:
                            attributes[QN_PERIOD_TYPE.clarkNotation] = periodType
                        balance = obj.propertyObjectValue(QN_BALANCE)
                        if balance:
                            attributes[QN_BALANCE.clarkNotation] = balance
                        if objClass  == XbrlConcept:
                            dataType = obj.dataType
                            if dataType:
                                attributes["type"] = str(dataType)
                            attributes["substitutionGroup"] = "xbrli:item"
                            attributes[QN_PERIOD_TYPE.clarkNotation] = "duration"
                        conceptElt = addChild(schemaElt,
                                              QN_ELEMENT,
                                              attributes=attributes)
                    elif objClass == XbrlDimension:
                        attributes["abstract"] = attributes["nillable"] = "true"
                        attributes["substitutionGroup"] = "xbrldt:dimensionItem"
                        conceptElt = addChild(schemaElt,
                                              QN_ELEMENT,
                                              attributes=attributes)

        doc.save()