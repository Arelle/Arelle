from __future__ import annotations

from collections import defaultdict
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    TypeVar,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from arelle.ModelXbrl import ModelXbrl

T = TypeVar('T')
K = TypeVar('K')

def partitionIntoEquivalenceClasses(items: Iterable[T], key: Callable[[T], K]) -> dict[K, tuple[T, ...]]:
    d = defaultdict(list)
    for item in items:
        d[key(item)].append(item)
    return {k: tuple(v) for k, v in d.items()}
