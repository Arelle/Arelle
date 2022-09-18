'''
Created on Sept 29, 2014

@author: Mark V Systems Limited
(c) Copyright 2014 Mark V Systems Limited, All rights reserved.
'''
from collections import defaultdict
import datetime, re
from arelle import XmlUtil, XbrlConst, XPathParser, XPathContext
from arelle.ModelValue import qname, QName, dateTime
from arelle.ModelObject import ModelObject
from arelle.ModelDtsObject import ModelResource
from arelle.ModelInstanceObject import ModelFact
from arelle.XbrlUtil import typedValue

CDR_LINKBASE = "http://www.ffiec.gov/2003/linkbase"
CONCEPT_FORMULA_ARCROLE = "http://www.ffiec.gov/2003/arcrole/concept-formula"

class CdrFormula(ModelResource):
    def init(self, modelDocument):
        super(CdrFormula, self).init(modelDocument)
        
    @property
    def select(self):
        return self.get("select")
        
class CdrContextResource(ModelResource):
    def init(self, modelDocument):
        super(CdrContextResource, self).init(modelDocument)
        if not hasattr(modelDocument, "cdrContextResources"):
            modelDocument.cdrContextResources = {}
        modelDocument.cdrContextResources[self.id] = self
        
class CdrAbsoluteContext(ModelResource):
    def init(self, modelDocument):
        super(CdrAbsoluteContext, self).init(modelDocument)
        
    def instantConstraint(self):
        elt = XmlUtil.descendant(self, CDR_LINKBASE, "instantConstraint")
        if elt is not None:
            return dateTime("{}-{}-{}".format(elt.get('year'),elt.get('month').elt.get('day')))
        return None
    
class CdrRelativeContext(ModelResource):
    def init(self, modelDocument):
        super(CdrRelativeContext, self).init(modelDocument)
        
    def instantBase(self):
        elt = XmlUtil.descendant(self, CDR_LINKBASE, "instantOffset")
        if elt is not None:
            return elt.get("base")
        return None
    
    def instantOffset(self):
        elt = XmlUtil.descendant(self, CDR_LINKBASE, "instantOffset")
        if elt is not None:
            return elt.get("offset")
        return None
    
        