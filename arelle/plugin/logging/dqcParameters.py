'''
See COPYRIGHT.md for copyright information.
'''
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelObject import ModelObject
from arelle.PythonUtil import flattenSequence
from arelle.Version import authorLabel, copyrightLabel
from arelle.XmlUtil import xmlstring, descendantAttr
from arelle import XbrlConst, XmlUtil
import regex as re
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

def loggingMessageParameters(messageCode, msgIn, modelObjectArgs, fmtArgs, *args, **kwargs):
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
        missingQnamedArguments = set()
        qnameFirstOrdinalPosition = {}  # for qnamed facts multiply in sequence (to insert on 2nd occurance in ordinal position)
        for arg in flattenSequence(modelObjectArgs):
            # Pargmeter may be a ModelFact, or a name of a concept (such as a dimension)
            if isinstance(arg, ModelFact):
                _strQName = str(arg.qname)
                if _strQName in qnamedReferences:
                    if _strQName not in factsByQname: # if twice in args, let one be an ordinal fact
                        factsByQname[_strQName].append(arg)
                        qnameFirstOrdinalPosition[_strQName] = len(factsArray)
                    elif arg not in factsArray: # if twice in args, insert first occurence in ordinal position
                        factsArray.insert(qnameFirstOrdinalPosition[_strQName], arg)
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
                                propVal = "{} to {}".format(XmlUtil.dateunionValue(cntx.startDatetime),
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
            fmtArgs[param] = propVal

        def setArgForConceptProperty(param, modelConceptOrQname, propertyNameParts):
            propVal = None
            property = propertyNameParts[0]
            if property == "label":
                if isinstance(modelConceptOrQname, ModelConcept):
                    propVal = modelConceptOrQname.label(labelrole,
                                                        lang=lang,
                                                        linkroleHint=XbrlConst.defaultLinkRole)
                elif isinstance(modelConceptOrQname, str):
                    propVal = modelConceptOrQname
            elif property == "name":
                if isinstance(modelConceptOrQname, ModelConcept):
                    propVal = str(modelConceptOrQname.qname)
                elif isinstance(modelConceptOrQname, str):
                    propVal = modelConceptOrQname
            elif property == "localName":
                if isinstance(modelConcept, ModelConcept):
                    propVal = modelConcept.qname.localName
                elif isinstance(modelConcept, str):
                    propVal = modelConcept.rpartition(':')[2]
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
                    else:
                        missingQnamedArguments.add(paramParts[0])
                elif len(paramParts) >= 2:
                    modelConcept = conceptsByQname.get(paramParts[0], paramParts[0]) # if no model concept pass in the qname
                    setArgForConceptProperty(param, modelConcept, paramParts[1:])
            except Exception as _ex:
                raise # pass
        if missingQnamedArguments:
            for arg in modelObjectArgs:
                # Pargmeter may be a ModelFact, or a name of a concept (such as a dimension)
                if isinstance(arg, ModelObject):
                    arg.modelXbrl.error("dqcErrorLog:unresolvedParameters",
                                        _("The error message %(messageCode)s has unresolved named parameters: %(unresolvedParameters)s"),
                                        modelObject=modelObjectArgs, messageCode=messageCode,
                                        unresolvedParameters=', '.join(sorted(missingQnamedArguments)))
                    break
            for missingArgument in missingQnamedArguments:
                fmtArgs[missingArgument] = "unavailable"
        return msg
    return None

def loggingCommandLineXbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    global labelrole, lang
    labelrole=options.labelRole
    lang=options.labelLang

def testcaseVariationExpectedSeverity(modelTestcaseVariation, *args, **kwargs):
    _severity = descendantAttr(modelTestcaseVariation, None, "error", "severity")
    if _severity is not None:
        return _severity.upper()
    return None

def testcaseVariationExpectedCount(modelTestcaseVariation, *args, **kwargs):
    try:
        return int(descendantAttr(modelTestcaseVariation, None, "error", "count"))
    except (ValueError, TypeError):
        pass
    return None

__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Logging - DQC Parameters',
    'version': '1.0',
    'description': '''DQC tests logging messages: adds parameter values from infrastructurally
provided logging arguments.  Usually uses modelObject arguments to supply parameters found
in message text that can be derived from the arguments.''',
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrCmdLine.Xbrl.Run': loggingCommandLineXbrlRun,
    'Logging.Message.Parameters': loggingMessageParameters,
    'ModelTestcaseVariation.ExpectedSeverity': testcaseVariationExpectedSeverity,
    'ModelTestcaseVariation.ExpectedCount': testcaseVariationExpectedCount
}
