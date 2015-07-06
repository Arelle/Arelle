'''
Created on Dec 12, 2013

@author: Mark V Systems Limited
(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelObject import ModelObject
from arelle.PythonUtil import flattenSequence
from arelle.XmlUtil import xmlstring
from arelle import XbrlConst, XmlUtil
import re
from collections import defaultdict
from decimal import Decimal

labelrole = None
lang = None

altParametersPattern = re.compile(r"\$\{([\w.:-]+)\}")
parametersPattern = re.compile(r"%\(([\w.:-]+)\)")
factNumberPattern = re.compile(r"fact(\d+)")

def measureFormat(measure):
    if measure.namespaceURI in (XbrlConst.iso4217, XbrlConst.xbrli):
        return measure.localName
    return str(measure)  # qname str

def loggingMessageParameters(messageCode, msgIn, modelObjectArgs, fmtArgs):
    if messageCode and messageCode.startswith("DQC"):
        # change ${...} in message into %(...)s
        msg = altParametersPattern.sub(r"%(\1)s", msgIn)
        
        # find qnamed fact references
        qnamedReferences = set()
        paramNames = parametersPattern.findall(msg)
        for param in paramNames:
            paramParts = param.split('.')
            if len(paramParts) > 1 and not factNumberPattern.match(paramParts[0]):
                qnamedReferences.add(paramParts[0])
        factsArray = []
        factsByQname = defaultdict(list)  # list of facts with the qname
        conceptsByQname = {}
        for arg in flattenSequence(modelObjectArgs):
            # Pargmeter may be a ModelFact, or a name of a concept (such as a dimension)
            if isinstance(arg, ModelFact):
                if str(arg.qname) in qnamedReferences:
                    factsByQname[str(arg.qname)].append(arg)
                else:
                    factsArray.append(arg)
                    cntx = arg.context
                    if cntx is not None:
                        for dim in cntx.qnameDims.values():
                            if str(dim.dimensionQname) in qnamedReferences:
                                conceptsByQname[str(dim.dimensionQname)] = dim.dimension
                            elif str(dim.dimensionQname) in qnamedReferences:
                                conceptsByQname[str(dim.memberQname)] = dim.member
 
        def setArgForFactProperty(param, modelFact, propertyNameParts):
            propVal = None
            property = propertyNameParts[0]
            if property == "value":
                if isinstance(modelFact.xValue, Decimal):
                    propVal = "{:,}".format(modelFact.xValue)
                else:
                    propVal = modelFact.value
            elif property == "decimals":
                propVal = modelFact.decimals
            elif property == "label" and modelFact.concept is not None:
                propVal = modelFact.concept.label(labelrole,
                                                  lang=lang,
                                                  linkroleHint=XbrlConst.defaultLinkRole)
            elif property == "name":
                propVal = str(modelFact.qname)
            elif property == "localName":
                propVal = modelFact.qname.localName
            else:
                cntx = modelFact.context
                unit = modelFact.unit
                if cntx is not None:
                    if property == "period":
                        if len(propertyNameParts) == 1:
                            if cntx.isForeverPeriod:
                                propVal = "forever"
                            elif cntx.isInstantPeriod:
                                propVal = XmlUtil.dateunionValue(cntx.instantDatetime, subtractOneDay=True)
                            else:
                                propVal = "{} - {}".format(XmlUtil.dateunionValue(cntx.startDatetime),
                                                           XmlUtil.dateunionValue(cntx.endDatetime, subtractOneDay=True))
                        else:
                            dateSelection = propertyNameParts[1]
                            if dateSelection == "startDate":
                                propVal = XmlUtil.dateunionValue(cntx.startDatetime)
                            elif dateSelection == "endDate":
                                propVal = XmlUtil.dateunionValue(cntx.endDatetime, subtractOneDay=True)
                            elif dateSelection == "instant":
                                propVal = XmlUtil.dateunionValue(cntx.instant, subtractOneDay=True)
                            elif dateSelection == "durationDays":
                                propVal = str((cntx.endDatetime - cntx.startDatetime).days)
                    elif property == "dimensions":
                        if cntx.qnameDims:
                            propVal = "\n".join("{} = {}".format(d.dimensionQname, 
                                                                d.memberQname if d.isExplicit else
                                                                XmlUtil.xmlstring( XmlUtil.child(d), stripXmlns=True, prettyPrint=True ))
                                                for d in cntx.qnameDims.values())
                        else:
                            propVal = "none"
                if property == "unit":
                    if unit is None:
                        propVal = "none"
                    else:
                        measures = unit.measures
                        if measures[1]:
                            propVal = 'mul {}\ndiv {} '.format(
                                    ', '.join(measureFormat(m) for m in measures[0]),
                                    ', '.join(measureFormat(m) for m in measures[1]))
                        else:
                            propVal = ', '.join(measureFormat(m) for m in measures[0])
            if propVal is not None:
                fmtArgs[param] = propVal
                
        def setArgForConceptProperty(param, modelConcept, propertyNameParts):
            propVal = None
            property = propertyNameParts[0]
            if property == "label":
                propVal = modelConcept.label(labelrole,
                                             lang=lang,
                                             linkroleHint=XbrlConst.defaultLinkRole)
            elif property == "name":
                propVal = str(modelConcept.qname)
            elif property == "localName":
                propVal = modelConcept.qname.localName
            if propVal is not None:
                fmtArgs[param] = propVal
                
        # parse parameter names out of msg
        for param in paramNames:
            try:
                paramParts = param.split('.')
                if len(paramParts) >= 2 and factNumberPattern.match(paramParts[0]):
                    modelFactNum = int(factNumberPattern.match(paramParts[0]).group(1))
                    if 1 <= modelFactNum <= len(factsArray):
                        modelFact = factsArray[modelFactNum - 1]
                        setArgForFactProperty(param, modelFact, paramParts[1:])
                elif len(paramParts) >= 3 and paramParts[1] == "fact":
                    # take first matching fact ??
                    if paramParts[0] in factsByQname:
                        modelFact = factsByQname[paramParts[0]][0] # there may be multiple facts of this QName, take first
                        setArgForFactProperty(param, modelFact, paramParts[2:])
                elif len(paramParts) >= 2 and paramParts[0] in conceptsByQname:
                    modelConcept = conceptsByQname[paramParts[0]]
                    setArgForConceptProperty(param, modelConcept, paramParts[1:])
            except Exception as _ex:
                raise # pass
        if set(paramNames) - _DICT_SET(fmtArgs.keys()):
            for arg in modelObjectArgs:
                # Pargmeter may be a ModelFact, or a name of a concept (such as a dimension)
                if isinstance(arg, ModelObject):
                    arg.modelXbrl.error("dqcErrorLog:unresolvedParameters",
                                        _("The error message %(messageCode)s has unresolved named parameters: %(unresolvedParameters)s"),
                                        modelObject=modelObjectArgs, messageCode=messageCode,
                                        unresolvedParameters=', '.join(sorted(set(paramNames) - _DICT_SET(fmtArgs.keys()))))
                    break
            for missingParam in set(paramNames) - _DICT_SET(fmtArgs.keys()):
                fmtArgs[missingParam] = "unavailable"
        return msg
    return None       

def loggingCommandLineXbrlRun(cntlr, options, modelXbrl):
    global labelrole, lang
    labelrole=options.labelRole
    lang=options.labelLang
                
__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Logging - DQC Parameters',
    'version': '1.0',
    'description': '''DQC tests logging messages: adds parameter values from infrastructurally 
provided logging arguments.  Usually uses modelObject arguments to supply parameters found
in message text that can be derived from the arguments.''',
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2014 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrCmdLine.Xbrl.Run': loggingCommandLineXbrlRun,
    'Logging.Message.Parameters': loggingMessageParameters
}