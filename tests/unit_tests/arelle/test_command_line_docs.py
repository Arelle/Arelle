import subprocess
import sys
from pathlib import Path

import regex

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def test_help_options_documented():
    """Every option in --help output should appear in command_line.md docs."""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "arelleCmdLine.py"), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"--help failed: {result.stderr}"
    helpOptions = {m.lower() for m in regex.findall(r"--([a-zA-Z][\w-]*)", result.stdout)}

    docsText = (PROJECT_ROOT / "docs" / "source" / "command_line.md").read_text(encoding="utf-8")
    docsOptions = {m.lower() for m in regex.findall(r"--([a-zA-Z][\w-]*)", docsText)}

    missing = helpOptions - docsOptions
    assert not missing, (
        f"CLI options from --help not found in docs/source/command_line.md: "
        f"{', '.join(f'--{o}' for o in sorted(missing))}"
    )
