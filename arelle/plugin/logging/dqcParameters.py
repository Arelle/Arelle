'''
Created on Dec 12, 2013

@author: Mark V Systems Limited
(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelInstanceObject import ModelFact
from arelle.XmlUtil import xmlstring
from arelle import XbrlConst, XmlUtil
import re
from collections import defaultdict

labelrole = None
lang = None

altParametersPattern = re.compile(r"\$\{([\w.]+)\}")
parametersPattern = re.compile(r"%\(([\w.]+)\)")
factNumberPattern = re.compile(r"fact(\d+)")

def measureFormat(measure):
    if measure.namespaceURI in (XbrlConst.iso4217, XbrlConst.xbrli):
        return measure.localName
    return str(measure)  # qname str

def loggingMessageParameters(messageCode, msgIn, modelObjectArgs, fmtArgs):
    if messageCode.startswith("DQC"):
        # change ${...} in message into %(...)s
        msg = altParametersPattern.sub(r"%(\1)s", msgIn)
        
        # find qnamed fact references
        qnamedFactReferences = set()
        for param in parametersPattern.findall(msg):
            paramParts = param.split('.')
            if len(paramParts) > 1 and not factNumberPattern.match(paramParts[0]):
                qnamedFactReferences.add(paramParts[0])
        factsArray = []
        factsByQname = defaultdict(list)  # list of facts with the qname
        for arg in modelObjectArgs:
            # Pargmeter may be a ModelFact, or any other ModelObject
            if isinstance(arg, ModelFact):
                if str(arg.qname) in qnamedFactReferences:
                    factsByQname[str(arg.qname)].append(arg)
                else:
                    factsArray.append(arg)

 
        def setArgForFactProperty(param, modelFact, propertyNameParts):
            propVal = None
            property = propertyNameParts[0]
            if property == "value":
                propVal = modelFact.value
            elif property == "decimals":
                propVal = modelFact.decimals
            elif property == "label" and modelFact.concept is not None:
                propVal = modelFact.concept.label(labelrole,
                                                  lang=lang,
                                                  linkroleHint=XbrlConst.defaultLinkRole)
            else:
                cntx = modelFact.context
                unit = modelFact.unit
                if cntx is not None:
                    if property == "period":
                        if cntx.isForeverPeriod:
                            propVal = "forever"
                        elif cntx.isInstantPeriod:
                            propVal = XmlUtil.dateunionValue(cntx.instantDatetime, subtractOneDay=True)
                        else:
                            propVal = "{} - {}".format(XmlUtil.dateunionValue(cntx.startDatetime),
                                                       XmlUtil.dateunionValue(cntx.endDatetime, subtractOneDay=True))
                    elif property == "dimensions":
                        propVal = "\n".join("{} = {}".format(d.dimensionQname, 
                                                            d.memberQname if d.isExplicit else
                                                            XmlUtil.xmlstring( XmlUtil.child(d), stripXmlns=True, prettyPrint=True ))
                                            for d in cntx.qnameDims.values())
                if unit is not None and propVal is None and property == "unit":
                    measures = unit.measures
                    if measures[1]:
                        propVal = 'mul {}\ndiv {} '.format(
                                ', '.join(measureFormat(m) for m in measures[0]),
                                ', '.join(measureFormat(m) for m in measures[1]))
                    else:
                        propVal = ', '.join(measureFormat(m) for m in measures[0])
            if propVal is not None:
                fmtArgs[param] = propVal
                
        # parse parameter names out of msg
        for param in parametersPattern.findall(msg):
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
                        modelFact = factsByQname[paramParts[0]]
                        setArgForFactProperty(param, modelFact, paramParts[2:])
            except Exception:
                pass
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
