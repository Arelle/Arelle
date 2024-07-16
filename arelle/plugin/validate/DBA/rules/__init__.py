"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import datetime
import itertools
from typing import Iterable, Callable, cast, Union

from arelle.ModelDocument import ModelDocument
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl
from arelle.XmlValidateConst import VALID
from arelle.utils.validate.Validation import Validation
from arelle.ValidateXbrl import ValidateXbrl


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
    if facts:
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
        membeQn: QName
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
                ) == membeQn
                      and fact.context.qnameDims.keys() == {dimensionQn}):
                    foundFacts.add(fact)
                elif not len(fact.context.qnameDims):
                    foundFacts.add(fact)
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
        factMemberQn = cast(Union[QName, None], fact.context.dimMemberQname(dimensionQn))
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
    return {
        k: sorted(v, key=lambda f: f.objectIndex)
        for k, v in itertools.groupby(facts, key=lambda f: f.contextID)
    }
