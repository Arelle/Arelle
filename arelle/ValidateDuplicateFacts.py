"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from enum import Enum
from typing import cast, Callable, Iterator

from arelle.ModelInstanceObject import ModelFact, ModelContext, ModelUnit
from arelle.ModelValue import DateTime, QName


class DisallowMode(Enum):
    DISALLOW_NONE = 1
    DISALLOW_COMPLETE = 2  # Incomplete consistents allowed, all inconsistents allowed

    def toArg(self) -> str:
        return self.name[9:].lower()

    @staticmethod
    def fromArg(arg: str):
        return DisallowMode[f"DISALLOW_{arg.upper()}"]


def areCompleteDuplicates(duplicateFacts: list[ModelFact]) -> bool:
    """
    Returns whether or not the given duplicate facts are complete duplicates.
    :param duplicateFacts:
    :return: True if complete, False if incomplete consistent, or inconsistent.
    """
    if not areFactsAllValueEqual(duplicateFacts):
        # If facts are not value-equal, they are not complete
        return False
    if not areDecimalsMatching(duplicateFacts):
        # If facts do not have matching decimal values, they are not complete
        return False
    return True


def areDecimalsMatching(duplicateFacts: list[ModelFact]) -> bool:
    """
    Returns whether or not the given duplicate facts have matching decimals
    attribute values.
    :param duplicateFacts:
    :return: True if decimals match, False otherwise.
    """
    value = duplicateFacts[0].decimals
    for fact in duplicateFacts[1:]:
        if fact.decimals != value:
            return False
    return True


def areDuplicatesDisallowed(duplicateFacts: list[ModelFact], disallowMode: DisallowMode):
    """
    Returns whether or not the given duplicate facts should be disallowed
    based on the disallowed mode.
    :param disallowMode:
    :param duplicateFacts:
    :return: True if disallowed, False if allowed.
    """
    if disallowMode == DisallowMode.DISALLOW_NONE:
        return False
    if disallowMode == DisallowMode.DISALLOW_COMPLETE:
        return areCompleteDuplicates(duplicateFacts)
    raise ValueError(f"Invalid duplicate detection mode: {disallowMode}")


def areFactsAllValueEqual(duplicateFacts: list[ModelFact]) -> bool:
    """
    Returns if a list of facts are fact-value equal with each other,
    as defined in OIM 1.0 specification: "5.1.1 Fact value equality"
    :param duplicateFacts: List of duplicate facts
    :return: Whether all facts are fact-value equal with each other
    """
    firstFact = duplicateFacts[0]
    for fact in duplicateFacts[1:]:
        if not areFactsValueEqual(firstFact, fact):
            return False
    return True


def areFactsValueEqual(f1: ModelFact, f2: ModelFact) -> bool:
    """
    Returns whether the given facts are value-equal
    :param f1:
    :param f2:
    :return: True if the given facts are value-equal
    """
    if f1.context is None or f1.concept is None:
        return False  # need valid context and concept for v-Equality of nonTuple
    if f1.isNil:
        return f2.isNil
    if f2.isNil:
        return False
    if not f1.context.isEqualTo(f2.context):
        return False
    xValue1 = f1.xValue
    xValue2 = f2.xValue
    if isinstance(xValue1, type(xValue2)):
        if f1.concept.isLanguage and f2.concept.isLanguage and xValue1 is not None and xValue2 is not None:
            return xValue1.lower() == xValue2.lower()  # required to handle case insensitivity
        if isinstance(xValue1, DateTime):  # with/without time makes values unequal
            return xValue1.dateOnly == cast(DateTime, xValue2).dateOnly and xValue1 == xValue2
        return xValue1 == xValue2  # required to handle date/time with 24 hrs.
    return f1.value == f2.value


def getAllDuplicates(factsInInstance: set[ModelFact], filterFunction: Callable = lambda facts: True):
    """
    Given all facts in an instance, return a list of duplicate fact sets,
    after optionally applying a filter function.
    :param factsInInstance:
    :param filterFunction: A function that returns True if a given list of duplicate facts should be returned as duplicates.
    :return: List of duplicate fact sets.
    """
    duplicates = []
    hashEquivalentFactGroups = getHashEquivalentFactGroups(factsInInstance)
    for hashEquivalentFacts in hashEquivalentFactGroups:
        if len(hashEquivalentFacts) < 2:
            continue
        for duplicateFacts in getAspectEqualFacts(hashEquivalentFacts):  # dups by equal-context equal-unit
            if filterFunction(duplicateFacts):
                duplicates.append(duplicateFacts)
    del hashEquivalentFactGroups
    return duplicates


def getAspectEqualFacts(
        hashEquivalentFacts: list[ModelFact],
) -> Iterator[list[ModelFact]]:
    """
    Given a list of concept/context/unit hash-equivalent facts,
    yeilds sets of aspect-equal facts from this list.
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


def getDisallowedDuplicates(factsInInstance: set[ModelFact], disallowMode: DisallowMode) -> list[list[ModelFact]]:
    """
    Return a list of duplicate fact lists generated from the given fact list and based on
    the configuration of which types of duplicates should be disallowed.
    :param factsInInstance:
    :param disallowMode: Which types of duplicates should be considered disallowed
    :return: A list of disallowed duplicate fact lists
    """
    if disallowMode == DisallowMode.DISALLOW_NONE:
        return []
    return getAllDuplicates(
        factsInInstance,
        filterFunction=lambda duplicateFacts: areDuplicatesDisallowed(duplicateFacts, disallowMode)
    )


def getHashEquivalentFactGroups(factsInInstance: set[ModelFact]) -> list[list[ModelFact]]:
    """
    Given a list of facts in an instance, returns a list of sets of facts
    that are concept/context/unit hash-equivalent.
    :param factsInInstance:
    :return: List of hash-equivalent fact sets
    """
    hashDict = defaultdict(list)
    for f in factsInInstance:
        if (f.isNil or getattr(f, "xValid", 0) >= 4) and f.context is not None and f.concept is not None and f.concept.type is not None:
            hashDict[f.conceptContextUnitHash].append(f)
    return list(hashDict.values())
