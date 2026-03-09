"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Union, cast

from arelle import XbrlConst
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl
from arelle.typing import TypeGetText
from arelle.XmlValidateConst import VALID


_: TypeGetText

XSI_NIL_ATTR = "{http://www.w3.org/2001/XMLSchema-instance}nil"


def factHasXsiNilAttribute(fact: ModelFact) -> bool:
    """
    Returns True if the fact has the xsi:nil attribute set (regardless of value).
    """
    return fact.get(XSI_NIL_ATTR) is not None


def factHasPrecisionAttribute(fact: ModelFact) -> bool:
    """
    Returns True if the fact has the precision attribute explicitly set.
    Checks the raw attribute value, not the effective precision from type defaults.
    """
    return fact.get("precision") is not None


def isEmptyStringItemFact(fact: ModelFact) -> bool:
    """
    Returns True if the fact is a string item type concept with an empty value.
    """
    return (
        fact.concept is not None
        and fact.concept.instanceOfType(XbrlConst.qnXbrliStringItemType)
        and not fact.xValue
    )


def isValidNonNilFact(fact: ModelFact) -> bool:
    """
    Returns True if fact is valid (xValid >= VALID) and non-nil.
    """
    return fact.xValid >= VALID and not fact.isNil


def factHasNegativeNumericValue(fact: ModelFact) -> bool:
    """
    Returns True if fact is valid and has a negative numeric value.
    """
    return fact.xValid >= VALID and fact.xValue is not None and isinstance(fact.xValue, int) and fact.xValue < 0


def getDuplicateFactGroupsByConceptContextUnit(
    facts: Iterable[ModelFact],
) -> dict[object, list[ModelFact]]:
    """
    Groups facts by their concept/context/unit hash. Returns a mapping of
    hash to list of facts. Used by validation rules that detect duplicate facts
    based on concept, context, and unit.
    """
    groups: dict[object, list[ModelFact]] = defaultdict(list)
    for fact in facts:
        groups[fact.conceptContextUnitHash].append(fact)
    return groups


def iterValidNonNilFactsByQname(modelXbrl: ModelXbrl, qname: QName) -> Iterable[ModelFact]:
    """
    Yields facts with the given QName that are valid and non-nil.
    """
    for fact in modelXbrl.factsByQname.get(qname, set()):
        if isValidNonNilFact(fact):
            yield fact


def hasValidNonNilFactByQname(modelXbrl: ModelXbrl, qname: QName) -> bool:
    """
    Returns True if at least one valid, non-nil fact exists for the given QName.
    """
    return any(True for fact in iterValidNonNilFactsByQname(modelXbrl, qname))


def getUsedConceptsFromFacts(modelXbrl: ModelXbrl) -> set[ModelConcept]:
    """
    Returns the set of concepts used on facts in the instance.
    """
    return {fact.concept for fact in modelXbrl.facts if fact.concept is not None}


def hasNonNillFact(
    modelXbrl: ModelXbrl,
    conceptKey: Union[QName, str],
) -> bool:
    """
    Returns True if a fact with the given concept key is tagged with a non-nil, valid value.
    conceptKey is QName or str (localName).
    """
    facts: set[ModelFact]
    if isinstance(conceptKey, QName):
        facts  = modelXbrl.factsByQname.get(conceptKey, set())
    else:
        facts = modelXbrl.factsByLocalName.get(conceptKey, set())
    for fact in facts:
        if isinstance(fact, ModelFact) and not fact.isNil and fact.xValid >= VALID:
            return True
    return False


def getNegativeFacts(
    modelXbrl: ModelXbrl,
    conceptKey: Union[QName, str],
) -> list[ModelFact]:
    """
    Returns the list of facts with the given concept key that have a negative value.
    conceptKey is QName when byQname=True, else str (localName).
    """
    facts: set[ModelFact]
    if isinstance(conceptKey, QName):
        facts = modelXbrl.factsByQname.get(conceptKey, set())
    else:
        facts = modelXbrl.factsByLocalName.get(conceptKey, set())
    errorModelFacts: list[ModelFact] = []
    for fact in facts:
        if isinstance(fact, ModelFact) and factHasNegativeNumericValue(fact):
            errorModelFacts.append(fact)
    return errorModelFacts
