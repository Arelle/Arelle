from __future__ import annotations

import json
import locale
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import PurePath
from typing import TYPE_CHECKING, Any, cast

import boto3
import pytest
import regex
from botocore import UNSIGNED
from botocore.config import Config as BotocoreConfig

from arelle import PackageManager, PluginManager
from arelle.Cntlr import Cntlr
from arelle.CntlrCmdLine import parseAndRun
from arelle.FileSource import archiveFilenameParts
from arelle.ModelDocumentType import ModelDocumentType

if TYPE_CHECKING:
    from _pytest.mark import ParameterSet
    from types_boto3_s3 import S3Client

    from arelle.ModelDocument import ModelDocument


@dataclass(frozen=True)
class VariationResult:
    """The outcome of running one testcase variation, passed to pytest as a parameter."""
    status: str
    match_all: bool
    expected: str
    expected_warnings: dict[str, int]
    configured_errors: dict[str, int]
    actual_codes: dict[str, int]
    actual_assertions: dict[str, dict[str, int]]
    duration: float | None


def get_document_id(doc: ModelDocument) -> str:
    """
    Given a ModelDocument, attempt to find a basepath that can be used to generate a user-friendly document ID
    :param doc:
    :return: A parent path of the document's filepath.
    """
    parents = [p.as_posix() for p in PurePath(doc.filepath).parents]
    checked_paths = set()
    file_source = doc.modelXbrl.fileSource
    # Try basefile
    basefile: str = cast(str, getattr(file_source, "basefile", None))
    if basefile is not None:
        basefile = PurePath(basefile).as_posix()
        if basefile in parents:
            return get_document_id_from_basepath(doc, basefile)
        else:
            checked_paths.add(basefile)
    # Try referenced documents
    ref_file_source = next(iter(file_source.referencedFileSources.values()), None)
    ref_basefile: str | None = ref_file_source.basefile if ref_file_source is not None else None  # type: ignore[assignment]
    if ref_basefile is not None:
        ref_basefile = PurePath(ref_basefile).as_posix()
        if ref_basefile in parents:
            return get_document_id_from_basepath(doc, ref_basefile)
        else:
            checked_paths.add(ref_basefile)
    # Try archive subpath
    archive_path_parts = archiveFilenameParts(doc.filepath)
    if archive_path_parts is not None:
        archive_path_part = PurePath(archive_path_parts[1]).as_posix()
        return archive_path_part
    # Use file source URL as fallback if basepath not found
    file_source_url = PurePath(os.path.dirname(file_source.url)).as_posix()  # type: ignore[arg-type,type-var]
    if file_source_url in parents:
        return get_document_id_from_basepath(doc, file_source_url)
    else:
        checked_paths.add(file_source_url)
    raise ValueError(f'Could not determine basepath. '
                     f'None of the checked paths ({checked_paths}) were parents of "{doc.filepath}".')


def get_document_id_from_basepath(doc: ModelDocument, basepath: str) -> str:
    return PurePath(doc.filepath).relative_to(basepath).as_posix()


_S3_BASE_CONFIG = BotocoreConfig(
    retries={
        "mode": "adaptive",
        "total_max_attempts": 5,
    }
)


_PRIVATE_S3_CLIENT: S3Client | None = None
_S3_BUCKET_REGION = "us-east-1"


def _get_private_s3_client() -> S3Client:
    global _PRIVATE_S3_CLIENT
    if _PRIVATE_S3_CLIENT is None:
        _PRIVATE_S3_CLIENT = boto3.client(
            service_name="s3",
            region_name=_S3_BUCKET_REGION,
            config=_S3_BASE_CONFIG,
        )
    return _PRIVATE_S3_CLIENT


_PUBLIC_S3_CLIENT: S3Client | None = None


def _get_public_s3_client() -> S3Client:
    global _PUBLIC_S3_CLIENT
    if _PUBLIC_S3_CLIENT is None:
        _PUBLIC_S3_CLIENT = boto3.client(
            service_name="s3",
            region_name=_S3_BUCKET_REGION,
            config=_S3_BASE_CONFIG.merge(BotocoreConfig(signature_version=UNSIGNED)),
        )
    return _PUBLIC_S3_CLIENT


def _download_from_s3(
    client: S3Client,
    bucket: str,
    download_path: str | os.PathLike[str],
    key: str,
    version_id: str | None = None,
) -> None:
    if parent_dir := os.path.dirname(download_path):
        os.makedirs(parent_dir, exist_ok=True)
    extra_args = {"VersionId": version_id} if version_id else {}
    client.download_file(bucket, Key=key, Filename=str(download_path), ExtraArgs=extra_args)


def download_from_public_s3(download_path: str | os.PathLike[str], key: str, version_id: str | None = None) -> None:
    _download_from_s3(_get_public_s3_client(), "arelle-public", download_path, key, version_id)


def download_from_private_s3(download_path: str | os.PathLike[str], key: str, version_id: str | None = None) -> None:
    _download_from_s3(_get_private_s3_client(), "arelle", download_path, key, version_id)


def get_test_data(
        args: list[str],
        expected_failure_ids: frozenset[str] = frozenset(),
        required_locale_by_ids: dict[str, regex.Pattern[str]] | None = None,
        strict_testcase_index: bool = True,
) -> list[ParameterSet]:
    """
    Produces a list of Pytest Params that can be fed into a parameterized pytest function

    :param args: The args to be parsed by arelle in order to correctly produce the desired result set
    :param expected_failure_ids: The set of string test IDs that are expected to fail
    :param required_locale_by_ids: The dict of IDs for tests which require a system locale matching a regex pattern.
    :param strict_testcase_index: Don't allow IOerrors when loading the testcase index
    :return: A list of PyTest Params that can be used to run a parameterized pytest function
    """
    if required_locale_by_ids is None:
        required_locale_by_ids = {}
    cntlr = parseAndRun(args)
    try:
        system_locale = locale.setlocale(locale.LC_CTYPE)
        results: list[ParameterSet] = []
        test_cases_with_no_variations = set()
        test_cases_with_unrecognized_type = {}
        skipped_test_cases = set()
        model_document = cntlr.modelManager.modelXbrl.modelDocument  # type: ignore[union-attr]
        test_cases: list[ModelDocument] = []
        if strict_testcase_index and model_document.type == ModelDocumentType.TESTCASESINDEX:  # type: ignore[union-attr]
            model_errors = sorted(cntlr.modelManager.modelXbrl.errors)  # type: ignore[union-attr]
            assert "IOerror" not in model_errors, f'One or more testcases referenced by testcases index "{model_document.filepath}" were not found.'  # type: ignore[union-attr]
        collect_test_data(
            cntlr=cntlr,
            expected_failure_ids=expected_failure_ids,
            required_locale_by_ids=required_locale_by_ids,
            system_locale=system_locale,
            results=results,
            model_document=model_document,  # type: ignore[arg-type]
            test_cases=test_cases,
        )
        for test_case in sorted(test_cases, key=lambda doc: doc.uri):
            test_case_file_id = get_document_id(test_case)
            if test_case.type not in (ModelDocumentType.TESTCASE, ModelDocumentType.REGISTRYTESTCASE):
                test_cases_with_unrecognized_type[test_case_file_id] = test_case.type
            if not getattr(test_case, "testcaseVariations", None):
                test_cases_with_no_variations.add(test_case_file_id)
            else:
                for mv in test_case.testcaseVariations:
                    test_id = f"{test_case_file_id}:{mv.id}"
                    if mv.status == "skip":
                        skipped_test_cases.add(test_id)
                        continue  # don't report variations skipped due to shards
                    marks = []
                    if isExpectedFailure(test_id, expected_failure_ids, required_locale_by_ids, system_locale):
                        marks.append(pytest.mark.xfail())
                    expected_results: Any
                    if isinstance(mv.expected, str):
                        expected_results = mv.expected
                    elif isinstance(mv.expected, dict):
                        expected_results = {"ASSERTIONS": {assertionId: name_assertion_counts(counts) for assertionId, counts in mv.expected.items()}}
                    elif mv.expected:
                        expected_results = {"ERROR": Counter(str(error) for error in mv.expected)}
                    else:
                        expected_results = {}
                    expected_warnings: dict[str, int] = {}
                    if mv.modelXbrl is not None and mv.modelXbrl.modelManager.formulaOptions.testcaseResultsCaptureWarnings:
                        expected_warnings = dict(Counter(str(warning) for warning in mv.expectedWarnings or []))
                    configured_errors = dict(Counter(str(error) for error in mv.userExpectedErrors))
                    actual_codes = dict(sorted(mv.actualCounts.items()))
                    param = pytest.param(
                        VariationResult(
                            status=mv.status,
                            match_all=mv.matchAll,
                            expected=json.dumps(expected_results),
                            expected_warnings=expected_warnings,
                            configured_errors=configured_errors,
                            actual_codes=actual_codes,
                            actual_assertions=get_actual_assertion_results(mv.actual),
                            duration=mv.duration,
                        ),
                        id=test_id,
                        marks=marks,
                    )
                    results.append(param)
        if test_cases_with_unrecognized_type:
            raise Exception(f"Some test cases have an unrecognized document type: {sorted(test_cases_with_unrecognized_type.items())}.")
        test_id_frequencies = Counter(cast(str, p.id) for p in results)
        nonunique_test_ids = {test_id: count for test_id, count in test_id_frequencies.items() if count > 1}
        if nonunique_test_ids:
            raise Exception(f"Some test IDs are not unique.  Frequencies of nonunique test IDs: {nonunique_test_ids}.")
        nonexistent_expected_failure_ids = expected_failure_ids - skipped_test_cases - test_id_frequencies.keys()
        if nonexistent_expected_failure_ids:
            raise Exception(f"Some expected failure IDs don't match any test cases: {sorted(nonexistent_expected_failure_ids)}.")
        nonexistent_required_locale_testcase_ids = required_locale_by_ids.keys() - test_id_frequencies.keys()
        if nonexistent_required_locale_testcase_ids:
            raise Exception(f"Some required locale IDs don't match any test cases: {sorted(nonexistent_required_locale_testcase_ids)}.")
        return results
    finally:
        cntlr.modelManager.close()
        PackageManager.close()
        PluginManager.getInstance().close()


def name_assertion_counts(counts: tuple[int, ...]) -> dict[str, int]:
    """Labels the satisfied and not satisfied counts of a formula assertion result."""
    # Actual results add three counts that split the unsatisfied evaluations by OK, warning and error
    # severity, which testcases don't state.
    return {"satisfied": counts[0], "not satisfied": counts[1]}


def get_actual_assertion_results(actual: list[Any]) -> dict[str, dict[str, int]]:
    """
    Collects formula assertion results from a variation's actual results, as labeled
    satisfied and not satisfied counts per assertion ID.
    """
    return {
        assertionId: name_assertion_counts(counts)
        for result in actual
        if isinstance(result, dict)
        for assertionId, counts in result.items()
    }


def format_failure_message(result: VariationResult) -> str:
    match_mode = "match-all" if result.match_all else "match-any"
    lines = [f"Testcase variation failed ({match_mode})", f"Expected by the suite: {result.expected}"]
    if result.expected_warnings:
        lines.append(f"Expected warnings: {result.expected_warnings}")
    if result.configured_errors:
        lines.append(f"Configured additional errors: {result.configured_errors}")
    lines.append(f"Actual codes: {result.actual_codes}")
    if result.actual_assertions:
        lines.append(f"Actual assertion results: {result.actual_assertions}")
    return "\n".join(lines)


def collect_test_data(
        cntlr: Cntlr,
        expected_failure_ids: frozenset[str],
        required_locale_by_ids: dict[str, regex.Pattern[str]],
        system_locale: str,
        results: list[ParameterSet],
        model_document: ModelDocument,
        test_cases: list[ModelDocument],
) -> None:
    if model_document.type == ModelDocumentType.TESTCASESINDEX:
        for child_document in model_document.referencesDocument.keys():
            collect_test_data(
                cntlr=cntlr,
                expected_failure_ids=expected_failure_ids,
                required_locale_by_ids=required_locale_by_ids,
                system_locale=system_locale,
                results=results,
                model_document=child_document,
                test_cases=test_cases,
            )
    elif model_document.type == ModelDocumentType.REGISTRY:
        test_cases.extend(model_document.referencesDocument.keys())
    elif model_document.type in (ModelDocumentType.TESTCASE, ModelDocumentType.REGISTRYTESTCASE):
        test_cases.append(model_document)
    else:
        raise Exception("Unhandled model document type: {}".format(model_document.type))


def isExpectedFailure(
        test_id: str,
        expected_failure_ids: frozenset[str],
        required_locale_by_ids: dict[str, regex.Pattern[str]],
        system_locale: str,
) -> bool:
    if test_id in expected_failure_ids:
        return True
    if test_id in required_locale_by_ids:
        return not required_locale_by_ids[test_id].search(system_locale)
    return False
