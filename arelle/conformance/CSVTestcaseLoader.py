"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

import csv
from io import TextIOWrapper
from pathlib import Path
from typing import TYPE_CHECKING, cast

from lxml import etree
from arelle import XmlUtil

from arelle.ModelValue import QName, qname
from arelle.ModelXbrl import ModelXbrl

if TYPE_CHECKING:
    from arelle import ModelDocument

CSV_TESTCASE_HEADER = (
    "input",
    "errors",
    "report_count",
    "description",
)

CONFORMANCE_NAMESPACE = "http://xbrl.org/2005/conformance"
TESTCASE_NAMESPACES_BY_PREFIX = {
    None: CONFORMANCE_NAMESPACE,
    "rpe": "https://xbrl.org/2023/report-package/error",
    "tpe": "http://xbrl.org/2016/taxonomy-package/errors",
}


class CSVTestcaseException(Exception):
    pass


def loadCsvTestcase(
    modelXbrl: ModelXbrl,
    filepath: str,
) -> ModelDocument.ModelDocument | None:
    from arelle import ModelDocument
    if Path(filepath).suffix != ".csv":
        raise CSVTestcaseException(f"Expected CSV testcase file, got {filepath}")
    try:
        _file = cast(TextIOWrapper, modelXbrl.fileSource.file(filepath)[0])
    except IOError as err:
        modelXbrl.error("arelle:testcaseCsvError", str(err), href=filepath)
        raise CSVTestcaseException from err
    reader = csv.reader(_file)
    header = next(reader)
    if tuple(header) != CSV_TESTCASE_HEADER:
        # CSV doesn't have a recognized testcase header.
        raise CSVTestcaseException(f"CSV file {filepath} doesn't have test case header: {CSV_TESTCASE_HEADER}, first row {header}")
    testcaseElement = etree.Element("testcase", nsmap=TESTCASE_NAMESPACES_BY_PREFIX)  # type: ignore[arg-type]
    document = ModelDocument.create(
        modelXbrl,
        ModelDocument.Type.TESTCASE,
        filepath,
        isEntry=True,
        initialComment=f"extracted from CSV Testcase {filepath}",
        documentEncoding="utf-8",
        base=modelXbrl.entryLoadingUrl,
        initialXml=etree.tostring(testcaseElement),
    )
    testcase = document.xmlRootElement
    for index, row in enumerate(reader):
        if len(row) != len(CSV_TESTCASE_HEADER):
            msg = f"CSV testcase file {filepath} row {index+2} doesn't match header format: Header {list(CSV_TESTCASE_HEADER)} - Row {row}"
            modelXbrl.error("arelle:testcaseCsvError", msg, href=filepath)
            raise CSVTestcaseException(msg)
        _input, errors, report_count, description = row
        _id = Path(_input).stem
        variation = XmlUtil.addChild(
            testcase,
            _conformanceQName("variation"),
            attributes={"id": _id, "name": _id},
        )
        XmlUtil.addChild(variation, _conformanceQName("description"), text=description)
        data = XmlUtil.addChild(variation, _conformanceQName("data"))
        XmlUtil.addChild(
            data,
            _conformanceQName("taxonomyPackage"),
            text=_input,
            attributes={"readMeFirst": "true"},
        )
        result = XmlUtil.addChild(
            variation,
            _conformanceQName("result"),
            attributes={"report_count": report_count},
        )
        for error in errors.split():
            XmlUtil.addChild(result, _conformanceQName("error"), text=error)
    modelXbrl.modelDocument = document
    document.testcaseDiscover(testcase, modelXbrl.modelManager.validateTestcaseSchema)
    return document


def _conformanceQName(name: str) -> QName:
    return qname(CONFORMANCE_NAMESPACE, name)
