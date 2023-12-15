import pytest
from tests.integration_tests.scripts.run_scripts import (
    ARGUMENTS,
    run_script_options
)


def pytest_addoption(parser: pytest.Parser) -> None:
    for arg in ARGUMENTS:
        arg_without_name = {k: v for k, v in arg.items() if k != "name"}
        parser.addoption(arg["name"], **arg_without_name)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """
    Parameterizes script_results for passing results to test_script
    https://docs.pytest.org/en/latest/how-to/parametrize.html#basic-pytest-generate-tests-example
    """
    config = metafunc.config
    options = config.option
    results = run_script_options(options)
    metafunc.parametrize("script_results", results)
