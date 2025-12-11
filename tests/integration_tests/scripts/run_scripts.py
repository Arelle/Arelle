from __future__ import annotations

import subprocess
import sys
from argparse import ArgumentParser, Namespace
from typing import Any, TYPE_CHECKING, cast

import pytest

from tests.integration_tests.download_cache import download_and_apply_cache
from tests.integration_tests.scripts.discover_tests import get_all_scripts, get_frozen_build_scripts

if TYPE_CHECKING:
    from _pytest.mark import ParameterSet

ALL_SCRIPTS_ZIP = "scripts/all_scripts.zip"
ARGUMENTS: list[dict[str, Any]] = [
    {
        "name": "--all",
        "action": "store_true",
        "help": "Select all configured integration tests."
    },
    {
        "name": "--all-frozen-builds",
        "action": "store_true",
        "help": "Select all configured integration tests that should run against frozen builds."
    },
    {
        "name": "--arelle",
        "action": "store",
        "help": "CLI command to run Arelle"
    },
    {
        "name": "--download-cache",
        "action": "store_true",
        "help": "Whether or not to download and apply cache."
    },
    {
        "name": "--list",
        "action": "store_true",
        "help": "List names of all integration tests."
    },
    {
        "name": "--name",
        "action": "store",
        "help": "Only run scripts whose name (stem) matches given name(s), comma-delimited."
    },
    {
        "name": "--offline",
        "action": "store_true",
        "help": "Whether or not Arelle should run in offline mode."
    },
    {
        "name": "--working-directory",
        "action": "store",
        "help": "Directory to place temporary files and log output."
    },
]


def run_script_options(options: Namespace) -> list[ParameterSet]:
    assert options.arelle, '--arelle is required'
    if options.all:
        scripts = get_all_scripts()
        if options.download_cache:
            download_and_apply_cache(
                ALL_SCRIPTS_ZIP,
                version_id='CNTq_CLLvVEpcpxw9x4ipF76gD7zvZWD'
            )
    elif options.all_frozen_builds:
        scripts = get_frozen_build_scripts()
    else:
        assert options.name, '--name or --all is required'
        scripts = [
            s
            for s in get_all_scripts()
            if s.stem in options.name.split(',')
        ]
    all_results = []
    assert scripts, 'No scripts found'
    for script in scripts:
        modulePath = script.parent.joinpath(script.stem).as_posix().replace('/', '.')
        args = [sys.executable, '-m', modulePath]
        args.extend(['--arelle', options.arelle])
        if options.download_cache and not options.all:
            # Only pass download cache arg if we didn't just download ALL_SCRIPTS_ZIP above
            args.append('--download-cache')
        if options.offline:
            args.append('--offline')
        if options.working_directory is not None:
            args.extend(['--working-directory', options.working_directory])

        print(f'Running integration test script "{script.stem}": {args}')
        result = subprocess.run(args, capture_output=True)
        returncode = result.returncode
        stderr = result.stderr.decode().strip()
        param = pytest.param(
            {
                'returncode': returncode,
                'stderr': stderr
            },
            id=script.stem,
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
        for name in get_all_scripts():
            print(name)
    else:
        results = run_script_options(options)
        for result in results:
            values = cast(dict[str, Any], result.values[0])
            returncode = values.get("returncode")
            if returncode == 0:
                print(f"{result.id} passed")
            else:
                stderr = values.get("stderr")
                print(f'"{result.id}" failed with code {returncode}:\n{stderr}\n', file=sys.stderr)


if __name__ == "__main__":
    run()
