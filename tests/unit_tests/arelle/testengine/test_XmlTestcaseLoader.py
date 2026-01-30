"""
See COPYRIGHT.md for copyright information.
"""

import pytest
import regex as re
from pathlib import Path

from arelle.ModelValue import QName
from arelle.testengine.Constraint import Constraint
from arelle.testengine.loader.XmlTestcaseLoader import XmlTestcaseLoader

CONFORMANCE_URI = "http://xbrl.org/2005/conformance"
TEST_URI = "http://xbrl.org/2005/test"

def _qname(localName: str, namespaceURI: str = CONFORMANCE_URI) -> QName:
    return QName(None, namespaceURI=namespaceURI, localName=localName)

class TestXmlTestcaseLoader:
    def test_is_loadable_xml(self) -> None:
        loader = XmlTestcaseLoader()
        assert loader.is_loadable(Path("index.XML"))

    def test_is_loadable_non_xml(self) -> None:
        loader = XmlTestcaseLoader()
        assert not loader.is_loadable(Path("index.csv"))

    def test_load_nonexistent(self) -> None:
        loader = XmlTestcaseLoader()
        result = loader.load(Path("nonexistent.xml"))
        assert len(result.load_errors) == 1
        assert re.fullmatch(r'Could not load file from local filesystem\. file: .*nonexistent\.xml', result.load_errors[0])

    def test_load(self) -> None:
        expected_constraints = {
            'invalid': [
                Constraint(pattern="*")
            ],
            'error': [
                Constraint(qname=_qname("ERROR"))
            ],
            'warning': [
                Constraint(pattern="WARNING")
            ],
            'multiple': [
                Constraint(qname=_qname('ERROR1')),
                Constraint(qname=_qname('ERROR2')),
                Constraint(qname=_qname('ERROR2')),
                Constraint(pattern='WARNING1'),
                Constraint(pattern='WARNING2'),
                Constraint(pattern='WARNING2')
            ],
            'non-standard-invalid': [
                Constraint(pattern="*")
            ],
            'non-standard-error': [
                Constraint(qname=_qname('ERROR1')),
                Constraint(pattern='ERROR2'),
            ],
            'qname': [
                Constraint(qname=_qname('ERROR', namespaceURI=TEST_URI)),
            ],
        }
        loader = XmlTestcaseLoader()
        result = loader.load(Path("tests/resources/conformance_suites/test/index.xml"))
        assert len(result.load_errors) == 0
        assert len(result.testcases) == 9
        for testcase in result.testcases:
            assert testcase.full_id == f"testcase.xml:{testcase.local_id}"
            assert testcase.name == f"{testcase.local_id}-name"
            assert testcase.description == f"{testcase.local_id}-description"
            assert testcase.read_first_uris == [f"{testcase.local_id}-input.zip"]
            assert testcase.constraint_set.constraints == expected_constraints.get(testcase.local_id, [])
