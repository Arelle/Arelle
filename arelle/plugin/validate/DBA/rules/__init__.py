"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import datetime
import itertools
from typing import Iterable, Callable, cast, Union

from arelle.ModelInstanceObject import ModelFact
from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl
from arelle.XmlValidateConst import VALID
from arelle.utils.validate.Validation import Validation


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
    facts1 = getValidDateFactsWithDimensionMember(modelXbrl, fact1Qn, dimensionQn)
    facts2 = getValidDateFactsWithDimensionMember(modelXbrl, fact2Qn, dimensionQn)
    for fact1, fact2 in itertools.product(facts1, facts2):
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


def getValidDateFactsWithDimensionMember(
        modelXbrl: ModelXbrl,
        factQn: QName,
        dimensionQn: QName
) -> list[ModelFact]:
    """
    Retrieves facts with the given QName.
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
    facts: set[ModelFact] = modelXbrl.factsByQname.get(factQn, set())
    for fact in facts:
        if fact.xValid < VALID:
            continue
        if not isinstance(fact.xValue, datetime.datetime):
            continue
        factMemberQn = cast(Union[QName, None], fact.context.dimMemberQname(dimensionQn))
        if memberQn is None or memberQn == factMemberQn:
            results.append(fact)
    return sorted(results, key=lambda f: f.objectIndex)
