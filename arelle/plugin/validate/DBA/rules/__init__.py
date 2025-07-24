"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import datetime
import itertools
from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Optional, cast

from arelle.ModelDocument import ModelDocument
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl
from arelle.typing import TypeGetText
from arelle.UrlUtil import scheme
from arelle.utils.Contexts import ContextHashKey
from arelle.utils.validate.Validation import Validation
from arelle.ValidateFilingText import parseImageDataURL
from arelle.ValidateXbrl import ValidateXbrl
from arelle.XmlValidateConst import VALID


_: TypeGetText


def errorOnDateFactComparison(
        modelXbrl: ModelXbrl,
        fact1Qn: QName,
        fact2Qn: QName,
        dimensionQn: QName,
        code: str,
        message: str,
        assertion: Callable[[datetime.datetime, datetime.datetime], bool],
) -> Iterable[Validation]:
    """
    Compares fact pairs of the given QNames with the given assertion lambda.
    If the assertion fails, yields an error on the given ModelXbrl with
    the given code and message.
    If a dimension is provided, only considers facts that have the default
    dimension value as the member for that dimension.
    :return: Yields validation errors.
    """
    facts1 = getValidDateFactsWithDefaultDimension(modelXbrl, fact1Qn, dimensionQn)
    facts1 = sorted(facts1, key=lambda f: f.objectIndex)
    facts2 = getValidDateFactsWithDefaultDimension(modelXbrl, fact2Qn, dimensionQn)
    facts2 = sorted(facts2, key=lambda f: f.objectIndex)
    for fact1, fact2 in itertools.product(facts1, facts2):
        if fact1.contextID != fact2.contextID:
            continue
        datetime1 = cast(datetime.datetime, fact1.xValue)
        datetime2 = cast(datetime.datetime, fact2.xValue)
        if assertion(datetime1, datetime2):
            continue
        yield Validation.error(
            codes=code,
            msg=message,
            modelObject=[fact1, fact2],
            fact1=fact1.xValue,
            fact2=fact2.xValue,
        )


def errorOnForbiddenImage(
        images: set[str],
        code: str,
        message: str,
) -> Iterable[Validation]:
    """
    Yield an error of an image is an url or not a base64 encoded image
    images is a list of either urls or data:images.
    """
    invalidImages = []
    for image in images:
        if scheme(image) in ("http", "https", "ftp"):
            invalidImages.append(image)
        elif image.startswith("data:image"):
            dataURLParts = parseImageDataURL(image)
            if not dataURLParts or not dataURLParts.isBase64:
                invalidImages.append(image)
    if len(invalidImages) > 0:
        yield Validation.error(
            codes=code,
            msg=message,
            modelObject=invalidImages,
        )


def errorOnMandatoryFacts(
        modelXbrl: ModelXbrl,
        factQn: QName,
        code: str,
) -> Iterable[Validation]:
    """
    Yields an error when the specified factQn does not appear on a tagged fact in the document
    :return: Yields validation errors
    """
    facts = modelXbrl.factsByQname.get(factQn, set())
    if len(facts) == 0:
        yield Validation.error(
            code,
            _('{} must be tagged in the document.').format(factQn.localName)
        )


def errorOnMultipleFacts(
        modelXbrl: ModelXbrl,
        factQn: QName,
        code: str,
) -> Iterable[Validation]:
    """
    Yields an error if the specified QName appears on more than one fact
    :return: Yields validation errors
    """
    facts = modelXbrl.factsByQname.get(factQn, set())
    if len(facts) > 1:
        yield Validation.error(
            code,
            _('{} must only be tagged once. {} facts were found.').format(factQn.localName, len(facts)),
            modelObject=facts
        )


def errorOnRequiredFact(
        modelXbrl: ModelXbrl,
        factQn: QName,
        code: str,
        message: str,
) -> Iterable[Validation]:
    """
    Yields an error if a fact with the given QName is not tagged with a non-nil value.
    :return: Yields validation errors.
    """
    facts: set[ModelFact] = modelXbrl.factsByQname.get(factQn, set())
    for fact in facts:
        if not fact.isNil:
            return
    yield Validation.error(
        codes=code,
        msg=message,
)


def errorOnRequiredPositiveFact(
        modelXbrl: ModelXbrl,
        facts: set[ModelFact],
        code: str,
        message: str,
) -> Iterable[Validation]:
    """
    Yields an error if a fact with the given QName is not tagged with a valid date and a non-nil value.
    :return: Yields validation errors.
    """
    errorModelObjects: list[ModelFact | ModelDocument| None] = []
    if not facts:
        errorModelObjects.append(modelXbrl.modelDocument)
    else:
        for fact in facts:
            if fact.xValid >= VALID and cast(int, fact.xValue) < 0:
                errorModelObjects.append(fact)
    if errorModelObjects:
        yield Validation.error(
            codes=code,
            msg=message,
            modelObject=errorModelObjects
        )


def getFactsWithDimension(
        val: ValidateXbrl,
        conceptQn: QName,
        dimensionQn: QName,
        memberQns: list[QName]
) -> set[ModelFact ]:
    foundFacts: set[ModelFact] = set()
    facts = val.modelXbrl.factsByQname.get(conceptQn)
    if facts:
        for fact in facts:
            if fact is not None:
                if fact.context is None:
                    continue
                elif (fact.context.dimMemberQname(
                        dimensionQn
                ) in memberQns
                      and fact.context.qnameDims.keys() == {dimensionQn}):
                    foundFacts.add(fact)
                elif not len(fact.context.qnameDims):
                    foundFacts.add(fact)
    return foundFacts


def getFactsWithoutDimension(
        val: ValidateXbrl,
        conceptQn: QName,
) -> set[ModelFact ]:
    foundFacts: set[ModelFact] = set()
    facts = val.modelXbrl.factsByQname.get(conceptQn, set())
    foundFacts = {
        fact for fact in facts
        if fact is not None
        if fact.xValid >= VALID
        if fact.context is not None
        if len(fact.context.qnameDims) == 0
        }
    return foundFacts

def getValidDateFacts(
        modelXbrl: ModelXbrl,
        conceptQn: QName,
) -> list[ModelFact]:
    """
    Retrieves facts with the given QName and valid date values.
    :return:
    """
    results = []
    facts: set[ModelFact] = modelXbrl.factsByQname.get(conceptQn, set())
    for fact in facts:
        if fact.xValid < VALID:
            continue
        if not isinstance(fact.xValue, datetime.datetime):
            continue
        results.append(fact)
    return results


def getValidDateFactsWithDefaultDimension(
        modelXbrl: ModelXbrl,
        factQn: QName,
        dimensionQn: QName
) -> list[ModelFact]:
    """
    Retrieves facts with the given QName and valid date values.
    Only retrieves facts that have the default member for
    the given dimension. If dimension details can not be
    retrieved, includes the fact regardless.
    :return:
    """
    results = []
    memberQn = None
    dimensionConcept = modelXbrl.qnameConcepts.get(dimensionQn)
    if dimensionConcept is not None:
        dimensionDefaultConcept = modelXbrl.dimensionDefaultConcepts.get(dimensionConcept)
        if dimensionDefaultConcept is not None:
            memberQn = dimensionDefaultConcept.qname
    facts = getValidDateFacts(modelXbrl, factQn)
    for fact in facts:
        factMemberQn = cast(Optional[QName], fact.context.dimMemberQname(dimensionQn))
        if memberQn is None or memberQn == factMemberQn:
            results.append(fact)
    return results


def getFactsGroupedByContextId(modelXbrl: ModelXbrl, *conceptQns: QName) -> dict[str, list[ModelFact]]:
    """
    Groups facts by their context ID.
    :return: A dictionary of context ID to list of facts.
    """
    facts: set[ModelFact] = set()
    for conceptQn in conceptQns:
        facts.update(modelXbrl.factsByQname.get(conceptQn, set()))
    groupedFacts: dict[str, list[ModelFact]] = {}
    for fact in facts:
        contextId = fact.contextID
        if contextId not in groupedFacts:
            groupedFacts[contextId] = []
        groupedFacts[contextId].append(fact)
    return dict(sorted(groupedFacts.items()))


def groupFactsByContextHash(facts: set[ModelFact]) -> dict[ContextHashKey, list[ModelFact]]:
    """
    Groups facts by their context hash key.
    :return: A dictionary of context hash keys to list of facts.
    """
    groupedFacts: defaultdict[ContextHashKey, list[ModelFact]] = defaultdict(list)
    for fact in facts:
        if fact.xValid >= VALID:
            contextHash = ContextHashKey(fact.context, dimensionalAspectModel=True)
            groupedFacts[contextHash].append(fact)
    groupedFacts.default_factory = None
    return groupedFacts


def lookup_namespaced_facts(modelXbrl: ModelXbrl, namespaceURI: str) -> set[ModelFact]:
    """
    Returns the set of facts that are tagged with a concept from a particular namespace
    :Return: a set of facts
    """
    return {f for f in modelXbrl.facts if f.xValid >= VALID and f.xValue is not None and f.concept.qname.namespaceURI == namespaceURI}


def minimumRequiredFactsFound(
        modelXbrl: ModelXbrl,
        factQns: frozenset[QName],
        requiredCount: int,
) -> bool:
    """
    This function indicates if a minimum number of facts from a given set of QNames have been tagged in the document.
    :return: Boolean.
    """
    count = 0
    for factQn in factQns:
        facts: set[ModelFact] = modelXbrl.factsByQname.get(factQn, set())
        for fact in facts:
            if fact is not None and fact.xValid >= VALID:
                count += 1
                break
        if count >= requiredCount:
            return True
    return False


def consolidatedDimensionExists(modelXbrl: ModelXbrl, consolidatedSoloQn: QName) -> bool:
    """
    Check to see if the ConsolidatedSoloDimension is used in the filing

    :return: Boolean
    """
    for context in modelXbrl.contexts.values():
        if consolidatedSoloQn in context.qnameDims:
            return True
    return False
