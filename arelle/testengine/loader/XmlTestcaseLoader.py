"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Any
from urllib.parse import urlparse
from urllib.request import url2pathname

from arelle.Cntlr import Cntlr
from arelle.ModelDocument import ModelDocument, Type as ModelDocumentType
from arelle.ModelTestcaseObject import ModelTestcaseVariation
from arelle.ModelValue import QName
from arelle.RuntimeOptions import RuntimeOptions
from arelle.api.Session import Session
from arelle.logging.handlers.LogToBufferHandler import LogToBufferHandler
from arelle.testengine.Constraint import Constraint
from arelle.testengine.ConstraintSet import ConstraintSet
from arelle.testengine.ErrorLevel import ErrorLevel
from arelle.testengine.Testcase import Testcase
from arelle.testengine.TestcaseSet import TestcaseSet
from arelle.testengine.loader.TestcaseLoader import TestcaseLoader

CALC_MODES_MAP: dict[str | None, str] = {
    'truncate': 'truncation',
}
PARAMETER_SEPARATOR = '\n'
TARGET_SUFFIX_SEPARATOR = '|'


def _get_calc_mode(variation: ModelTestcaseVariation) -> str | None:
    """
    Determine a single calculation mode for the testcase variation.
    Raises an AssertionError if it is ambiguous.
    :param variation:
    :return: The calculation mode to use for this testcase.
    """
    calc_modes = {
        calc_mode
        for result_elt in variation.iterdescendants("{*}result")
        if (calc_mode := result_elt.attr('{https://xbrl.org/2023/conformance}mode')) is not None
    }
    assert len(calc_modes) <= 1, f"Multiple calculation modes found: {calc_modes}."
    calc_mode = next(iter(calc_modes), None)
    calc_mode = CALC_MODES_MAP.get(calc_mode, calc_mode)
    return calc_mode


def _get_constraints(variation: ModelTestcaseVariation) -> list[Constraint]:
    """
    Given a ModelTestcase, build list of testcase constraints.
    :param variation:
    :return: Testcase constraints.
    """
    constraints = []
    expected = variation.expected or 'valid'
    if not isinstance(expected, list):
        expected = [expected]
    for error in expected:
        constraints.extend(_get_error_constraints(error))
    expected_warnings = variation.expectedWarnings or []
    for warning in expected_warnings:
        constraints.extend(_get_warning_constraints(warning))
    return constraints


def _get_error_constraints(error: Any) -> list[Constraint]:
    """
    Build testcase constraints based off of expected errors.
    :param error: Error object of indeterminate type.
    :return: Testcase constraints.
    """
    constraints = []
    if error == 'valid':
        pass
    elif error == 'invalid':
        constraints.append(Constraint(
            pattern='*',  # matches any code
        ))
    elif isinstance(error, QName):
        constraints.append(Constraint(
            qname=error,
        ))
    elif isinstance(error, str):
        constraints.append(Constraint(
            pattern=error,
        ))
    elif isinstance(error, dict):
        for pattern, assertions in error.items():
            satisfied_count, not_satisfied_count = assertions
            count_map = {
                ErrorLevel.SATISFIED: satisfied_count,
                ErrorLevel.NOT_SATISFIED: not_satisfied_count,
            }
            for level, count in count_map.items():
                for i in range(0, count):
                    constraints.append(Constraint(
                        level=level,
                        pattern=pattern,
                    ))
    else:
        raise ValueError(f"Unexpected expected error type: {type(error)}")
    return constraints


def _get_parameters(variation: ModelTestcaseVariation) -> list[str]:
    """
    Build parameters arguments based given a ModelTestcaseVariation
    :param variation:
    :return: Parameters arguments for setting in RuntimeOptions.
    """
    parameters = [
        f'{k.clarkNotation}={v[1]}'
        for k, v in variation.parameters.items()
    ]
    assert all(PARAMETER_SEPARATOR not in parameter for parameter in parameters), \
        'Parameter separator found in parameter key or value.'
    return parameters


def _get_warning_constraints(warning: Any) -> list[Constraint]:
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
        constraints.append(Constraint(
            level=ErrorLevel.ERROR,
            qname=warning,
        ))
    elif isinstance(warning, str):
        constraints.append(Constraint(
            level=ErrorLevel.ERROR,
            pattern=warning,
        ))
    else:
        raise ValueError(f"Unexpected expected warning type: {type(warning)}")
    return constraints


def _iter_targets(variation: ModelTestcaseVariation) -> Iterable[str | None]:
    """
    Iterate over the targets involved in this testcase.
    Each unique target in a source variation triggers a separate execution.
    :param variation:
    :return: Iterable of inline target values.
    """
    targets = [
        inst_elt.get("target")
        for result_elt in variation.iterdescendants("{*}result")
        for inst_elt in result_elt.iterdescendants("{*}instance")
    ] or [None]
    for target in targets:
        if len(targets) > 1 and target is None:
            target = "(default)"
        yield target


def _load_testcase_doc(doc: ModelDocument, index_file: Path, testcases: list[Testcase]) -> bool:
    """
    Appends the given document's testcases to the given list.
    :param doc:
    :param index_file:
    :param testcases:
    :return: Whether any testcases were found
    """
    testcases_found = False
    root_dir = index_file.absolute().parent
    for variation in getattr(doc, "testcaseVariations", []):
        assert variation.base is not None
        base_path = _get_base_path(variation.base)
        canonical_path = base_path.relative_to(root_dir).as_posix()
        for target in _iter_targets(variation):
            variation.ixdsTarget = target
            assert variation.id, f'Test case contains variation with no ID: {variation.base}'
            assert TARGET_SUFFIX_SEPARATOR not in variation.id, \
                f"The '{TARGET_SUFFIX_SEPARATOR}' character is used internally as a separator " + \
                "and can not be included in a testcase ID."
            local_id = f"{variation.id}" + (f"{TARGET_SUFFIX_SEPARATOR}{target}" if target else "")
            full_id = f"{canonical_path}:{local_id}"

            calc_mode = _get_calc_mode(variation)
            constraints = _get_constraints(variation)
            parameters = _get_parameters(variation)

            compare_instance_uri = None
            instance_uri = variation.resultXbrlInstanceUri
            if instance_uri:
                compare_instance_uri = Path(doc.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(instance_uri, variation.base))

            # TODO: testcase.resultTableUri (not currently validated)

            constraint_set = ConstraintSet(
                constraints=constraints,
                match_all=False,
            )
            testcases.append(Testcase(
                base=base_path,
                blocked_code_pattern=variation.blockedMessageCodes,
                calc_mode=calc_mode,
                compare_instance_uri=compare_instance_uri,
                description=variation.description,
                expected_instance_count=None,
                full_id=full_id,
                inline_target=target,
                local_id=local_id,
                name=variation.name,
                parameters=PARAMETER_SEPARATOR.join(parameters),
                read_first_uris=variation.readMeFirstUris,
                status=variation.status,
                constraint_set=constraint_set,
            ))
            testcases_found = True
    return testcases_found


def _get_base_path(base: str) -> Path:
    """
    TODO: Replace with Path.from_uri after removing support for <= 3.12
    """
    if base.startswith('file:/'):
        parsed = urlparse(base)
        path_str = url2pathname(parsed.path)
        return Path(path_str)
    return Path(base)


class XmlTestcaseLoader(TestcaseLoader):

    def __init__(self) -> None:
        super().__init__()

    def is_loadable(self, index_file: Path) -> bool:
        return index_file.name.lower().endswith('.xml')

    def load(self, index_file: Path) -> TestcaseSet:
        """
        Use the Arelle Session API to load an XML testcase index and build testcases for running in the test engine.
        TODO: Don't rely on ModelTestcaseVariation.
        :param index_file:
        :return:
        """
        runtime_options = RuntimeOptions(
            entrypointFile=str(index_file),
            keepOpen=True,
        )
        with Session() as session:
            log_handler = LogToBufferHandler()
            session.run(
                runtime_options,
                logHandler=log_handler,
            )
            log_json = json.loads(log_handler.getJson(clearLogBuffer=True))
            load_errors: list[Any] = [
                log['message']['text']
                for log in log_json['log']
                if log['level'].lower() == 'error'
            ]
            assert isinstance(session._cntlr, Cntlr)
            models = session.get_models()
            testcases: list[Testcase] = []
            for model in models:
                for doc in model.urlDocs.values():
                    is_testcase_doc = doc.type in (ModelDocumentType.TESTCASE, ModelDocumentType.REGISTRYTESTCASE)
                    if _load_testcase_doc(doc, index_file, testcases):
                        if not is_testcase_doc:
                            load_errors.append(f"Document of unknown type ({doc.type}) contained testcases: {Path(doc.uri).as_posix()}")
                    elif is_testcase_doc:
                        load_errors.append(f"Testcase document contained no testcases: {Path(doc.uri).as_posix()}")
            return TestcaseSet(
                load_errors=load_errors,
                skipped_testcases=[],
                testcases=testcases,
            )
