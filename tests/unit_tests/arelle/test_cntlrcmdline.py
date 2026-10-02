"""See COPYRIGHT.md for copyright information."""

from pathlib import Path

import pytest

from arelle.CntlrCmdLine import parseArgs


@pytest.mark.parametrize("option", ["--showEnvironment", "--showenvironment", None])
def test_entrypoint_requirement(
    option: str | None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    args = ["--disablePersistentConfig"]

    if option is None:
        with pytest.raises(SystemExit) as exc:
            parseArgs(args)
        assert exc.value.code == 2
        assert "No entrypoint specified" in capsys.readouterr().err
    else:
        runtimeOptions, _ = parseArgs(args + [option])
        assert runtimeOptions.showEnvironment
        assert runtimeOptions.entrypointFile is None
