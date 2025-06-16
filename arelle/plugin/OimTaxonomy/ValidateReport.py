'''
See COPYRIGHT.md for copyright information.
'''

from arelle.oim.Load import PeriodPattern
from arelle.ModelValue import QName
from .XbrlConcept import XbrlConcept
from .XbrlDimension import XbrlDimension
from .ValidateTaxonomyModel import validateValue

def validateReport(xbrlReport):
    txmyMdl = xbrlReport
    for fact in xbrlReport.facts:
        id = fact.id
        if not id:
            txmyMdl.error("oime:missingFactId",
                          _("The id MUST be present on fact: %(id)s."),
                          xbrlObject=obj)
        cQn = fact.dimensions.get("concept")
        cObj = txmyMdl.namedObjects.get(cObj)
        if cObj is None or not isinstance(cObj, XbrlConcept):
            txmyMdl.error("oime:missingConceptDimension",
                          _("The concept core dimension MUST be present on fact: %(id)s and must be a taxonomy concept."),
                          xbrlObject=obj, id=id)
            continue
        validateValue(txmyMdl, fact, fact.value, cObj.dataType, f"/value")
        if "language" in fact.dimensions:
            lang = fact.dimensions["language"]
            if concept.type.isOimTextFactType:
                if not lang.islower():
                    txmyMdl.error("xbrlje:invalidLanguageCodeCase",
                                  _("Language MUST be lower case: \"%(lang)s\", fact %(factId)s, concept %(concept)s."),
                                  xbrlObject=obj, factId=id, concept=cQn, lang=lang)
        if "period" in fact.dimensions:
            per = fact.dimensions["period"]
            if not PeriodPattern.match(period):
                txmyMdl.error("oimce:invalidPeriodRepresentation",
                              _("The fact %(factId)s, concept %(element)s has a lexically invalid period dateTime %(periodError)s"),
                              xbrlObject=obj, factId=id, element=cQn, periodError=per)
                continue
            _start, _sep, _end = per.rpartition('/')
            if ((cObj.periodType == "duration" and (not _start or _start == _end)) or
                  (cObj.periodType == "instant" and _start and _start != _end)):
                txmyMdl.error("oime:invalidPeriodDimension",
                              _("Invalid period for %(periodType)s fact %(factId)s period %(period)s."),
                              xbrlObject=obj, factId=id, periodType=cObj.periodType, period=per)
                continue # skip creating fact because context would be bad
        elif cObj.periodType != "duration":
             txmyMdl.error("oime:missingPeriodDimension",
                           _("Missing period for %(periodType)s fact %(factId)s."),
                           xbrlObject=obj, factId=id, periodType=cObj.periodType, period=per)
        for dimName, dimVal in fact.dimensions.items():
            if not isinstance(dimName, QName):
                if dimName not in {"concept", "entity", "period", "unit", "language"}:
                    txmyMdl.error("oime:unknownDimension",
                                  _("Fact %(factId)s taxonomy-defined dimension QName not be resolved with available DTS: %(qname)s."),
                                  xbrlObject=obj, factId=id, qname=dimName)
            else:
                dimObj = txmyMdl.namedObjects.get(dimQname)
                if not isinstance(dimObj, XbrlDimension):
                    txmyMdl.error("oime:unknownDimension",
                                  _("Fact %(factId)s taxonomy-defined dimension QName not be resolved with available DTS: %(qname)s."),
                                  xbrlObject=obj, factId=id, qname=dimName)
                    continue
                if dimConcept.isExplicitDimension:
                    memQn = txmyMdl.namedObjects.get(dimValue)
                    if memQn is None:
                        txmyMdl.error("{}:invalidDimensionValue".format(valErrPrefix),
                                      _("Fact %(factId)s taxonomy-defined explicit dimension value is invalid: %(memberQName)s."),
                                      modelObject=modelXbrl, factId=id, memberQName=memQn)
                        continue
                    memObj = txmyMdl.namedObjects.get(memQn)
                    if memObj is not None and modelXbrl.dimensionDefaultConcepts.get(dimConcept) == memConcept:
                        error("{}:invalidDimensionValue".format("oime" if valErrPrefix == "xbrlje" else valErrPrefix),
                              _("Fact %(factId)s taxonomy-defined explicit dimension value must not be the default member: %(memberQName)s."),
                              xbrlObject=objmodelObject=modelXbrl, factId=id, memberQName=dimVal)
                        continue
                elif dimConcept.isTypedDimension:
                    # a modelObject xml element is needed for all of the instance functions to manage the typed dim
                    if dimConcept.typedDomainElement.baseXsdType in ("ENTITY", "ENTITIES", "ID", "IDREF", "IDREFS", "NMTOKEN", "NMTOKENS", "NOTATION") or (
                       dimConcept.typedDomainElement.instanceOfType(XbrlConst.dtrPrefixedContentTypes) and not dimConcept.typedDomainElement.instanceOfType(XbrlConst.dtrSQNameNamesTypes)) or (
                        dimConcept.typedDomainElement.type is not None and
                        dimConcept.typedDomainElement.type.qname != XbrlConst.qnXbrliDateUnion and
                        (dimConcept.typedDomainElement.type.localName == "complexType" or
                         any(c.localName in ("union","list") for c in dimConcept.typedDomainElement.type.iterchildren()))):
                        error("oime:unsupportedDimensionDataType",
                              _("Fact %(factId)s taxonomy-defined typed dimension value is not supported: %(memberQName)s."),
                              modelObject=modelXbrl, factId=id, memberQName=dimVal)
                        continue
                    if (canonicalValuesFeature and dimVal is not None and
                        not CanonicalXmlTypePattern.get(dimConcept.typedDomainElement.baseXsdType, NoCanonicalPattern).match(dimVal)):
                        error("xbrlje:nonCanonicalValue",
                              _("Numeric typed dimension must have canonical %(type)s value \"%(value)s\": %(concept)s."),
                              modelObject=modelXbrl, type=dimConcept.typedDomainElement.baseXsdType, concept=dimConcept, value=dimVal)
                    mem = XmlUtil.addChild(modelXbrl.modelDocument, dimConcept.typedDomainElement.qname, text=dimVal, attributes=memberAttrs, appendChild=False)
                else:
                    mem = None # absent typed dimension
                if mem is not None:
                    qnameDims[dimQname] = DimValuePrototype(modelXbrl, None, dimQname, mem, contextElement)
