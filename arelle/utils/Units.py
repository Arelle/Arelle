from __future__ import annotations

from typing import TYPE_CHECKING, Any

from arelle.utils.Equivalence import partitionIntoEquivalenceClasses

if TYPE_CHECKING:
    from collections.abc import Iterable
    from arelle.ModelXbrl import ModelXbrl
    from arelle.ModelInstanceObject import ModelUnit

class UnitHashKey:
    __slots__ = ('unit', 'hash')
    unit: ModelUnit
    hash: int

    def __init__(self, unit: ModelUnit) -> None:
        self.unit = unit
        self.hash = self.unit.hash

    def __eq__(self, o: Any) -> bool:
        if isinstance(o, UnitHashKey):
            return self.unit.isEqualTo(o.unit)
        return NotImplemented

    def __hash__(self) -> int:
        return self.hash

def partitionUnits(units: Iterable[ModelUnit]) -> dict[UnitHashKey, tuple[ModelUnit, ...]]:
    return partitionIntoEquivalenceClasses(units, UnitHashKey)

def partitionModelXbrlUnits(modelXbrl: ModelXbrl) -> dict[UnitHashKey, tuple[ModelUnit, ...]]:
    return partitionUnits(modelXbrl.units.values())

def getDuplicateUnitGroups(modelXbrl: ModelXbrl) -> list[tuple[ModelUnit, ...]]:
    return [partition for partition in partitionModelXbrlUnits(modelXbrl).values() if len(partition) > 1]
