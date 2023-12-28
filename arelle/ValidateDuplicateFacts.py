"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import auto, Flag, Enum
from functools import cached_property
from math import isnan
from typing import cast, Iterator

from arelle import XmlValidateConst
from arelle.ModelInstanceObject import ModelFact, ModelContext, ModelUnit
from arelle.ModelValue import DateTime, QName
from arelle.ValidateXbrlCalcs import rangeValue, inferredDecimals


@dataclass(frozen=True)
class DuplicateFactSet:
    facts: list[ModelFact]

    def __iter__(self):
        return iter(self.facts)

    @cached_property
    def areCompleteDuplicates(self) -> bool:
        """
        Returns whether these duplicates are complete duplicates.
        :return: True if complete, False if incomplete consistent, or inconsistent.
        """
        return self.areDecimalsEqual and self.areValueEqual

    @cached_property
    def areConsistentDuplicates(self) -> bool:
        """
        Returns whether these duplicates are consistent with each other.
        :return: True if consistent or complete, False if incomplete inconsistent.
        """
        if self.areCompleteDuplicates:
            return True
        if self.areNumeric:
            # If facts are numeric but NOT complete duplicates,
            # they must be within rounding error to be consistent
            return self.areWithinRoundingError
        # If facts are not complete duplicates and not numeric, then they are not consistent
        return False

    @cached_property
    def areDecimalsEqual(self) -> bool:
        """
        :return: Whether these facts have matching decimals values.
        """
        firstFact = self.facts[0]
        for fact in self.facts[1:]:
            if firstFact.decimals != fact.decimals:
                # If facts do not have matching decimal values, they are not complete
                return False
        return True

    @cached_property
    def areInconsistentDuplicates(self) -> bool:
        """
        Returns whether these duplicates are inconsistent with each other.
        :return: True if inconsistent, False if consistent or complete.
        """
        if self.areNumeric:
            # If facts are numeric, they are inconsistent if they are not consistent
            return not self.areConsistentDuplicates
        # If facts are not numeric, they are inconsistent if they are not fact-value equal
        return not self.areValueEqual

    @cached_property
    def areNumeric(self) -> bool:
        """
        :return: Whether the duplicate set consists of numeric facts.
        """
        return self.facts[0].isNumeric

    @cached_property
    def areValueEqual(self) -> bool:
        """
        :return: Whether all facts in this set are fact-value equal.
        """
        firstFact = self.facts[0]
        for fact in self.facts[1:]:
            if not areFactsValueEqual(firstFact, fact):
                # If facts are not value-equal, they are not complete
                return False
        return True

    @cached_property
    def areWithinRoundingError(self) -> bool:
        """
        :return: Whether the set of numeric fact values are within rounding error of each other.
        """
        maxLower = float("-inf")
        minUpper = float("inf")
        decimalValues = {}
        for fact in self.facts:
            value = fact.xValue
            if isnan(value):
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

    @property
    def duplicateType(self) -> DuplicateType | None:
        """
        Determines type of duplicate based on previously evaluated conditions.
        If duplicate type status has not been evaluated, returns None.
        :return: Duplicate type, or None
        """
        # Access __dict__ directly to check if given properties have been evaluated
        # and, if so, what the evaluated value is.
        if self.__dict__.get('areCompleteDuplicates'):
            return DuplicateType.COMPLETE
        if self.__dict__.get('areConsistentDuplicates'):
            return DuplicateType.CONSISTENT
        if self.__dict__.get('areInconsistentDuplicates'):
            return DuplicateType.INCONSISTENT
        return None


class DuplicateType(Flag):
    NONE = 0
    INCONSISTENT = auto()
    CONSISTENT = auto()
    INCOMPLETE = auto()
    COMPLETE = auto()

    # Flags before 3.11 did not support iterating Flag values,
    # so we have to override with our own iterator. Remove when we no longer support 3.10
    def __iter__(self):
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


def areDuplicatesOfType(duplicateFacts: DuplicateFactSet, duplicateType: DuplicateType) -> bool:
    """
    Returns whether or not the given duplicate facts should be disallowed
    based on the disallowed mode.
    :param duplicateFacts:
    :param duplicateType:
    :return: True if disallowed, False if allowed.
    """
    inconsistent = DuplicateType.INCONSISTENT in duplicateType
    consistent = DuplicateType.CONSISTENT in duplicateType
    incomplete = DuplicateType.INCOMPLETE in duplicateType
    complete = DuplicateType.COMPLETE in duplicateType
    if (inconsistent and consistent) or (incomplete and complete):
        return True
    if inconsistent:
        if duplicateFacts.areInconsistentDuplicates:
            return True
    if consistent:
        if duplicateFacts.areConsistentDuplicates:
            return True
    if incomplete:
        if not duplicateFacts.areCompleteDuplicates:
            return True
    if complete:
        if duplicateFacts.areCompleteDuplicates:
            return True
    return False


def areFactsValueEqual(factA: ModelFact, factB: ModelFact) -> bool:
    """
    Returns whether the given facts are value-equal
    :param factA:
    :param factB:
    :return: True if the given facts are value-equal
    """
    if factA.context is None or factA.concept is None:
        return False  # need valid context and concept for v-Equality of nonTuple
    if factA.isNil:
        return factB.isNil
    if factB.isNil:
        return False
    if not factA.context.isEqualTo(factB.context):
        return False
    xValueA = factA.xValue
    xValueB = factB.xValue
    if isinstance(xValueA, type(xValueB)):
        if factA.concept.isLanguage and factB.concept.isLanguage and xValueA is not None and xValueB is not None:
            return xValueA.lower() == xValueB.lower()  # required to handle case insensitivity
        if isinstance(xValueA, DateTime):  # with/without time makes values unequal
            return xValueA.dateOnly == cast(DateTime, xValueB).dateOnly and xValueA == xValueB
        return xValueA == xValueB  # required to handle date/time with 24 hrs.
    return factA.value == factB.value


def getAspectEqualFacts(hashEquivalentFacts: list[ModelFact]) -> Iterator[list[ModelFact]]:
    """
    Given a list of concept/context/unit hash-equivalent facts,
    yields sublists of aspect-equal facts from this list.
    :param hashEquivalentFacts:
    :return: Lists of aspect-equal facts.
    """
    aspectEqualFacts: dict[tuple[QName, str], dict[tuple[ModelContext, ModelUnit], list[ModelFact]]] = defaultdict(dict)
    for fact in hashEquivalentFacts:  # check for hash collision by value checks on context and unit
        contextUnitDict = aspectEqualFacts[(
            fact.qname,
            (fact.xmlLang or "").lower() if fact.concept.type.isWgnStringFactType else None
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
            if len(duplicateFacts) < 2:
                continue
            yield duplicateFacts


def getDuplicateFactSets(facts: list[ModelFact]) -> Iterator[DuplicateFactSet]:
    """
    Yields each pairing of facts from the provided set that are duplicates of the given type(s).
    :param facts: Facts to find duplicate sets from.
    :return: Yields duplicate fact sets.
    """
    hashEquivalentFactGroups = getHashEquivalentFactGroups(facts)
    for hashEquivalentFacts in hashEquivalentFactGroups:
        if len(hashEquivalentFacts) < 2:
            continue
        for duplicateFactList in getAspectEqualFacts(hashEquivalentFacts):  # dups by equal-context equal-unit
            duplicateFactSet = DuplicateFactSet(facts=duplicateFactList)
            yield duplicateFactSet


def getDuplicateFactSetsOfType(facts: list[ModelFact], duplicateType: DuplicateType) -> Iterator[DuplicateFactSet]:
    if duplicateType == DuplicateType.NONE:
        return
    for duplicateFactSet in getDuplicateFactSets(facts):
        if areDuplicatesOfType(duplicateFactSet, duplicateType):
            yield duplicateFactSet


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
