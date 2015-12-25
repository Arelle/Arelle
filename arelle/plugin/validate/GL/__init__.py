'''
Created on Dec 20, 2015

@author: Mark V Systems Limited
(c) Copyright 2015 Mark V Systems Limited, All rights reserved.
'''
import os
from arelle import ModelDocument, ModelValue, XmlUtil, XbrlConst
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelValue import qname
try:
    import regex as re
except ImportError:
    import re
from collections import defaultdict

glNamespaceDatePattern = re.compile(r"http://www.xbrl.org/int/gl/(\w{3,4})/([0-9]{4}-[01][0-9]-[0-3][0-9])")
gl06date = "2006-10-25"
srcd07date = "2007-02-08"
gl15date = "2015-03-25"

glCor06 = "http://www.xbrl.org/int/gl/cor/2006-10-25"
glCor15 = "http://www.xbrl.org/int/gl/cor/2015-03-25"
glCorAll = (glCor06, glCor15)

'''
def dislosureSystemTypes(disclosureSystem, *args, **kwargs):
    # return ((disclosure system name, variable name), ...)
    return (("GL", "GLplugin"),)

def disclosureSystemConfigURL(disclosureSystem, *args, **kwargs):
    return os.path.join(os.path.dirname(__file__), "config.xml")
'''

def tupleFacts(tuple):
    return dict((f.qname.localName, f) for 
                f in tuple.iterdescendants()
                if isinstance(f, ModelFact))
    
def tupleValues(tuple):
    return dict((f.qname.localName, getattr(f,"xValue")) 
                for f in tuple.iterdescendants()
                if isinstance(f, ModelFact))
    
def validateXbrlStart(val, parameters=None, *args, **kwargs):
    # val.validateGLplugin = val.validateDisclosureSystem and getattr(val.disclosureSystem, "GLplugin", False)

    # validate if there's a GL instance document irrespective of DisclosureSystem authority
    val.validateGLplugin =  (val.modelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE and
                             any(f.namespaceURI in glCorAll and f.localName == "accountingEntries"
                                 for f in val.modelXbrl.facts))
    if not (val.validateGLplugin):
        return

    val.validateUTR = False # do not use default UTR validation, irrelevant and not streamable
    val.gl06 = val.gl15 = False
    val.summaryTaxonomies = {}  # ID:href

    modelDocument = val.modelXbrl.modelDocument
    if modelDocument.type == ModelDocument.Type.INSTANCE:
        for doc, docRef in modelDocument.referencesDocument.items():
            if docRef.referenceType == "href":
                if docRef.referringModelObject.localName == "schemaRef":
                    _match = glNamespaceDatePattern.match(doc.targetNamespace)
                    if _match:
                        _module = _match.group(1)
                        _date = _match.group(2)
                        if _date == gl06date or (_module == "srcd" and _date == srcd07date):
                            val.gl06 = True
                        elif _date == gl15date:
                            val.gl15 = True
                        else:
                            modelXbrl.warning("xbrl-gl:namespaceDate",
                                    _('GL instance references %(module)s namespace date %(date)s not recognized'),
                                    modelObject=doc, module=_module, date=_date)
        if val.gl06 and val.gl15:
            modelXbrl.error("xbrl-gl:namespaceDateClash",
                    _('GL modules have namespace date clash between modules %(modules06)s and %(modules15)s.'),
                    modelObject=doc, modules06=", ".join(_06modules), modules15=", ".join(_15modules))

def validateFacts(val, factsToCheck, *args, **kwargs):
    # compatible with streaming (of level 2 tuples) or non-streaming mode
    if not (val.validateGLplugin):
        return
    modelXbrl = val.modelXbrl
    modelDocument = val.modelXbrl.modelDocument
    for f in factsToCheck:
        if f.localName == "accountingEntries":
            validateFacts(val, f.modelTupleFacts)
        elif f.localName == "documentInfo":
            for fSRT in f.iterchildren("{*}summaryReportingTaxonomies"):
                srt = tupleValues(fSRT)
                _id = srt.get("summaryReportingTaxonomyID")
                _href = srt.get("summaryReportingTaxonomySchemaRefHref")
                if not _id:
                    modelXbrl.warning("xbrl-gl:summaryReportingTaxonomyIdMissing",
                            _('No ID for summary taxonomy %(href)s'),
                            modelObject=fSRT, href=srt.get("summaryReportingTaxonomySchemaRefHref", "missingHref"))
                else:
                    if _id in val.summaryTaxonomies:
                        modelXbrl.warning("xbrl-gl:summaryReportingTaxonomyIdDuplicate",
                                _('Duplicate ID %(id)s for summary taxonomy %(href)s'),
                                modelObject=fSRT, id=_id, href=_href)
                    elif not _href:
                        modelXbrl.warning("xbrl-gl:summaryReportingTaxonomyHrefMissing",
                                _('No href for summary taxonomy %(id)s'),
                                modelObject=fSRT, id=_id)
                    else:
                        val.summaryTaxonomies[_id] = _href
                        # load _href for validation of referenced elements
                        if ModelDocument.load(modelXbrl, _href, isDiscovered=False, base=modelDocument.baseForElement(fSRT), referringElement=f) is None:
                            modelXbrl.error("xbrl-gl:summaryReportingTaxonomyHrefUnloadable",
                                    _('Unable to load summary reporting taxonomy %(href)s'),
                                    modelObject=fSRT, href=_href)
                            
        elif f.localName == "entityInfo":
            pass
        elif f.localName == "entryHeader":
            validateFacts(val, f.modelTupleFacts)
        elif f.localName == "entryDetail":
            tv = tupleValues(f)
            for fXI in f.iterchildren("{*}xbrlInfo"):
                xi = tupleValues(fXI)
                _summaryQnElt = xi.get("summaryReportingElement") # type is QName or None
                _summaryConcept = modelXbrl.qnameConcepts.get(_summaryQnElt)
                if _summaryConcept is None:
                    modelXbrl.error("xbrl-gl:summaryReportingElement",
                            _('No summaryReportingElement %(element)s'),
                            modelObject=fXI, element=_summaryQnElt)
                _detailQnElt = xi.get("detailMatchingElement")
                if _detailQnElt:
                    numDetailMatchingElements = 0
                    
                    for _detailMatchingFact in f.iterdescendants(_detailQnElt.clarkNotation):
                        numDetailMatchingElements += 1
                        if (_summaryConcept is not None and _detailMatchingFact.concept is not None and
                            not((_summaryConcept.isNumeric and _detailMatchingFact.isNumeric) or
                                (_summaryConcept.baseXsdType == _detailMatchingFact.concept.baseXsdType))):
                            modelXbrl.error("xbrl-gl:detailMatchingElementType",
                                    _('Base type of detailMatchingElement, %(detailElement)s, %(detailElementType)s doesn\'t match summary element %(summaryElement)s type %(summaryElementType)s'),
                                    modelObject=fXI, 
                                    detailElement=_detailQnElt, detailElementType=_detailMatchingFact.concept.baseXsdType, 
                                    summaryElement=_summaryQnElt, summaryElementType=_summaryConcept.baseXsdType)
                    if numDetailMatchingElements != 1:
                        modelXbrl.error("xbrl-gl:detailMatchingElement",
                                _('Must have exactly one detailMatchingElement %(element)s, %(numDetailMatchingElements)s found.'),
                                modelObject=fXI, element=_detailQnElt, numDetailMatchingElements=numDetailMatchingElements)
                if "summaryIdentifier" not in xi or "summaryScheme" not in xi:
                    modelXbrl.error("xbrl-gl:summaryEntity",
                            _('Incomplete summaryEntity for summaryReportingElement %(element)s'),
                            modelObject=fXI, element=_summaryQnElt)
                # units declared as tokens, check for proper QName
                _unitMeasureQn = None
                for _unitToken in ("{*}summaryNumerator", "{*}summaryDenominator"):
                    for _fUnit in fXI.iterdescendants(_unitToken):
                        _unitMeasureQn = _fUnit.prefixedNameQname(_fUnit.xValue)
                        if _unitMeasureQn is None:
                            modelXbrl.error("xbrl-gl:summaryUnit",
                                    _('Invalid unit measure %(measure)s for summaryReportingElement %(element)s'),
                                    modelObject=fXI, element=_summaryQnElt, measure=_fUnit.xValue)
                if _summaryConcept is not None:
                    if _summaryConcept.isNumeric and "summaryNumerator" not in xi:
                        modelXbrl.error("xbrl-gl:summaryUnit",
                                _('No summaryUnit for numeric summaryReportingElement %(element)s'),
                                modelObject=fXI, element=_summaryQnElt)
                    # note that units are tokens, not QNames
                    elif _summaryConcept.isMonetary and (_unitMeasureQn is None or _unitMeasureQn.namespaceURI != XbrlConst.iso4217):
                        modelXbrl.error("xbrl-gl:summaryUnitMonetary",
                                _('Monetary concept summaryUnit invalid for numeric summaryReportingElement %(element)s: %(monetaryUnit)s'),
                                modelObject=fXI, element=_summaryQnElt, monetaryUnit=xi["summaryNumerator"])
                    if (_summaryConcept.periodType == "instant") != ("summaryInstant" in xi):
                        modelXbrl.error("xbrl-gl:summaryPeriodType",
                                _('Summary period type %(summaryPeriodType)s doesn\'t match summaryReportingElement  %(element)s period type %(periodType)s'),
                                modelObject=fXI, element=_summaryQnElt, periodType=_summaryConcept.periodType,
                                summaryPeriodType="instant" if "summaryInstant" in xi else "duration")
                if ("summaryStartDate" in xi) ^ ("summaryEndDate" in xi):
                    modelXbrl.error("xbrl-gl:summaryStartDateEndDate",
                            _('Incomplete startDate/endDate for summaryReportingElement %(element)s'),
                            modelObject=fXI, element=_summaryQnElt)
                _summaryTxmyId = xi.get("summaryReportingTaxonomyIDRef", "(missing)")
                
                if _summaryTxmyId not in val.summaryTaxonomies:
                    modelXbrl.error("xbrl-gl:summaryReportingTaxonomyIDRef",
                            _('SummaryReportingTaxonomyIDRef invalid: %(summaryReportingTaxonomyIDRef)s.'),
                            modelObject=fXI, summaryReportingTaxonomyIDRef=_summaryTxmyId)

def validateXbrlFinally(val, *args, **kwargs):
    if not (val.validateGLplugin):
        return

    modelXbrl = val.modelXbrl
    modelDocument = modelXbrl.modelDocument
    
    if not getattr(modelXbrl, "isStreamingMode", False):
        validateFacts(val, modelXbrl.facts)


                
__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate GL',
    'version': '1.0',
    'description': '''Global Ledger (GL) Validation.''',
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2013-15 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    #'DisclosureSystem.Types': dislosureSystemTypes,
    #'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally,
}
