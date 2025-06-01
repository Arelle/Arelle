'''
See COPYRIGHT.md for copyright information.
Python version specific utilities

do not convert 3 to 2
'''
from __future__ import annotations

import fractions
import os
import subprocess
import sys
from collections import OrderedDict
from collections.abc import Iterable, Iterator, Mapping, MappingView, MutableSet, Set
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Generic, TypeVar

from arelle.typing import OptionalString

STR_NUM_TYPES = (str, int, float, Decimal, fractions.Fraction)

# python 3 unquote, because py2 unquote doesn't do utf-8 correctly
def py3unquote(string, encoding='utf-8', errors='replace'):
    """Replace %xx escapes by their single-character equivalent. The optional
    encoding and errors parameters specify how to decode percent-encoded
    sequences into Unicode characters, as accepted by the bytes.decode()
    method.
    By default, percent-encoded sequences are decoded with UTF-8, and invalid
    sequences are replaced by a placeholder character.

    unquote('abc%20def') -> 'abc def'.
    """
    if string == '':
        return string
    res = string.split('%')
    if len(res) == 1:
        return string
    if encoding is None:
        encoding = 'utf-8'
    if errors is None:
        errors = 'replace'
    # pct_sequence: contiguous sequence of percent-encoded bytes, decoded
    pct_sequence = b''
    string = res[0]
    for item in res[1:]:
        try:
            if not item:
                raise ValueError
            pct_sequence += str(bytearray.fromhex(item[:2]))
            rest = item[2:]
            if not rest:
                # This segment was just a single percent-encoded character.
                # May be part of a sequence of code units, so delay decoding.
                # (Stored in pct_sequence).
                continue
        except ValueError:
            rest = '%' + item
        # Encountered non-percent-encoded characters. Flush the current
        # pct_sequence.
        string += pct_sequence.decode(encoding, errors) + rest
        pct_sequence = b''
    if pct_sequence:
        # Flush the final pct_sequence
        string += pct_sequence.decode(encoding, errors)
    return string

def pyTypeName(object):
    try:
        objectClass = object.__class__
        classModule = objectClass.__module__
        className = objectClass.__name__
        if classModule == 'builtins':
            return className
        fullname = classModule + '.' + className
        if fullname == 'arelle.ModelValue.DateTime':
            if object.dateOnly:
                fullname += '-dateOnly'
            else:
                fullname += '-dateTime'
        return fullname
    except:
        return str(type(object))

def pyNamedObject(name, *args, **kwargs):
    try:
        import builtins
        objectConstructor = builtins.__dict__[name]
        return objectConstructor(*args, **kwargs)
    except:
        return None

def lcStr(value): # lower case first letter of string
    if len(value):
        return value[0].lower() + value[1:]
    return str

def strTruncate(value, length) -> str:
    _s = str(value).strip()
    if len(_s) <= length:
        return _s
    return _s[0:length-3] + "..."


def normalizeSpace(s: OptionalString) -> OptionalString:
    if isinstance(s, str):
        return " ".join(s.split())
    return s

SEQUENCE_TYPES = (tuple,list,set,frozenset,MappingView)
def flattenSequence(x, sequence=None) -> list[Any]:
    if sequence is None:
        if not isinstance(x, SEQUENCE_TYPES):
            if x is None:
                return [] # none as atomic value is an empty sequence in xPath semantics
            return [x]
        sequence = []
    for el in x:
        if isinstance(el, SEQUENCE_TYPES):
            flattenSequence(el, sequence)
        else:
            sequence.append(el)
    return sequence

def flattenToSet(x, _set=None):
    if _set is None:
        if not isinstance(x, SEQUENCE_TYPES):
            if x is None:
                return set() # none as atomic value is an empty sequence in xPath semantics
            return {x}
        _set = set()
    for el in x:
        if isinstance(el, SEQUENCE_TYPES):
            flattenToSet(el, _set)
        else:
            _set.add(el)
    return _set

class attrdict(dict):
    """ utility to simulate an object with named fields from a dict """
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.__dict__ = self

class OrderedDefaultDict(OrderedDict):
    """ call with default factory and optional sorted initial entries
        e.g., OrderedDefaultDict(list, ((1,11),(2,22),...))
    """
    def __init__(self, *args):
        self.default_factory = None
        if len(args) > 0:
            # arg0 is default_factory
            self.default_factory = args[0]
        if len(args) > 1:
            # arg1 is initial contents
            super(OrderedDefaultDict, self).__init__(args[1])
        else:
            super(OrderedDefaultDict, self).__init__()

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        _missingValue = self.default_factory()
        self[key] = _missingValue
        return _missingValue


T = TypeVar('T')

class OrderedSet(MutableSet[T]):
    """
    OrderedSet implementation copied from Python recipe:
    https://code.activestate.com/recipes/576694/
    """

    def __init__(self, iterable: Iterable[T] | None = None) -> None:
        self.end: list[Any] = []
        end = self.end
        end += [None, end, end]            # sentinel node for doubly linked list
        self.map: dict[T, list[Any]] = {}  # key --> [key, prev, next]
        if iterable is not None:
            self.update(iterable)

    def __getitem__(self, index: int) -> T:
        if not isinstance(index, int):
            raise TypeError("Index must be an integer")
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError("Index out of range")
        end = self.end
        curr = end[2]
        for _ in range(index):
            curr = curr[2]
        return curr[0]

    def __len__(self) -> int:
        return len(self.map)

    def __contains__(self, key: object) -> bool:
        return key in self.map

    def add(self, key: T) -> None:
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def update(self, other: Iterable[T]) -> None:
        for key in other:
            self.add(key)

    def discard(self, key: T) -> None:
        if key in self.map:
            key, prev, next = self.map.pop(key)
            prev[2] = next
            next[1] = prev

    def __iter__(self) -> Iterator[T]:
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self) -> Iterator[T]:
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def pop(self, last: bool = True) -> T:
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key

    def __repr__(self) -> str:
        if not self:
            return f'{self.__class__.__name__}()'
        return f'{self.__class__.__name__}({list(self)!r})'

    def __eq__(self, other: object) -> bool:
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        if isinstance(other, Iterable):
            return set(self) == set(other)
        return NotImplemented

class FrozenOrderedSet(Set[T]):
    """
    Like frozenset vs set, this is the immutable counterpart to OrderedSet.
    Maintains insertion order and provides set-like operations without mutation.
    """

    def __init__(self, iterable: Iterable[T] | None = None) -> None:
        if iterable is None:
            self._items: tuple[T, ...] = ()
            self._set: frozenset[T] = frozenset()
        else:
            unique_items = dict.fromkeys(iterable)
            self._items = tuple(unique_items.keys())
            self._set = frozenset(unique_items.keys())
        self._hash: int | None = None

    def __getitem__(self, index: int) -> T:
        return self._items[index]

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, key: object) -> bool:
        return key in self._set

    def __iter__(self) -> Iterator[T]:
        return iter(self._items)

    def __reversed__(self) -> Iterator[T]:
        return reversed(self._items)

    def __repr__(self) -> str:
        if not self:
            return f'{self.__class__.__name__}()'
        return f'{self.__class__.__name__}({self._items!r})'

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (FrozenOrderedSet, OrderedSet)):
            return len(self) == len(other) and list(self) == list(other)
        if isinstance(other, Iterable):
            return set(self) == set(other)
        return NotImplemented

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = hash(self._items)
        return self._hash

KT = TypeVar('KT')
VT = TypeVar('VT')


class FrozenDict(Generic[KT, VT], Mapping[KT, VT]):
    def __init__(self, data: Mapping[KT, VT] | None = None) -> None:
        self._dict: Mapping[KT, VT] = MappingProxyType(dict(data) if data is not None else dict())
        self._hash: int | None = None

    def __getitem__(self, key: KT) -> VT:
        return self._dict[key]

    def __iter__(self) -> Iterator[KT]:
        return iter(self._dict)

    def __len__(self) -> int:
        return len(self._dict)

    def __repr__(self) -> str:
        if not self:
            return f'{self.__class__.__name__}()'
        return f"{self.__class__.__name__}({self._dict})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, FrozenDict):
            return self._dict == other._dict
        if isinstance(other, Mapping):
            return self._dict == other
        return NotImplemented

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = hash(tuple(sorted(self._dict.items())))
        return self._hash


def Fraction(numerator,denominator=None):
    if denominator is None:
        if isinstance(numerator, (fractions.Fraction,str,Decimal)):
            return Fraction(numerator)
    elif isinstance(numerator, Decimal) and isinstance(denominator, Decimal):
        return Fraction(int(numerator), int(denominator))
    return Fraction(numerator, denominator)

def pyObjectSize(obj, seen=None):
    """Recursively finds size of objects"""
    size = sys.getsizeof(obj)
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    # Important mark as seen *before* entering recursion to gracefully handle
    # self-referential objects
    seen.add(obj_id)
    if isinstance(obj, dict):
        size += sum([pyObjectSize(v, seen) for v in obj.values()])
        size += sum([pyObjectSize(k, seen) for k in obj.keys()])
    elif hasattr(obj, '__dict__'):
        size += pyObjectSize(obj.__dict__, seen)
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
        size += sum([pyObjectSize(i, seen) for i in obj])
    return size


def tryRunCommand(*args: str) -> str | None:
    """
    Tries to return the results of the provided command.
    Returns stdout or None if the command exists with a non-zero code.
    """
    try:
        return subprocess.run(
            args,
            capture_output=True,
            check=True,
            text=True,
            # A call to get std handle throws an OSError if stdin is not specified when run on Windows as a service.
            stdin=subprocess.PIPE,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None

def isLegacyAbs(path: str) -> bool:
    """
    Implements legacy behavior of os.path.isabs() prior to Python 3.13
    where True was returned for paths beginning with single slashes on Windows.
    """
    if os.path.isabs(path):
        return True
    from arelle.SystemInfo import PlatformOS
    if PlatformOS.getPlatformOS() == PlatformOS.WINDOWS:
        return path.startswith(("/", "\\"))
    return False
