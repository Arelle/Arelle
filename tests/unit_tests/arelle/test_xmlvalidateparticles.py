from io import BytesIO
from zipfile import ZipFile

import pytest
from lxml import etree

from arelle import ModelDocument, XmlValidate
from arelle.Cntlr import Cntlr
from arelle.FileSource import openFileSource
from arelle.ModelDtsObject import ModelAll, ModelChoice, ModelSequence
from arelle.ModelObjectFactory import KnownNamespacesModelObjectClassLookup


def build_schema(compositor, member_min_occurs=(1, 1), group_optional=False, following_element=None):
    group = f"""<xs:{compositor} minOccurs="{0 if group_optional else 1}">
            <xs:element name="a" type="xs:string" minOccurs="{member_min_occurs[0]}"/>
            <xs:element name="b" type="xs:string" minOccurs="{member_min_occurs[1]}"/>
          </xs:{compositor}>"""
    if following_element:
        group = f"""<xs:sequence>
          {group}
          <xs:element name="{following_element}" type="xs:string"/>
          </xs:sequence>"""
    return f"""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
        xmlns:t="urn:test" targetNamespace="urn:test" elementFormDefault="qualified">
      <xs:element name="root">
        <xs:complexType>
          {group}
        </xs:complexType>
      </xs:element>
    </xs:schema>"""


def load_test_document(cntlr, schema_xml, instance_xml):
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("schema.xsd", schema_xml)
        archive.writestr("instance.xml", instance_xml)
    stream.seek(0)
    file_source = openFileSource("schema.xsd", cntlr, sourceZipStream=stream)
    model = cntlr.modelManager.load(file_source)
    assert model.modelDocument is not None
    document = ModelDocument.load(model, "instance.xml", base=model.modelDocument.uri)
    assert document is not None
    assert not model.errors
    return model, document


@pytest.mark.parametrize("name, expected", [
    ("all", ModelAll), ("choice", ModelChoice), ("sequence", ModelSequence),
])
def test_compositor_class_lookup(name, expected):
    parser = etree.XMLParser()
    parser.set_element_class_lookup(KnownNamespacesModelObjectClassLookup(None))
    element = etree.fromstring(f'<xs:{name} xmlns:xs="http://www.w3.org/2001/XMLSchema"/>', parser)
    assert type(element) is expected


@pytest.fixture
def cntlr():
    cntlr = Cntlr(logFileName="logToBuffer", disable_persistent_config=True)
    cntlr.webCache.workOffline = True
    yield cntlr
    cntlr.modelManager.close()
    cntlr.close()


@pytest.mark.parametrize("instance_xml, errors", [
    pytest.param(
        '<root xmlns="urn:test"><a>First child</a><b>Second child</b></root>',
        [], id="valid-order",
    ),
    pytest.param(
        '<root xmlns="urn:test"><b>Second child</b><a>First child</a></root>',
        [], id="valid-reverse",
    ),
    pytest.param(
        '<root xmlns="urn:test"><a>First child</a></root>',
        ["xmlSchema:missingParticlesError"], id="missing-required",
    ),
])
def test_all_document(cntlr, instance_xml, errors):
    schema_xml = build_schema("all")
    model, document = load_test_document(cntlr, schema_xml, instance_xml)
    XmlValidate.validate(model, document.xmlRootElement)
    assert model.errors == errors


def test_skipped_optional_sequence_before_required_member(cntlr):
    schema_xml = build_schema("sequence", group_optional=True, following_element="c")
    instance_xml = '<root xmlns="urn:test"><c/></root>'
    model, document = load_test_document(cntlr, schema_xml, instance_xml)
    XmlValidate.validate(model, document.xmlRootElement)
    assert not model.errors


@pytest.mark.parametrize("compositor, member_min_occurs, group_optional, children, expected_valid", [
    ("all", (1, 1), False, ("a", "b"), True),
    ("all", (1, 1), False, ("b", "a"), True),
    ("all", (1, 1), False, ("a",), False),
    ("all", (1, 1), False, (), False),
    ("all", (1, 1), False, ("a", "b", "a"), False),
    ("all", (1, 1), False, ("a", "a", "b"), False),
    ("all", (1, 1), False, ("a", "b", "c"), False),
    ("all", (0, 1), False, ("b",), True),
    ("all", (0, 1), False, ("b", "a"), True),
    ("all", (0, 1), False, (), False),
    ("all", (1, 1), True, (), True),
    ("all", (1, 1), True, ("a",), False),
    ("all", (1, 1), True, ("b", "a"), True),
    ("all", (0, 0), False, (), True),
    ("all", (0, 0), False, ("a",), True),
    ("all", (0, 0), False, ("b",), True),
    ("all", (0, 0), False, ("a", "b"), True),
    ("all", (0, 0), False, ("b", "a"), True),
    ("all", (0, 0), False, ("a", "a"), False),
    ("choice", (1, 1), False, ("a", "b"), False),
    ("choice", (1, 1), False, ("b", "a"), False),
    ("choice", (1, 1), False, ("a",), True),
    ("choice", (1, 1), False, (), False),
    ("choice", (1, 1), False, ("a", "b", "a"), False),
    ("choice", (1, 1), False, ("a", "a", "b"), False),
    ("choice", (1, 1), False, ("a", "b", "c"), False),
    ("choice", (0, 1), False, ("b",), True),
    ("choice", (0, 1), False, ("b", "a"), False),
    ("choice", (0, 1), False, (), True),
    ("choice", (1, 1), True, (), True),
    ("choice", (1, 1), True, ("a",), True),
    ("choice", (1, 1), True, ("b", "a"), False),
    ("choice", (0, 0), False, (), True),
    ("choice", (0, 0), False, ("a",), True),
    ("choice", (0, 0), False, ("b",), True),
    ("choice", (0, 0), False, ("a", "b"), False),
    ("choice", (0, 0), False, ("b", "a"), False),
    ("choice", (0, 0), False, ("a", "a"), False),
    ("sequence", (1, 1), False, ("a", "b"), True),
    ("sequence", (1, 1), False, ("b", "a"), False),
    ("sequence", (1, 1), False, ("a",), False),
    ("sequence", (1, 1), False, (), False),
    ("sequence", (1, 1), False, ("a", "b", "a"), False),
    ("sequence", (1, 1), False, ("a", "a", "b"), False),
    ("sequence", (1, 1), False, ("a", "b", "c"), False),
    ("sequence", (0, 1), False, ("b",), True),
    ("sequence", (0, 1), False, ("b", "a"), False),
    ("sequence", (0, 1), False, (), False),
    ("sequence", (1, 1), True, (), True),
    ("sequence", (1, 1), True, ("a",), False),
    ("sequence", (1, 1), True, ("b", "a"), False),
    ("sequence", (0, 0), False, (), True),
    ("sequence", (0, 0), False, ("a",), True),
    ("sequence", (0, 0), False, ("b",), True),
    ("sequence", (0, 0), False, ("a", "b"), True),
    ("sequence", (0, 0), False, ("b", "a"), False),
    ("sequence", (0, 0), False, ("a", "a"), False),
])
def test_compositor_validation(cntlr, compositor, member_min_occurs, group_optional, children, expected_valid):
    schema_xml = build_schema(compositor, member_min_occurs, group_optional)
    instance_xml = '<t:root xmlns:t="urn:test">' + "".join(f"<t:{name}/>" for name in children) + "</t:root>"
    model, document = load_test_document(cntlr, schema_xml, instance_xml)
    XmlValidate.validate(model, document.xmlRootElement)
    assert bool(model.errors) == (not expected_valid), model.errors
