from dataclasses import dataclass

from test_suite.TestcaseConstraintSet import TestcaseConstraintSet


@dataclass(frozen=True)
class TestcaseVariation:
    id: str
    name: str
    description: str
    base: str
    readFirstUris: list[str]
    shortName: str
    status: str
    testcaseConstraintSet: TestcaseConstraintSet | None
    blockedCodePattern: str

    @property
    def fullId(self) -> str:
        return f"{self.base}:{self.id}"
