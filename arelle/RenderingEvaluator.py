'''
Created on Jun 6, 2012

@author: Mark V Systems Limited
(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''
from arelle import (XPathContext, XbrlConst)
from arelle.ModelFormulaObject import (aspectModels, Aspect)
from arelle.ModelRenderingObject import (ModelRuleAxis, ModelDimensionRelationshipAxis)
from arelle.ModelValue import (QName)

def init(modelXbrl):
    # setup modelXbrl for rendering evaluation

    # dimension defaults required in advance of validation
    from arelle import ValidateXbrlDimensions, ValidateFormula, ModelDocument
    ValidateXbrlDimensions.loadDimensionDefaults(modelXbrl)
    
    hasXbrlTables = False
    
    # validate table linkbase dimensions
    for baseSetKey in modelXbrl.baseSets.keys():
        arcrole, ELR, linkqname, arcqname = baseSetKey
        if ELR and linkqname and arcqname and XbrlConst.isTableRenderingArcrole(arcrole):
            ValidateFormula.checkBaseSet(modelXbrl, arcrole, ELR, modelXbrl.relationshipSet(arcrole,ELR,linkqname,arcqname))
            if arcrole == XbrlConst.tableAxis:
                hasXbrlTables = True

    # provide context for view
    if modelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE:
        instance = None # use instance of the entry pont
    else: # need dummy instance
        instance = ModelDocument.create(modelXbrl, ModelDocument.Type.INSTANCE, 
                                        "dummy.xml",  # fake URI and fake schemaRef 
                                        ("http://www.xbrl.org/2003/xbrl-instance-2003-12-31.xsd",))
        
    if hasXbrlTables:
        # formula processor is needed for 2011 XBRL tables but not for 2010 Eurofiling tables
        modelXbrl.rendrCntx = XPathContext.create(modelXbrl, instance)
        
        modelXbrl.profileStat(None)
        
        # setup fresh parameters from formula optoins
        modelXbrl.parameters = modelXbrl.modelManager.formulaOptions.typedParameters()
        
        # validate parameters and custom function signatures
        ValidateFormula.validate(modelXbrl, xpathContext=modelXbrl.rendrCntx, parametersOnly=True, statusMsg=_("compiling rendering tables"))
        
        # compile and validate tables
        for modelTable in modelXbrl.modelRenderingTables:
            modelTable.fromInstanceQnames = None # required if referred to by variables scope chaining
            modelTable.compile()

            # check aspectModel
            if modelTable.aspectModel not in ("non-dimensional", "dimensional"):
                modelXbrl.error("xbrlte:unknownAspectModel",
                    _("Table %(xlinkLabel)s, aspect model %(aspectModel)s not recognized"),
                    modelObject=modelTable, xlinkLabel=modelTable.xlinkLabel, aspectModel=modelTable.aspectModel)
            else:
                modelTable.priorAspectAxisDisposition = {}
                # check ordinate aspects against aspectModel
                oppositeAspectModel = (_DICT_SET({'dimensional','non-dimensional'}) - _DICT_SET({modelTable.aspectModel})).pop()
                uncoverableAspects = aspectModels[oppositeAspectModel] - aspectModels[modelTable.aspectModel]
                for tblAxisRel in modelXbrl.relationshipSet(XbrlConst.tableAxis).fromModelObject(modelTable):
                    checkAxisAspectModel(modelXbrl, modelTable, tblAxisRel, uncoverableAspects)
                del modelTable.priorAspectAxisDisposition
        # compile messages
        for msgArcrole in (XbrlConst.tableAxisMessage, XbrlConst.tableAxisSelectionMessage):
            for msgRel in modelXbrl.relationshipSet(msgArcrole).modelRelationships:
                ValidateFormula.compileMessage(modelXbrl, msgRel.toModelObject)
    
        modelXbrl.profileStat(_("compileTables"))

def checkAxisAspectModel(modelXbrl, modelTable, tblAxisRel, uncoverableAspects):
    tblAxis = tblAxisRel.toModelObject
    tblAxisDisposition = tblAxisRel.axisDisposition
    hasCoveredAspect = False
    for aspect in tblAxis.aspectsCovered():
        if (aspect in uncoverableAspects or
            (isinstance(aspect, QName) and modelTable.aspectModel == 'non-dimensional')):
            modelXbrl.error("xbrlte:axisAspectModelMismatch",
                _("%(axis)s ordinate %(xlinkLabel)s, aspect model %(aspectModel)s, aspect %(aspect)s not allowed"),
                modelObject=modelTable, axis=tblAxis.localName, xlinkLabel=tblAxis.xlinkLabel, aspectModel=modelTable.aspectModel,
                aspect=str(aspect) if isinstance(aspect,QName) else Aspect.label[aspect])
        hasCoveredAspect = True
        if aspect in modelTable.priorAspectAxisDisposition:
            if tblAxisDisposition != modelTable.priorAspectAxisDisposition[aspect]:
                modelXbrl.error("xbrlte:axisAspectClash",
                    _("%(axis)s ordinate %(xlinkLabel)s, aspect %(aspect)s defined on axes of disposition %(axisDisposition)s and %(otherAxisDisposition)s"),
                    modelObject=modelTable, axis=tblAxis.localName, xlinkLabel=tblAxis.xlinkLabel, 
                    axisDisposition=tblAxisDisposition, axisDisposition2=modelTable.priorAspectAxisDisposition[aspect],
                    aspect=str(aspect) if isinstance(aspect,QName) else Aspect.label[aspect])
        else:
            modelTable.priorAspectAxisDisposition[aspect] = tblAxisDisposition
    if isinstance(tblAxis, ModelDimensionRelationshipAxis):
        hasCoveredAspect = True
        if modelTable.aspectModel == 'non-dimensional':
            modelXbrl.error("xbrlte:axisAspectModelMismatch",
                _("DimensionRelationship axis %(xlinkLabel)s can't be used in non-dimensional aspect model"),
                modelObject=(modelTable,tblAxis), xlinkLabel=tblAxis.xlinkLabel)
    axisOrdinateHasChild = False
    for axisSubtreeRel in modelXbrl.relationshipSet(XbrlConst.tableAxisSubtree).fromModelObject(tblAxis):
        checkAxisAspectModel(modelXbrl, modelTable, axisSubtreeRel, uncoverableAspects)
        axisOrdinateHasChild = True
    if not axisOrdinateHasChild and not hasCoveredAspect:
        modelXbrl.error("xbrlte:aspectValueNotDefinedByOrdinate",
            _("%(axis)s ordinate %(xlinkLabel)s does not define an aspect"),
            modelObject=(modelTable,tblAxis), xlinkLabel=tblAxis.xlinkLabel)
        
