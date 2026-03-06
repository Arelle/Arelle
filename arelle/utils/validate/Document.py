from typing import Optional

from arelle import ModelDocument
from arelle.ModelDocumentType import ModelDocumentType
from arelle.ModelObject import ModelObject
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
        if modelDocument.type == ModelDocumentType.INLINEXBRLDOCUMENTSET:
            continue
        if documentType is not None and modelDocument.type != documentType:
            continue
        if modelDocument.documentEncoding is None or modelDocument.documentEncoding.lower() not in encodings:
            docsWithDisallowedEncoding.append(modelDocument)
    return docsWithDisallowedEncoding


def getReferencedModelObjects(val: ValidateXbrl, modelDocumentType: int, referenceType: str) -> list[ModelObject]:
    """
    Returns a list of ModelObjects that are referenced by referenceType.

    :param val: validateXbrl object containing the modelXbrl with the documents to check.
    :param modelDocumentType: integer representation of the document type used to filter=(e.g., ModelDocumentType.INSTANCE).
    :param referenceType: local name of the reference type to check for (e.g., "schemaRef").
    :return: list of ModelObjects that are referenced.
    """
    refModelObjects = []
    for doc in val.modelXbrl.urlDocs.values():
        if doc.type == modelDocumentType:
            for docRef in doc.referencesDocument.values():
                if docRef.referringModelObject.localName == referenceType:
                    refModelObjects.append(docRef.referringModelObject)
    return refModelObjects
