"""
Confirms the plugin example published on the website still produces the output published with it.
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path

from tests.integration_tests.scripts.script_util import (
    assert_result,
    parse_args,
    run_arelle_cmd,
)

COMMAND_PREFIX = "arelleCmdLine "

errors: list[str] = []
this_file = Path(__file__)
repository_root = this_file.parents[4]
examples_directory = repository_root / "docs" / "website" / "examples"
filing_path = examples_directory / "filing" / "demo-20251231.xbrl"
plugin_path = examples_directory / "house_rules"
command_path = examples_directory / "plugin-command.txt"
output_path = examples_directory / "plugin-output.txt"

args = parse_args(
    this_file.stem,
    (
        "Confirm the arelle.org plugin example still produces "
        "its published output."
    ),
)

command_line = command_path.read_text().strip()
command_text = re.sub(r"\\\r?\n[ \t]*", " ", command_line)
expected_output = [
    line.rstrip()
    for line in output_path.read_text().splitlines()
    if line.strip()
]
assert command_line.startswith(COMMAND_PREFIX), (
    f"Unexpected command in {command_path}: {command_line}"
)

# The website shows bare filenames; run the same arguments against the
# committed files so the published command is the one actually executed.
paths_by_name = {filing_path.name: filing_path, plugin_path.name: plugin_path}
example_args = [
    str(paths_by_name.get(argument, argument))
    for argument in shlex.split(command_text.removeprefix(COMMAND_PREFIX))
]

print(f"Running published example: {command_line}")
result = run_arelle_cmd(
    args.arelle,
    additional_args=example_args,
    offline=args.offline,
)
if result.returncode != 0:
    errors.append(
        f"Arelle exited {result.returncode}: "
        f"{result.stderr.decode().strip()}"
    )

output = (result.stdout + result.stderr).decode()
actual_output = [line.rstrip() for line in output.splitlines() if line.strip()]
if actual_output != expected_output:
    errors.append(
        "Published output is out of date. Update {} to match:\n{}".format(
            output_path.relative_to(repository_root),
            "\n".join(actual_output),
        )
    )

assert_result(errors)
