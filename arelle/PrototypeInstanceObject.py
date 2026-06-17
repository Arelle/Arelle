'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Sequence
# for python 3.10
from typing_extensions import Self

from arelle import XbrlConst, XmlUtil
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelValue import QName, DateTime, dateTime, DATETIME
from arelle.ModelObject import ModelObject

if TYPE_CHECKING:
    from arelle.ModelManager import ModelManager
    from arelle.ModelXbrl import ModelXbrl

Aspect: Any = None


class FactPrototype:  # behaves like a fact for dimensional validity testing
    def __init__(
            self,
            v: Any,
            aspectValues: dict[int | QName, str | ModelObject | QName | DateTime | Sequence[Any]] | None = None
        ) -> None:
        global Aspect
        if Aspect is None:
            from arelle.Aspect import Aspect
        self.modelXbrl: ModelXbrl = v.modelXbrl
        if aspectValues is None:
            aspectValues = {}
        self.aspectEntryObjectId = aspectValues.get("aspectEntryObjectId", None)  # type: ignore[call-overload]
        if Aspect.CONCEPT in aspectValues:
            qname = aspectValues[Aspect.CONCEPT]
            self.qname: QName | None = qname  # type: ignore[assignment]
            self.concept: ModelConcept | None = v.modelXbrl.qnameConcepts.get(qname)
            self.isItem: bool = self.concept is not None and self.concept.isItem
            self.isTuple: bool = self.concept is not None and self.concept.isTuple
        else:
            self.qname = None # undefined concept
            self.concept = None # undefined concept
            self.isItem = False # don't block aspectMatches
            self.isTuple = False
        if Aspect.LOCATION in aspectValues:
            self.parent: Any = aspectValues[Aspect.LOCATION]
            try:
                self.isTuple = self.parent.isTuple  # type: ignore[union-attr]
            except AttributeError:
                self.isTuple = False
        else:
            self.parent = v.modelXbrl.modelDocument.xmlRootElement
        self.isNumeric: bool = self.concept is not None and self.concept.isNumeric
        self.context: ContextPrototype | None = ContextPrototype(v, aspectValues)
        self.unit: UnitPrototype | None
        if {Aspect.UNIT, Aspect.UNIT_MEASURES, Aspect.MULTIPLY_BY, Aspect.DIVIDE_BY} & aspectValues.keys():
            self.unit = UnitPrototype(v, aspectValues)
        else:
            self.unit = None
        self.factObjectId: str | None = None
        v.modelXbrl.factPrototypeNextIndex = self.objectIndex = getattr(v.modelXbrl, "factPrototypeNextIndex", 0) + 1
        self.uniqueUUID: uuid.UUID = uuid.uuid4()

    def clear(self) -> None:
        if self.context is not None:
            self.context.clear()
        self.__dict__.clear()  # delete local attributes

    def objectId(self) -> str:
        return "_factPrototype_" + str(self.qname)

    def getparent(self) -> Any:
        return self.parent

    @property
    def propertyView(self) -> tuple[tuple[str, str] | tuple[()], ...]:
        dims = self.context.qnameDims  # type: ignore[union-attr]
        return (("concept", str(self.qname) if self.concept is not None else "not specified"),  # type: ignore[return-value]
                ("dimensions", "({0})".format(len(dims)),
                  tuple(dimVal.propertyView if dimVal is not None else (str(dim.qname), "None")
                        for dim, dimVal in sorted(dims.items(), key=lambda i:i[0])
                        if hasattr(dimVal, "propertyView")))
                  if dims else (),
                )

    @property
    def viewConcept(self) -> Self:
        return self


class ContextPrototype:  # behaves like a context
    def __init__(
            self,
            v: Any,
            aspectValues: dict[int | QName, str | ModelObject | QName | DateTime | Sequence[Any]]
        ) -> None:
        self.modelXbrl: ModelXbrl = v.modelXbrl
        self.segDimVals: dict[ModelConcept, DimValuePrototype] = {}
        self.scenDimVals: dict[ModelConcept, DimValuePrototype] = {}
        self._nonDimValues: dict[int | str, list[ModelObject]] = {}
        self.qnameDims: dict[QName, DimValuePrototype] = {}
        self.entityIdentifierHash: int | None = None
        self.entityIdentifier: tuple[str | None, str | None] = (None, None)
        self.isStartEndPeriod: bool = False
        self.isInstantPeriod: bool = False
        self.isForeverPeriod: bool = False
        self.startDatetime: DateTime | None = None
        self.endDatetime: DateTime | None = None
        self.instantDatetime: DateTime | None = None

        for aspect, aspectValue in aspectValues.items():
            if aspect == Aspect.PERIOD_TYPE:
                if aspectValue == "forever":
                    self.isForeverPeriod = True
                elif aspectValue == "instant":
                    self.isInstantPeriod = True
                elif aspectValue == "duration":
                    self.isStartEndPeriod = True
            elif aspect == Aspect.START:
                self.isStartEndPeriod = True
                self.startDatetime = aspectValue  # type: ignore[assignment]
            elif aspect == Aspect.END:
                self.isStartEndPeriod = True
                if isinstance(aspectValue, DateTime) and aspectValue.dateOnly: # passed by reference, need a new datetime object
                    aspectValue = dateTime(aspectValue, addOneDay=True, type=DATETIME)  # type: ignore[assignment]
                self.endDatetime = aspectValue  # type: ignore[assignment]
            elif aspect == Aspect.INSTANT:
                self.isInstantPeriod = True
                if isinstance(aspectValue, DateTime) and aspectValue.dateOnly: # passed by reference, need a new datetime object
                    aspectValue = dateTime(aspectValue, addOneDay=True, type=DATETIME)  # type: ignore[assignment]
                self.endDatetime = self.instantDatetime = aspectValue  # type: ignore[assignment]
            elif aspect == Aspect.VALUE:
                self.entityIdentifier = (self.entityIdentifier[0], aspectValue)  # type: ignore[assignment]
                self.entityIdentifierHash = hash(self.entityIdentifier)
            elif aspect == Aspect.SCHEME:
                self.entityIdentifier = (aspectValue, self.entityIdentifier[1])  # type: ignore[assignment]
                self.entityIdentifierHash = hash(self.entityIdentifier)
            elif aspect in (Aspect.COMPLETE_SEGMENT, Aspect.COMPLETE_SCENARIO, "segment", Aspect.NON_XDT_SEGMENT, "scenario", Aspect.NON_XDT_SCENARIO):
                if aspectValue == [XbrlConst.qnFormulaOccEmpty]:
                    self._nonDimValues[aspect] = []  # type: ignore[index]
                else:
                    self._nonDimValues[aspect] = aspectValue  # type: ignore[index,assignment]
            elif isinstance(aspect, QName):
                try: # if a DimVal, then it has a suggested context element
                    contextElement = aspectValue.contextElement  # type: ignore[union-attr]
                    isTyped = aspectValue.isTyped  # type: ignore[union-attr]
                    aspectValue = (aspectValue.memberQname or aspectValue.typedMember)  # type: ignore[union-attr]
                except AttributeError: # probably is a QName, not a dim value or dim prototype
                    contextElement = v.modelXbrl.qnameDimensionContextElement.get(aspect)
                    isTyped = False
                if v.modelXbrl.qnameDimensionDefaults.get(aspect) != aspectValue or isTyped: # not a default
                    try:
                        dimConcept = v.modelXbrl.qnameConcepts[aspect]
                        dimValPrototype = DimValuePrototype(v, dimConcept, aspect, aspectValue, contextElement)  # type: ignore[arg-type]
                        self.qnameDims[aspect] = dimValPrototype
                        if contextElement != "scenario": # could be segment, ambiguous, or no information
                            self.segDimVals[dimConcept] = dimValPrototype
                        else:
                            self.scenDimVals[dimConcept] = dimValPrototype
                    except KeyError:
                        pass
            elif isinstance(aspectValue, ModelObject):
                # these do not expect a string aspectValue, but the object model aspect value
                if aspect == Aspect.PERIOD: # period xml object
                    context = aspectValue.getparent()
                    for contextPeriodAttribute in ("isForeverPeriod", "isStartEndPeriod", "isInstantPeriod",
                                                   "startDatetime", "endDatetime", "instantDatetime",
                                                   "periodHash"):
                        setattr(self, contextPeriodAttribute, getattr(context, contextPeriodAttribute, None))
                elif aspect == Aspect.ENTITY_IDENTIFIER: # entitytIdentifier xml object
                    context = aspectValue.getparent().getparent()  # type: ignore[union-attr]
                    for entityIdentAttribute in ("entityIdentifier", "entityIdentifierHash"):
                        setattr(self, entityIdentAttribute, getattr(context, entityIdentAttribute, None))

    def clear(self) -> None:
        try:
            for dim in self.qnameDims.values():
                # only clear if its a prototype, but not a 'reused' model object from other instance
                if isinstance(dim, DimValuePrototype):
                    dim.clear()
        except AttributeError:
            pass
        self.__dict__.clear()  # delete local attributes

    def dimValue(self, dimQname: QName) -> DimValuePrototype | QName | None:
        """(ModelDimension or QName) -- ModelDimension object if dimension is reported (in either context element), or QName of dimension default if there is a default, otherwise None"""
        try:
            return self.qnameDims[dimQname]
        except KeyError:
            try:
                return self.modelXbrl.qnameDimensionDefaults[dimQname]
            except KeyError:
                return None

    def dimValues(self, contextElement: str | None, oppositeContextElement: bool = False) -> dict[ModelConcept, DimValuePrototype]:
        if not oppositeContextElement:
            return self.segDimVals if contextElement == "segment" else self.scenDimVals
        else:
            return self.scenDimVals if contextElement == "segment" else self.segDimVals

    def nonDimValues(self, contextElement: str | int) -> list[ModelObject]:
        return self._nonDimValues.get(contextElement, [])

    def isEntityIdentifierEqualTo(self, cntx2: ContextPrototype) -> bool:
        return self.entityIdentifierHash is None or self.entityIdentifierHash == cntx2.entityIdentifierHash

    def isPeriodEqualTo(self, cntx2: ContextPrototype) -> bool:
        if self.isForeverPeriod:
            return cntx2.isForeverPeriod
        elif self.isStartEndPeriod:
            if not cntx2.isStartEndPeriod:
                return False
            return self.startDatetime == cntx2.startDatetime and self.endDatetime == cntx2.endDatetime
        elif self.isInstantPeriod:
            if not cntx2.isInstantPeriod:
                return False
            return self.instantDatetime == cntx2.instantDatetime
        else:
            return False


class DimValuePrototype:
    typedMember: QName | None
    isExplicit: bool
    isTyped: bool
    memberQname: QName | None
    member: ModelConcept | None

    def __init__(
        self,
        v: Any,
        dimConcept: ModelConcept | None,
        dimQname: QName,
        mem: QName | ModelObject | None,
        contextElement: str | None,
    ) -> None:
        from arelle.ModelValue import QName
        if dimConcept is None: # note no concepts if modelXbrl.skipDTS:
            dimConcept = v.modelXbrl.qnameConcepts.get(dimQname)
        self.dimension: ModelConcept | None = dimConcept
        self.dimensionQname: QName = dimQname
        self.contextElement: str | None = contextElement
        if isinstance(mem, QName):
            self.isExplicit = True
            self.isTyped = False
            self.memberQname = mem
            self.member = v.modelXbrl.qnameConcepts.get(mem)
            self.typedMember = None
        else:
            self.isExplicit = False
            self.isTyped = True
            self.typedMember = mem  # type: ignore[assignment]
            self.memberQname = None
            self.member = None

    def clear(self) -> None:
        self.__dict__.clear()  # delete local attributes

    @property
    def propertyView(self) -> tuple[str, str]:
        if self.isExplicit:
            return (str(self.dimensionQname), str(self.memberQname))
        else:
            return (str(self.dimensionQname),
                    XmlUtil.xmlstring(self.typedMember, stripXmlns=True, prettyPrint=True)
                    if isinstance(self.typedMember, ModelObject) else "None")


class UnitPrototype:  # behaves like a context
    def __init__(
            self,
            v: Any,
            aspectValues: dict[int | QName, str | ModelObject | QName | DateTime | Sequence[Any]]
        ) -> None:
        self.modelXbrl: ModelXbrl = v.modelXbrl
        self.hash: int | None = None
        self.measures: tuple[tuple[Any, ...], ...] | None = None
        self.isSingleMeasure: bool | None = None
        for aspect, aspectValue in aspectValues.items():
            if aspect == Aspect.UNIT and aspectValue is not None: # entitytIdentifier xml object
                for unitAttribute in ("measures", "hash", "isSingleMeasure", "isDivide"):
                    setattr(self, unitAttribute, getattr(aspectValue, unitAttribute, None))
            elif aspect == Aspect.MULTIPLY_BY:
                measuresList = tuple(sorted(aspectValue))  # type: ignore[arg-type]
                if not self.measures:
                    self.measures = (measuresList, ())
                else:
                    self.measures = (measuresList, self.measures[1])
                self.hash = hash(self.measures)
            elif aspect == Aspect.DIVIDE_BY:
                measuresList = tuple(sorted(aspectValue))  # type: ignore[arg-type]
                if not self.measures:
                    self.measures = ((), measuresList)
                    self.hash = hash(self.measures)
                else:
                    self.measures = (self.measures[0], measuresList)
                self.hash = hash(self.measures)

    def clear(self) -> None:
        self.__dict__.clear()  # delete local attributes

    def isEqualTo(self, unit2: UnitPrototype | None) -> bool:
        if unit2 is None or unit2.hash != self.hash:
            return False
        return unit2 is self or self.measures == unit2.measures

    @property
    def propertyView(self) -> tuple[tuple[str, Any], ...]:
        measures = self.measures
        if measures[1]:  # type: ignore[index]
            return (tuple(("mul", m) for m in measures[0]) +  # type: ignore[index]
                   tuple(("div", d) for d in measures[1]))  # type: ignore[index]
        else:
            return tuple(("measure", m) for m in measures[0])  # type: ignore[index]


class XbrlPrototype: # behaves like ModelXbrl
    def __init__(self, modelManager: ModelManager, uri: str, *arg: Any, **kwarg: Any) -> None:
        self.modelManager: ModelManager = modelManager
        self.errors: list[Any] = []
        self.skipDTS: bool = False
        from arelle.PrototypeDtsObject import DocumentPrototype
        self.modelDocument = DocumentPrototype(self, uri)  # type: ignore[arg-type]

    def close(self) -> None:
        self.modelDocument.clear()
        self.__dict__.clear()  # delete local attributes
