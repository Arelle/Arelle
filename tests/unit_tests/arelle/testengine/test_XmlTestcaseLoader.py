"""
See COPYRIGHT.md for copyright information.
"""

import pytest
from unittest.mock import Mock

from arelle.ModelValue import QName
from arelle.testengine.TestcaseConstraint import TestcaseConstraint
from arelle.testengine.loader.XmlTestcaseLoader import XmlTestcaseLoader

CONFORMANCE_URI = "http://xbrl.org/2005/conformance"
TEST_URI = "http://xbrl.org/2005/test"

def _qname(localName: str, namespaceURI: str = CONFORMANCE_URI) -> QName:
    return QName(None, namespaceURI=namespaceURI, localName=localName)

class TestXmlTestcaseLoader:
    def test_is_loadable_xml(self) -> None:
        loader = XmlTestcaseLoader()
        assert loader.is_loadable(Mock(index_file="index.XML"))

    def test_is_loadable_non_xml(self) -> None:
        loader = XmlTestcaseLoader()
        assert not loader.is_loadable(Mock(index_file="index.csv"))

    def test_load_nonexistent(self) -> None:
        loader = XmlTestcaseLoader()
        result = loader.load(Mock(index_file="nonexistent.xml"))

    def test_load(self) -> None:
        expected_constraints = {
            'invalid': [
                TestcaseConstraint(pattern="*")
            ],
            'error': [
                TestcaseConstraint(qname=_qname("ERROR"))
            ],
            'warning': [
                TestcaseConstraint(pattern="WARNING")
            ],
            'multiple': [
                TestcaseConstraint(qname=_qname('ERROR1')),
                TestcaseConstraint(qname=_qname('ERROR2')),
                TestcaseConstraint(qname=_qname('ERROR2')),
                TestcaseConstraint(pattern='WARNING1'),
                TestcaseConstraint(pattern='WARNING2'),
                TestcaseConstraint(pattern='WARNING2')
            ],
            'non-standard-invalid': [
                TestcaseConstraint(pattern="*")
            ],
            'non-standard-error': [
                TestcaseConstraint(qname=_qname('ERROR1')),
                TestcaseConstraint(pattern='ERROR2'),
            ],
            'qname': [
                TestcaseConstraint(qname=_qname('ERROR', namespaceURI=TEST_URI)),
            ],
        }
        loader = XmlTestcaseLoader()
        result = loader.load(Mock(index_file="tests/resources/conformance_suites/test/index.xml"))
        assert len(result.load_errors) == 0
        assert len(result.testcase_variations) == 9
        for testcase_variation in result.testcase_variations:
            assert testcase_variation.short_name == f"testcase.xml:{testcase_variation.id}"
            assert testcase_variation.full_id.endswith(f"tests/resources/conformance_suites/test/testcase.xml:{testcase_variation.id}")
            assert testcase_variation.name == f"{testcase_variation.id}-name"
            assert testcase_variation.description == f"{testcase_variation.id}-description"
            assert testcase_variation.read_first_uris == [f"{testcase_variation.id}-input.zip"]
            assert testcase_variation.testcase_constraint_set.constraints == expected_constraints.get(testcase_variation.id, [])
