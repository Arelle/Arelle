from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from arelle.ModelValue import QName

if TYPE_CHECKING:
    from arelle.ModelInstanceObject import ModelFact


class FactAspectsCache:
    def __init__(self, maxSize: int) -> None:
        self._maxSize = maxSize if maxSize >= 0 else float("inf")
        self.clear()

    def clear(self) -> None:
        # Dictionaries and sets only undergo resizing upon insertion. Clearing them does not reclaim memory.
        self._size = 0
        self._prioritizedAspects: set[int | QName] = set()
        self._matchingAspects: defaultdict[
            ModelFact,
            defaultdict[
                ModelFact,
                defaultdict[int | QName, bool | None]
            ]
        ] = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: None)))

    @property
    def prioritizedAspects(self) -> set[int | QName]:
        return self._prioritizedAspects

    def evaluations(self, fact1: ModelFact, fact2: ModelFact) -> defaultdict[int | QName, bool | None]:
        return self._matchingAspects[fact1][fact2]

    def cacheMatch(self, fact1: ModelFact, fact2: ModelFact, aspect: int | QName) -> None:
        self._register(fact1, fact2, aspect, True)

    def cacheNotMatch(self, fact1: ModelFact, fact2: ModelFact, aspect: int | QName) -> None:
        self._prioritizedAspects.add(aspect)
        self._register(fact1, fact2, aspect, False)

    def _register(self, fact1: ModelFact, fact2: ModelFact, aspect: int | QName, value: bool) -> None:
        if self._size >= self._maxSize:
            # Stopping additions to the cache entirely is somewhat rudimentary. Alternative caching strategies, such as
            # LRU, were explored, but they demonstrated poorer performance on average across all tested documents. The
            # current strategy involves retaining the cache, but preventing additions once it reaches the maximum size.
            return
        self._size += 1
        self._matchingAspects[fact1][fact2][aspect] = value
        self._matchingAspects[fact2][fact1][aspect] = value

    def __repr__(self) -> str:
        return f"FactAspectsCache(size={self._size}, maxSize={self._maxSize}, prioritizedAspects={self._prioritizedAspects}, matchingAspects={self._matchingAspects})"
