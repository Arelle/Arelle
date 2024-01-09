"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from _decimal import Decimal
from collections import defaultdict
from dataclasses import dataclass
from enum import auto, Flag, Enum
from functools import cached_property
from math import isnan
from typing import cast, Iterator, Any, SupportsFloat

from arelle import XmlValidateConst
from arelle.ModelInstanceObject import ModelFact, ModelContext, ModelUnit
from arelle.ModelValue import DateTime, QName, TypeXValue
from arelle.ValidateXbrlCalcs import rangeValue, inferredDecimals


@dataclass(frozen=True)
class DuplicateFactSet:
    facts: list[ModelFact]

    def __iter__(self) -> Iterator[ModelFact]:
        return iter(self.facts)

    @cached_property
    def areAllComplete(self) -> bool:
        """
        :return: Whether all facts in the set are complete duplicates of each other.
        """
        return self.areAllDecimalsEqual and self.areAllValueEqual

    @cached_property
    def areAllConsistent(self) -> bool:
        """
        :return: Whether all facts in the set are consistent duplicates of each other.
        """
        if self.areAllComplete:
            return True
        if self.areNumeric:
            # If facts are numeric but NOT complete duplicates,
            # they must be within rounding error to be consistent
            return self.areWithinRoundingError
        # If facts are not complete duplicates and not numeric, then they are not consistent
        return False

    @cached_property
    def areAllDecimalsEqual(self) -> bool:
        """
        :return: Whether all facts have matching decimals values.
        """
        firstFact = self.facts[0]
        for fact in self.facts[1:]:
            if firstFact.decimals != fact.decimals:
                # If facts do not have matching decimal values, they are not complete
                return False
        return True

    @cached_property
    def areAllValueEqual(self) -> bool:
        """
        :return: Whether all facts in this set are fact-value equal with each other.
        """
        firstFact = self.facts[0]
        for fact in self.facts[1:]:
            if not areFactsValueEqual(firstFact, fact):
                # If facts are not value-equal, they are not complete
                return False
        return True

    @cached_property
    def areAnyComplete(self) -> bool:
        """
        :return: Whether any facts in the set are complete duplicates of each other.
        """
        decimalsValueMap: dict[float | int, set[TypeFactValueEqualityKey]] = defaultdict(set)
        for fact in self.facts:
            decimals = inferredDecimals(fact)
            value = getFactValueEqualityKey(fact)
            decimalsValues = decimalsValueMap[decimals]
            if value in decimalsValues:
                return True
            decimalsValues.add(value)
        return False

    @cached_property
    def areAnyConsistent(self) -> bool:
        """
        :return: Whether any facts in the set are consistent duplicates of each other.
        """
        # Checking for any complete duplicates is inexpensive,
        # so check for that before worrying about decimal ranges.
        if self.areAnyComplete:
            return True
        if not self.areNumeric:
            # Non-numeric and incompete: inconsistent
            return False
        ranges: list[tuple[Decimal, Decimal, float | int]] = []
        for fact in self.facts:
            decimalsA = inferredDecimals(fact)
            lowerA, upperA, __, __ = rangeValue(fact.xValue, decimalsA)
            for lowerB, upperB, decimalsB in ranges:
                if decimalsB == decimalsA:
                    # We've already checked for complete duplicates,
                    # so any facts with matching decimals can not have matching values
                    # Different values, same decimals: not consistent
                    continue
                if lowerB <= upperA and upperB >= lowerA:
                    # Different values, different decimals, ranges overlap: consistent
                    return True
            ranges.append((lowerA, upperA, decimalsA))
        return False

    @cached_property
    def areAnyIncomplete(self) -> bool:
        """
        :return: Whether any facts in the set are not complete duplicates of each other.
        """
        return not self.areAllComplete

    @cached_property
    def areAnyInconsistent(self) -> bool:
        """
        :return: Whether any facts in the set are not consistent duplicates of each other.
        """
        if self.areNumeric:
            # If facts are numeric, they are inconsistent if they are not consistent
            return not self.areAllConsistent
        # If facts are not numeric, they are inconsistent if they are not fact-value equal
        return not self.areAllValueEqual

    @cached_property
    def areNumeric(self) -> bool:
        """
        :return: Whether the duplicate set consists of numeric facts.
        """
        return cast(bool, self.facts[0].isNumeric)

    @cached_property
    def areWithinRoundingError(self) -> bool:
        """
        :return: Whether all fact values are within rounding error of each other.
        """
        maxLower = Decimal("-Infinity")
        minUpper = Decimal("Infinity")
        decimalValues: dict[float | int, TypeXValue] = {}
        for fact in self.facts:
            value = fact.xValue
            if isnan(cast(SupportsFloat, value)):
                # NaN values are not comparable, can't be equal/consistent.
                return False
            decimals = inferredDecimals(fact)
            if decimals in decimalValues:
                if value != decimalValues[decimals]:
                    # Facts with the same `decimals` value MUST have the same numeric value in order to be considered consistent.
                    return False
            else:
                decimalValues[decimals] = value
            lower, upper, __, ___ = rangeValue(value, decimals)
            if lower > maxLower:
                maxLower = lower
            if upper < minUpper:
                minUpper = upper
            if minUpper < maxLower:
                # One fact's upper bound is less than another fact's lower bound, not consistent
                return False
        return True


class DuplicateType(Flag):
    NONE = 0
    INCONSISTENT = auto()
    CONSISTENT = auto()
    INCOMPLETE = auto()
    COMPLETE = auto()

    # Flags before 3.11 did not support iterating Flag values,
    # so we have to override with our own iterator. Remove when we no longer support 3.10
    def __iter__(self) -> Iterator[DuplicateType]:
        # num must be a positive integer
        num = self.value
        while num:
            b = num & (~num + 1)
            yield DuplicateType(b)
            num ^= b


class DuplicateTypeArg(Enum):
    NONE = 'none'
    INCONSISTENT = 'inconsistent'
    CONSISTENT = 'consistent'
    INCOMPLETE = 'incomplete'
    COMPLETE = 'complete'
    ALL = 'all'

    def duplicateType(self) -> DuplicateType:
        return DUPLICATE_TYPE_ARG_MAP.get(self, DuplicateType.NONE)


DUPLICATE_TYPE_ARG_MAP = {
    DuplicateTypeArg.NONE: DuplicateType.NONE,
    DuplicateTypeArg.INCONSISTENT: DuplicateType.INCONSISTENT,
    DuplicateTypeArg.CONSISTENT: DuplicateType.CONSISTENT,
    DuplicateTypeArg.INCOMPLETE: DuplicateType.INCOMPLETE,
    DuplicateTypeArg.COMPLETE: DuplicateType.COMPLETE,
    DuplicateTypeArg.ALL: DuplicateType.INCONSISTENT | DuplicateType.CONSISTENT,
}


def doesSetHaveDuplicateType(duplicateFacts: DuplicateFactSet, duplicateType: DuplicateType) -> bool:
    """
    :param duplicateFacts:
    :param duplicateType:
    :return: Whether the given duplicate fact set has any duplicates of the given type.
    """
    inconsistent = DuplicateType.INCONSISTENT in duplicateType
    consistent = DuplicateType.CONSISTENT in duplicateType
    incomplete = DuplicateType.INCOMPLETE in duplicateType
    complete = DuplicateType.COMPLETE in duplicateType
    if (inconsistent and consistent) or (incomplete and complete):
        return True
    if inconsistent and duplicateFacts.areAnyInconsistent:
        return True
    if consistent and duplicateFacts.areAnyConsistent:
        return True
    if incomplete and duplicateFacts.areAnyIncomplete:
        return True
    if complete and duplicateFacts.areAnyComplete:
        return True
    return False


def areFactsValueEqual(factA: ModelFact, factB: ModelFact) -> bool:
    """
    Returns whether the given facts are value-equal
    :param factA:
    :param factB:
    :return: True if the given facts are value-equal
    """
    return getFactValueEqualityKey(factA) == getFactValueEqualityKey(factB)


def getAspectEqualFacts(hashEquivalentFacts: list[ModelFact]) -> Iterator[list[ModelFact]]:
    """
    Given a list of concept/context/unit hash-equivalent facts,
    yields sublists of aspect-equal facts from this list.
    :param hashEquivalentFacts:
    :return: Lists of aspect-equal facts.
    """
    aspectEqualFacts: dict[tuple[QName, str | None], dict[tuple[ModelContext, ModelUnit], list[ModelFact]]] = defaultdict(dict)
    for fact in hashEquivalentFacts:  # check for hash collision by value checks on context and unit
        contextUnitDict = aspectEqualFacts[(
            fact.qname,
            cast(str, fact.xmlLang or "").lower() if fact.concept.type.isWgnStringFactType else None
        )]
        _matched = False
        for (context, unit), contextUnitFacts in contextUnitDict.items():
            if fact.context is None:
                if context is not None:
                    continue
            elif not fact.context.isEqualTo(context):
                continue
            if fact.unit is None:
                if unit is not None:
                    continue
            elif not fact.unit.isEqualTo(unit):
                continue
            _matched = True
            contextUnitFacts.append(fact)
            break
        if not _matched:
            contextUnitDict[(fact.context, fact.unit)] = [fact]
    for contextUnitDict in aspectEqualFacts.values():  # dups by qname, lang
        for duplicateFacts in contextUnitDict.values():  # dups by equal-context equal-unit
            if len(duplicateFacts) > 1:
                yield duplicateFacts


def getDuplicateFactSets(facts: list[ModelFact]) -> Iterator[DuplicateFactSet]:
    """
    :param facts: Facts to find duplicate sets from.
    :return: Each set of duplicate facts from the given list.
    """
    hashEquivalentFactGroups = getHashEquivalentFactGroups(facts)
    for hashEquivalentFacts in hashEquivalentFactGroups:
        if len(hashEquivalentFacts) < 2:
            continue
        for duplicateFactList in getAspectEqualFacts(hashEquivalentFacts):  # dups by equal-context equal-unit
            duplicateFactSet = DuplicateFactSet(facts=duplicateFactList)
            yield duplicateFactSet


def getDuplicateFactSetsWithType(facts: list[ModelFact], duplicateType: DuplicateType) -> Iterator[DuplicateFactSet]:
    """
    :param facts: Facts to find duplicate sets from.
    :param duplicateType: Type of duplicate to filter duplicate sets by.
    :return: Each set of duplicate facts from the given list of facts that contain the given duplicate type.
    """
    if duplicateType == DuplicateType.NONE:
        return
    for duplicateFactSet in getDuplicateFactSets(facts):
        if doesSetHaveDuplicateType(duplicateFactSet, duplicateType):
            yield duplicateFactSet


class FactValueEqualityType(Enum):
    DEFAULT = 'default'
    DATETIME = 'datetime'
    LANGUAGE = 'language'


TypeFactValueEqualityKey = tuple[FactValueEqualityType, tuple[Any, ...]]


def getFactValueEqualityKey(fact: ModelFact) -> TypeFactValueEqualityKey:
    """
    :param fact:
    :return: A key to be used for fact-value-equality comparison.
    """
    if fact.isNil:
        return FactValueEqualityType.DEFAULT, (None,)
    xValue = fact.xValue
    if fact.isNumeric:
        if isnan(cast(SupportsFloat, xValue)):
            return FactValueEqualityType.DEFAULT, (float("nan"),)
    if fact.concept.isLanguage:
        return FactValueEqualityType.LANGUAGE, (cast(str, xValue).lower() if xValue is not None else None,)
    if isinstance(xValue, DateTime):  # with/without time makes values unequal
        return FactValueEqualityType.DATETIME, (xValue, xValue.dateOnly)
    return FactValueEqualityType.DEFAULT, (fact.value,)


def getHashEquivalentFactGroups(facts: list[ModelFact]) -> list[list[ModelFact]]:
    """
    Given a list of facts in an instance, returns a list of lists of facts
    that are concept/context/unit hash-equivalent.
    :param facts:
    :return: List of hash-equivalent fact lists
    """
    hashDict = defaultdict(list)
    for f in facts:
        if (f.isNil or getattr(f, "xValid", XmlValidateConst.UNVALIDATED) >= XmlValidateConst.VALID) and f.context is not None and f.concept is not None and f.concept.type is not None:
            hashDict[f.conceptContextUnitHash].append(f)
    return list(hashDict.values())
