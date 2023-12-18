import pytest
from tests.integration_tests.validation.run_conformance_suites import (
    ARGUMENTS,
    run_conformance_suites_options
)


def pytest_addoption(parser: pytest.Parser) -> None:
    for arg in ARGUMENTS:
        arg_without_name = {k: v for k, v in arg.items() if k != "name"}
        parser.addoption(arg["name"], **arg_without_name)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """
    Parameterizes conformance_suite_results for passing results to test_conformance_suite
    https://docs.pytest.org/en/latest/how-to/parametrize.html#basic-pytest-generate-tests-example
    """
    config = metafunc.config
    options = config.option
    options.test = True
    results = run_conformance_suites_options(options)
    metafunc.parametrize("conformance_suite_results", results)
