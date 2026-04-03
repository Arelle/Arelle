"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import os
from typing import Any, cast

from collections import Counter
from collections.abc import Iterable
from decimal import Decimal

from arelle import XbrlConst
from arelle.typing import TypeGetText
from arelle.ValidateXbrl import ValidateXbrl
from lxml.etree import _Comment, _ElementTree, _Entity, _ProcessingInstruction
from arelle.ModelDocumentType import ModelDocumentType
from arelle.ModelInstanceObject import ModelInlineFact, ModelUnit
from arelle.ModelValue import qname
from arelle.ModelXbrl import ModelXbrl
from arelle.PythonUtil import strTruncate
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.ValidateDuplicateFacts import getDuplicateFactSets
from arelle.XbrlConst import qnXbrliMonetaryItemType, qnXbrliXbrl, xhtml
from arelle.XmlValidateConst import VALID
from ..ValidationPluginExtension import CURRENCIES_DIMENSION, EQUITY, PRINCIPAL_CURRENCY, TURNOVER_REVENUE
from ..PluginValidationDataExtension import MANDATORY_ELEMENTS, SCHEMA_PATTERNS, TR_NAMESPACES, UK_REF_NS_PATTERN, PluginValidationDataExtension


def checkFileEncoding(modelXbrl: ModelXbrl) -> None:
    for doc in modelXbrl.urlDocs.values():
        if doc.documentEncoding.lower() != "utf-8":
            modelXbrl.error("ROS.documentEncoding",
                            _("iXBRL documents submitted to Revenue should be UTF-8 encoded: %(encoding)s"),
                            modelObject=doc, encoding=doc.documentEncoding)


def checkFileExtensions(modelXbrl: ModelXbrl) -> None:
    for doc in modelXbrl.urlDocs.values():
        if doc.type == ModelDocumentType.INLINEXBRL:
            _baseName, _baseExt = os.path.splitext(doc.basename)
            if _baseExt not in (".xhtml", ".html", ".htm", ".ixbrl", ".xml", ".xhtml"):
                modelXbrl.error("ROS.fileNameExtension",
                                _("The list of acceptable file extensions for upload is: html, htm, ixbrl, xml, xhtml: %(fileName)s"),
                                modelObject=doc, fileName=doc.basename)


_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_main(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> None:

    _xhtmlNs = "{{{}}}".format(xhtml)
    _xhtmlNsLen = len(_xhtmlNs)
    modelXbrl = val.modelXbrl
    modelDocument = modelXbrl.modelDocument
    if not modelDocument:
         return # never loaded properly

    _statusMsg = _("validating {0} filing rules").format(val.disclosureSystem.name)
    modelXbrl.profileActivity()
    modelXbrl.modelManager.showStatus(_statusMsg)
    if modelDocument.type == ModelDocumentType.INSTANCE:
        modelXbrl.error("ROS:instanceMustBeInlineXBRL",
                        _("ROS expects inline XBRL instances."),
                        modelObject=modelXbrl)
    if modelDocument.type in (ModelDocumentType.INLINEXBRL, ModelDocumentType.INLINEXBRLDOCUMENTSET):
        checkFileExtensions(modelXbrl)
        checkFileEncoding(modelXbrl)
        for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements: # ix root elements for all ix docs in IXDS
            ixNStag = ixdsHtmlRootElt.modelDocument.ixNStag
            ixTags = set(ixNStag + ln for ln in ("nonNumeric", "nonFraction", "references", "relationship"))

        transformRegistryErrors = set()
        ixTargets = set()
        for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements:
            for elt in ixdsHtmlRootElt.iter():
                if isinstance(elt, (_Comment, _ElementTree, _Entity, _ProcessingInstruction)):
                    continue # comment or other non-parsed element
                if isinstance(elt, ModelInlineFact):
                    if elt.format is not None and elt.format.namespaceURI not in TR_NAMESPACES:
                        transformRegistryErrors.add(elt)
                    if elt.isEscaped:
                        modelXbrl.error("ROS.escapedHTML",
                                        _("Escaped (x)html fact content is not supported: %(element)s"),
                                        modelObject=elt, element=eltTag)
                eltTag = elt.tag
                if eltTag in ixTags:
                    ixTargets.add( elt.get("target") )
                else:
                    if eltTag.startswith(_xhtmlNs):
                        eltTag = eltTag[_xhtmlNsLen:]
                        if eltTag == "link" and elt.get("type") == "text/css":
                            modelXbrl.error("ROS.externalCssStyle",
                                            _("CSS must be embedded in the inline XBRL document: %(element)s"),
                                            modelObject=elt, element=eltTag)
                        elif ((eltTag in ("object", "script")) or
                              (eltTag == "a" and "javascript:" in elt.get("href","")) or
                              (eltTag == "img" and "javascript:" in elt.get("src",""))):
                            modelXbrl.error("ROS.embeddedCode",
                                            _("Inline XBRL documents MUST NOT contain embedded code: %(element)s"),
                                            modelObject=elt, element=eltTag)
                        elif eltTag == "img":
                            src = elt.get("src","").strip()
                            if not src.startswith("data:image"):
                                modelXbrl.warning("ROS.embeddedCode",
                                                  _("Images should be inlined as a base64-encoded string: %(element)s"),
                                                  modelObject=elt, element=eltTag)

        if len(ixTargets) > 1:
            modelXbrl.error("ROS:singleOutputDocument",
                            _("Multiple target instance documents are not supported: %(targets)s."),
                            modelObject=modelXbrl, targets=", ".join((t or "(default)") for t in ixTargets))

        if len(pluginData.getFilingTypes(modelXbrl)) != 1:
            modelXbrl.error("ROS:multipleFilingTypes",
                            _("Multiple filing types detected: %(filingTypes)s."),
                            modelObject=modelXbrl, filingTypes=", ".join(sorted(pluginData.getFilingTypes(modelXbrl))))
        if len(pluginData.getUnexpectedTaxonomyReferences(modelXbrl)):
            modelXbrl.error("ROS:unexpectedTaxonomyReferences",
                            _("Referenced schema(s) does not map to a taxonomy supported by Revenue (schemaRef): %(unexpectedReferences)s."),
                            modelObject=modelXbrl, unexpectedReferences=", ".join(sorted(pluginData.getUnexpectedTaxonomyReferences(modelXbrl))))

        # single document IXDS
        if pluginData.getNumIxDocs(modelXbrl) > 1:
            modelXbrl.warning("ROS:multipleInlineDocuments",
                              _("A single inline document should be submitted but %(numberDocs)s were found."),
                              modelObject=modelXbrl, numberDocs=pluginData.getNumIxDocs(modelXbrl))

        # build namespace maps
        nsMap = {}
        for prefix in ("ie-common", "bus", "uk-bus", "ie-dpl", "core"):
            if prefix in modelXbrl.prefixedNamespaces:
                nsMap[prefix] = modelXbrl.prefixedNamespaces[prefix]

        # build mandatory table by ns qname in use
        mandatory = set()
        for prefix in MANDATORY_ELEMENTS:
            if prefix in nsMap:
                ns = nsMap[prefix]
                for localName in MANDATORY_ELEMENTS[prefix]:
                    mandatory.add(qname(ns, prefix + ":" + localName))
        # document creator requirement
        if "bus" in nsMap:
            if qname("bus:NameProductionSoftware",nsMap) not in modelXbrl.factsByQname or qname("bus:VersionProductionSoftware",nsMap) not in modelXbrl.factsByQname:
                modelXbrl.warning("ROS:documentCreatorProductInformation",
                                  _("Please use the NameProductionSoftware tag to identify the software package and the VersionProductionSoftware tag to identify the version of the software package."),
                                  modelObject=modelXbrl)
        elif "uk-bus" in nsMap:
            if qname("uk-bus:NameAuthor",nsMap) not in modelXbrl.factsByQname or qname("uk-bus:DescriptionOrTitleAuthor",nsMap) not in modelXbrl.factsByQname:
                modelXbrl.warning("ROS:documentCreatorProductInformation",
                                  _("Revenue request that vendor, product and version information is embedded in the generated inline XBRL document using a single XBRLDocumentAuthorGrouping tuple. The NameAuthor tag should be used to identify the name and version of the software package."),
                                  modelObject=modelXbrl)


        schemeEntityIds = set()
        hasCRO = False
        unsupportedSchemeContexts = []
        mismatchIdentifierContexts = []
        for context in modelXbrl.contexts.values():
            schemeEntityIds.add(context.entityIdentifier)
            scheme, entityId = context.entityIdentifier
            if scheme not in SCHEMA_PATTERNS:
                unsupportedSchemeContexts.append(context)
            elif not SCHEMA_PATTERNS[scheme].match(entityId):
                mismatchIdentifierContexts.append(context)
            if scheme == "http://www.cro.ie/":
                hasCRO = True

        if len(schemeEntityIds) > 1:
            modelXbrl.error("ROS:differentContextEntityIdentifiers",
                            _("Context entity identifier not all the same: %(schemeEntityIds)s."),
                            modelObject=modelXbrl, schemeEntityIds=", ".join(sorted(str(s) for s in schemeEntityIds)))
        if unsupportedSchemeContexts:
            modelXbrl.error("ROS:unsupportedContextEntityIdentifierScheme",
                            _("Context identifier scheme(s) is not supported: %(schemes)s."),
                            modelObject=unsupportedSchemeContexts,
                            schemes=", ".join(sorted(set(c.entityIdentifier[0] for c in unsupportedSchemeContexts))))
        if mismatchIdentifierContexts:
            modelXbrl.error("ROS:invalidContextEntityIdentifier",
                            _("Context entity identifier(s) lexically invalid: %(identifiers)s."),
                            modelObject=mismatchIdentifierContexts,
                            identifiers=", ".join(sorted(set(c.entityIdentifier[1] for c in mismatchIdentifierContexts))))

        if hasCRO and "ie-common" in nsMap:
            mandatory.add(qname("ie-common:CompaniesRegistrationOfficeNumber", nsMap))  # type-ignore[arg-type]

        reportedMandatory = set()

        for qn, facts in modelXbrl.factsByQname.items():
            if qn in mandatory:
                reportedMandatory.add(qn)

        missingElements = (mandatory - reportedMandatory) # | (reportedFootnoteIfNil - reportedFootnoteIfNil)

        if missingElements:
            modelXbrl.error("ROS:missingRequiredElements",
                            _("Required elements missing from document: %(elements)s."),
                            modelObject=modelXbrl, elements=", ".join(sorted(str(qn) for qn in missingElements)))

        rosFacts = [
            f for f in modelXbrl.facts
            if (f.parentElement.qname == qnXbrliXbrl
                and (f.isNil or getattr(f, "xValid", 0) >= VALID)
                and f.context is not None
                and f.concept is not None
                and f.concept.type is not None)
        ]
        for duplicateFactSet in getDuplicateFactSets(rosFacts, includeSingles=False):
            fList = duplicateFactSet.facts
            f0 = fList[0]
            if duplicateFactSet.areNumeric:
                if duplicateFactSet.areAnyInconsistent:
                    modelXbrl.error("ROS.inconsistentDuplicateFacts",
                                    "Inconsistent duplicate fact values %(element)s: %(values)s, in contexts: %(contextIDs)s.",
                                    modelObject=fList, element=f0.qname,
                                    contextIDs=", ".join(sorted(set(f.contextID for f in fList))),
                                    values=", ".join(strTruncate(f.value, 64) for f in fList))
            elif any(not f.isVEqualTo(f0) for f in fList[1:]):
                modelXbrl.error("ROS.inconsistentDuplicateFacts",
                                "Inconsistent duplicate fact values %(element)s: %(values)s, in contexts: %(contextIDs)s.",
                                modelObject=fList, element=f0.qname,
                                contextIDs=", ".join(sorted(set(f.contextID for f in fList))),
                                values=", ".join(strTruncate(f.value, 64) for f in fList))
    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ros19(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    ROS: Rule 19: DPLTurnoverRevenue should be tested to be less than or equal to 10x the absolute value of Equity
    """
    def convertToDecimal(value):
        return Decimal(value) if isinstance(value, float) else cast(Decimal, value)
    equity_facts = val.modelXbrl.factsByLocalName.get(EQUITY, set())
    largest_equity_fact = None
    for e_fact in equity_facts:
        if e_fact.xValid >= VALID and e_fact.xValue is not None:
            if largest_equity_fact is None or abs(convertToDecimal(e_fact.xValue)) > abs(convertToDecimal(largest_equity_fact.xValue)):
                largest_equity_fact = e_fact

    turnover_facts = val.modelXbrl.factsByLocalName.get(TURNOVER_REVENUE, set())
    largest_turnover_fact = None
    for t_fact in turnover_facts:
        if t_fact.xValid >= VALID and t_fact.xValue is not None:
            if largest_turnover_fact is None or convertToDecimal(t_fact.xValue) > convertToDecimal(largest_turnover_fact.xValue):
                largest_turnover_fact = t_fact

    if (largest_equity_fact is not None and
            largest_turnover_fact is not None and
            convertToDecimal(largest_turnover_fact.xValue) > (10 * abs(convertToDecimal(largest_equity_fact.xValue)))):
        yield Validation.error(
            "ROS.19",
            _("Turnover / Revenue (DPLTurnoverRevenue) may exceed the maximum expected value. Please review the submission and, if correct, test your submission with Revenue Online's iXBRL test facility."),
            modelObject=[largest_equity_fact, largest_turnover_fact],
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ros20(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    ROS: Rule 20:PrincipalCurrencyUsedInBusinessReport must exist and its value must match the unit
    used for the majority of monetary facts.
    """
    principal_currency_facts = val.modelXbrl.factsByLocalName.get(PRINCIPAL_CURRENCY, set())
    principal_currency_values = {
        currencyDimensionCode
        for pc_fact in principal_currency_facts
        if (currencyDimensionCode := _getCurrencyDimensionCode(val.modelXbrl, pc_fact))
    }
    if len(principal_currency_values) != 1:
        yield Validation.error(
            "ROS.20",
            _("'PrincipalCurrencyUsedInBusinessReport' must exist and have a single value.  Values found: %(principal_currency_values)s."),
            modelObject=principal_currency_facts,
            principal_currency_values=sorted(principal_currency_values),
        )
    else:
        principal_currency_value = principal_currency_values.pop()
        monetary_facts = list(val.modelXbrl.factsByDatatype(False, qnXbrliMonetaryItemType))
        monetary_units = [
            list(fact.utrEntries)[0].unitId for fact in monetary_facts if fact.unit is not None and len(fact.utrEntries) > 0
        ]
        unit_counts = Counter(monetary_units)
        principal_currency_value_count = unit_counts[principal_currency_value]
        for count in unit_counts.values():
            if count > principal_currency_value_count:
                yield Validation.warning(
                    "ROS.20",
                    _("'PrincipalCurrencyUsedInBusinessReport' has a %(currencies_dimension)s value of %(principal_currency_value)s, "
                      "which must match the functional(majority) unit of the financial statement."),
                    modelObject=principal_currency_facts,
                    currencies_dimension=CURRENCIES_DIMENSION,
                    principal_currency_value=principal_currency_value,
                )
                break

def _getCurrencyDimensionCode(modelXbrl: ModelXbrl, fact: ModelInlineFact) -> str | None:
    if fact.context is None:
        return None
    for dim, mem in fact.context.qnameDims.items():
        if dim.localName != CURRENCIES_DIMENSION:
            continue
        if mem.xValid < VALID:
            return None
        mem_concept = modelXbrl.qnameConcepts.get(mem.xValue)
        if mem_concept is None:
            return None
        for ref_rel in modelXbrl.relationshipSet(XbrlConst.conceptReference).fromModelObject(mem_concept):
            concept_ref = ref_rel.toModelObject
            uk_ref_ns = None
            for ns in concept_ref.nsmap.values():
                if UK_REF_NS_PATTERN.match(ns):
                    uk_ref_ns = ns
                    break
            if uk_ref_ns is None:
                continue
            if code := concept_ref.findtext(f"{{{uk_ref_ns}}}Code"):
                return code.strip()
        return None
