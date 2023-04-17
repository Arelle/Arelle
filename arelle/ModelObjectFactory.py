'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

from arelle.ModelObject import ModelObject, init as moduleObject_init
from typing import Any, Optional, TYPE_CHECKING, Type

if TYPE_CHECKING:
    from arelle.ModelValue import QName
    from arelle.ModelXbrl import ModelXbrl

elementSubstitutionModelClass: dict[Optional[QName], Type[ModelObject]] = {}

from lxml import etree
from arelle import XbrlConst, XmlUtil
from arelle.ModelValue import qnameNsLocalName
from arelle.ModelDtsObject import (
    ModelConcept,
    ModelAttribute,
    ModelAttributeGroup,
    ModelType,
    ModelGroupDefinition,
    ModelAll,
    ModelChoice,
    ModelSequence,
    ModelAny,
    ModelAnyAttribute,
    ModelEnumeration,
    ModelRoleType,
    ModelLocator,
    ModelLink,
    ModelResource,
)

from arelle.ModelRssItem import ModelRssItem
from arelle.ModelTestcaseObject import ModelTestcaseVariation

# would be circular imports, resolve at first use after static loading
ModelDocument: Any = None
ModelFact: Any = None


def parser(
        modelXbrl: ModelXbrl,
        baseUrl: str | None,
        target: None = None
) -> tuple[etree.XMLParser, KnownNamespacesModelObjectClassLookup, DiscoveringClassLookup]:
    moduleObject_init()  # init ModelObject globals
    _parser = etree.XMLParser(recover=True, huge_tree=True, target=target,
                              resolve_entities=False)
    return setParserElementClassLookup(_parser, modelXbrl, baseUrl)


def setParserElementClassLookup(
        _parser: etree.XMLParser,
        modelXbrl: ModelXbrl,
        baseUrl: str | None = None,
) -> tuple[etree.XMLParser, KnownNamespacesModelObjectClassLookup, DiscoveringClassLookup]:
    classLookup = DiscoveringClassLookup(modelXbrl, baseUrl)
    nsNameLookup = KnownNamespacesModelObjectClassLookup(modelXbrl, fallback=classLookup)
    _parser.set_element_class_lookup(nsNameLookup)
    return _parser, nsNameLookup, classLookup


SCHEMA = 1
LINKBASE = 2
VERSIONINGREPORT = 3
RSSFEED = 4


class KnownNamespacesModelObjectClassLookup(etree.CustomElementClassLookup):
    def __init__(self, modelXbrl: ModelXbrl, fallback: etree.ElementClassLookup | None = None) -> None:
        super(KnownNamespacesModelObjectClassLookup, self).__init__(fallback)
        self.modelXbrl = modelXbrl
        self.type: int | None = None

    def lookup(self, node_type: str, document: etree._Document, ns: str | None, ln: str) -> Type[etree.ElementBase] | None:
        # node_type is "element", "comment", "PI", or "entity"
        if node_type == "element":
            if ns == XbrlConst.xsd:
                if self.type is None:
                    self.type = SCHEMA
                if ln == "element":
                    return ModelConcept
                elif ln == "attribute":
                    return ModelAttribute
                elif ln == "attributeGroup":
                    return ModelAttributeGroup
                elif ln == "complexType" or ln == "simpleType":
                    return ModelType
                elif ln == "group":
                    return ModelGroupDefinition
                elif ln == "sequence":
                    return ModelSequence
                elif ln == "choice" or ln == "all":
                    return ModelChoice
                elif ln == "all":
                    return ModelAll
                elif ln == "any":
                    return ModelAny
                elif ln == "anyAttribute":
                    return ModelAnyAttribute
                elif ln == "enumeration":
                    return ModelEnumeration
            elif ns == XbrlConst.link:
                if self.type is None:
                    self.type = LINKBASE
                if ln == "roleType" or ln == "arcroleType":
                    return ModelRoleType
            elif ns == "http://edgar/2009/conformance":
                # don't force loading of test schema
                if ln == "variation":
                    return ModelTestcaseVariation
                else:
                    return ModelObject
            elif ln == "testcase" and (
                ns is None or ns in ("http://edgar/2009/conformance",) or ns.startswith("http://xbrl.org/")):
                return ModelObject
            elif ln == "variation" and (
                ns is None or ns in ("http://edgar/2009/conformance",) or ns.startswith("http://xbrl.org/")):
                return ModelTestcaseVariation
            elif ln == "testGroup" and ns == "http://www.w3.org/XML/2004/xml-schema-test-suite/":
                return ModelTestcaseVariation
            elif ln == "test-case" and ns == "http://www.w3.org/2005/02/query-test-XQTSCatalog":
                return ModelTestcaseVariation
            elif ns == XbrlConst.ver:
                if self.type is None:
                    self.type = VERSIONINGREPORT
            elif ns == "http://dummy":
                return etree.ElementBase
            if self.type is None and ln == "rss":
                self.type = RSSFEED
            elif self.type == RSSFEED:
                if ln == "item":
                    return ModelRssItem
                else:
                    return ModelObject

            # match specific element types or substitution groups for types
            return self.modelXbrl.matchSubstitutionGroup(qnameNsLocalName(ns, ln), elementSubstitutionModelClass)
        elif node_type == "comment":
            from arelle.ModelObject import ModelComment

            return ModelComment
        elif node_type == "PI":
            return etree.PIBase  # type: ignore[no-any-return]
        elif node_type == "entity":
            return etree.EntityBase  # type: ignore[no-any-return]
        # returning None delegates to fallback lookup classes
        return None


class DiscoveringClassLookup(etree.PythonElementClassLookup):  # type: ignore[misc]
    def __init__(self, modelXbrl: ModelXbrl, baseUrl: str | None, fallback: etree.ElementClassLookup | None = None) -> None:
        super(DiscoveringClassLookup, self).__init__(fallback)
        self.modelXbrl = modelXbrl
        self.streamingOrSkipDTS = modelXbrl.skipDTS or getattr(modelXbrl, "isStreamingMode", False)
        self.baseUrl = baseUrl
        self.discoveryAttempts: set[str] = set()
        global ModelFact, ModelDocument
        if ModelDocument is None:
            from arelle import ModelDocument
        if self.streamingOrSkipDTS and ModelFact is None:
            from arelle.ModelInstanceObject import ModelFact

    def lookup(self, document: etree._Document, proxyElement: etree._Element) -> Type[ModelObject]:
        # check if proxyElement's namespace is not known
        ns: str | None
        ns, sep, ln = proxyElement.tag.partition("}")
        if sep:
            ns = ns[1:]
        else:
            ln = ns
            ns = None
        if (ns and
            ns not in self.discoveryAttempts and
            ns not in self.modelXbrl.namespaceDocs):
            # is schema loadable?  requires a schemaLocation
            relativeUrl = XmlUtil.schemaLocation(proxyElement, ns)
            self.discoveryAttempts.add(ns)
            if relativeUrl:
                ModelDocument.loadSchemalocatedSchema(self.modelXbrl, proxyElement, relativeUrl, ns, self.baseUrl)

        modelObjectClass = self.modelXbrl.matchSubstitutionGroup(
            qnameNsLocalName(ns, ln), elementSubstitutionModelClass
        )

        if modelObjectClass is not None:
            return modelObjectClass
        elif self.streamingOrSkipDTS and ns not in (XbrlConst.xbrli, XbrlConst.link):
            # self.makeelementParentModelObject is set in streamingExtensions.py and ModelXbrl.createFact
            ancestor = proxyElement.getparent() or getattr(self.modelXbrl, "makeelementParentModelObject", None)
            while ancestor is not None:
                tag = ancestor.tag  # not a modelObject yet, just parser prototype
                if tag.startswith("{http://www.xbrl.org/2003/instance}") or tag.startswith("{http://www.xbrl.org/2003/linkbase}"):
                    if tag == "{http://www.xbrl.org/2003/instance}xbrl":
                        # element not parented by context or footnoteLink
                        return ModelFact  # type: ignore[no-any-return]
                    else:
                        break  # cannot be a fact
                ancestor = ancestor.getparent()

        xlinkType = proxyElement.get("{http://www.w3.org/1999/xlink}type")
        if xlinkType == "extended":
            return ModelLink
        elif xlinkType == "locator":
            return ModelLocator
        elif xlinkType == "resource":
            return ModelResource

        return ModelObject
