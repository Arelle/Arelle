"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import zipfile
from typing import BinaryIO

from arelle.ModelDocument import ModelDocument
from arelle.typing import TypeGetText

_: TypeGetText


def saveOimReportToXmlInstance(modelDocument: ModelDocument, filePath: str, responseZipStream: BinaryIO | None = None) -> None:
    if responseZipStream:
        with zipfile.ZipFile(responseZipStream, "a", zipfile.ZIP_DEFLATED, True) as _zip:
            modelDocument.save(filePath, _zip)
        responseZipStream.seek(0)
    else:
        modelDocument.save(filePath)
