from dataclasses import dataclass


@dataclass(frozen=True)
class TestSuiteOptions:
    indexFile: str
    options: str
    parallel: bool
