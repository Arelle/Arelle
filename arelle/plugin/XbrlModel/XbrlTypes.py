"""
See COPYRIGHT.md for copyright information.
"""

from typing import GenericAlias, ClassVar, _GenericAlias, _UnionGenericAlias, get_origin, Union
from typing_extensions import TypeAlias, List
from arelle.ModelValue import QName
from ordered_set import OrderedSet

XbrlLabelAlias: TypeAlias = "XbrlLabel"
XbrlLayoutAlias: TypeAlias = "XbrlLayout"
XbrlDataTableAlias: TypeAlias = "XbrlDataTable"
XbrlPropertyAlias: TypeAlias = "XbrlProperty"
XbrlTaxonomyModelAlias: TypeAlias = "XbrlCompiledModel"
XbrlModuleAlias: TypeAlias = "XbrlModule"
XbrlUnitTypeAlias: TypeAlias = "XbrlUnitType"

class QNameKeyType(QName): # a QName which is also the primary key for parent collection object
    pass
class SQNameKeyType(QName): # an SQName which is also the primary key for parent collection object
    pass
class strKeyType(str): # a str which is also the primary key for parent collection object
    pass
class DefaultTrue: # a bool which if absent defaults to true
    pass
class DefaultFalse: # a bool which if absent defaults to false
    pass
class DefaultZero: # a number which if absent defaults to zero
    pass
class DefaultOne: # a number which if absent defaults to one
    pass
class OptionalList(List): # list of objects like OrderedSet which is absent (None) when no objects
    pass
class OptionalDict(dict): # dict of objects which is absent (None) when no contents
    pass
class NonemptySet(OrderedSet): # set of objects like OrderedSet which is present and nonempty
    pass


# ── Type Annotation Introspection Helpers ─────────────────────────────
#
# Python type annotations use several internal representations depending on
# how the type is written:
#
#   OrderedSet[XbrlConcept]           → GenericAlias        (plain collection)
#   Optional[NonemptySet[XbrlCube]]   → _UnionGenericAlias  (Union[NonemptySet[XbrlCube], None])
#   list[str]                         → GenericAlias
#   dict[QName, Any]                  → GenericAlias
#   ClassVar[...]                     → _GenericAlias
#
# Code that introspects these annotations to iterate collections, check
# element types, or unwrap Optional wrappers has historically used ad-hoc
# isinstance checks that handled GenericAlias but missed _UnionGenericAlias,
# causing bugs when properties were changed from OrderedSet to Optional[NonemptySet].
#
# These helpers provide a single place for type introspection, so callers
# don't need to repeat the unwrapping logic or risk missing a variant.
# ──────────────────────────────────────────────────────────────────────

_COLLECTION_ORIGINS = (set, list, OrderedSet, dict)

def collectionInfo(propType):
    """Introspect a property type annotation to extract collection details.

    Handles plain collections (``OrderedSet[X]``), Optional collections
    (``Optional[NonemptySet[X]]``), and internal _GenericAlias forms.

    Returns:
        A tuple ``(origin, elementType, keyType, isOptional)`` where:
        - *origin* is the collection class (OrderedSet, set, dict, list, etc.)
        - *elementType* is the type of elements (or values for dicts)
        - *keyType* is the dict key type, or None for non-dicts
        - *isOptional* is True if the type was Optional[...]

        Returns ``None`` if *propType* is not a collection type.
    """
    isOptional = False
    innerType = propType

    # Unwrap Optional[X] → X  (i.e. Union[X, None])
    if isinstance(propType, _UnionGenericAlias):
        args = getattr(propType, "__args__", ())
        if args and args[-1] is type(None):
            isOptional = True
            innerType = args[0]

    # GenericAlias: OrderedSet[X], dict[K,V], set[X], list[X]
    if isinstance(innerType, GenericAlias):
        origin = innerType.__origin__
        args = innerType.__args__
        if origin in _COLLECTION_ORIGINS or (isinstance(origin, type) and issubclass(origin, _COLLECTION_ORIGINS)):
            if issubclass(origin, dict) and len(args) == 2:
                return (origin, args[1], args[0], isOptional)
            elif len(args) >= 1:
                return (origin, args[0], None, isOptional)

    # _GenericAlias: internal typing forms like OptionalList[X]
    if isinstance(innerType, _GenericAlias):
        origin = getattr(innerType, "__origin__", None)
        if origin is not None and isinstance(origin, type) and issubclass(origin, _COLLECTION_ORIGINS):
            args = getattr(innerType, "__args__", ())
            if args:
                if issubclass(origin, dict) and len(args) == 2:
                    return (origin, args[1], args[0], isOptional)
                return (origin, args[0], None, isOptional)

    return None


def isOptionalType(propType):
    """Return True if propType is Optional[X] (Union[X, None])."""
    if isinstance(propType, _UnionGenericAlias):
        args = getattr(propType, "__args__", ())
        return bool(args) and args[-1] is type(None)
    return False


def isClassVar(propType):
    """Return True if propType is ClassVar[...]."""
    return isinstance(propType, _GenericAlias) and getattr(propType, "__origin__", None) is ClassVar