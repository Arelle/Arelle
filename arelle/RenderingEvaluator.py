'''
Created on Jun 6, 2012

@author: Mark V Systems Limited
(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''
from arelle import (XPathContext, XbrlConst, XmlUtil, XbrlUtil, XmlValidate)
from arelle.FunctionXs import xsString
from arelle.ModelObject import ModelObject
from arelle.ModelFormulaObject import (aspectModels, Aspect, aspectModelAspect,
                                 ModelFormula, ModelTuple, ModelExistenceAssertion,
                                 ModelValueAssertion,
                                 ModelFactVariable, ModelGeneralVariable, ModelVariable,
                                 ModelParameter, ModelFilter, ModelAspectCover, ModelBooleanFilter,
                                 ModelMessage)
from arelle.ModelValue import (QName)
import datetime
from collections import defaultdict

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
        ValidateFormula.validate(modelXbrl, xpathContext=modelXbrl.rendrCntx, parametersOnly=True, statusMsg=_("compiling rendering tables"))
            
        for msgRel in modelXbrl.relationshipSet(XbrlConst.tableAxisMessage).modelRelationships:
            ValidateFormula.compileMessage(modelXbrl, msgRel.toModelObject)
    
        for modelTable in modelXbrl.modelRenderingTables:
            modelTable.fromInstanceQnames = None # required if referred to by variables scope chaining
            modelTable.compile()
        modelXbrl.profileStat(_("compileTables"))

