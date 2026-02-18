from typing import Optional, cast

from arelle import ModelDocument
from arelle.ModelDocumentType import ModelDocumentType
from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.validate.Common import isExtensionUri


def checkDocumentEncoding(val: ValidateXbrl, encodings: list[str], taxonomyUrlPrefixes: frozenset[str],  documentType: Optional[ModelDocumentType] = None,) -> list[ModelDocument.ModelDocument]:
    """
    Checks the encoding of documents on the ModelXbrl against a list of allowed encodings.
    If documentType is not specified, all documents except INLINEXBRLDOCUMENTSET are checked.
    If documentType is specified, only documents of that type are checked.

    :param val: validateXbrl object containing the modelXbrl with the documents to check.
    :param encodings: lower case list of allowed encodings (e.g., ['utf-8', 'iso-8859-1', 'utf-8-sig'])
    :param taxonomyUrlPrefixes: frozenset of URL prefixes that identify taxonomy documents (e.g., {'http://www.xbrl.org/2003/linkbase', 'http://www.xbrl.org/2003/instance'})
    :param documentType: optional ModelDocumentType to filter documents by type (e.g., ModelDocumentType.INSTANCE). If None, all non-INLINEXBRLDOCUMENTSET document types are checked.
    :return: list of ModelDocument objects that have a disallowed encoding.
    """
    docsWithDisallowedEncoding = []
    for modelDocument in val.modelXbrl.urlDocs.values():
        if not isExtensionUri(modelDocument.uri, val.modelXbrl, taxonomyUrlPrefixes):
            continue
        if ModelDocumentType == cast(type[ModelDocumentType], ModelDocumentType.INLINEXBRLDOCUMENTSET):
            continue
        if documentType is not None and modelDocument.type != documentType:
            continue
        if modelDocument.documentEncoding is None or modelDocument.documentEncoding.lower() not in encodings:
            docsWithDisallowedEncoding.append(modelDocument)
    return docsWithDisallowedEncoding
