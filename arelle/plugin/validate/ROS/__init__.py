'''
Created on Oct 12, 2020

Filer Guidelines: 
    https://www.revenue.ie/en/online-services/support/documents/ixbrl/ixbrl-technical-note.pdf
    https://www.revenue.ie/en/online-services/support/documents/ixbrl/error-messages.pdf

@author: Mark V Systems Limited
(c) Copyright 2020 Mark V Systems Limited, All rights reserved.
'''
import os, re
from collections import defaultdict
from lxml.etree import _ElementTree, _Comment, _ProcessingInstruction
from arelle import ModelDocument
from arelle.ModelInstanceObject import ModelInlineFact
from arelle.ModelValue import qname
from arelle.PythonUtil import strTruncate
from arelle.ValidateXbrlCalcs import inferredDecimals, rangeValue

taxonomyReferences = {
    "https://xbrl.frc.org.uk/ireland/FRS-101/2019-01-01/ie-FRS-101-2019-01-01.xsd": "FRS 101 Irish Extension",
    "https://xbrl.frc.org.uk/ireland/FRS-102/2019-01-01/ie-FRS-102-2019-01-01.xsd": "FRS 102 Irish Extension",
    "https://xbrl.frc.org.uk/ireland/IFRS/2019-01-01/ie-IFRS-2019-01-01.xsd": "EU IFRS Irish Extension"
    }

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
        "StartDateForPeriodCoveredByReport",
        "EndDateForPeriodCoveredByReport"
        },
    "uk-bus": {
        "StartDateForPeriodCoveredByReport",
        "EndDateForPeriodCoveredByReport",
        "ProfitLossOnOrdinaryActivitiesBeforeTax"
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
        "ProfitLossBeforeTax"
        }
    }
                
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
    if modelDocument.type in (ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INSTANCE):
        transformRegistryErrors = set()
        for elt in modelDocument.xmlRootElement.iter():
            if isinstance(elt, ModelInlineFact):
                if elt.format is not None and elt.format.namespaceURI not in TRnamespaces:
                    transformRegistryErrors.add(elt)
                        
               
        # identify type of filing
        filingTypes = [taxonomyReferences[referencedDoc.uri]
                       for referencedDoc in modelDocument.referencesDocument.keys()
                       if referencedDoc.type == ModelDocument.Type.SCHEMA
                       if referencedDoc.uri in taxonomyReferences]
        unexpectedTaxonomyReferences = [referencedDoc.uri
                                        for referencedDoc in modelDocument.referencesDocument.keys()
                                        if referencedDoc.type == ModelDocument.Type.SCHEMA
                                        if referencedDoc.uri not in taxonomyReferences]
        if len(filingTypes) != 1:
            modelXbrl.error("ROS:multipleFilingTypes",
                            _("Multiple filing types detected: %(filingTypes)s."), 
                            modelObject=modelXbrl, filingTypes=", ".join(filingTypes))
        if unexpectedTaxonomyReferences:
            modelXbrl.error("ROS:unexpectedTaxonomyReferences",
                            _("Referenced schema(s) does not map to a taxonomy supported by Revenue (schemaRef): %(unexpectedReferences)s."), 
                            modelObject=modelXbrl, unexpectedReferences=", ".join(unexpectedTaxonomyReferences))

        # build namespace maps
        nsPrefixMap = {}
        for prefix in ("ie-common", "bus", "uk-bus", "ie-dpl", "core"):
            if prefix in modelXbrl.prefixedNamespaces:
                nsPrefixMap[prefix] = modelXbrl.prefixedNamespaces[prefix]
                
        # build mandatory and footnoteIfNil tables by ns qname in use
        mandatory = set()
        for prefix in mandatoryElements:
            if prefix in nsPrefixMap:
                ns = nsPrefixMap[prefix]
                for localName in mandatoryElements[prefix]:
                    mandatory.add(qname(ns, prefix + ":" + localName))
          
        orMandatoryElements = [
            (qname(nsPrefixMap.get("uk-bus"),"ProfitLossOnOrdinaryActivitiesBeforeTax"), 
             qname(nsPrefixMap.get("core"), "ProfitLossBeforeTax")),
            ]  
            
        schemeEntityIds = set()
        mapContext = {} # identify unique contexts and units
        mapUnit = {}
        uniqueContextHashes = {}
        hasCRO = False
        for context in modelXbrl.contexts.values():
            schemeEntityIds.add(context.entityIdentifier)
            scheme, entityId = context.entityIdentifier
            if scheme not in schemePatterns:
                modelXbrl.error("ROS:unsupportedContextEntityIdentifierScheme",
                                _("Context identifier scheme is not supported: %(scheme)s."), 
                                modelObject=context, scheme=scheme)
            elif not schemePatterns[scheme].match(entityId):
                modelXbrl.error("ROS:invalidContextEntityIdentifier",
                                _("Context entity identifier lexically invalid for scheme %(scheme)s: %(identifier)s."), 
                                modelObject=context, scheme=scheme, identifier=entityId)
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
                                modelObject=modelXbrl, schemeIds=", ".join(sorted(schemeEntityIds)))

        uniqueUnitHashes = {}
        for unit in modelXbrl.units.values():
            h = unit.hash
            if h in uniqueUnitHashes:
                if unit.isEqualTo(uniqueUnitHashes[h]):
                    mapUnit[unit] = uniqueUnitHashes[h]
            else:
                uniqueUnitHashes[h] = unit
        del uniqueUnitHashes


        if hasCRO and "ie-common" in nsPrefixMap:
            mandatory.add(qname(nsPrefixMap["ie-common"], "CompaniesRegistrationOfficeNumber"))
        
        reportedMandatory = set()
        numFactsByConceptContextUnit = defaultdict(list) 
                
        for qn, facts in modelXbrl.factsByQname.items():
            if qn in mandatory:
                reportedMandatory.add(qn)
            for f in facts:
                if f.isNumeric:
                    numFactsByConceptContextUnit[(f.qname, mapContext.get(f.context,f.context), mapUnit.get(f.unit, f.unit))].append(f)
            
        missingElements = (mandatory - reportedMandatory) # | (reportedFootnoteIfNil - reportedFootnoteIfNil)
        
        for qn1, qn2 in orMandatoryElements: # remove missing elements for which an or-match was reported
            if qn1 in reportedMandatory:
                missingElements.discard(qn2)
            if qn2 in reportedMandatory:
                missingElements.discard(qn1)
                
        if missingElements:
            modelXbrl.error("ROS:missingRequiredElements",
                            _("Required elements missing from document: %(elements)s."), 
                            modelObject=modelXbrl, elements=", ".join(sorted(str(qn) for qn in missingElements)))
                
        for fList in numFactsByConceptContextUnit.values():
            if len(fList) > 1:
                f0 = fList[0]
                if any(f.isNil for f in fList):
                    _inConsistent = not all(f.isNil for f in fList)
                elif all(inferredDecimals(f) == inferredDecimals(f0) for f in fList[1:]): # same decimals
                    v0 = rangeValue(f0.value)
                    _inConsistent = not all(rangeValue(f.value) == v0 for f in fList[1:])
                else: # not all have same decimals
                    aMax, bMin = rangeValue(f0.value, inferredDecimals(f0))
                    for f in fList[1:]:
                        a, b = rangeValue(f.value, inferredDecimals(f))
                        if a > aMax: aMax = a
                        if b < bMin: bMin = b
                    _inConsistent = (bMin < aMax)
                if _inConsistent:
                    modelXbrl.error(("ROS.inconsistentDuplicateFacts"),
                        "Inconsistent duplicate numeric facts: %(fact)s were used more than once in contexts equivalent to %(contextID)s: values %(values)s.  ",
                        modelObject=fList, fact=f0.qname, contextID=f0.contextID, values=", ".join(strTruncate(f.value, 128) for f in fList))
                


    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)
    

__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate ROS',
    'version': '1.0',
    'description': '''ROS (Ireland) Validation.''',
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2020 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally,
}