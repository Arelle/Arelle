from __future__ import annotations

from typing import TYPE_CHECKING, Any

from arelle.utils.Equivalence import partitionIntoEquivalenceClasses

if TYPE_CHECKING:
    from collections.abc import Iterable
    from arelle.ModelXbrl import ModelXbrl
    from arelle.ModelInstanceObject import ModelContext

class ContextHashKey:
    __slots__ = ('context', 'dimensionalAspectModel', 'hash')
    context: ModelContext
    dimensionalAspectModel: bool
    hash: int

    def __init__(self, context: ModelContext, dimensionalAspectModel: bool) -> None:
        self.context = context
        self.dimensionalAspectModel = dimensionalAspectModel
        self.hash = self.context.contextDimAwareHash if dimensionalAspectModel else self.context.contextNonDimAwareHash

    def __eq__(self, o: Any) -> bool:
        if isinstance(o, ContextHashKey):
            return self.dimensionalAspectModel == o.dimensionalAspectModel and self.context.isEqualTo(o.context, self.dimensionalAspectModel)
        return NotImplemented

    def __hash__(self) -> int:
        return self.hash

def partitionContexts(contexts: Iterable[ModelContext], dimensionalAspectModel: bool) -> dict[ContextHashKey, tuple[ModelContext, ...]]:
    return partitionIntoEquivalenceClasses(contexts, lambda c: ContextHashKey(c, dimensionalAspectModel))

def partitionModelXbrlContexts(modelXbrl: ModelXbrl) -> dict[ContextHashKey, tuple[ModelContext, ...]]:
    return partitionContexts(modelXbrl.contexts.values(), dimensionalAspectModel=modelXbrl.hasXDT)

def getDuplicateContextGroups(modelXbrl: ModelXbrl) -> list[tuple[ModelContext, ...]]:
    return [partition for partition in partitionModelXbrlContexts(modelXbrl).values() if len(partition) > 1]
