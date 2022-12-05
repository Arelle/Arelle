import os
from dataclasses import dataclass, field


CONFORMANCE_SUITE_PATH_PREFIX = 'tests/resources/conformance_suites'


@dataclass(frozen=True)
class ConformanceSuiteConfig:
    file: str
    info_url: str
    local_filepath: str
    name: str
    additional_downloads: dict[str, str] = field(default_factory=dict)
    args: list[str] = field(default_factory=list)
    capture_warnings: bool = True
    expected_empty_testcases: frozenset[str] = frozenset()
    expected_failure_ids: frozenset[str] = frozenset()
    expected_model_errors: frozenset[str] = frozenset()
    extract_path: str = None
    membership_url: str = None
    public_download_url: str = None
    url_replace: str = None

    @property
    def prefixed_extract_filepath(self):
        if self.extract_path is None:
            return None
        return os.path.join(CONFORMANCE_SUITE_PATH_PREFIX, self.extract_path)

    @property
    def prefixed_local_filepath(self):
        return os.path.join(CONFORMANCE_SUITE_PATH_PREFIX, self.local_filepath)
