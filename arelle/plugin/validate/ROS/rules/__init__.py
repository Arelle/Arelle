"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Iterable, Callable, cast, Union

from arelle.ModelInstanceObject import ModelFact
from arelle.ModelXbrl import ModelXbrl
from arelle.utils.validate.Validation import Validation


def errorOnRequiredFact(
        modelXbrl: ModelXbrl,
        conceptLn: str,
        code: str,
        message: str,
) -> Iterable[Validation]:
    """
    Yields an error if a fact with the given QName is not tagged with a non-nil value.
    :return: Yields validation errors.
    """
    facts: set[ModelFact] = modelXbrl.factsByLocalName.get(conceptLn, set())
    for fact in facts:
        if not fact.isNil:
            return
    yield Validation.error(
        codes=code,
        msg=message,
        conceptLn=conceptLn,

    )
