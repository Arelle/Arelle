'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

import decimal
import os
from collections import defaultdict
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, ItemsView

from arelle import XbrlConst
from arelle.LinkRelationships import LinkRelationships
from arelle.ModelDocumentType import ModelDocumentType
from arelle.XmlValidateConst import VALID
from arelle.typing import LocPrototypeBase, PrototypeElementTreeBase, PrototypeObjectBase

if TYPE_CHECKING:
    from arelle.ModelDocument import ModelDocument, ModelDocumentReference
    from arelle.ModelDtsObject import ModelResource
    from arelle.ModelObject import ModelObject, ModelAttribute
    from arelle.ModelValue import QName, TypeXValue, TypeSValue
    from arelle.ModelXbrl import ModelXbrl


class PrototypeObject(PrototypeObjectBase):
    def __init__(
        self,
        modelDocument: ModelDocument | DocumentPrototype,
        sourceElement: ModelObject | None = None,
    ) -> None:
        self.modelDocument = modelDocument
        self.sourceElement = sourceElement
        self.attributes: dict[str, str] = {}

    @property
    def sourceline(self) -> int | None:
        return self.sourceElement.sourceline if self.sourceElement is not None else None

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.attributes.get(key, default)

    def itersiblings(self, **kwargs: Any) -> Iterator[ModelObject | PrototypeObject]:
        """Method proxy for itersiblings() of lxml arc element"""
        return self.sourceElement.itersiblings(**kwargs) if self.sourceElement is not None else iter(())

    def getparent(self) -> ModelObject | PrototypeObject | None:
        """(_ElementBase) -- Method proxy for getparent() of lxml arc element"""
        return self.sourceElement.getparent() if self.sourceElement is not None else None

    def iterchildren(self) -> Iterator[ModelObject | PrototypeObject]:
        yield from ()  # no children

    def iterdescendants(self) -> Iterator[ModelObject | PrototypeObject]:
        for elt in self.iterchildren():
            yield elt
            for e in elt.iterdescendants():
                yield e


class LinkPrototype(PrototypeObject, LinkRelationships):  # behaves like a ModelLink for relationship prototyping
    def __init__(
        self,
        modelDocument: ModelDocument | DocumentPrototype,
        parent: ModelObject | PrototypeObject | None,
        qname: QName,
        role: str | None,
        sourceElement: ModelObject | None = None,
    ) -> None:
        super().__init__(modelDocument, sourceElement)
        self._parent = parent
        self.modelXbrl: ModelXbrl = modelDocument.modelXbrl
        self.qname: QName = qname
        self.elementQname: QName = qname
        self.namespaceURI: str | None = qname.namespaceURI
        self.localName: str = qname.localName
        self.role: str | None = role
        # children are arc and loc elements or prototypes
        self.childElements: list[ModelObject | PrototypeObject] = []
        self.text: str | None = None
        self.textValue: str | None = None
        self.attributes = {"{http://www.w3.org/1999/xlink}type": "extended"}
        if role:
            self.attributes["{http://www.w3.org/1999/xlink}role"] = role
        self.labeledResources: dict[str, list[ModelObject]] = defaultdict(list)
        self.initRelationships()

    def clear(self) -> None:
        self.__dict__.clear()  # dereference here, not an lxml object, don't use superclass clear()

    def __iter__(self) -> Iterator[ModelObject | PrototypeObject]:
        return iter(self.childElements)

    def getparent(self) -> ModelObject | PrototypeObject | None:
        return self._parent

    def iterchildren(self) -> Iterator[ModelObject | PrototypeObject]:
        return iter(self.childElements)


class LocPrototype(PrototypeObject, LocPrototypeBase):
    def __init__(
        self,
        modelDocument: ModelDocument | DocumentPrototype,
        parent: ModelObject | PrototypeObject | None,
        label: str,
        locObject: str | ModelObject | ModelResource,
        role: str | None = None,
        sourceElement: ModelObject | None = None,
    ) -> None:
        super().__init__(modelDocument, sourceElement)
        self._parent = parent
        self.modelXbrl: ModelXbrl = modelDocument.modelXbrl
        self.qname: QName = XbrlConst.qnLinkLoc
        self.elementQname: QName = self.qname
        self.namespaceURI: str | None = self.qname.namespaceURI
        self.localName: str = self.qname.localName
        self.text: str | None = None
        self.textValue: str | None = None
        # children are arc and loc elements or prototypes
        self.attributes = {
            "{http://www.w3.org/1999/xlink}type": "locator",
            "{http://www.w3.org/1999/xlink}label": label,
        }
        # add an href if it is a 1.1 id
        if isinstance(locObject, str):  # it is an id
            self.attributes["{http://www.w3.org/1999/xlink}href"] = "#" + locObject
        if role:
            self.attributes["{http://www.w3.org/1999/xlink}role"] = role
        self.locObject: str | ModelObject | ModelResource = locObject

    def clear(self) -> None:
        self.__dict__.clear()  # dereference here, not an lxml object, don't use superclass clear()

    @property
    def xlinkLabel(self) -> str | None:
        return self.attributes.get("{http://www.w3.org/1999/xlink}label")

    def dereference(self) -> Any:
        if isinstance(self.locObject, str):  # dereference by ID
            idObjects = getattr(self.modelDocument, "idObjects", {})
            return idObjects.get(self.locObject, None)  # id may not exist
        else:  # it's an object pointer
            return self.locObject

    def getparent(self) -> ModelObject | PrototypeObject | None:
        return self._parent

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.attributes.get(key, default)


class ArcPrototype(PrototypeObject):
    def __init__(
        self,
        modelDocument: ModelDocument | DocumentPrototype,
        parent: ModelObject | PrototypeObject | None,
        qname: QName,
        fromLabel: str,
        toLabel: str,
        linkrole: str,
        arcrole: str,
        order: str = "1",
        sourceElement: ModelObject | None = None,
    ) -> None:
        super().__init__(modelDocument, sourceElement)
        self._parent = parent
        self.modelXbrl: ModelXbrl = modelDocument.modelXbrl
        self.qname: QName = qname
        self.elementQname: QName = qname
        self.namespaceURI: str | None = qname.namespaceURI
        self.localName: str = qname.localName
        self.linkrole: str = linkrole
        self.arcrole: str = arcrole
        self.order: str = order
        self.text: str | None = None
        self.textValue: str | None = None
        # children are arc and loc elements or prototypes
        self.attributes = {
            "{http://www.w3.org/1999/xlink}type": "arc",
            "{http://www.w3.org/1999/xlink}from": fromLabel,
            "{http://www.w3.org/1999/xlink}to": toLabel,
            "{http://www.w3.org/1999/xlink}arcrole": arcrole,
        }
        # must look validated (because it can't really be validated)
        self.xValid: int = VALID
        self.xValue: TypeXValue = None
        self.sValue: TypeSValue = None
        self.xAttributes: dict[str, ModelAttribute] = {}

    @property
    def orderDecimal(self) -> decimal.Decimal:
        return decimal.Decimal(self.order)

    def clear(self) -> None:
        self.__dict__.clear()  # dereference here, not an lxml object, don't use superclass clear()

    @property
    def arcElement(self) -> ModelObject | None:
        return self.sourceElement if self.sourceElement is not None else None

    def getparent(self) -> ModelObject | PrototypeObject | None:
        return self._parent

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.attributes.get(key, default)

    def items(self) -> ItemsView[str, str]:
        return self.attributes.items()


class DocumentPrototype:
    def __init__(
        self,
        modelXbrl: ModelXbrl,
        uri: str,
        base: str | None = None,
        referringElement: ModelObject | None = None,
        isEntry: bool = False,
        isDiscovered: bool = False,
        isIncluded: bool | None = None,
        namespace: str | None = None,
        reloadCache: bool = False,
        **kwargs: Any,
    ) -> None:
        self.modelXbrl = modelXbrl
        self.skipDTS: bool = modelXbrl.skipDTS
        self.modelDocument: DocumentPrototype = self
        if referringElement is not None:
            if referringElement.localName == "schemaRef":
                self.type: int = ModelDocumentType.SCHEMA
            elif referringElement.localName == "linkbaseRef":
                self.type = ModelDocumentType.LINKBASE
            else:
                self.type = ModelDocumentType.UnknownXML
        else:
            self.type = ModelDocumentType.UnknownXML
        normalizedUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(uri, base)
        self.filepath: str | None = modelXbrl.modelManager.cntlr.webCache.getfilename(normalizedUri, filenameOnly=True)
        self.uri: str = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(self.filepath)
        self.basename: str = os.path.basename(self.filepath) if self.filepath else ""
        self.targetNamespace: str | None = None
        self.referencesDocument: dict[ModelDocument, ModelDocumentReference] = {}
        self.hrefObjects: list[tuple[ModelObject, ModelDocument | None, str | None]] = []
        self.schemaLocationElements: set[ModelObject] = set()
        self.referencedNamespaces: set[str] = set()
        self.inDTS: bool = False
        self.xmlRootElement: ModelObject | None = None


    def clear(self) -> None:
        self.__dict__.clear()  # dereference here, not an lxml object, don't use superclass clear()


class PrototypeElementTree(PrototypeElementTreeBase):  # equivalent to _ElementTree for parenting root element in non-lxml situations
    def __init__(self, rootElement: ModelObject) -> None:
        self.rootElement = rootElement

    def getroot(self) -> ModelObject:
        return self.rootElement

    def iter(self) -> Iterator[ModelObject]:
        yield self.rootElement
        for e in self.rootElement.iterdescendants():
            yield e

    def ixIter(self, childOnly: bool = False) -> Iterator[ModelObject]:
        yield self.rootElement
        if not childOnly:
            for e in self.rootElement.ixIter(childOnly):  # type: ignore[attr-defined]
                yield e
