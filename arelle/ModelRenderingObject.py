'''
Created on Mar 7, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import (XmlUtil, XbrlConst)
from arelle.ModelDtsObject import ModelResource
from arelle.ModelValue import qname

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

# 2010 EU Table linkbase
class ModelAxisCoord(ModelRenderingResource):
    def __init__(self, modelDocument):
        super().__init__(modelDocument)
        
    @property
    def abstract(self):
        return self.get("abstract") if self.get("abstract") else 'false'
    
    @property
    def primaryItemQname(self):
        priItem = XmlUtil.childAttr(self, XbrlConst.euRend, "primaryItem", "name")
        if priItem is not None:
            return self.prefixedNameQname(priItem)
        return None
    
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

# 2011 Table linkbase
class ModelExplicitAxisMember(ModelRenderingResource):
    def __init__(self, modelDocument):
        super().__init__(modelDocument)
        
    @property
    def abstract(self):
        if self.localName == "explicitAxis":
            return 'false'
        elif self.get("presentation") == 'false':
            return 'true'
        return 'false'
    
    @property
    def primaryItemQname(self):
        conceptRule = XmlUtil.child(self, XbrlConst.formula, "concept")
        if conceptRule is not None:
            qnameElt = XmlUtil.child(conceptRule, XbrlConst.formula, "qname")
            if qnameElt is not None:
                return qname(qnameElt, qnameElt.text)
        return None
    
    @property
    def explicitDims(self):
        return {(self.prefixedNameQname(e.get("dimension")),
                 self.prefixedNameQname(XmlUtil.text(qn)))
                for e in XmlUtil.children(self, XbrlConst.formula, "explicitDimension")
                for m in XmlUtil.children(e, XbrlConst.formula, "member")
                for qn in XmlUtil.children(m, XbrlConst.formula, "qname")}
    
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
        return ("explicitAxisMember[{0}]{1})".format(self.objectId(),self.propertyView))

from arelle.ModelObjectFactory import elementSubstitutionModelClass
elementSubstitutionModelClass.update((
    (XbrlConst.qnEuTable, ModelTable),
    (XbrlConst.qnTableTable, ModelTable),
    (XbrlConst.qnEuAxisCoord, ModelAxisCoord),
    (XbrlConst.qnTableExplicitAxis, ModelExplicitAxisMember),
    (XbrlConst.qnTableExplicitAxisMember, ModelExplicitAxisMember),
     ))