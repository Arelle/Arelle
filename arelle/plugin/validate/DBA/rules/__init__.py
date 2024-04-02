"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import itertools
from typing import Iterator

from arelle.ModelInstanceObject import ModelFact
from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl
from arelle.XmlValidateConst import VALID


def getValidFactPairs(modelXbrl: ModelXbrl, qname1: QName, qname2: QName) -> Iterator[tuple[ModelFact, ModelFact]]:
    facts1: list[ModelFact] = sorted(modelXbrl.factsByQname.get(qname1, set()), key=lambda f: f.objectIndex)
    facts2: list[ModelFact] = sorted(modelXbrl.factsByQname.get(qname2, set()), key=lambda f: f.objectIndex)
    for fact1, fact2 in itertools.product(facts1, facts2):
        if fact1.xValid < VALID or fact2.xValid < VALID:
            continue
        yield fact1, fact2
