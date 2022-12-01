from tests.integration_tests.validation.run_conformance_suites import (
    ARGUMENTS,
    run_conformance_suites_options
)


def pytest_addoption(parser):
    for arg in ARGUMENTS:
        parser.addoption(arg["name"], action=arg["action"], help=arg["help"])


def pytest_generate_tests(metafunc):
    """
    Parameterizes conformance_suite_results for passing results to test_conformance_suite
    https://docs.pytest.org/en/latest/how-to/parametrize.html#basic-pytest-generate-tests-example
    """
    config = metafunc.config
    options = config.option
    options.log_to_file = False
    options.test = True
    results = run_conformance_suites_options(options)
    metafunc.parametrize("conformance_suite_results", results)
