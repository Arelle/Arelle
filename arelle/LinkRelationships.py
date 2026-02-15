from __future__ import annotations

from collections import defaultdict
from itertools import chain
from typing import TYPE_CHECKING, Callable, cast

from arelle import XbrlConst
from arelle.typing import ModelResourceBase, LocPrototypeBase

if TYPE_CHECKING:
    from arelle.ModelDtsObject import ModelLink, ModelRelationship, ModelResource
    from arelle.ModelValue import QName
    from arelle.PrototypeDtsObject import LinkPrototype, LocPrototype

ModelRelationship = None  # type: ignore[assignment,misc]


class LinkRelationships:
    _relationships: tuple[ModelRelationship, ...] | None
    _relationshipsByArcrole: dict[str, tuple[ModelRelationship, ...]] | None
    _relationshipsByArcroleArcqname: dict[str, dict[QName, tuple[ModelRelationship, ...]]] | None
    _dimensionRelationships: tuple[ModelRelationship, ...] | None
    _formulaRelationships: tuple[ModelRelationship, ...] | None
    _tableRenderingRelationships: tuple[ModelRelationship, ...] | None

    def initRelationships(self) -> None:
        self._relationships = None
        self._relationshipsByArcrole = None
        self._relationshipsByArcroleArcqname = None
        self._dimensionRelationships = None
        self._formulaRelationships = None
        self._tableRenderingRelationships = None

    @property
    def relationships(self) -> tuple[ModelRelationship, ...]:
        if self._relationships is None:
            self._collectRelationships()
            assert self._relationships is not None
        return self._relationships

    @property
    def relationshipsByArcrole(self) -> dict[str, tuple[ModelRelationship, ...]]:
        if self._relationshipsByArcrole is None:
            self._collectRelationships()
            assert self._relationshipsByArcrole is not None
        return self._relationshipsByArcrole

    @property
    def relationshipsByArcroleArcqname(self) -> dict[str, dict[QName, tuple[ModelRelationship, ...]]]:
        if self._relationshipsByArcroleArcqname is None:
            self._collectRelationships()
            assert self._relationshipsByArcroleArcqname is not None
        return self._relationshipsByArcroleArcqname

    @property
    def dimensionRelationships(self) -> tuple[ModelRelationship, ...]:
        # "XBRL-dimensions"
        if self._dimensionRelationships is None:
            self._dimensionRelationships = self._relationshipsForArcrolePredicate(XbrlConst.isDimensionArcrole)
            assert self._dimensionRelationships is not None
        return self._dimensionRelationships

    @property
    def formulaRelationships(self) -> tuple[ModelRelationship, ...]:
        # "XBRL-formulae"
        if self._formulaRelationships is None:
            self._formulaRelationships = self._relationshipsForArcrolePredicate(XbrlConst.isFormulaArcrole)
            assert self._formulaRelationships is not None
        return self._formulaRelationships

    @property
    def tableRenderingRelationships(self) -> tuple[ModelRelationship, ...]:
        # "Table-rendering"
        if self._tableRenderingRelationships is None:
            self._tableRenderingRelationships = self._relationshipsForArcrolePredicate(XbrlConst.isTableRenderingArcrole)
            assert self._tableRenderingRelationships is not None
        return self._tableRenderingRelationships

    def _relationshipsForArcrolePredicate(self, predicate: Callable[[str], bool]) -> tuple[ModelRelationship, ...]:
        return tuple(
            relationship
            for arcrole, relationships in self.relationshipsByArcrole.items()
            if predicate(arcrole)
            for relationship in relationships
        )

    def _collectRelationships(self) -> None:
        global ModelRelationship
        if ModelRelationship is None:
            from arelle.ModelDtsObject import ModelRelationship
        linkElement = cast('ModelLink | LinkPrototype', self)
        linkrole = linkElement.role
        labeledResources = linkElement.labeledResources
        modelDocument = linkElement.modelDocument
        allRelationships = []
        relationshipsByArcrole = defaultdict(list)
        relationshipsByArcroleArcqname: dict[str, dict[QName, list[list[ModelRelationship]]]] = defaultdict(lambda: defaultdict(list))
        for linkChild in linkElement:
            linkChildArcrole = linkChild.get("{http://www.w3.org/1999/xlink}arcrole")
            if not (linkChild.get("{http://www.w3.org/1999/xlink}type") == "arc" and linkChildArcrole):
                continue
            relationships = []
            fromLabel = linkChild.get("{http://www.w3.org/1999/xlink}from")
            toLabel = linkChild.get("{http://www.w3.org/1999/xlink}to")
            if fromLabel is None or toLabel is None:
                continue
            for fromResource in labeledResources[fromLabel]:
                if not isinstance(fromResource, (ModelResourceBase, LocPrototypeBase)):
                    continue
                fromResource = cast('ModelResource | LocPrototype', fromResource)
                for toResource in labeledResources[toLabel]:
                    if not isinstance(toResource, (ModelResourceBase, LocPrototypeBase)):
                        continue
                    toResource = cast('ModelResource | LocPrototype', toResource)
                    fromResourceElement = fromResource.dereference()  # type: ignore [no-untyped-call]
                    toResourceElement = toResource.dereference()  # type: ignore [no-untyped-call]
                    modelRel = ModelRelationship(modelDocument, linkChild, fromResourceElement, toResourceElement, linkrole=linkrole)  # type: ignore [no-untyped-call]
                    relationships.append(modelRel)
            allRelationships.append(relationships)
            relationshipsByArcrole[linkChildArcrole].append(relationships)
            relationshipsByArcroleArcqname[linkChildArcrole][linkChild.qname].append(relationships)

        self._relationships = tuple(chain.from_iterable(allRelationships))
        self._relationshipsByArcrole = {
            arcrole: tuple(chain.from_iterable(relationships))
            for arcrole, relationships in relationshipsByArcrole.items()
        }
        self._relationshipsByArcroleArcqname = {
            arcrole: {arcqname: tuple(chain.from_iterable(relationships)) for arcqname, relationships in relationshipsByArcqname.items()}
            for arcrole, relationshipsByArcqname in relationshipsByArcroleArcqname.items()
        }
