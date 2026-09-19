from io import BytesIO
from zipfile import ZipFile

import pytest

from arelle import ModelDocument, XmlValidate
from arelle.Cntlr import Cntlr
from arelle.FileSource import openFileSource


def build_schema(compositor, group_optional=False, following_element=None):
    group = f"""<xs:{compositor} minOccurs="{0 if group_optional else 1}">
            <xs:element name="a" type="xs:string"/>
            <xs:element name="b" type="xs:string"/>
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


@pytest.fixture
def cntlr():
    cntlr = Cntlr(logFileName="logToBuffer", disable_persistent_config=True)
    cntlr.webCache.workOffline = True
    yield cntlr
    cntlr.modelManager.close()
    cntlr.close()


def test_skipped_optional_sequence_before_required_member(cntlr):
    schema_xml = build_schema("sequence", group_optional=True, following_element="c")
    instance_xml = '<root xmlns="urn:test"><c/></root>'
    model, document = load_test_document(cntlr, schema_xml, instance_xml)
    XmlValidate.validate(model, document.xmlRootElement)
    assert not model.errors
