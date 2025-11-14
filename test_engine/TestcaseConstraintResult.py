"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations
from dataclasses import dataclass

from arelle.ModelValue import QName


@dataclass(frozen=True)
class TestcaseConstraintResult:
    code: str | QName
    diff: int

    def __str__(self):
        if self.diff < 0:
            num = f'Missing {abs(self.diff)} expected'
        else:
            num = f'{self.diff} unexpected'
        return f"{num} \"{self.code or '(any)'}\""
