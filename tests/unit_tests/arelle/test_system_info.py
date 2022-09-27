"""Tests for system info."""
from arelle.SystemInfo import get_system_info


def test_get_system_info() -> None:
    """Test that function get_system_info returns."""
    function_result = get_system_info()

    expected_keys = {
        "arch",
        "docker",
        "os_name",
        "version_arelle",
        "version_os",
        "version_python",
        "virtualenv"
    }

    resulting_keys = set(function_result.keys())

    missing_keys = expected_keys - resulting_keys
    assert len(missing_keys) == 0, f"Missing keys {missing_keys}"
