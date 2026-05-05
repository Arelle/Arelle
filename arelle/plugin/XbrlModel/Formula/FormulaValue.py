"""
FormulaValue.py - Value representation for XBRL Query and Rules Language interpreter.

Wraps Python scalars and OIM model objects (XbrlFact, XbrlConcept, XbrlCube, etc.)
together with their alignment signature so the interpreter can carry alignment context
through every sub-expression without repeated lookups.

See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, auto
from typing import Any, Dict, FrozenSet, List, Optional, Tuple, TYPE_CHECKING

from arelle.ModelValue import QName

if TYPE_CHECKING:
    from arelle.plugin.XbrlModel.XbrlReport import XbrlFact
    from arelle.plugin.XbrlModel.XbrlConcept import XbrlConcept
    from arelle.plugin.XbrlModel.XbrlCube import XbrlCube
    from arelle.plugin.XbrlModel.XbrlNetwork import XbrlNetwork
    from arelle.plugin.XbrlModel.XbrlModel import XbrlCompiledModel


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------

class FormulaValueType(Enum):
    NONE = auto()       # the 'none' literal
    SKIP = auto()       # the 'skip' sentinel (stops iteration without error)
    BOOLEAN = auto()
    INTEGER = auto()
    FLOAT = auto()
    DECIMAL = auto()
    STRING = auto()
    QNAME = auto()
    DATE = auto()
    DATETIME = auto()
    DURATION = auto()
    FACT = auto()           # XbrlFact
    FACT_SET = auto()       # list[XbrlFact] (unaligned collection)
    CONCEPT = auto()        # XbrlConcept
    CUBE = auto()           # XbrlCube
    NETWORK = auto()        # XbrlNetwork
    TAXONOMY = auto()       # XbrlCompiledModel
    SET = auto()            # frozenset[FormulaValue]
    LIST = auto()           # list[FormulaValue]
    DICT = auto()           # dict[FormulaValue, FormulaValue]
    SEVERITY = auto()       # error | warning | ok | pass


# ---------------------------------------------------------------------------
# Alignment signature
#
# An alignment signature is an immutable mapping  dim_qname → value  for all
# dimensions EXCEPT the concept (xbrl:concept).  Two facts are aligned when
# their signatures are equal.  We store it as a frozenset of (QName, value)
# tuples so it can be used as a dict key.
# ---------------------------------------------------------------------------

AlignmentKey = FrozenSet[Tuple[QName, Any]]


def alignmentKeyOf(fact: "XbrlFact", conceptDimQn: Optional[QName] = None) -> AlignmentKey:
    """
    Build the alignment key for a fact: all dimensions except xbrl:concept.

    Parameters
    ----------
    fact:
        The XbrlFact object whose `factDimensions` dict will be inspected.
    conceptDimQn:
        QName of the concept dimension (e.g. xbrl:concept).  If None, defaults
        to a well-known value.
    """
    from arelle.ModelValue import qname as makeQName
    if conceptDimQn is None:
        conceptDimQn = makeQName("https://xbrl.org/2021", "concept")

    items: List[Tuple[QName, Any]] = []
    for dimQn, value in fact.factDimensions.items():
        if dimQn == conceptDimQn:
            continue
        # Normalise typed-dimension values to something hashable
        hashable_val = _makeHashable(value)
        items.append((dimQn, hashable_val))
    return frozenset(items)


def _makeHashable(value: Any) -> Any:
    """Convert mutable/complex values to hashable equivalents for alignment keys."""
    if isinstance(value, dict):
        return frozenset((k, _makeHashable(v)) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return tuple(_makeHashable(v) for v in value)
    if isinstance(value, set):
        return frozenset(_makeHashable(v) for v in value)
    return value


# ---------------------------------------------------------------------------
# FormulaValue
# ---------------------------------------------------------------------------

@dataclass
class FormulaValue:
    """
    A typed value produced by the formula interpreter.

    Attributes
    ----------
    type:
        One of the `FormulaValueType` enum members.
    value:
        The underlying Python / OIM object.
    alignment:
        The alignment key inherited from any fact(s) that contributed to this
        value.  None for non-fact scalars (literals, taxonomy objects, etc.).
    tagBindings:
        Mapping of tag-name → FormulaValue for fact references tagged with '#'.
        E.g.  @Assets#a  creates tag 'a' bound to the fact value.
    """
    type: FormulaValueType
    value: Any
    alignment: Optional[AlignmentKey] = field(default=None, compare=False)
    tagBindings: Dict[str, "FormulaValue"] = field(default_factory=dict, compare=False)

    # ------------------------------------------------------------------
    # Convenient constructors
    # ------------------------------------------------------------------

    @classmethod
    def fromFact(cls, fact: "XbrlFact", tag: Optional[str] = None,
                 conceptDimQn: Optional[QName] = None) -> "FormulaValue":
        """Wrap an XbrlFact, capturing its primary numeric/string value and alignment key."""
        # Retrieve the first factValue's value (OIM facts can have multiple values, but
        # the formula language treats the primary value as the scalar).
        raw = None
        if fact.factValues:
            fv = next(iter(fact.factValues))
            raw = fv.value
        fv_obj = cls(
            type=FormulaValueType.FACT,
            value=fact,
            alignment=alignmentKeyOf(fact, conceptDimQn),
        )
        if tag:
            fv_obj.tagBindings[tag] = fv_obj
        return fv_obj

    @classmethod
    def fromScalar(cls, value: Any) -> "FormulaValue":
        """Infer type from a Python scalar."""
        if value is None:
            return cls(FormulaValueType.NONE, None)
        if isinstance(value, bool):
            return cls(FormulaValueType.BOOLEAN, value)
        if isinstance(value, int):
            return cls(FormulaValueType.INTEGER, value)
        if isinstance(value, float):
            return cls(FormulaValueType.FLOAT, value)
        if isinstance(value, Decimal):
            return cls(FormulaValueType.DECIMAL, value)
        if isinstance(value, str):
            return cls(FormulaValueType.STRING, value)
        if isinstance(value, QName):
            return cls(FormulaValueType.QNAME, value)
        return cls(FormulaValueType.STRING, str(value))

    @classmethod
    def none(cls) -> "FormulaValue":
        return cls(FormulaValueType.NONE, None)

    @classmethod
    def skip(cls) -> "FormulaValue":
        return cls(FormulaValueType.SKIP, None)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def isNone(self) -> bool:
        return self.type == FormulaValueType.NONE

    @property
    def isSkip(self) -> bool:
        return self.type == FormulaValueType.SKIP

    @property
    def isFact(self) -> bool:
        return self.type == FormulaValueType.FACT

    @property
    def isNumeric(self) -> bool:
        return self.type in (FormulaValueType.INTEGER, FormulaValueType.FLOAT,
                             FormulaValueType.DECIMAL)

    def numericValue(self) -> Decimal:
        """Return Decimal representation for arithmetic. Raises TypeError if not numeric."""
        if self.type == FormulaValueType.FACT:
            # Unwrap to primary fact value
            if self.value.factValues:
                fv = next(iter(self.value.factValues))
                raw = fv.value
                if raw is None:
                    raise TypeError("Fact value is nil")
                return Decimal(str(raw))
            raise TypeError("Fact has no factValues")
        if self.type == FormulaValueType.DECIMAL:
            return self.value
        if self.type in (FormulaValueType.INTEGER, FormulaValueType.FLOAT):
            return Decimal(str(self.value))
        raise TypeError(f"Cannot convert {self.type} to numeric")

    def mergeAlignment(self, other: "FormulaValue") -> Optional[AlignmentKey]:
        """
        Merge the alignment keys of two values.

        Returns the common alignment key if both have one and they are compatible
        (identical), otherwise raises FormulaAlignmentError.
        """
        if self.alignment is None:
            return other.alignment
        if other.alignment is None:
            return self.alignment
        if self.alignment == other.alignment:
            return self.alignment
        raise FormulaAlignmentError(
            f"Alignment mismatch: {self.alignment!r} vs {other.alignment!r}"
        )

    def __repr__(self) -> str:
        if self.type == FormulaValueType.FACT:
            return f"FormulaValue(FACT, {self.value.name!r})"
        return f"FormulaValue({self.type.name}, {self.value!r})"


# ---------------------------------------------------------------------------
# Special value singletons
# ---------------------------------------------------------------------------

NONE_VALUE = FormulaValue(FormulaValueType.NONE, None)
SKIP_VALUE = FormulaValue(FormulaValueType.SKIP, None)
TRUE_VALUE = FormulaValue(FormulaValueType.BOOLEAN, True)
FALSE_VALUE = FormulaValue(FormulaValueType.BOOLEAN, False)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class FormulaRuntimeError(Exception):
    """Raised for recoverable formula execution errors (bad type, missing fact, etc.)."""


class FormulaAlignmentError(FormulaRuntimeError):
    """Raised when two sub-expressions have incompatible alignment signatures."""


class FormulaIterationStop(Exception):
    """
    Raised inside the interpreter to stop processing an iteration
    (e.g. when a fact query returns no matching facts).
    """


class FormulaSkip(Exception):
    """Raised when a 'skip' value propagates to a rule level — silently suppresses output."""
