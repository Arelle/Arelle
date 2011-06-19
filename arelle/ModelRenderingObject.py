'''
Created on Mar 7, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import (XmlUtil, XbrlConst)
from arelle.ModelDtsObject import ModelResource

class ModelRenderingResource(ModelResource):
    def __init__(self, modelDocument):
        super().__init__(modelDocument)
        

class ModelTable(ModelRenderingResource):
    def __init__(self, modelDocument):
        super().__init__(modelDocument)
        
    @property
    def propertyView(self):
        return (("id", self.id),
                ("label", self.xlinkLabel))
        
    def __repr__(self):
        return ("table[{0}]{1})".format(self.objectId(),self.propertyView))

class ModelAxisCoord(ModelRenderingResource):
    def __init__(self, modelDocument):
        super().__init__(modelDocument)
        
    @property
    def abstract(self):
        return self.get("abstract") if self.get("abstract") else 'false'
    
    @property
    def primaryItemQname(self):
        priItem = XmlUtil.childAttr(self, XbrlConst.euRend, "primaryItem", "name")
        return self.prefixedNameQname(priItem) if priItem else None
    
    @property
    def explicitDims(self):
        return {(self.prefixedNameQname(e.get("dimension")),
                 self.prefixedNameQname(e.get("value")))
                for e in XmlUtil.children(self, XbrlConst.euRend, "explicitDimCoord")}
    
    @property
    def instant(self):
        return XmlUtil.childAttr(self, XbrlConst.euRend, "timeReference","instant")
    
    @property
    def propertyView(self):
        explicitDims = self.explicitDims
        return (("id", self.id),
                ("xlink:label", self.xlinkLabel),
                ("header label", self.genLabel()),
                ("header doc", self.genLabel(role="http://www.xbrl.org/2008/role/documentation")),
                ("header code", self.genLabel(role="http://www.eurofiling.info/role/2010/coordinate-code")),
                ("primary item", self.primaryItemQname),
                ("dimensions", "({0})".format(len(explicitDims)),
                  tuple((str(dim),str(mem)) for dim,mem in sorted(explicitDims)))
                  if explicitDims else (),
                ("abstract", self.abstract),
                ("instant", self.instant))
        
    def __repr__(self):
        return ("axisCoord[{0}]{1})".format(self.objectId(),self.propertyView))

from arelle.ModelObjectFactory import elementSubstitutionModelClass
elementSubstitutionModelClass.update((
    (XbrlConst.qnEuTable, ModelTable),
    (XbrlConst.qnEuAxisCoord, ModelAxisCoord),
     ))