from __future__ import annotations

from arelle.oim._tc.metadata.common import TCMetadataValidationError

_TEST_CODE = "test:code"


class TestTCMetadataValidationError:
    def test_initial_json_pointer(self) -> None:
        err = TCMetadataValidationError("test", "key", code=_TEST_CODE)
        assert err.json_pointer == "/key"

    def test_multi_segment_path(self) -> None:
        err = TCMetadataValidationError("test", "a", "b", "key", code=_TEST_CODE)
        assert err.json_pointer == "/a/b/key"

    def test_prepend_path_accumulates_segments(self) -> None:
        err = TCMetadataValidationError("test", "field", code=_TEST_CODE)
        err.prepend_path("a", "b")
        assert err.json_pointer == "/a/b/field"
        err.prepend_path("root")
        assert err.json_pointer == "/root/a/b/field"

    def test_str_format(self) -> None:
        err = TCMetadataValidationError("Expected str, got int: 42", "key", code=_TEST_CODE)
        assert str(err) == "/key: Expected str, got int: 42"

    def test_error_code(self) -> None:
        err = TCMetadataValidationError("test", "key", code=_TEST_CODE)
        assert err.code == _TEST_CODE
