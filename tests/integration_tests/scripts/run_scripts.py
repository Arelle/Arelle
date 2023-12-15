from __future__ import annotations

import os
import subprocess
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any, TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.mark import ParameterSet


ARGUMENTS: list[dict[str, Any]] = [
    {
        "name": "--all",
        "action": "store_true",
        "help": "Select all configured integration tests"
    },
    {
        "name": "--cli",
        "action": "store",
        "help": "Determines the arelleCmdLine command"
    },
    {
        "name": "--list",
        "action": "store_true",
        "help": "List names of all integration tests"
    },
    {
        "name": "--name",
        "action": "append",
        "help": "Only run scripts whose name (stem) matches given name(s)"
    },
]
EXT_BAT = '.bat'
EXT_SH = '.sh'
SCRIPT_TYPES = (EXT_BAT, EXT_SH)
TESTS_PATH = './tests/integration_tests/scripts/tests'


def _get_all_scripts() -> list[Path]:
    """
    Returns absolute paths of runnable scripts based on the operating system.
    :return: Tuple of runnable scripts.
    """
    script_type = EXT_BAT if os.name == 'nt' else EXT_SH
    return [x.resolve() for x in Path(TESTS_PATH).glob('**/*') if x.suffix == script_type]


def run_script_options(options: Namespace) -> list[ParameterSet]:
    assert options.cli, '--cli is required'
    all_scripts = _get_all_scripts()
    if options.all:
        scripts = all_scripts
    else:
        names = options.name
        assert names, '--name or --all is required'
        scripts = [s for s in all_scripts if s.stem in names]
    all_results = []
    assert scripts, 'No scripts found'
    for script in scripts:
        scriptPath = script.as_posix()
        print('Running integration test script: ' + scriptPath)
        result = subprocess.run([scriptPath, options.cli], capture_output=True)
        stderr = result.stderr.decode()
        param = pytest.param(
            {
                'status': 'pass' if result.returncode == 0 else 'fail',
                'expected': '',
                'actual': stderr.strip()
            },
            id=scriptPath,
            marks=[],
        )
        all_results.append(param)
    return all_results


def run() -> None:
    parser = ArgumentParser(prog=sys.argv[0])
    for arg in ARGUMENTS:
        arg_without_name = {k: v for k, v in arg.items() if k != "name"}
        parser.add_argument(arg["name"], **arg_without_name)
    options = parser.parse_args(sys.argv[1:])
    if options.list:
        for name in _get_all_scripts():
            print(name)
    else:
        run_script_options(options)


if __name__ == "__main__":
    run()
