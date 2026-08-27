"""
Confirms the webserver example published on the website still produces the output published with it.
"""
from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from tests.integration_tests.scripts.script_util import (
    _get_arelle_args,
    assert_result,
    parse_args,
    wait_for_localhost_port,
)

COMMAND_PREFIX = "arelleCmdLine "
IGNORED_OUTPUT_PREFIXES = (
    "Bottle v",
    "WARNING: Arelle's built-in webserver",
)

errors: list[str] = []
this_file = Path(__file__)
repository_root = this_file.parents[4]
examples_directory = repository_root / "docs" / "website" / "examples"
command_path = examples_directory / "webserver-command.txt"
output_path = examples_directory / "webserver-output.txt"

args = parse_args(
    this_file.stem,
    "Confirm the arelle.org webserver example still produces its published output.",
)

command_line = command_path.read_text().strip()
expected_output = [
    line.rstrip()
    for line in output_path.read_text().splitlines()
    if line.strip()
]
assert command_line.startswith(COMMAND_PREFIX), (
    f"Unexpected command in {command_path}: {command_line}"
)

example_args = shlex.split(command_line.removeprefix(COMMAND_PREFIX))
print(f"Running published example: {command_line}")
port = int(example_args[example_args.index("--webserver") + 1].split(":")[1])
process = subprocess.Popen(
    _get_arelle_args(
        args.arelle,
        additional_args=example_args,
        offline=args.offline,
    ),
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)
try:
    wait_for_localhost_port(port, process)
finally:
    if process.poll() is None:
        process.kill()
    output, _ = process.communicate()

actual_output = [
    line.rstrip()
    for line in output.decode().splitlines()
    if line.strip() and not line.startswith(IGNORED_OUTPUT_PREFIXES)
]
if actual_output != expected_output:
    errors.append(
        "Published output is out of date. Update {} to match:\n{}".format(
            output_path.relative_to(repository_root),
            "\n".join(actual_output),
        )
    )

assert_result(errors)
