"""Tests for system info."""
from arelle.SystemInfo import getSystemInfo


def test_get_system_info() -> None:
    """Test that function get_system_info returns."""
    function_result = getSystemInfo()

    expected_keys = {
        "arelle_version",
        "arch",
        "args",
        "docker",
        "os_name",
        "os_version",
        "python_branch",
        "python_compiler",
        "python_implementation",
        "python_version",
        "python_virtualenv"
    }

    resulting_keys = set(function_result.keys())

    missing_keys = expected_keys - resulting_keys
    assert len(missing_keys) == 0, f"Missing keys {missing_keys}"
