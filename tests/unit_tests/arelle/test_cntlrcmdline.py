"""See COPYRIGHT.md for copyright information."""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


@pytest.mark.parametrize("option", ["--showEnvironment", "--showenvironment", None])
def test_entrypoint_requirement(
    option: str | None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARELLE_ARGS", "")
    args = [
        sys.executable, str(PROJECT_ROOT / "arelleCmdLine.py"),
        "--disablePersistentConfig", "--xdgConfigHome", str(tmp_path),
    ]
    if option is not None:
        args.append(option)
    result = subprocess.run(args, capture_output=True, text=True)

    if option is None:
        assert result.returncode != 0
        assert "No entrypoint specified" in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert "Config directory:" in result.stdout
        assert "Cache directory:" in result.stdout
