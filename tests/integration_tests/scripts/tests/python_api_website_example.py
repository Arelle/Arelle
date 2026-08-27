"""
Confirms the Python API example published on arelle.org still produces the
published output.

The command and output files in docs/website/examples are the contract. This
script runs the published script itself, so the code on the website and its
published output cannot drift apart.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tests.integration_tests.scripts.script_util import assert_result, parse_args

errors: list[str] = []
this_file = Path(__file__)
repository_root = this_file.parents[4]
examples_directory = repository_root / "docs" / "website" / "examples"
filing_directory = examples_directory / "filing"
script_path = examples_directory / "revenue.py"
command_path = examples_directory / "python-api-command.txt"
output_path = examples_directory / "python-api-output.txt"
expected_command = f"python {script_path.name}"

args = parse_args(
    this_file.stem,
    "Confirm the arelle.org Python API example still produces its published output.",
    arelle=False,
)

command_line = command_path.read_text().strip()
expected_output = [
    line.rstrip()
    for line in output_path.read_text().splitlines()
    if line.strip()
]


# Test does not guarantee the order of facts in factsByLocalName.
def normalize_output(output: list[str]) -> list[str]:
    return output[:1] + sorted(output[1:])


assert command_line == expected_command, (
    f"Unexpected command in {command_path}: {command_line}"
)

# The published script resolves the filing relative to the working directory,
# so run it the way the website tells the reader to.
environment = dict(os.environ, PYTHONPATH=str(repository_root))
print(f"Running published example: {command_line}")
result = subprocess.run(
    [sys.executable, str(script_path)],
    capture_output=True,
    cwd=filing_directory,
    env=environment,
)
if result.returncode != 0:
    errors.append(
        f"Example exited {result.returncode}: "
        f"{result.stderr.decode().strip()}"
    )

actual_output = [
    line.rstrip()
    for line in result.stdout.decode().splitlines()
    if line.strip()
]
if normalize_output(actual_output) != normalize_output(expected_output):
    errors.append(
        "Published output is out of date. Update {} to match:\n{}".format(
            output_path.relative_to(repository_root),
            "\n".join(actual_output),
        )
    )

assert_result(errors)
