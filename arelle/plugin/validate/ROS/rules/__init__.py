"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from arelle.ModelInstanceObject import ModelFact
from arelle.ModelXbrl import ModelXbrl
from arelle.XmlValidateConst import VALID
from arelle.utils.validate.Validation import Validation


def errorOnMissingRequiredFact(
        modelXbrl: ModelXbrl,
        conceptLn: str,
        code: str,
        message: str,
) -> Iterable[Validation]:
    """
    Yields an error if a fact with the given localName is not tagged with a non-nil value.
    :return: Yields validation errors.
    """
    facts: set[ModelFact] = modelXbrl.factsByLocalName.get(conceptLn, set())
    for fact in facts:
        if not fact.isNil:
            return
    yield Validation.error(
        conceptLn=conceptLn,
        codes=code,
        msg=message,
    )


def errorOnNegativeFact(
        modelXbrl: ModelXbrl,
        conceptLn: str,
        code: str,
        message: str,
) -> Iterable[Validation]:
    """
    Yields an error if a fact with the given localName is tagged with a negative value.
    :return: Yields validation errors.
    """
    errorModelFacts: list[ModelFact] = []
    facts = modelXbrl.factsByLocalName.get(conceptLn, set())
    for fact in facts:
        if fact.xValid >= VALID and cast(int, fact.xValue) < 0:
            errorModelFacts.append(fact)
    if errorModelFacts:
        yield Validation.error(
            codes=code,
            modelObject=errorModelFacts,
            msg=message,
        )
