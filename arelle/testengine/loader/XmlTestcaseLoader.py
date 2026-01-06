"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Iterable, Any

from arelle.Cntlr import Cntlr
from arelle.ModelDocument import ModelDocument, Type as ModelDocumentType
from arelle.ModelTestcaseObject import ModelTestcaseVariation
from arelle.ModelValue import QName
from arelle.RuntimeOptions import RuntimeOptions
from arelle.api.Session import Session
from arelle.testengine.ErrorLevel import ErrorLevel
from arelle.testengine.TestEngineOptions import TestEngineOptions
from arelle.testengine.TestcaseConstraint import TestcaseConstraint
from arelle.testengine.TestcaseConstraintSet import TestcaseConstraintSet
from arelle.testengine.TestcaseVariation import TestcaseVariation
from arelle.testengine.TestcaseVariationSet import TestcaseVariationSet
from arelle.testengine.loader.TestcaseLoader import TestcaseLoader, TESTCASE_LOADER_ERROR_PREFIX

CALC_MODES_MAP: dict[str | None, str] = {
    'truncate': 'truncation',
}
CWD = Path.cwd()
PARAMETER_SEPARATOR = '\n'
TARGET_SUFFIX_SEPARATOR = '|'


def _get_calc_mode(testcase_variation: ModelTestcaseVariation) -> str | None:
    """
    Determine a single calculation mode for the variation.
    Raises an AssertionError if it is ambiguous.
    :param testcase_variation:
    :return: The calculation mode to use for this testcase variation.
    """
    calc_modes = {
        calc_mode
        for result_elt in testcase_variation.iterdescendants("{*}result")
        if (calc_mode := result_elt.attr('{https://xbrl.org/2023/conformance}mode')) is not None
    }
    assert len(calc_modes) <= 1, f"Multiple calculation modes found: {calc_modes}."
    calc_mode = next(iter(calc_modes), None)
    calc_mode = CALC_MODES_MAP.get(calc_mode, calc_mode)
    return calc_mode


def _get_constraints(testcase_variation: ModelTestcaseVariation) -> list[TestcaseConstraint]:
    """
    Given a ModelTestcaseVariation, build list of testcase constraints.
    :param testcase_variation:
    :return: Testcase constraints.
    """
    constraints = []
    expected = testcase_variation.expected or 'valid'
    if not isinstance(expected, list):
        expected = [expected]
    for error in expected:
        constraints.extend(_get_error_constraints(error))
    expected_warnings = testcase_variation.expectedWarnings or []
    for warning in expected_warnings:
        constraints.extend(_get_warning_constraints(warning))
    return constraints


def _get_error_constraints(error: Any) -> list[TestcaseConstraint]:
    """
    Build testcase constraints based off of expected errors.
    :param error: Error object of indeterminate type.
    :return: Testcase constraints.
    """
    constraints = []
    if error == 'valid':
        pass
    elif error == 'invalid':
        constraints.append(TestcaseConstraint(
            pattern='*',  # matches any code
        ))
    elif isinstance(error, QName):
        constraints.append(TestcaseConstraint(
            qname=error,
        ))
    elif isinstance(error, str):
        constraints.append(TestcaseConstraint(
            pattern=error,
        ))
    elif isinstance(error, dict):
        for pattern, assertions in error.items():
            satisfied_count, not_satisfied_count = assertions
            count_map = {
                ErrorLevel.SATISIFED: satisfied_count,
                ErrorLevel.NOT_SATISFIED: not_satisfied_count,
            }
            for level, count in count_map.items():
                for i in range(0, count):
                    constraints.append(TestcaseConstraint(
                        level=level,
                        pattern=pattern,
                    ))
    else:
        raise ValueError(f"Unexpected expected error type: {type(error)}")
    return constraints


def _get_parameters(testcase_variation: ModelTestcaseVariation) -> list[str]:
    """
    Build parameters arguments based given a ModelTestcaseVariation
    :param testcase_variation:
    :return: Parameters arguments for setting in RuntimeOptions.
    """
    parameters = [
        f'{k.clarkNotation}={v[1]}'
        for k, v in testcase_variation.parameters.items()
    ]
    assert all(PARAMETER_SEPARATOR not in parameter for parameter in parameters), \
        'Parameter separator found in parameter key or value.'
    return parameters


def _get_warning_constraints(warning: Any) -> list[TestcaseConstraint]:
    """
    Build testcase constraints based off of expected warnings.
    TODO: Ideally Arelle would retain the level (ERROR vs. WARNING) of logged errors,
      which would allow us to validate that the correct level was logged here.
      For now, all constraints will expect errors, and Arelle can be configured to elevate
      all fired warnings as errors.
    :param warning: Warning object of indeterminate type.
    :return: Testcase constraints.
    """
    constraints = []
    if isinstance(warning, QName):
        constraints.append(TestcaseConstraint(
            level=ErrorLevel.ERROR,
            qname=warning,
        ))
    elif isinstance(warning, str):
        constraints.append(TestcaseConstraint(
            level=ErrorLevel.ERROR,
            pattern=warning,
        ))
    else:
        raise ValueError(f"Unexpected expected warning type: {type(warning)}")
    return constraints


def _iter_targets(testcase_variation: ModelTestcaseVariation) -> Iterable[str | None]:
    """
    Iterate over the targets involved in this testcase variation.
    Each unique target in a source variation triggers a separate execution.
    :param testcase_variation:
    :return: Iterable of inline target values.
    """
    targets = [
        inst_elt.get("target")
        for result_elt in testcase_variation.iterdescendants("{*}result")
        for inst_elt in result_elt.iterdescendants("{*}instance")
    ] or [None]
    for target in targets:
        if len(targets) > 1 and target is None:
            target = "(default)"
        yield target


def _load_testcase_doc(doc: ModelDocument, test_engine_options: TestEngineOptions, testcase_variations: list[TestcaseVariation]) -> bool:
    """
    Appends the given document's testcase variations to the given list.
    :param doc:
    :param test_engine_options:
    :param testcase_variations:
    :return: Whether any testcases were found
    """
    testcases_found = False
    doc_path = Path(doc.uri)
    root_dir = Path(test_engine_options.index_file).absolute().parent
    doc_path = doc_path.relative_to(root_dir) if doc_path.is_relative_to(root_dir) else doc_path
    for testcase_variation in getattr(doc, "testcaseVariations", []):
        base = testcase_variation.base
        assert base is not None
        if base.startswith("file:\\"):
            base = base[6:]
        for target in _iter_targets(testcase_variation):
            testcase_variation.ixdsTarget = target
            assert TARGET_SUFFIX_SEPARATOR not in testcase_variation.id, \
                f"The '{TARGET_SUFFIX_SEPARATOR}' character is used internally as a separator " + \
                "and can not be included in a testcase variation ID."
            local_id = f"{testcase_variation.id}" + (f"{TARGET_SUFFIX_SEPARATOR}{target}" if target else "")
            full_id = f"{base}:{local_id}"
            short_name = f"{doc_path}:{local_id}"

            calc_mode = _get_calc_mode(testcase_variation)
            constraints = _get_constraints(testcase_variation)
            parameters = _get_parameters(testcase_variation)

            compare_instance_uri = None
            compare_formula_output_uri = None
            instance_uri = testcase_variation.resultXbrlInstanceUri
            if instance_uri:
                compare_instance_uri = Path(doc.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(instance_uri, testcase_variation.base))
                if test_engine_options.compare_formula_output:
                    compare_formula_output_uri = compare_instance_uri
                    compare_instance_uri = None

            # TODO: testcase_variation.resultTableUri (not currently validated)

            testcase_constraint_set = TestcaseConstraintSet(
                constraints=constraints,
                match_all=test_engine_options.match_all,
            )
            testcase_variations.append(TestcaseVariation(
                base=base,
                blocked_code_pattern=testcase_variation.blockedMessageCodes,
                calc_mode=calc_mode,
                compare_formula_output_uri=compare_formula_output_uri,
                compare_instance_uri=compare_instance_uri,
                description=testcase_variation.description,
                full_id=full_id,
                id=local_id,
                ignore_levels=test_engine_options.ignore_levels,
                inline_target=target,
                name=testcase_variation.name,
                parameters=PARAMETER_SEPARATOR.join(parameters),
                read_first_uris=testcase_variation.readMeFirstUris,
                report_count=None,
                short_name=short_name,
                status=testcase_variation.status,
                testcase_constraint_set=testcase_constraint_set,
            ))
            testcases_found = True
    return testcases_found

class XmlTestcaseLoader(TestcaseLoader):

    def __init__(self) -> None:
        super().__init__()

    def is_loadable(self, test_engine_options: TestEngineOptions) -> bool:
        return test_engine_options.index_file.lower().endswith('.xml')

    def load(self, test_engine_options: TestEngineOptions) -> TestcaseVariationSet:
        """
        Use the Arelle Session API to load an XML testcase index and build variations for running in the test engine.
        TODO: Don't rely on ModelTestcaseVariation.
        :param test_engine_options:
        :return:
        """
        runtime_options = RuntimeOptions(
            entrypointFile=test_engine_options.index_file,
            keepOpen=True,
        )
        with Session() as session:
            session.run(
                runtime_options,
            )
            load_errors: list[Any] = []
            assert isinstance(session._cntlr, Cntlr)
            load_errors.extend(session._cntlr.errors)
            models = session.get_models()
            testcase_variations: list[TestcaseVariation] = []
            for model in models:
                load_errors.extend(model.errors)
                for doc in model.urlDocs.values():
                    is_testcase_doc = doc.type in (ModelDocumentType.TESTCASE, ModelDocumentType.REGISTRYTESTCASE)
                    if _load_testcase_doc(doc, test_engine_options, testcase_variations):
                        if not is_testcase_doc:
                            load_errors.append(f"{TESTCASE_LOADER_ERROR_PREFIX}: Document of unknown type ({doc.type}) contained testcases: {doc.uri}")
                    elif is_testcase_doc:
                        load_errors.append(f"T{TESTCASE_LOADER_ERROR_PREFIX}: Testcase document contained no testcases: {doc.uri}")
            return TestcaseVariationSet(
                load_errors=load_errors,
                skipped_testcase_variations=[],
                testcase_variations=testcase_variations,
            )
