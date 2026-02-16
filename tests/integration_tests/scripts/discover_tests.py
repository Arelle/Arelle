from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import TypedDict

import itertools
import sys

from ..github import LINUX, MACOS, WINDOWS

ALL_OPERATING_SYSTEMS = [LINUX, MACOS, WINDOWS]
ALL_PYTHON_VERSIONS = (
    '3.10',
    '3.11',
    '3.12',
    '3.13',
    '3.14.2',
)
LATEST_PYTHON_VERSION = '3.14.2'
PRIMARY_OPERATING_SYSTEM = LINUX
FUNCTION_REGISTRY_TESTS = frozenset({
    'xbrl_formula_1_0_function_registry',
    'xbrl_transformation_registry_3',
    'xbrl_transformation_registry_4',
    'xbrl_transformation_registry_5',
})
NO_CI_TESTS = frozenset([
    'conformance_suite_configs'
])
TESTS_PATH = './tests/integration_tests/scripts/tests'


class Entry(TypedDict, total=False):
    environment: str
    name: str
    os: str
    private: bool
    python_version: str

def generate_config_entry(name: str, os: str, private: bool, python_version: str) -> Entry:
    e: Entry = {
        'environment': 'integration-tests' if private else 'none',
        'name': name,
        'os': os,
        'private': private,
        'python_version': python_version,
    }
    return e


def get_all_scripts() -> list[Path]:
    """
    Returns absolute paths of runnable scripts based on the operating system.
    :return: Tuple of runnable scripts.
    """
    return [x for x in Path(TESTS_PATH).glob('**/*.py')]

def get_frozen_build_scripts() -> list[Path]:
    """
    Returns absolute paths of scripts that frozen builds should be tested against.
    :return: Tuple of runnable scripts.
    """
    return [p for p in get_all_scripts() if _for_frozen_build(p)]

def _for_frozen_build(path: Path) -> bool:
    if path.stem.startswith("python_api_"):
        return False
    if _is_no_ci(path):
        return False
    if _is_private(path):
        return False
    return True

def _is_no_ci(path: Path) -> bool:
    return path.stem in NO_CI_TESTS

def _is_private(path: Path) -> bool:
    return path.stem in FUNCTION_REGISTRY_TESTS

def _run_for_each_os(path: Path) -> bool:
    return path.stem not in FUNCTION_REGISTRY_TESTS

def _run_for_each_version(path: Path) -> bool:
    return path.stem not in FUNCTION_REGISTRY_TESTS

def main() -> None:
    output: list[Entry] = []
    groups = defaultdict(list)
    for path in get_all_scripts():
        if _is_no_ci(path):
            continue
        systems = ALL_OPERATING_SYSTEMS if _run_for_each_os(path) else [PRIMARY_OPERATING_SYSTEM]
        versions = ALL_PYTHON_VERSIONS if  _run_for_each_version(path) else [LATEST_PYTHON_VERSION]
        private = _is_private(path)
        for system, version in itertools.product(systems, versions):
            groups[(system, version, private)].append(path)

    for (system, version, private), paths in groups.items():
        output.append(generate_config_entry(
            name=','.join(p.stem for p in paths),
            os=system,
            private=private,
            python_version=version
        ))

    json.dump(output, sys.stdout, indent=4)
    print()


if __name__ == '__main__':
    main()
