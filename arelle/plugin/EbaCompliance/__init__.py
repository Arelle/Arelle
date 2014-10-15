'''
Improve the EBA compliance of the currently loaded facts.

For the time being, there are only two improvements that are implemented:
1. The filing indicators are regenerated using a fixed context with ID "c".
2. The decimals attribute is computed according to the actually supplied value.

(c) Copyright 2014 Acsone S. A., All rights reserved.
'''

from arelle import ModelDocument, XmlValidate, ModelXbrl, XbrlConst
from arelle.ModelValue import qname
from arelle.DialogNewFactItem import getNewFactItemOptions
from lxml import etree
from arelle.ViewWinRenderedGrid import ViewRenderedGrid
from .ViewWalkerRenderedGrid import viewWalkerRenderedGrid
from .FactWalkingAction import FactWalkingAction

EbaURL = "www.eba.europa.eu/xbrl"
qnFindFilingIndicators = qname("{http://www.eurofiling.info/xbrl/ext/filing-indicators}find:fIndicators")
qnFindFilingIndicator = qname("{http://www.eurofiling.info/xbrl/ext/filing-indicators}find:filingIndicator")
qnPercentItemType = qname("{http://www.xbrl.org/dtr/type/numeric}num:percentItemType")

def improveEbaCompliance(dts, cntlr, lang="en"):
    ':type dts: ModelXbrl'
    try:
        if not isEbaInstance(dts):
            dts.modelManager.showStatus(_("Only applicable to EBA instances"), 5000)
            return
        dts.modelManager.showStatus(_("Improving the EBA compliance"))
        factWalkingAction = FactWalkingAction(dts)
        newFactItemOptions = getFactItemOptions(dts, cntlr)
        if not newFactItemOptions:
            return
        from arelle import XbrlConst
        from arelle.ModelRenderingObject import ModelEuTable, ModelTable
        
        class nonTkBooleanVar():
            def __init__(self, value=True):
                self.value = value
            def set(self, value):
                self.value = value
            def get(self):
                return self.value
        class View():
            def __init__(self, tableOrELR, ignoreDimValidity, xAxisChildrenFirst, yAxisChildrenFirst):
                self.tblELR = tableOrELR
                # context menu boolean vars (non-tkinter boolean)
                self.ignoreDimValidity = nonTkBooleanVar(value=ignoreDimValidity)
                self.xAxisChildrenFirst = nonTkBooleanVar(value=xAxisChildrenFirst)
                self.yAxisChildrenFirst = nonTkBooleanVar(value=yAxisChildrenFirst)

        groupTableRels = dts.modelXbrl.relationshipSet(XbrlConst.euGroupTable)
        modelTables = []


        def viewTable(modelTable, factWalkingAction):
            if isinstance(modelTable, (ModelEuTable, ModelTable)):
                # status
                dts.modelManager.cntlr.addToLog("improving: " + modelTable.id)

                viewWalkerRenderedGrid(dts,
                                       factWalkingAction,
                                       lang=lang,
                                       viewTblELR=modelTable,
                                       sourceView=View(modelTable, False, False, True))

            for rel in groupTableRels.fromModelObject(modelTable):
                viewTable(rel.toModelObject, factWalkingAction)

    
        for rootConcept in groupTableRels.rootConcepts:
            sourceline = 0
            for rel in dts.modelXbrl.relationshipSet(XbrlConst.euGroupTable).fromModelObject(rootConcept):
                sourceline = rel.sourceline
                break
            modelTables.append((rootConcept, sourceline))
            
        for modelTable, order in sorted(modelTables, key=lambda x: x[1]):  # @UnusedVariable
            viewTable(modelTable, factWalkingAction)

        createOrReplaceFilingIndicators(dts, factWalkingAction.allFilingIndicatorCodes, newFactItemOptions)
        dts.modelManager.showStatus(_("EBA compliance improved"), 5000)
    except Exception as ex:
        dts.error("exception",
            _("EBA compliance improvements generation exception: %(error)s"), error=ex,
            modelXbrl=dts,
            exc_info=True)

def isEbaInstance(dts):
    if dts.modelDocument.type == ModelDocument.Type.INSTANCE:
        doc = dts.modelDocument.xmlDocument
        for el in doc.iter("*"):
            if isinstance(el, etree._Element):
                for _, NS in _DICT_SET(el.nsmap.items()):  # @UndefinedVariable
                    if EbaURL in NS:
                        return True;
        return False
    else:
        return False

def createOrReplaceFilingIndicators(dts, allFilingIndicatorCodes, newFactItemOptions):
    filingIndicatorsElements = dts.factsByQname(qnFindFilingIndicators, set())
    if len(filingIndicatorsElements)>0:
        filingIndicatorsElement = filingIndicatorsElements.pop()
    else:
        filingIndicatorsElement = None
    if filingIndicatorsElement is not None:
        removeUselessFilingIndicatorsInModel(dts)
        parent = filingIndicatorsElement.getparent()
        parent.remove(filingIndicatorsElement)
        XmlValidate.validate(dts, parent) # must validate after content is deleted
    if len(allFilingIndicatorCodes)>0:
        filingIndicatorsElement = createFilingIndicatorsElement(dts, newFactItemOptions)
        for filingIndicatorCode in allFilingIndicatorCodes:
            dts.createFact(qnFindFilingIndicator, 
                           parent=filingIndicatorsElement,
                           attributes={"contextRef": "c"}, 
                           text=filingIndicatorCode,
                           validate=False)
        XmlValidate.validate(dts, filingIndicatorsElement) # must validate after content is created

def removeUselessFilingIndicatorsInModel(dts):
    ''':type dts: ModelXbrl'''
    # First remove the context
    context = dts.contexts["c"]
    parent = context.getparent()
    parent.remove(context)
    del dts.contexts["c"]
    # Remove the elements from the facts and factsInInstance data structure
    filingIndicatorsElements = dts.factsByQname(qnFindFilingIndicators, set())
    for fact in filingIndicatorsElements:
        dts.factsInInstance.remove(fact)
        dts.facts.remove(fact)
        if fact in dts.undefinedFacts:
            dts.undefinedFacts.remove(fact)
    filingIndicatorElements = dts.factsByQname(qnFindFilingIndicator, set())
    for fact in filingIndicatorElements:
        dts.factsInInstance.remove(fact)
        # non-top-level elements are not in 'facts'

def createFilingIndicatorsElement(dts, newFactItemOptions):
    dts.createContext(newFactItemOptions.entityIdentScheme,
        newFactItemOptions.entityIdentValue,
        'instant',
        None,
        newFactItemOptions.endDateDate,
        None, # no dimensional validity checking (like formula does)
        {}, [], [],
        id='c',
        afterSibling=ModelXbrl.AUTO_LOCATE_ELEMENT)
    filingIndicatorsTuple = dts.createFact(qnFindFilingIndicators,
                                           validate=False)
    return filingIndicatorsTuple

def getFactItemOptions(dts, cntlr):
    newFactItemOptions = None
    for view in dts.views:
        if isinstance(view, ViewRenderedGrid):
            if (not view.newFactItemOptions.entityIdentScheme or  # not initialized yet
            not view.newFactItemOptions.entityIdentValue or
            not view.newFactItemOptions.startDateDate or not view.newFactItemOptions.endDateDate):
                if not getNewFactItemOptions(cntlr, view.newFactItemOptions):
                    return None
            newFactItemOptions = view.newFactItemOptions
            break
    return newFactItemOptions

def improveEbaComplianceMenuExtender(cntlr, menu):
    # Extend menu with an item for the improve compliance menu
    menu.add_command(label=_("Improve EBA compliance"), 
                     underline=0, 
                     command=lambda: improveEbaComplianceMenuCommand(cntlr) )

def improveEbaComplianceMenuCommand(cntlr):
    # improve EBA compliance menu item has been invoked
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
        cntlr.addToLog("No DTS loaded.")
        return
    dts = cntlr.modelManager.modelXbrl
    getFactItemOptions(dts, cntlr)
    import threading
    thread = threading.Thread(target=lambda 
                                  _dts=dts: 
                                        improveEbaCompliance(_dts, cntlr))
    thread.daemon = True
    thread.start()

def decimalsComputer(locale, value, concept, defaultDecimals):
    '''
    :type locale: dict
    :type value: string
    :type concept: ModelConcept
    :type defaultDecimals: str
    :rtype (boolean, str)
    '''
    if len(defaultDecimals)==0:
        defaultDecimals = 'INF'
    if concept.isNumeric and defaultDecimals != 'INF':
        decimalPoint = locale["decimal_point"]
        explodedNumber = value.split(decimalPoint)
        integerPart = ""
        if len(explodedNumber)==2:
            # If there is a decimal point and if there are decimals after that point,
            # count the decimals!
            integerPart, fractionalPart = explodedNumber
            return (True, str(len(fractionalPart)))
        else:
            integerPart = value
        #Count the trailing zeros in the part before the decimal point
        if integerPart == '0':
            return (True, '0')
        else:
            for index, char in enumerate(reversed(integerPart)):
                if char != '0':
                    break;
            return (True, ('0' if index==0 or (index+1==len(integerPart) and integerPart[0]=='0') else "-"+str(index)))
    else:
        return (False, defaultDecimals)

def ebaDecimals(locale, value, concept, defaultDecimals):
    '''
    :type locale: dict
    :type value: string
    :type concept: ModelConcept
    :type defaultDecimals: str
    :rtype (boolean, str)
    '''
    isPercent = concept.typeQname == qnPercentItemType
    isInteger = XbrlConst.isIntegerXsdType(concept.type.baseXsdType)
    isMonetary = concept.isMonetary
    decimalsFound, decimals = decimalsComputer(locale, value, concept, defaultDecimals)
    if not(decimalsFound) or decimals == 'INF':
        return (decimalsFound, decimals)
    else:
        # the default values are for non-monetary items
        lowerBound = -20
        upperBound = 20
        decimalsAsInteger = int(decimals)
        if isMonetary:
            lowerBound = -3
        elif isInteger:
            lowerBound = upperBound = 0
        elif isPercent: # percent values
            lowerBound = 4
            upperBound = 20
        if decimalsAsInteger<lowerBound:
            decimals = str(lowerBound)
            decimalsAsInteger = lowerBound
        if decimalsAsInteger>upperBound:
            decimals = 'INF' # approximation
            decimalsAsInteger = upperBound
        return (decimalsFound, decimals)

__pluginInfo__ = {
    'name': 'Improve EBA compliance of XBRL instances',
    'version': '1.1',
    'description': "This module regenerates EBA filing indicators if needed and supplies a custom method for computing the decimals attribute according to the actually supplied value.",
    'license': 'Apache-2',
    'author': 'Gregorio Mongelli (Acsone S. A.)',
    'copyright': '(c) Copyright 2014 Acsone S. A.',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': improveEbaComplianceMenuExtender,
    'CntlrWinMain.Rendering.ComputeDecimals': ebaDecimals
}
