"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Iterable

from arelle.ModelInstanceObject import ModelFact
from arelle.typing import TypeGetText
from arelle.utils.validate.Validation import Level, Validation
from arelle.ValidateDuplicateFacts import getDuplicateFactSetsWithType
from arelle.ValidateDuplicateFactsConst import DuplicateType

_: TypeGetText


def validateDuplicateFacts(
    facts: list[ModelFact],
    duplicateType: DuplicateType,
    codes: str | tuple[str, ...],
    msg: str | None = None,
    level: Level = Level.ERROR,
) -> Iterable[Validation]:
    """Yield a validation for each set of duplicate facts containing the given duplicate type."""
    duplicateTypeDescription = duplicateType.description
    if msg is None:
        msg = _(
            "{} duplicate facts MUST NOT be tagged. "
            "%(fact)s was used more than once in contexts equivalent to %(contextIDs)s: "
            "values %(values)s."
        ).format(duplicateTypeDescription.capitalize())
    for duplicateFactSet in getDuplicateFactSetsWithType(facts, duplicateType):
        duplicateFacts = duplicateFactSet.facts
        yield Validation.build(
            level,
            codes,
            msg,
            modelObject=duplicateFacts,
            fact=duplicateFacts[0].qname,
            duplicateType=duplicateTypeDescription,
            contextIDs=", ".join(sorted({f.contextID for f in duplicateFacts if f.contextID is not None})),
            values=", ".join(f.value for f in duplicateFacts),
        )
