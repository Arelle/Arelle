from __future__ import annotations

import json
import os
from pathlib import Path

import regex

from tests.integration_tests.scripts.script_util import (
    assert_result,
    parse_args,
    prepare_logfile, run_arelle, validate_log_text,
)

errors = []
this_file = Path(__file__)
args = parse_args(
    this_file.stem,
    "Confirm ESEF validation runs successfully using the webserver.",
    arelle=False,
)
arelle_command = args.arelle
arelle_offline = args.offline
working_directory = Path(args.working_directory)
test_directory = Path(args.test_directory)


instance_files = [
    test_directory / 'a.xml',
    test_directory / 'b.xml',
]

test_cases: list[tuple[str, str, list[str], dict[regex.Pattern[str], int]]] = [
    # Entry point only set in options file
    (
        'options_only',
        json.dumps({
            'validate': True,
            'entrypointFile': str(instance_files[0]),
        }),
        [],
        {
            regex.compile(r'\[IOerror] .*a\.xml'): 1,
        },
    ),
    # Entry point only set via command line arg
    (
        'cli_only',
        json.dumps({
            'validate': True
        }),
        [
            "--file", str(instance_files[0]),
        ],
        {
            regex.compile(r'\[IOerror] .*a\.xml'): 1,
        },
    ),
    # Entry point set via both options file and command line arg (command line arg takes precedence)
    (
        'both',
        json.dumps({
            'validate': True,
            'entrypointFile': str(instance_files[0]),
        }),
        [
            "--file", str(instance_files[1]),
        ],
        {
            regex.compile(r'\[IOerror] .*a\.xml'): 0,
            regex.compile(r'\[IOerror] .*b\.xml'): 1,
        },
    ),
    # Use option provided by plugin
    (
        'plugin_option',
        json.dumps({
            'validate': True,
            'inlineTarget': 'value',
            'plugins': 'inlineXbrlDocumentSet',
            'entrypointFile': str(instance_files[0])
        }),
        [],
        {
            regex.compile(r'\[IOerror] .*a\.xml'): 2,
        },
    ),
    # Invalid option name
    (
        'invalid_option',
        json.dumps({
            'validate': True,
            'inlineTarget': 'value',
            'entrypointFile': str(instance_files[0])
        }),
        [],
        {
            regex.compile(r"Unexpected name 'inlineTarget' found in options file."): 1,
        },
    ),
    # Invalid JSON
    (
        'invalid_json',
        '{ "validate": True }',
        [],
        {
            regex.compile(r'Unable to parse options JSON file: Expecting value: line 1 column 15'): 1,
        },
    ),
    # Duplicate optionsFile arg
    (
        'duplicate_arg',
        json.dumps({
            'validate': True,
        }),
        [
            "--optionsFile", "another_options_file.json",
        ],
        {
            regex.compile(r'Multiple \'optionsFile\' values found during argument preparsing.'): 1,
        },
    ),
    # Missing options file
    (
        'missing',
        '',
        [],
        {
            regex.compile(r'Options file path does not exist: '): 1,
        },
    ),
]
options_files = []

for name, options_json, additional_args, expected_results in test_cases:
    print(f"Running testcase: {name}")
    options_file = str(test_directory / f'{name}.json')
    if name != 'missing':
        with open(test_directory / f'{name}.json', 'w') as f:
            f.write(options_json)
    log_file = prepare_logfile(test_directory, this_file, name=name, ext='txt')
    try:
        run_arelle(
            arelle_command,
            additional_args=[
                "--optionsFile", options_file,
                *additional_args,
            ],
            offline=arelle_offline,
            logFile=log_file,
        )
    except Exception as e:
        with open(log_file, 'a') as f:
            f.write(str(e))
    errors += validate_log_text(log_file, expected_results=expected_results)
    assert_result(errors)
    options_files.append(options_file)

assert_result(errors)

print("Cleaning up")
for options_file in options_files:
    try:
        os.unlink(options_file)
    except OSError:
        pass
