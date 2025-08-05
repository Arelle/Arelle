"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import zipfile
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import regex

from arelle.ModelDocument import Type as ModelDocumentType
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelObject import ModelObject
from arelle.ModelValue import QName, qname
from arelle.ModelXbrl import ModelXbrl
from arelle.PrototypeDtsObject import LinkPrototype
from arelle.ValidateDuplicateFacts import getDeduplicatedFacts, DeduplicationType
from arelle.ValidateXbrl import ValidateXbrl
from arelle.XmlValidate import VALID
from arelle.typing import TypeGetText
from arelle.utils.PluginData import PluginData
from .FormType import FormType
from .Constants import CORPORATE_FORMS

_: TypeGetText


@dataclass(frozen=True)
class UploadContents:
    amendmentPaths: dict[FormType, frozenset[Path]]
    directories: frozenset[Path]
    forms: dict[FormType, frozenset[Path]]
    unknownPaths: frozenset[Path]


@dataclass
class PluginValidationDataExtension(PluginData):
    assetsIfrsQn: QName
    documentTypeDeiQn: QName
    jpcrpEsrFilingDateCoverPageQn: QName
    jpcrpFilingDateCoverPageQn: QName
    jpspsFilingDateCoverPageQn: QName
    liabilitiesAndEquityIfrsQn: QName
    nonConsolidatedMemberQn: QName
    ratioOfFemaleDirectorsAndOtherOfficersQn: QName

    contextIdPattern: regex.Pattern[str]

    _primaryModelXbrl: ModelXbrl | None = None

    def __init__(self, name: str):
        super().__init__(name)
        jpcrpEsrNamespace = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp-esr/2024-11-01/jpcrp-esr_cor"
        jpcrpNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2024-11-01/jpcrp_cor'
        jpdeiNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor'
        jpigpNamespace = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2024-11-01/jpigp_cor"
        jppfsNamespace = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2024-11-01/jppfs_cor"
        jpspsNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpsps/2024-11-01/jpsps_cor'
        self.assetsIfrsQn = qname(jpigpNamespace, 'AssetsIFRS')
        self.documentTypeDeiQn = qname(jpdeiNamespace, 'DocumentTypeDEI')
        self.jpcrpEsrFilingDateCoverPageQn = qname(jpcrpEsrNamespace, 'FilingDateCoverPage')
        self.jpcrpFilingDateCoverPageQn = qname(jpcrpNamespace, 'FilingDateCoverPage')
        self.jpspsFilingDateCoverPageQn = qname(jpspsNamespace, 'FilingDateCoverPage')
        self.liabilitiesAndEquityIfrsQn = qname(jpigpNamespace, "LiabilitiesAndEquityIFRS")
        self.nonConsolidatedMemberQn = qname(jppfsNamespace, "NonConsolidatedMember")
        self.ratioOfFemaleDirectorsAndOtherOfficersQn = qname(jpcrpNamespace, "RatioOfFemaleDirectorsAndOtherOfficers")

        self.contextIdPattern = regex.compile(r'(Prior[1-9]Year|CurrentYear|Prior[1-9]Interim|Interim)(Duration|Instant)')

    # Identity hash for caching.
    def __hash__(self) -> int:
        return id(self)

    @lru_cache(1)
    def isCorporateForm(self, modelXbrl: ModelXbrl) -> bool:
        documentTypes = self.getDocumentTypes(modelXbrl)
        if any(documentType == form.value for form in CORPORATE_FORMS for documentType in documentTypes):
            return True
        return False

    @lru_cache(1)
    def shouldValidateUpload(self, val: ValidateXbrl) -> bool:
        """
        Determine if the upload validation should be performed on this model.

        Upload validation should not be performed if the target document is
        not a zipfile.

        Upload validation should only be performed once for the entire package,
        not duplicated for each model. To facilitate this with Arelle's validation
        system which largely prevents referencing other models, we can use `--keepOpen`
        and check if the given model is the first to be loaded.
        :param val: The ValidateXbrl instance with a model to check.
        :return: True if upload validation should be performed, False otherwise.
        """
        modelXbrl = val.modelXbrl
        if modelXbrl == val.testModelXbrl:
            # Not running within a testcase
            if modelXbrl != modelXbrl.modelManager.loadedModelXbrls[0]:
                return False
        if not modelXbrl.fileSource.fs:
            return False  # No stream
        if not isinstance(modelXbrl.fileSource.fs, zipfile.ZipFile):
            return False  # Not a zipfile
        return True

    @lru_cache(1)
    def getDeduplicatedFacts(self, modelXbrl: ModelXbrl) -> list[ModelFact]:
        return getDeduplicatedFacts(modelXbrl, DeduplicationType.CONSISTENT_PAIRS)

    @lru_cache(1)
    def getDocumentTypes(self, modelXbrl: ModelXbrl) -> set[str]:
        documentFacts = modelXbrl.factsByQname.get(self.documentTypeDeiQn, set())
        documentTypes = set()
        for fact in documentFacts:
            if fact.xValid >= VALID:
                documentTypes.add(fact.textValue)
        return documentTypes

    @lru_cache(1)
    def getFootnoteLinkElements(self, modelXbrl: ModelXbrl) -> list[ModelObject | LinkPrototype]:
        # TODO: Consolidate with similar implementations in EDGAR and FERC
        doc = modelXbrl.modelDocument
        if doc is None:
            return []
        if doc.type in (ModelDocumentType.INLINEXBRL, ModelDocumentType.INLINEXBRLDOCUMENTSET):
            elts = (linkPrototype
                            for linkKey, links in modelXbrl.baseSets.items()
                            for linkPrototype in links
                            if linkPrototype.modelDocument.type in (ModelDocumentType.INLINEXBRL, ModelDocumentType.INLINEXBRLDOCUMENTSET)
                            and linkKey[1] and linkKey[2] and linkKey[3]  # fully specified roles
                            and linkKey[0] != "XBRL-footnotes")
        else:
            rootElt = doc.xmlDocument.getroot()
            elts = rootElt.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}footnoteLink")
        return [
            elt
            for elt in elts
            if isinstance(elt, (ModelObject, LinkPrototype))
        ]


    def getUploadFileSizes(self, modelXbrl: ModelXbrl) -> dict[Path, int]:
        """
        Get the sizes of files in the upload directory.
        :param modelXbrl: The ModelXbrl instance to get file sizes for.
        :return: A dictionary mapping file paths to their sizes.
        """
        if not self.isUpload(modelXbrl):
            return {}
        assert isinstance(modelXbrl.fileSource.fs, zipfile.ZipFile)
        return {
            Path(i.filename): i.file_size
            for i in modelXbrl.fileSource.fs.infolist()
            if not i.is_dir()
        }

    @lru_cache(1)
    def getUploadContents(self, modelXbrl: ModelXbrl) -> UploadContents:
        uploadFilepaths = self.getUploadFilepaths(modelXbrl)
        amendmentPaths = defaultdict(list)
        unknownPaths = []
        directories = []
        forms = defaultdict(list)
        for path in uploadFilepaths:
            parents = list(reversed([p.name for p in path.parents if len(p.name) > 0]))
            if len(parents) == 0:
                continue
            if parents[0] == 'XBRL':
                if len(parents) > 1:
                    formName = parents[1]
                    formType = FormType.parse(formName)
                    if formType is not None:
                        forms[formType].append(path)
                        continue
            formName = parents[0]
            formType = FormType.parse(formName)
            if formType is not None:
                amendmentPaths[formType].append(path)
                continue
            if len(path.suffix) == 0:
                directories.append(path)
                continue
            unknownPaths.append(path)
        return UploadContents(
            amendmentPaths={k: frozenset(v) for k, v in amendmentPaths.items() if len(v) > 0},
            directories=frozenset(directories),
            forms={k: frozenset(v) for k, v in forms.items() if len(v) > 0},
            unknownPaths=frozenset(unknownPaths)
        )

    @lru_cache(1)
    def getUploadFilepaths(self, modelXbrl: ModelXbrl) -> list[Path]:
        if not self.isUpload(modelXbrl):
            return []
        paths = set()
        assert isinstance(modelXbrl.fileSource.fs, zipfile.ZipFile)
        for name in modelXbrl.fileSource.fs.namelist():
            path = Path(name)
            paths.add(path)
            paths.update(path.parents)
        return sorted(paths)

    def hasRequiredValidFact(self, modelXbrl: ModelXbrl, qname: QName) -> bool:
        requiredFacts = modelXbrl.factsByQname.get(qname, set())
        if not len([fact for fact in requiredFacts if fact is not None and fact.xValid >= VALID and not fact.isNil]):
            return False
        return True

    @lru_cache(1)
    def isUpload(self, modelXbrl: ModelXbrl) -> bool:
        if not modelXbrl.fileSource.fs or \
                not isinstance(modelXbrl.fileSource.fs, zipfile.ZipFile):
            modelXbrl.warning(
                codes="EDINET.uploadNotValidated",
                msg=_("The target file is not a zip file, so upload validation could not be performed.")
            )
            return False
        return True

    def isStandardTaxonomyUrl(self, uri: str, modelXbrl: ModelXbrl) -> bool:
        return modelXbrl.modelManager.disclosureSystem.hrefValidForDisclosureSystem(uri)
