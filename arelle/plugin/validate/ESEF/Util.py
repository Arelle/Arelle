"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from collections.abc import Collection
from typing import Any, Dict, Generator, List, Union, cast
import regex as re

from lxml.etree import _Element

from arelle.FileSource import openFileStream
from arelle.ModelDocument import ModelDocument
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelInstanceObject import ModelContext, ModelFact, ModelUnit
from arelle.ModelManager import ModelManager
from arelle.ModelObject import ModelObject
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from arelle.XmlValidateConst import VALID
from arelle.typing import TypeGetText
from .Const import esefCorNsPattern, esefNotesStatementConcepts, esefTaxonomyNamespaceURIs, htmlEventHandlerAttributes, svgEventAttributes

_: TypeGetText

YEAR_GROUP = "year"
DISCLOSURE_SYSTEM_YEAR_PATTERN = re.compile(rf"esef-(?:unconsolidated-)?(?P<{YEAR_GROUP}>20\d\d)")


def getDisclosureSystemYear(modelXbrl: ModelXbrl) -> int:
    for name in modelXbrl.modelManager.disclosureSystem.names:
        disclosureSystemYear = DISCLOSURE_SYSTEM_YEAR_PATTERN.fullmatch(name)
        if disclosureSystemYear:
            return int(disclosureSystemYear.group(YEAR_GROUP))
    raise ValueError(f"Unable to determine year of ESEF disclosure system matching pattern 'esef-20XX' from {modelXbrl.modelManager.disclosureSystem.names}")


# check if a modelDocument URI is an extension URI (document URI)
# also works on a uri passed in as well as modelObject
def isExtension(val: ValidateXbrl, modelObject: ModelObject | ModelDocument | str | None) -> bool:
    if modelObject is None:
        return False
    if isinstance(modelObject, str):
        uri = modelObject
    else:
        uri = modelObject.modelDocument.uri
    return (uri.startswith(val.modelXbrl.uriDir) or
            not any(uri.startswith(standardTaxonomyURI) for standardTaxonomyURI in val.authParam["standardTaxonomyURIs"]))


# check if in core esef taxonomy (based on namespace URI)
def isInEsefTaxonomy(val: ValidateXbrl, modelObject: ModelObject | None) -> bool:
    if modelObject is None:
        return False
    assert modelObject.qname is not None
    ns = modelObject.qname.namespaceURI
    assert ns is not None
    return (any(ns.startswith(esefNsPrefix) for esefNsPrefix in esefTaxonomyNamespaceURIs))


def resourcesFilePath(modelManager: ModelManager, fileName: str) -> str:
    # resourcesDir can be in cache dir (production) or in validate/EFM/resources (for development)
    _resourcesDir = os.path.join( os.path.dirname(__file__), "resources") # dev/testing location

    if not os.path.isabs(_resourcesDir):
        _resourcesDir = os.path.abspath(_resourcesDir)
    if not os.path.exists(_resourcesDir): # production location
        _resourcesDir = os.path.join(modelManager.cntlr.webCache.cacheDir, "resources", "validation", "ESEF")

    return os.path.join(_resourcesDir, fileName)


def loadAuthorityValidations(modelXbrl: ModelXbrl) -> list[Any] | dict[Any, Any]:
    _file = openFileStream(modelXbrl.modelManager.cntlr, resourcesFilePath(modelXbrl.modelManager, "authority-validations.json"), 'rt', encoding='utf-8')
    validations = json.load(_file) # {localName: date, ...}
    _file.close()
    return cast(Union[Dict[Any, Any], List[Any]], validations)


def checkForMultiLangDuplicates(modelXbrl: ModelXbrl) -> None:
    _factConceptContextUnitHash: defaultdict[int, list[ModelFact]] = defaultdict(list)

    for f in modelXbrl.factsInInstance:
        if (
            (f.isNil or getattr(f, "xValid", 0) >= VALID)
            and f.context is not None
            and f.concept is not None
            and f.concept.type is not None
            and f.concept.type.isWgnStringFactType
        ):
            _factConceptContextUnitHash[f.conceptContextUnitHash].append(f)

    for hashEquivalentFacts in _factConceptContextUnitHash.values():
        if len(hashEquivalentFacts) <= 1:  # skip facts present only once
            continue
        _aspectEqualFacts: defaultdict[tuple[QName, str], dict[tuple[ModelContext, ModelUnit | None], list[ModelFact]]] = defaultdict(dict)
        for f in hashEquivalentFacts:  # check for hash collision by value checks on context and unit
            cuDict = _aspectEqualFacts[(f.qname, (f.xmlLang or "").lower())]
            _matched = False
            for (_cntx, _unit), fList in cuDict.items():
                if (f.context.isEqualTo(_cntx)
                        and ((_unit is None and f.unit is None)
                             or (f.unit is not None and f.unit.isEqualTo(_unit)))):
                    _matched = True
                    fList.append(f)
                    break
            if not _matched:
                cuDict[(f.context, f.unit)] = [f]
        for cuDict in _aspectEqualFacts.values():
            for fList in cuDict.values():
                if len(fList) > 1 and not all(f.xValue == fList[0].xValue for f in fList):
                    modelXbrl.warning("ESEF.2.2.4.inconsistentDuplicateNonnumericFactInInlineXbrlDocument",
                        "Inconsistent duplicate non-numeric facts SHOULD NOT appear in the content of an inline XBRL document. "
                        "%(fact)s that was used more than once in contexts equivalent to %(contextID)s, with different values but same language (%(language)s).",
                        modelObject=fList, fact=fList[0].qname, contextID=fList[0].contextID, language=fList[0].xmlLang)


def getEsefNotesStatementConcepts(modelXbrl: ModelXbrl) -> set[str]:
    document_name_spaces = modelXbrl.namespaceDocs
    esef_notes_statement_concepts:set[str] = set()
    esef_cor_Nses = []
    for targetNs, models in document_name_spaces.items():
        if esefCorNsPattern.match(targetNs):
            found_prefix = ''
            found_namespace = ''
            for prefix, namespace in models[0].targetXbrlRootElement.nsmap.items():
                if targetNs == namespace:
                    found_namespace = targetNs
                    found_prefix = '' if prefix is None else prefix
                    break
            esef_cor_Nses.append((found_prefix, found_namespace))
    if len(esef_cor_Nses) == 0:
        modelXbrl.error("ESEF.RTS.efrsCoreRequired",
                          _("RTS on ESEF requires EFRS core taxonomy."),
                          modelObject=modelXbrl)
    elif len(esef_cor_Nses) > 1:
        modelXbrl.warning("Arelle.ESEF.multipleEsefTaxonomies",
                        _("Multiple ESEF taxonomies were imported %(esefNamespaces)s."),
                        modelObject=modelXbrl, esefNamespaces=", ".join(ns[1] for ns in esef_cor_Nses))
    else:
        esef_notes_statement_concepts = set(str(QName(esef_cor_Nses[0][0], esef_cor_Nses[0][1], n)) for n in esefNotesStatementConcepts)
    return esef_notes_statement_concepts


def isChildOfNotes(
    child: ModelConcept,
    relSet: ModelRelationshipSet,
    esefNotesConcepts: set[str],
    _visited: set[ModelConcept],
) -> bool:
    if len(esefNotesConcepts) == 0:
        return False
    relations_to = relSet.toModelObject(child)
    if not relations_to and str(child.qname) in esefNotesConcepts:
        return True

    _visited.add(child)
    for rel in relations_to:
        parent = rel.fromModelObject
        if parent is not None and parent not in _visited:
            if isChildOfNotes(parent, relSet, esefNotesConcepts, _visited):
                return True
    _visited.remove(child)
    return False


def hasEventHandlerAttributes(elt: Any) -> bool:
    return _hasEventAttributes(elt, htmlEventHandlerAttributes)


def hasSvgEventAttributes(elt: Any) -> bool:
    return _hasEventAttributes(elt, svgEventAttributes)


def _hasEventAttributes(elt: Any, attributes: Collection[str]) -> bool:
    if isinstance(elt, _Element):
        return any(a in attributes for a in elt.keys())
    return False


def etreeIterWithDepth(
    node: ModelObject | _Element,
    depth: int = 0,
) -> Generator[tuple[ModelObject | _Element, int], None, None]:
    yield node, depth
    for child in node.iterchildren():
        for n_d in etreeIterWithDepth(child, depth + 1):
            yield n_d
