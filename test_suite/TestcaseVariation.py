from dataclasses import dataclass

from test_suite.ExpectedErrorSet import ExpectedErrorSet


@dataclass(frozen=True)
class TestcaseVariation:
    id: str
    name: str
    description: str
    base: str
    readFirstUris: list[str]
    status: str
    expectedErrorSet: ExpectedErrorSet | None
