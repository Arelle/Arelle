"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from arelle.Cntlr import Cntlr
from arelle.ModelDocument import Type

INLINE_XBRL = (
    '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">'
    '<head><title>t</title></head><body><div style="display:none"><ix:header/></div></body></html>'
)
XHTML_WITHOUT_INLINE_XBRL = '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>t</title></head><body/></html>'
XBRL_INSTANCE = '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"/>'
TESTCASE = '<testcase name="t"/>'


@pytest.fixture
def cntlr():
    cntlr = Cntlr(logFileName="logToBuffer", disable_persistent_config=True)
    cntlr.webCache.workOffline = True
    yield cntlr
    with patch("arelle.ModelManager.gc"):
        cntlr.modelManager.close()
    cntlr.close()


@pytest.mark.parametrize(
    "content, requiredDocumentTypes, expectError",
    [
        (INLINE_XBRL, Type.INLINEXBRLTYPES, False),
        (INLINE_XBRL, (Type.INSTANCE,), True),
        (XHTML_WITHOUT_INLINE_XBRL, (), False),
        (XHTML_WITHOUT_INLINE_XBRL, Type.INLINEXBRLTYPES, True),
        (XBRL_INSTANCE, (), False),
        (XBRL_INSTANCE, Type.INLINEXBRLTYPES, True),
        (XBRL_INSTANCE, (Type.INSTANCE,), False),
        (TESTCASE, Type.INLINEXBRLTYPES, False),
    ],
)
def test_load_requiredDocumentTypes(
    cntlr: Cntlr,
    tmp_path: Path,
    content: str,
    requiredDocumentTypes: tuple[int, ...],
    expectError: bool,
) -> None:
    entry = tmp_path / "entry.xml"
    entry.write_text(content)
    modelXbrl = cntlr.modelManager.load(
        str(entry), requiredDocumentTypes=requiredDocumentTypes
    )
    assert ("arelle:unsupportedDocumentType" in modelXbrl.errors) == expectError
