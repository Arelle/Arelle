import pytest
import sys
from argparse import ArgumentParser, Namespace
from tests.integration_tests.validation.validation_util import get_conformance_suite_test_results
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig
from tests.integration_tests.validation.conformance_suite_configs import (
    ALL_CONFORMANCE_SUITE_CONFIGS,
    PUBLIC_CONFORMANCE_SUITE_CONFIGS
)
from tests.integration_tests.validation.download_conformance_suites import (
    download_conformance_suite, extract_conformance_suite
)

ARGUMENTS = [
    {
        "name": "--all",
        "action": "store_true",
        "help": "Select all configured conformance suites"
    },
    {
        "name": "--download-overwrite",
        "action": "store_true",
        "help": "Download (and overwrite) selected conformance suite files"
    },
    {
        "name": "--download-missing",
        "action": "store_true",
        "help": "Download missing selected conformance suite files"
    },
    {
        "name": "--list",
        "action": "store_true",
        "help": "List names of all configured conformance suites"
    },
    {
        "name": "--log-to-file",
        "action": "store_true",
        "help": "Writes logs and results to .txt and .csv files"
    },
    {
        "name": "--name",
        "action": "store",
        "help": "Select only conformance suites with given names, comma delimited"
    },
    {
        "name": "--offline",
        "action": "store_true",
        "help": "Run without loading anything from the internet (local files and cache only)"
    },
    {
        "name": "--public",
        "action": "store_true",
        "help": "Select all public conformance suites"
    },
    {
        "name": "--test",
        "action": "store_true",
        "help": "Run selected conformance suite tests"
    },
]
DOWNLOAD_MISSING = 'missing'
DOWNLOAD_OVERWRITE = 'overwrite'
SELECT_ALL = 'all'
SELECT_PUBLIC = 'public'


def _get_conformance_suite_names(select_option: str) -> tuple[ConformanceSuiteConfig, ...]:
    if select_option == SELECT_ALL:
        return ALL_CONFORMANCE_SUITE_CONFIGS
    elif select_option == SELECT_PUBLIC:
        return PUBLIC_CONFORMANCE_SUITE_CONFIGS
    elif select_option:
        filter_list = select_option.split(',')
        names = []
        for filter_item in filter_list:
            match_configs = [c for c in ALL_CONFORMANCE_SUITE_CONFIGS if c.name == filter_item]
            if not match_configs:
                raise ValueError(f'Provided name "{filter_item}" did not match any configured conformance suite names.')
            names.extend(match_configs)
        return tuple(names)
    else:
        raise ValueError('Please use --all, --public, or --name to specify which conformance suites to use.')


def run_conformance_suites(
        select_option: str,
        test_option: bool,
        download_option: str = None,
        log_to_file: bool = False,
        offline_option: bool = False) -> list[pytest.param]:
    conformance_suite_configs = _get_conformance_suite_names(select_option)
    if download_option:
        overwrite = download_option == DOWNLOAD_OVERWRITE
        for conformance_suite_config in conformance_suite_configs:
            download_conformance_suite(conformance_suite_config, overwrite=overwrite)
    for conformance_suite_config in conformance_suite_configs:
        extract_conformance_suite(conformance_suite_config)
    all_results = []
    if test_option:
        for config in conformance_suite_configs:
            results = get_conformance_suite_test_results(config, log_to_file=log_to_file, offline=offline_option)
            all_results.extend(results)
    return all_results


def run_conformance_suites_options(options: Namespace) -> list[pytest.param]:
    select_option = get_select_option(options)
    download_option = get_download_option(options)
    return run_conformance_suites(
        select_option=select_option,
        test_option=options.test,
        download_option=download_option,
        log_to_file=options.log_to_file,
        offline_option=options.offline
    )


def get_download_option(options: Namespace) -> str | None:
    if options.download_overwrite:
        return DOWNLOAD_OVERWRITE
    elif options.download_missing:
        return DOWNLOAD_MISSING
    return None


def get_select_option(options: Namespace) -> str:
    if options.all:
        return SELECT_ALL
    elif options.public:
        return SELECT_PUBLIC
    return options.name


def run() -> None:
    parser = ArgumentParser(prog=sys.argv[0])
    for arg in ARGUMENTS:
        parser.add_argument(arg["name"], action=arg["action"], help=arg["help"])
    options = parser.parse_args(sys.argv[1:])
    if options.list:
        for config in ALL_CONFORMANCE_SUITE_CONFIGS:
            print(f'{config.name}\n'
                  f'\tInfo:       {config.info_url}\n'
                  f'\tDownload:   {config.public_download_url or config.membership_url}\n'
                  f'\tLocal Path: {config.prefixed_local_filepath}')
    else:
        run_conformance_suites_options(options)


if __name__ == "__main__":
    run()
