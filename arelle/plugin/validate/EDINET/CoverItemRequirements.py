"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import json
from pathlib import Path


# Cover item requirements do not appear to be specifically documented anywhere,
# so we have inferred them from the documentation and sample filings available to us:
#   Cover item requirements loaded by starting with "Taxonomy Element List" (ESE140114.xlsx),
#   which appears to give a mapping of ELR URIs to required cover items (Concepts with
#   "*CoverPage" local names). However, the sequence of the cover items (validated by EC1004E)
#   does not match the order in samples #10, #11, #21 and #22. In those cases, the sequences
#   have been updated to match the samples.
# A note at the bottom of "3-4-2 Cover Page" within "File Specification for EDINET Filing"
# (ESE140104.pdf) indicates that cover pages are either generated within EDINET's submission
# UI or manually. The manual process involves downloading a template cover page HTML file, editing it,
# and then re-uploading it. This suggests that there are cover page template files that may be the most
# reliable source of truth for cover item requirements, but we have not been able to access these templates.
class CoverItemRequirements:
    _jsonPath: Path
    _data: dict[str, list[str]] | None

    def __init__(self, jsonPath: Path):
        self._jsonPath = jsonPath
        self._data = None

    def _load(self) -> dict[str, list[str]]:
        if self._data is None:
            with open(self._jsonPath, encoding='utf-8') as f:
                self._data = json.load(f)
        return self._data

    def all(self) -> frozenset[str]:
        data = self._load()
        return frozenset(v for values in data.values() for v in values)

    def get(self, roleUri: str) -> list[str]:
        data = self._load()
        return data.get(roleUri, [])
