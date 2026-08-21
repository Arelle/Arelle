"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from arelle.ModelDocumentType import ModelDocumentType
from arelle.ModelObject import ModelObject
from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl
from arelle.utils.PluginData import PluginData
from arelle.utils.validate.Facts import hasValidNonNilFactByQname

LINKBASE_NS = "http://www.xbrl.org/2003/linkbase"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
SCHEMA_REF_TAG = f"{{{LINKBASE_NS}}}schemaRef"


@dataclass
class PluginValidationDataExtension(PluginData):

    # Taxonomy entry point URIs (553-E rules)
    validTcEntryPoints: frozenset[str]

    # Mandatory element sets (NVAD-E-0010, NVAD-E-0050)
    mandatoryTcBir51Qns: frozenset[QName]
    mandatoryTcBir52Qns: frozenset[QName]

    # Form-type detection
    # NVAD-E-0060: these concepts must NOT appear in a BIR51 (corporation) filing.
    bir52ExclusiveQns: frozenset[QName]
    # NVAD-E-0070: these concepts must NOT appear in a BIR52 (partnership) filing.
    bir51ExclusiveQns: frozenset[QName]

    # Identifiers & basis period
    basisPeriodStartDateQn: QName
    basisPeriodEndDateQn: QName

    # HKSIC code (nvad_structural, NVAD-E-0170/0180/0190)
    hksicCodeQn: QName
    hksicCodeRegex: re.Pattern[str]     # r'^\d{6}$'
    validHksicCodes: frozenset[str]

    # Identity hash for caching.
    def __hash__(self) -> int:
        return id(self)

    def _exclusiveQnCount(self, modelXbrl: ModelXbrl, qnames: frozenset[QName]) -> int:
        return sum(
            1 for qn in qnames
            if hasValidNonNilFactByQname(modelXbrl, qn)
        )

    @lru_cache(1)
    def isBir52(self, modelXbrl: ModelXbrl) -> bool:
        """True when the document is a BIR52 (partnership/proprietorship) filing.

        Detection is based on a higher count of BIR52-exclusive concepts
        than BIR51-exclusive concepts.
        """
        n52 = self._exclusiveQnCount(modelXbrl, self.bir52ExclusiveQns)
        n51 = self._exclusiveQnCount(modelXbrl, self.bir51ExclusiveQns)
        if n51 == 0 and n52 == 0:
            return False  # FS-only / no exclusive facts → keep today's BIR51 default
        return n52 > n51

    @lru_cache(1)
    def getSchemaRefsByDocument(
        self,
        modelXbrl: ModelXbrl,
    ) -> dict[str, list[ModelObject]]:
        """Return each Inline XBRL document's ``link:schemaRef`` elements,
        keyed by document URI.

        Grouped per physical document so callers can detect *within a
        single file* whether more than one schemaRef is present. A combined
        TC+FS filing normally has two documents, each with exactly one
        schemaRef, and must not be mistaken for a single document with two.

        The returned elements are suitable as ``modelObject`` on a
        :class:`~arelle.utils.validate.Validation.Validation`.
        """
        refsByDoc: dict[str, list[ModelObject]] = {}
        for doc in modelXbrl.urlDocs.values():
            if doc.type == ModelDocumentType.INLINEXBRL:
                root = doc.xmlRootElement
                if root is None:
                    continue
                refsByDoc[doc.uri] = list(root.iter(SCHEMA_REF_TAG))
        return refsByDoc

    @lru_cache(1)
    def getSchemaRefHrefs(self, modelXbrl: ModelXbrl) -> list[str]:
        """Return all non-empty ``xlink:href`` values from ``link:schemaRef``
        elements across the IXDS.

        Flattens hrefs from :meth:`getSchemaRefsByDocument` — appropriate
        for "does any file reference a valid entry point" checks.
        """
        return [
            href
            for refs in self.getSchemaRefsByDocument(modelXbrl).values()
            for ref in refs
            if (href := (ref.get(XLINK_HREF, "") or ""))
        ]
