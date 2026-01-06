"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations
from dataclasses import dataclass

from arelle.testengine.ActualError import ActualError
from arelle.testengine.TestcaseConstraintResult import TestcaseConstraintResult
from arelle.testengine.TestcaseConstraintSet import TestcaseConstraintSet
from arelle.testengine.TestcaseVariation import TestcaseVariation


@dataclass(frozen=True)
class TestcaseResult:
    actual_errors: list[ActualError]
    applied_constraint_set: TestcaseConstraintSet
    blocked_errors: dict[str, int]
    constraint_results: list[TestcaseConstraintResult]
    duration_seconds: float
    passed: bool
    skip: bool
    testcase_variation: TestcaseVariation

    def __str__(self) -> str:
        return (
            f"{self.testcase_variation.short_name} \t" +
            self.status.upper() +
            ", ".join(str(r) for r in self.constraint_results)
        ).strip()

    def report(self) -> str:
        return (
            f"[{self}]\n"
            f"\tID: {self.testcase_variation.full_id}\n"
            f"\tStatus: {self.status.upper()}\n"
            f"\tDuration: {self.duration_seconds:.2f} seconds\n"
            f"\tExpected:\n" +
            ("\n".join(f"\t\t {e}" for e in self.applied_constraint_set.constraints) if self.applied_constraint_set.constraints else "\t\t None") + "\n"
            "\tActual:\n" +
            ("\n".join(f"\t\t {e.code}" for e in self.actual_errors) if self.actual_errors else "\t\t None") + "\n"
            "\tBlocked:\n" +
            ("\n".join(f"\t\t {e}: {c}" for e, c in self.blocked_errors.items()) if self.blocked_errors else "\t\t None") + "\n"
            "\tResults:\n" +
            ("\n".join(f"\t\t {r}" for r in self.constraint_results) if self.constraint_results else "\t\t None")
        )

    @property
    def status(self) -> str:
        if self.skip:
            return "skip"
        return "pass" if self.passed else "fail"
