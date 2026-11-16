"""See COPYRIGHT.md for copyright information."""

from pathlib import Path

import pytest

from arelle.CntlrCmdLine import CntlrCmdLine, parseArgs
from arelle.RuntimeOptions import RuntimeOptions


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


@pytest.mark.parametrize(("startupLang", "requestLang", "warns"), [
    ("ka", "ka", False),
    ("ka", "ka-GE", False),
    (None, "en", False),
    ("ka", "fr", True),
    (None, "ka", True),
])
def test_run_warns_uiLang_not_applied(
    startupLang: str | None, requestLang: str, warns: bool,
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("LANG", "en_GB.UTF-8")
    cntlr = CntlrCmdLine(uiLang=startupLang, disable_persistent_config=True)
    messageCodes = []
    monkeypatch.setattr(cntlr, "addToLog", lambda *args, messageCode="", **kwargs: messageCodes.append(messageCode))
    cntlr.run(RuntimeOptions(uiLang=requestLang, disablePersistentConfig=True))
    assert ("arelle:uiLangNotApplied" in messageCodes) == warns
