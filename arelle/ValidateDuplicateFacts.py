"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from _decimal import Decimal
from collections import defaultdict
from dataclasses import dataclass, field
from enum import auto, Flag, Enum
from functools import cached_property
from math import isnan
from typing import cast, Iterator, Any, SupportsFloat, Tuple

from arelle import XmlValidateConst
from arelle.ModelInstanceObject import ModelFact, ModelContext, ModelUnit
from arelle.ModelValue import DateTime, QName, TypeXValue
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrlCalcs import rangeValue, inferredDecimals
from arelle.typing import TypeGetText
_: TypeGetText


@dataclass(frozen=True)
class DuplicateFactSet:
    facts: list[ModelFact]
    _inferredDecimals: dict[ModelFact, float | int | None] = field(init=False, default_factory=dict)
    _ranges: dict[ModelFact, tuple[Decimal, Decimal]] = field(init=False, default_factory=dict)

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
        decimalsValueMap: dict[float | int | None, set[TypeFactValueEqualityKey]] = defaultdict(set)
        for fact in self.facts:
            decimals = self.getDecimals(fact)
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
            # Non-numeric and incomplete: inconsistent
            return False
        ranges: list[tuple[Decimal, Decimal, float | int | None]] = []
        for fact in self.facts:
            decimalsA = self.getDecimals(fact)
            lowerA, upperA = self.getRange(fact)
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
            decimals = self.getDecimals(fact)
            assert decimals is not None
            if decimals in decimalValues:
                if value != decimalValues[decimals]:
                    # Facts with the same `decimals` value MUST have the same numeric value in order to be considered consistent.
                    return False
            else:
                decimalValues[decimals] = value
            lower, upper = self.getRange(fact)
            if lower > maxLower:
                maxLower = lower
            if upper < minUpper:
                minUpper = upper
            if minUpper < maxLower:
                # One fact's upper bound is less than another fact's lower bound, not consistent
                return False
        return True

    def deduplicateCompleteSubsets(self) -> list[ModelFact]:
        """
        :return: A list of the first fact found for each unique decimals/value combination.
        """
        seenKeys = set()
        results = []
        for fact in self.facts:
            key = (fact.decimals, fact.xValue)
            if key in seenKeys:
                continue
            seenKeys.add(key)
            results.append(fact)
        return results

    def deduplicateConsistentPairs(self) -> list[ModelFact]:
        """
        First performs deduplication of complete duplicates,
        then removes from the remaining facts any fact that is consistent with a higher precision fact.
        :return: A subset of the facts where the fact of lower precision in every consistent pair has been removed.
        """
        facts = self.deduplicateCompleteSubsets()
        if not self.areNumeric:
            # Consistency is equivalent to completeness for non-numeric facts
            return facts
        decimalsMap = defaultdict(list)
        for fact in facts:
            decimals = self.getDecimals(fact)
            assert decimals is not None
            decimalsMap[decimals].append(fact)
        if len(decimalsMap) < 2:
            return facts
        sortedDecimals = sorted(decimalsMap.keys())
        results = set(facts)

        for a, decimalLower in enumerate(sortedDecimals[:len(sortedDecimals)-1]):
            groupLower = decimalsMap[decimalLower]
            for factA in groupLower:
                lowerA, upperA = self.getRange(factA)
                if isnan(cast(SupportsFloat, factA.xValue)):
                    continue
                remove = False
                # Iterate through each higher decimals group
                for b, decimalHigher in enumerate(sortedDecimals[a+1:]):
                    groupHigher = decimalsMap[decimalHigher]
                    for factB in groupHigher:
                        lowerB, upperB = self.getRange(factB)
                        if isnan(cast(SupportsFloat, factB.xValue)):
                            continue
                        if lowerB <= upperA and upperB >= lowerA:
                            remove = True
                            break
                    if remove:
                        break
                if remove:
                    results.remove(factA)
        return list(results)

    def deduplicateConsistentSet(self) -> tuple[list[ModelFact], str | None]:
        """
        :return: If this set is numeric and fully consistent, a list containing only the highest-precision fact.
        Otherwise, deduplication of complete duplicates.
        """
        if not self.areNumeric:
            # Consistency is equivalent to completeness for non-numeric facts
            return self.deduplicateCompleteSubsets(), None
        if not self.areAllConsistent:
            # If facts are not all consistent, we will only perform complete deduplication
            return self.deduplicateCompleteSubsets(), 'Set has inconsistent facts'
        selectedFact = self.facts[0]
        maxDecimals = self.getDecimals(selectedFact)
        assert maxDecimals is not None
        for fact in self.facts[1:]:
            decimals = self.getDecimals(fact)
            assert decimals is not None
            if decimals > maxDecimals:
                maxDecimals = decimals
                selectedFact = fact
        return [selectedFact], None

    def getDecimals(self, fact: ModelFact) -> float | int | None:
        """
        Prevents repeated calculation of inferred decimal values.
        :param fact:
        :return: Retrieve cached inferred decimals value for the provided fact.
        """
        assert fact in self.facts, 'Attempted to get decimals for fact not in set'
        if fact not in self._inferredDecimals:
            self._inferredDecimals[fact] = None if fact.decimals is None else inferredDecimals(fact)
        return self._inferredDecimals[fact]

    def getRange(self, fact: ModelFact) -> tuple[Decimal, Decimal]:
        """
        Prevents repeated calculation of fact value ranges.
        :param fact:
        :return: Retrieve cached range values for the provided fact.
        """
        assert fact in self.facts, 'Attempted to get range for fact not in set'
        assert fact.isNumeric, 'Attempted to get range for non-numeric fact'
        if fact not in self._ranges:
            lower, upper, __, __ = rangeValue(fact.xValue, self.getDecimals(fact))
            self._ranges[fact] = lower, upper
        return self._ranges[fact]


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

    @property
    def description(self) -> str:
        return '|'.join([str(n.name) for n in self if n.name]).lower()


class DuplicateTypeArg(Enum):
    NONE = 'none'
    INCONSISTENT = 'inconsistent'
    CONSISTENT = 'consistent'
    INCOMPLETE = 'incomplete'
    COMPLETE = 'complete'
    ALL = 'all'

    def duplicateType(self) -> DuplicateType:
        return DUPLICATE_TYPE_ARG_MAP.get(self, DuplicateType.NONE)


class DeduplicationType(Enum):
    COMPLETE = 'complete'
    CONSISTENT_PAIRS = 'consistent-pairs'
    CONSISTENT_SETS = 'consistent-sets'


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
    if len(duplicateFacts.facts) < 2:
        return False
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


def getAspectEqualFacts(hashEquivalentFacts: list[ModelFact], includeSingles: bool) -> Iterator[list[ModelFact]]:
    """
    Given a list of concept/context/unit hash-equivalent facts,
    yields sublists of aspect-equal facts from this list.
    :param hashEquivalentFacts:
    :param includeSingles: Whether to include lists of single facts (with no duplicates).
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
            if includeSingles or len(duplicateFacts) > 1:
                yield duplicateFacts


def getDeduplicatedFacts(modelXbrl: ModelXbrl, deduplicationType: DeduplicationType) -> list[ModelFact]:
    results = []
    for duplicateFactSet in getDuplicateFactSets(modelXbrl.facts, includeSingles=True):
        message = None
        if len(duplicateFactSet.facts) < 2:
            facts = duplicateFactSet.facts
        elif deduplicationType == DeduplicationType.COMPLETE:
            facts = duplicateFactSet.deduplicateCompleteSubsets()
        elif deduplicationType == DeduplicationType.CONSISTENT_PAIRS:
            facts = duplicateFactSet.deduplicateConsistentPairs()
        elif deduplicationType == DeduplicationType.CONSISTENT_SETS:
            facts, message = duplicateFactSet.deduplicateConsistentSet()
        else:
            raise ValueError(f"Invalid deduplication type: {deduplicationType}")
        results.extend(facts)
        if message is not None:
            modelXbrl.warning(
                "info:deduplicationNotPossible",
                _("Deduplication of %(concept)s fact set not possible: %(message)s. concept=%(concept)s, context=%(context)s"),
                modelObject=facts[0], concept=facts[0].concept.qname, context=facts[0].contextID, message=message)
    return results


def getDuplicateFactSets(facts: list[ModelFact], includeSingles: bool) -> Iterator[DuplicateFactSet]:
    """
    :param facts: Facts to find duplicate sets from.
    :param includeSingles: Whether to include lists of single facts (with no duplicates).
    :return: Each set of duplicate facts from the given list.
    """
    hashEquivalentFactGroups = getHashEquivalentFactGroups(facts)
    for hashEquivalentFacts in hashEquivalentFactGroups:
        if not includeSingles and len(hashEquivalentFacts) < 2:
            continue
        for duplicateFactList in getAspectEqualFacts(hashEquivalentFacts, includeSingles=includeSingles):  # dups by equal-context equal-unit
            yield DuplicateFactSet(facts=duplicateFactList)


def getDuplicateFactSetsWithType(facts: list[ModelFact], duplicateType: DuplicateType) -> Iterator[DuplicateFactSet]:
    """
    :param facts: Facts to find duplicate sets from.
    :param duplicateType: Type of duplicate to filter duplicate sets by.
    :return: Each set of duplicate facts from the given list of facts that contain the given duplicate type.
    """
    if duplicateType == DuplicateType.NONE:
        return
    for duplicateFactSet in getDuplicateFactSets(facts, includeSingles=False):
        if doesSetHaveDuplicateType(duplicateFactSet, duplicateType):
            yield duplicateFactSet


class FactValueEqualityType(Enum):
    DEFAULT = 'default'
    DATETIME = 'datetime'
    LANGUAGE = 'language'


TypeFactValueEqualityKey = Tuple[FactValueEqualityType, Tuple[Any, ...]]


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


def logDeduplicatedFact(modelXbrl: ModelXbrl, fact: ModelFact) -> None:
    modelXbrl.info(
        "info:deduplicatedFact",
        _("Duplicate fact was excluded from deduplicated instance: %(fact)s, value=%(value)s, decimals=%(decimals)s"),
        modelObject=fact,
        fact=fact.qname,
        value=fact.xValue,
        decimals=fact.decimals,
    )


def saveDeduplicatedInstance(modelXbrl: ModelXbrl, deduplicationType: DeduplicationType, outputFilepath: str) -> None:
    deduplicatedFacts = frozenset(getDeduplicatedFacts(modelXbrl, deduplicationType))
    duplicateFacts = set(modelXbrl.facts) - deduplicatedFacts
    for fact in duplicateFacts:
        parent = fact.getparent()
        assert parent is not None
        parent.remove(fact)
        logDeduplicatedFact(modelXbrl, fact)
    modelXbrl.saveInstance(overrideFilepath=outputFilepath)
    modelXbrl.info(
        "info:deduplicatedInstance",
        _("Deduplicated instance was saved after removing %(count)s fact(s): %(filepath)s"),
        count=len(duplicateFacts),
        filepath=outputFilepath,
    )
