'''
Filer Guidelines:
    https://www.revenue.ie/en/online-services/support/documents/ixbrl/ixbrl-technical-note.pdf
    https://www.revenue.ie/en/online-services/support/documents/ixbrl/error-messages.pdf
    https://www.revenue.ie/en/online-services/support/documents/ixbrl/ixbrl-style-guide.pdf

See COPYRIGHT.md for copyright information.
'''
import os, re
from collections import defaultdict
from math import isnan
from lxml.etree import _ElementTree, _Comment, _ProcessingInstruction
from arelle import ModelDocument
from arelle.ModelInstanceObject import ModelInlineFact
from arelle.ModelValue import qname
from arelle.PythonUtil import strTruncate
from arelle.ValidateXbrlCalcs import inferredDecimals, rangeValue
from arelle.Version import authorLabel, copyrightLabel
from arelle.XbrlConst import qnXbrliXbrl, xhtml
from arelle.XmlValidate import VALID

taxonomyReferences = [
     "https://xbrl.frc.org.uk/ireland/FRS-101/2019-01-01/ie-FRS-101-2019-01-01.xsd",
     "https://xbrl.frc.org.uk/ireland/FRS-101/2022-01-01/ie-FRS-101-2022-01-01.xsd",
     "https://xbrl.frc.org.uk/ireland/FRS-102/2019-01-01/ie-FRS-102-2019-01-01.xsd",
     "https://xbrl.frc.org.uk/ireland/FRS-102/2022-01-01/ie-FRS-102-2022-01-01.xsd",
     "https://xbrl.frc.org.uk/ireland/IFRS/2019-01-01/ie-IFRS-2019-01-01.xsd",
     "https://xbrl.frc.org.uk/ireland/IFRS/2022-01-01/ie-IFRS-2022-01-01.xsd",
 ]

schemePatterns = {
    "http://www.revenue.ie/": re.compile(r"^(\d{7}[A-Z]{1,2}|CHY\d{1,5})$"),
    "http://www.cro.ie/": re.compile(r"^\d{1,6}$")
    }

TRnamespaces = {
    "http://www.xbrl.org/inlineXBRL/transformation/2010-04-20",
    "http://www.xbrl.org/inlineXBRL/transformation/2011-07-31",
    "http://www.xbrl.org/inlineXBRL/transformation/2015-02-26"
    }

mandatoryElements = {
    "bus": {
        "EntityCurrentLegalOrRegisteredName",
        "StartDateForPeriodCoveredByReport",
        "EndDateForPeriodCoveredByReport"
        },
    "uk-bus": {
        "EntityCurrentLegalOrRegisteredName",
        "StartDateForPeriodCoveredByReport",
        "EndDateForPeriodCoveredByReport",
        },
    "ie-dpl": {
        "DPLTurnoverRevenue",
        "DPLGovernmentGrantIncome",
        "DPLOtherOperatingIncome",
        "DPLGrossProfitLoss",
        "DPLStaffCostsEmployeeBenefitsExpense",
        "DPLSubcontractorCosts",
        "DPLProfitLossBeforeTax"
        },
    "core": {
        "Equity",
        }
    }

# lists of mandatory elements which can be satisfied by other taxonomies
equivalentMandatoryElements = [
    ]

def dislosureSystemTypes(disclosureSystem, *args, **kwargs):
    # return ((disclosure system name, variable name), ...)
    return (("ROS", "ROSplugin"),)

def disclosureSystemConfigURL(disclosureSystem, *args, **kwargs):
    return os.path.join(os.path.dirname(__file__), "config.xml")

def validateXbrlStart(val, parameters=None, *args, **kwargs):
    val.validateROSplugin = val.validateDisclosureSystem and getattr(val.disclosureSystem, "ROSplugin", False)
    if not (val.validateROSplugin):
        return

def validateXbrlFinally(val, *args, **kwargs):
    if not (val.validateROSplugin):
        return

    _xhtmlNs = "{{{}}}".format(xhtml)
    _xhtmlNsLen = len(_xhtmlNs)
    modelXbrl = val.modelXbrl
    modelDocument = modelXbrl.modelDocument
    if not modelDocument:
        return # never loaded properly

    _statusMsg = _("validating {0} filing rules").format(val.disclosureSystem.name)
    modelXbrl.profileActivity()
    modelXbrl.modelManager.showStatus(_statusMsg)


    if modelDocument.type == ModelDocument.Type.INSTANCE:
        modelXbrl.error("ROS:instanceMustBeInlineXBRL",
                        _("ROS expects inline XBRL instances."),
                        modelObject=modelXbrl)
    if modelDocument.type in (ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET):
        for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements: # ix root elements for all ix docs in IXDS
            ixNStag = ixdsHtmlRootElt.modelDocument.ixNStag
            ixTags = set(ixNStag + ln for ln in ("nonNumeric", "nonFraction", "references", "relationship"))

        transformRegistryErrors = set()
        ixTargets = set()
        for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements:
            for elt in ixdsHtmlRootElt.iter():
                if isinstance(elt, (_ElementTree, _Comment, _ProcessingInstruction)):
                    continue # comment or other non-parsed element
                if isinstance(elt, ModelInlineFact):
                    if elt.format is not None and elt.format.namespaceURI not in TRnamespaces:
                        transformRegistryErrors.add(elt)
                    if elt.get("escape") in ("true","1"):
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

        filingTypes = set()
        unexpectedTaxonomyReferences = set()
        numIxDocs = 0
        for doc in modelXbrl.urlDocs.values():
            if doc.type == ModelDocument.Type.INLINEXBRL:
                # base file extension
                _baseName, _baseExt = os.path.splitext(doc.basename)
                if _baseExt not in (".xhtml",".html", ".htm", ".ixbrl", ".xml", ".xhtml"):
                    modelXbrl.error("ROS.fileNameExtension",
                        _("The list of acceptable file extensions for upload is: html, htm, ixbrl, xml, xhtml: %(fileName)s"),
                        modelObject=doc, fileName=doc.basename)

                # document encoding
                if doc.documentEncoding.lower() != "utf-8":
                    modelXbrl.error("ROS.documentEncoding",
                        _("iXBRL documents submitted to Revenue should be UTF-8 encoded: %(encoding)s"),
                        modelObject=doc, encoding=doc.documentEncoding)

                # identify type of filing
                for referencedDoc in doc.referencesDocument.keys():
                    if referencedDoc.type == ModelDocument.Type.SCHEMA:
                        if referencedDoc.uri in taxonomyReferences:
                            filingTypes.add(referencedDoc.uri)
                        else:
                            unexpectedTaxonomyReferences.add(referencedDoc.uri)
                # count of inline docs in IXDS
                numIxDocs += 1

        if len(filingTypes) != 1:
            modelXbrl.error("ROS:multipleFilingTypes",
                            _("Multiple filing types detected: %(filingTypes)s."),
                            modelObject=modelXbrl, filingTypes=", ".join(sorted(filingTypes)))
        if unexpectedTaxonomyReferences:
            modelXbrl.error("ROS:unexpectedTaxonomyReferences",
                            _("Referenced schema(s) does not map to a taxonomy supported by Revenue (schemaRef): %(unexpectedReferences)s."),
                            modelObject=modelXbrl, unexpectedReferences=", ".join(sorted(unexpectedTaxonomyReferences)))

        # single document IXDS
        if numIxDocs > 1:
            modelXbrl.warning("ROS:multipleInlineDocuments",
                            _("A single inline document should be submitted but %(numberDocs)s were found."),
                            modelObject=modelXbrl, numberDocs=numIxDocs)

        # build namespace maps
        nsMap = {}
        for prefix in ("ie-common", "bus", "uk-bus", "ie-dpl", "core"):
            if prefix in modelXbrl.prefixedNamespaces:
                nsMap[prefix] = modelXbrl.prefixedNamespaces[prefix]

        # build mandatory table by ns qname in use
        mandatory = set()
        for prefix in mandatoryElements:
            if prefix in nsMap:
                ns = nsMap[prefix]
                for localName in mandatoryElements[prefix]:
                    mandatory.add(qname(ns, prefix + ":" + localName))

        equivalentManatoryQNames = [[qname(q,nsMap) for q in equivElts] for equivElts in equivalentMandatoryElements]

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
        mapContext = {} # identify unique contexts and units
        mapUnit = {}
        uniqueContextHashes = {}
        hasCRO = False
        unsupportedSchemeContexts = []
        mismatchIdentifierContexts = []
        for context in modelXbrl.contexts.values():
            schemeEntityIds.add(context.entityIdentifier)
            scheme, entityId = context.entityIdentifier
            if scheme not in schemePatterns:
                unsupportedSchemeContexts.append(context)
            elif not schemePatterns[scheme].match(entityId):
                mismatchIdentifierContexts.append(context)
            if scheme == "http://www.cro.ie/":
                hasCRO = True
            h = context.contextDimAwareHash
            if h in uniqueContextHashes:
                if context.isEqualTo(uniqueContextHashes[h]):
                    mapContext[context] = uniqueContextHashes[h]
            else:
                uniqueContextHashes[h] = context
        del uniqueContextHashes
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

        uniqueUnitHashes = {}
        for unit in modelXbrl.units.values():
            h = unit.hash
            if h in uniqueUnitHashes:
                if unit.isEqualTo(uniqueUnitHashes[h]):
                    mapUnit[unit] = uniqueUnitHashes[h]
            else:
                uniqueUnitHashes[h] = unit
        del uniqueUnitHashes


        if hasCRO and "ie-common" in nsMap:
            mandatory.add(qname("ie-common:CompaniesRegistrationOfficeNumber", nsMap))

        reportedMandatory = set()
        factForConceptContextUnitHash = defaultdict(list)

        for qn, facts in modelXbrl.factsByQname.items():
            if qn in mandatory:
                reportedMandatory.add(qn)
            for f in facts:
                if (f.parentElement.qname == qnXbrliXbrl and
                    (f.isNil or getattr(f,"xValid", 0) >= VALID) and f.context is not None and f.concept is not None and f.concept.type is not None):
                    factForConceptContextUnitHash[f.conceptContextUnitHash].append(f)

        missingElements = (mandatory - reportedMandatory) # | (reportedFootnoteIfNil - reportedFootnoteIfNil)

        for qnames in equivalentManatoryQNames: # remove missing elements for which an or-match was reported
            if any(qn in modelXbrl.factsByQname for qn in qnames):
                for qn in qnames:
                    missingElements.discard(qn)

        if missingElements:
            modelXbrl.error("ROS:missingRequiredElements",
                            _("Required elements missing from document: %(elements)s."),
                            modelObject=modelXbrl, elements=", ".join(sorted(str(qn) for qn in missingElements)))

        aspectEqualFacts = defaultdict(dict) # dict [(qname,lang)] of dict(cntx,unit) of [fact, fact]
        decVals = {}
        for hashEquivalentFacts in factForConceptContextUnitHash.values():
            if len(hashEquivalentFacts) > 1:
                for f in hashEquivalentFacts: # check for hash collision by value checks on context and unit
                    cuDict = aspectEqualFacts[(f.qname,
                                               (f.xmlLang or "").lower() if f.concept.type.isWgnStringFactType else None)]
                    _matched = False
                    for (_cntx,_unit),fList in cuDict.items():
                        if (((_cntx is None and f.context is None) or (f.context is not None and f.context.isEqualTo(_cntx))) and
                            ((_unit is None and f.unit is None) or (f.unit is not None and f.unit.isEqualTo(_unit)))):
                            _matched = True
                            fList.append(f)
                            break
                    if not _matched:
                        cuDict[(f.context,f.unit)] = [f]
                for cuDict in aspectEqualFacts.values(): # dups by qname, lang
                    for fList in cuDict.values():  # dups by equal-context equal-unit
                        if len(fList) > 1:
                            f0 = fList[0]
                            _inConsistent = True
                            if f0.concept.isNumeric:
                                if any(f.isNil for f in fList):
                                    _inConsistent = not all(f.isNil for f in fList)
                                else: # not all have same decimals
                                    _d = inferredDecimals(f0)
                                    _v = f0.xValue
                                    _inConsistent = isnan(_v) # NaN is incomparable, always makes dups inconsistent
                                    decVals[_d] = _v
                                    aMax, bMin = rangeValue(_v, _d)
                                    for f in fList[1:]:
                                        _d = inferredDecimals(f)
                                        _v = f.xValue
                                        if isnan(_v):
                                            _inConsistent = True
                                            break
                                        if _d in decVals:
                                            _inConsistent |= _v != decVals[_d]
                                        else:
                                            decVals[_d] = _v
                                        a, b = rangeValue(_v, _d)
                                        if a > aMax: aMax = a
                                        if b < bMin: bMin = b
                                    if not _inConsistent:
                                        _inConsistent = (bMin < aMax)
                                    decVals.clear()
                            else: # string complete duplicates
                                _inConsistent = any(not f.isVEqualTo(f0) for f in fList[1:])
                            if _inConsistent:
                                modelXbrl.error("ROS.inconsistentDuplicateFacts",
                                    "Inconsistent duplicate fact values %(element)s: %(values)s, in contexts: %(contextIDs)s.",
                                    modelObject=fList, element=f0.qname,
                                    contextIDs=", ".join(sorted(set(f.contextID for f in fList))),
                                    values=", ".join(strTruncate(f.value,64) for f in fList))
                aspectEqualFacts.clear()
        del factForConceptContextUnitHash, aspectEqualFacts

    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)


__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate ROS',
    'version': '1.0',
    'description': '''ROS (Ireland) Validation.''',
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    'import': ('inlineXbrlDocumentSet', ), # import dependent modules
    # classes of mount points (required)
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally,
}
