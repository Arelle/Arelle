import json
from pathlib import Path

import regex

from arelle.plugin.validate import ESEF
from arelle.plugin.validate.ESEF.Util import AUTHORITY_CODES

_AUTHORITY_VALIDATIONS_PATH = Path(ESEF.__file__).parent / "resources" / "authority-validations.json"

_NON_AUTHORITY_KEY_PATTERN = regex.compile(r"copyright|description|default|ESEF-\d{4}(?:-DRAFT)?")


class TestAuthorityCodes:
    def test_authority_codes_match_json(self) -> None:
        with open(_AUTHORITY_VALIDATIONS_PATH, encoding="utf-8") as f:
            validations = json.load(f)
        jsonAuthorityCodes = {
            key
            for key, value in validations.items()
            if isinstance(value, dict) and not _NON_AUTHORITY_KEY_PATTERN.fullmatch(key)
        }
        assert jsonAuthorityCodes == AUTHORITY_CODES, (
            f"AUTHORITY_CODES mismatch with authority-validations.json. "
            f"Missing from AUTHORITY_CODES: {jsonAuthorityCodes - AUTHORITY_CODES}, "
            f"Extra in AUTHORITY_CODES: {AUTHORITY_CODES - jsonAuthorityCodes}"
        )
