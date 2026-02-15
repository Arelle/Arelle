from typing import Optional

from arelle import ModelDocument
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.validate.Concepts import isExtensionUri


def checkDocumentEncoding(val: ValidateXbrl, encodings: list[str], taxonomyUrlPrefixes: frozenset[str],  documentType: Optional[int] = None,) -> list[ModelDocument.ModelDocument]:
    """
    Checks the encoding of documents on the ModelXbrl against a list of allowed encodings.
    If documentType is not specified, all documents except INLINEXBRLDOCUMENTSET are checked.
    If documentType is specified, only documents of that type are checked.

    :param val: validateXbrl object containing the modelXbrl with the documents to check.
    :param encodings: lower case list of allowed encodings (e.g., ['utf-8', 'iso-8859-1', 'utf-8-sig'])
    :param taxonomyUrlPrefixes: frozenset of URL prefixes that identify taxonomy documents (e.g., {'http://www.xbrl.org/2003/linkbase', 'http://www.xbrl.org/2003/instance'})
    :param documentType: optional ModelDocument.Type to filter documents by type (e.g., ModelDocument.Type.INSTANCE). If None, all non-INLINEXBRLDOCUMENTSET document types are checked.
    :return: list of ModelDocument objects that have a disallowed encoding.
    """
    docsWithDisallowedEncoding = []
    for modelDocument in val.modelXbrl.urlDocs.values():
        if not isExtensionUri(modelDocument.uri, val.modelXbrl, taxonomyUrlPrefixes):
            continue
        if ((documentType is None and modelDocument.type != ModelDocument.Type.INLINEXBRLDOCUMENTSET) or
                (documentType is not None and modelDocument.type == documentType)):
            if modelDocument.documentEncoding is None or modelDocument.documentEncoding.lower() not in encodings:
                docsWithDisallowedEncoding.append(modelDocument)
    return docsWithDisallowedEncoding
