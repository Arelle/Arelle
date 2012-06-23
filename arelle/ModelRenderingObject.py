'''
Created on Mar 7, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import XmlUtil, XbrlConst, XPathParser, Locale, XPathContext
from arelle.ModelDtsObject import ModelResource
from arelle.ModelValue import qname, QName
from arelle.ModelFormulaObject import (Trace, ModelFormulaResource, ModelFormulaRules, ModelConceptName,
                                       Aspect)

def ordObjects(ords):
    return [(ord.axisObject if isinstance(ord, OrdinateContext) else ord) for ord in ords]

# table linkbase ordinate context for rendering
class OrdinateContext:
    def __init__(self, parentOrdinateContext, axisObject):
        self.parentOrdinateContext = parentOrdinateContext
        self.axisObject = axisObject
        self.variables = {}
        self.aspects = {}
        self.subOrdinateContexts = []
        
    @property
    def isAbstract(self):
        try:
            return self.axisObject.abstract == "true"
        except AttributeError: # axis may never be abstract
            return False
        
    @property
    def cardinalityAndDepth(self):
        return self.axisObject.cardinalityAndDepth
    
    def hasAspect(self, aspect, inherit=True):
        return (aspect in self.aspects or 
                self.axisObject.hasAspect(aspect) or 
                (inherit and
                 self.parentOrdinateContext is not None and 
                 self.parentOrdinateContext.hasAspect(aspect)))
    
    def aspectValue(self, aspect, inherit=True, dims=None):
        if aspect == Aspect.DIMENSIONS:
            if dims is None: dims = set()
            if inherit and self.parentOrdinateContext is not None:
                dims |= self.parentOrdinateContext.aspectValue(aspect, dims=dims)
            if aspect in self.aspects:
                dims |= self.aspects[aspect]
            elif self.axisObject.hasAspect(aspect):
                dims |= set(self.axisObject.aspectValue(aspect) or {})
            if self.axisObject.hasAspect(Aspect.OMIT_DIMENSIONS):
                dims -= set(self.axisObject.aspectValue(Aspect.OMIT_DIMENSIONS))
            return dims
        if aspect in self.aspects:
            return self.aspects[aspect]
        elif self.axisObject.hasAspect(aspect):
            return self.axisObject.aspectValue(aspect)
        elif inherit and self.parentOrdinateContext is not None:
            return self.parentOrdinateContext.aspectValue(aspect)
        return None

    '''
    @property   
    def primaryItemQname(self):  # for compatibility with viewRelationsihps
        if Aspect.CONCEPT in self.aspects:
            return self.aspects[Aspect.CONCEPT]
        return self.axisObject.primaryItemQname
        
    @property
    def explicitDims(self):
        return self.axisObject.explicitDims
    '''
        
    def objectId(self, refId=""):
        return self.axisObject.objectId(refId)
        
    def header(self, role=None, lang=None):
        if role is None:
            # check for message before checking for genLabel
            msgsRelationshipSet = self.axisObject.modelXbrl.relationshipSet(XbrlConst.tableAxisMessage)
            if msgsRelationshipSet:
                msg = msgsRelationshipSet.label(self.axisObject, XbrlConst.standardMessage, lang, returnText=False)
                if msg is not None:
                    return self.evaluate(msg, msg.evaluate)
        return self.axisObject.genLabel(role=role, lang=lang)
    
    def evaluate(self, evalObject, evalMethod, xc=None):
        if xc is None: xc = self.axisObject.modelXbrl.rendrCntx
        removeVarQnames = []
        for qn, value in self.variables.items():
            if qn not in xc.inScopeVars:
                removeVarQnames.append(qn)
                xc.inScopeVars[qn] = value
        if self.parentOrdinateContext is not None:
            result = self.parentOrdinateContext.evaluate(evalObject, evalMethod, xc)
        else:
            try:
                result = evalMethod(xc)
            except XPathContext.XPathException as err:
                xc.modelXbrl.error(err.code,
                         _("%(element)s set %(xlinkLabel)s \nException: %(error)s"), 
                         modelObject=evalObject, element=evalObject.localName, 
                         xlinkLabel=evalObject.xlinkLabel, error=err.message)
                result = ''
        for qn in removeVarQnames:
            xc.inScopeVars.pop(qn)
        return result
        
    def __repr__(self):
        return ("ordinateContext[{0}]{1})".format(self.objectId(),self.axisObject))
        
# Root class for rendering is formula, to allow linked and nested compiled expressions

# 2010 EU Table linkbase
class ModelEuTable(ModelResource):
    def init(self, modelDocument):
        super(ModelEuTable, self).init(modelDocument)
        
    @property
    def aspectModel(self):
        return "dimensional"
        
    @property
    def propertyView(self):
        return (("id", self.id),
                ("label", self.xlinkLabel))
        
    def __repr__(self):
        return ("table[{0}]{1})".format(self.objectId(),self.propertyView))

class ModelEuAxisCoord(ModelResource):
    def init(self, modelDocument):
        super(ModelEuAxisCoord, self).init(modelDocument)
        
    @property
    def abstract(self):
        return self.get("abstract") if self.get("abstract") else 'false'
    
    @property
    def isAbstract(self):
        return self.abstract == "true"
    
    @property
    def parentChildOrder(self):
        return self.get("parentChildOrder")
    
    @property
    def parentOrdinateContext(self):
        try:
            return self._parentOrdinateContext
        except AttributeError:
            parentOrdinateContext = None
            for rel in self.modelXbrl.relationshipSet(XbrlConst.euAxisMember).toModelObject(self):
                parentOrdinateContext = rel.fromModelObject
                break
            self._parentOrdinateContext = parentOrdinateContext
            return parentOrdinateContext

    
    def hasAspect(self, aspect):
        if aspect == Aspect.CONCEPT:
            return XmlUtil.hasChild(self, XbrlConst.euRend, "primaryItem")
        elif aspect == Aspect.DIMENSIONS:
            return XmlUtil.hasChild(self, XbrlConst.euRend, "explicitDimCoord")
        elif aspect in (Aspect.PERIOD_TYPE, Aspect.INSTANT):
            return XmlUtil.hasChild(self, XbrlConst.euRend, "timeReference")
        elif isinstance(aspect, QName):
            for e in XmlUtil.children(self, XbrlConst.euRend, "explicitDimCoord"):
                if self.prefixedNameQname(e.get("dimension")) == aspect:
                    return True
        return False
    
    def aspectValue(self, aspect, inherit=False):
        if aspect == Aspect.DIMENSIONS:
            dims = set(self.prefixedNameQname(e.get("dimension"))
                       for e in XmlUtil.children(self, XbrlConst.euRend, "explicitDimCoord"))
            if inherit and self.parentOrdinateContext is not None:
                dims |= self.parentOrdinateContext.aspectValue(aspect, inherit)
            return dims
        if inherit and not self.hasAspect(aspect):
            if self.parentOrdinateContext is not None:
                return self.parentOrdinateContext.aspectValue(aspect, inherit)
            return None
        if aspect == Aspect.CONCEPT:
            priItem = XmlUtil.childAttr(self, XbrlConst.euRend, "primaryItem", "name")
            if priItem is not None:
                return self.prefixedNameQname(priItem)
            return None
        elif aspect == Aspect.PERIOD_TYPE:
            if XmlUtil.hasChild(self, XbrlConst.euRend, "timeReference"):
                return "instant"
        elif aspect == Aspect.INSTANT:
            return XmlUtil.datetimeValue(XmlUtil.childAttr(self, XbrlConst.euRend, "timeReference", "instant"), 
                                         addOneDay=True)
        elif isinstance(aspect, QName):
            for e in XmlUtil.children(self, XbrlConst.euRend, "explicitDimCoord"):
                if self.prefixedNameQname(e.get("dimension")) == aspect:
                    return self.prefixedNameQname(e.get("value"))
        return None

    '''
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
        return XmlUtil.datetimeValue(XmlUtil.childAttr(self, XbrlConst.euRend, "timeReference", "instant"), 
                                     addOneDay=True)
    '''

    @property
    def cardinalityAndDepth(self):
        return (1, 1)
        
    def header(self, role=None, lang=None):
        return self.genLabel(role=role, lang=lang)
    
    @property
    def propertyView(self):
        explicitDims = self.aspectValue(Aspect.DIMENSIONS, inherit=True)
        return (("id", self.id),
                ("xlink:label", self.xlinkLabel),
                ("header label", self.header()),
                ("header doc", self.header(role="http://www.xbrl.org/2008/role/documentation")),
                ("header code", self.header(role="http://www.eurofiling.info/role/2010/coordinate-code")),
                ("primary item", self.aspectValue(Aspect.CONCEPT, inherit=True)),
                ("dimensions", "({0})".format(len(explicitDims)),
                  tuple((str(dim),str(self.aspectValue(dim, inherit=True))) 
                        for dim in sorted(explicitDims)))
                  if explicitDims else (),
                ("abstract", self.abstract))
        
    def __repr__(self):
        return ("axisCoord[{0}]{1})".format(self.objectId(),self.propertyView))

# 2011 Table linkbase
class ModelTable(ModelFormulaResource):
    def init(self, modelDocument):
        super(ModelTable, self).init(modelDocument)
        self.modelXbrl.modelRenderingTables.add(self)
        self.modelXbrl.hasRenderingTables = True
        
    @property
    def aspectModel(self):
        return self.get("aspectModel")

    @property
    def descendantArcroles(self):        
        return (XbrlConst.tableFilter, XbrlConst.tableAxis)
                
    @property
    def filterRelationships(self):
        try:
            return self._filterRelationships
        except AttributeError:
            rels = [] # order so conceptName filter is first (if any) (may want more sorting in future)
            for rel in self.modelXbrl.relationshipSet(XbrlConst.tableFilter).fromModelObject(self):
                if isinstance(rel.toModelObject, ModelConceptName):
                    rels.insert(0, rel)  # put conceptName filters first
                else:
                    rels.append(rel)
            self._filterRelationships = rels
            return rels
    
    @property
    def propertyView(self):
        return (("id", self.id),
                ("label", self.xlinkLabel))
        
    def __repr__(self):
        return ("table[{0}]{1})".format(self.objectId(),self.propertyView))

class ModelOpenAxis(ModelFormulaResource):
    def init(self, modelDocument):
        super(ModelOpenAxis, self).init(modelDocument)
    
    @property
    def parentOrdinateContext(self):
        return None
                
    @property
    def descendantArcroles(self):        
        return (XbrlConst.tableAxisMessage,)
        
    def hasAspect(self, aspect):
        return False

    @property
    def variablename(self):
        """(str) -- name attribute"""
        return self.getStripped("name")

    @property
    def variableQname(self):
        """(QName) -- resolved name for an XPath bound result having a QName name attribute"""
        varName = self.variablename
        return qname(self, varName, noPrefixIsNoNamespace=True) if varName else None

    def aspectValue(self, aspect, inherit=True):
        if aspect == Aspect.DIMENSIONS:
            return []
        return None

    '''
    @property   
    def primaryItemQname(self):  # for compatibility with viewRelationsihps
        return None
        
    @property
    def explicitDims(self):
        return set()
    '''
    
    @property
    def cardinalityAndDepth(self):
        return (1, 
                1 if self.header() is not None else 0)
        
    def header(self, role=None, lang=None):
        return self.genLabel(role=role, lang=lang)
    
class ModelPredefinedAxis(ModelOpenAxis):
    def init(self, modelDocument):
        super(ModelPredefinedAxis, self).init(modelDocument)
        
    @property
    def abstract(self):
        if self.get("abstract") == 'true':
            return 'true'
        return 'false'
    
    @property
    def isAbstract(self):
        return self.abstract == 'true'
        
    @property
    def parentChildOrder(self):
        return self.get("parentChildOrder")

    @property
    def descendantArcroles(self):        
        return (XbrlConst.tableAxisSubtree, XbrlConst.tableAxisMessage)
    
    @property
    def ordinateView(self):        
        return XmlUtil.xmlstring(self, stripXmlns=True, prettyPrint=True)
    
class ModelRuleAxis(ModelFormulaRules, ModelPredefinedAxis):
    def init(self, modelDocument):
        super(ModelRuleAxis, self).init(modelDocument)
        
    def hasAspect(self, aspect, inherit=None):
        return self.hasRule(aspect)
    
    def aspectValue(self, aspect, inherit=None):
        return self.evaluateRule(self.modelXbrl.rendrCntx, aspect)
    
    '''
    @property   
    def primaryItemQname(self):
        return self.evaluateRule(self.modelXbrl.rendrCntx, Aspect.CONCEPT)

    @property
    def explicitDims(self):
        dimMemSet = set()
        dims = self.evaluateRule(self.modelXbrl.rendrCntx, Aspect.DIMENSIONS)
        if dims: # may be none if no dim aspects on this ruleAxis
            for dim in dims:
                mem = self.evaluateRule(self.modelXbrl.rendrCntx, dim)
                if mem: # may be none if dimension was omitted
                    dimMemSet.add( (dim, mem) )
        return dimMemSet
    
    @property
    def instant(self):
        periodType = self.evaluateRule(self.modelXbrl.rendrCntx, Aspect.PERIOD_TYPE)
        if periodType == "forever":
            return None
        return self.evaluateRule(self.modelXbrl.rendrCntx, 
                                 {"instant": Aspect.INSTANT,
                                  "duration": Aspect.END}[periodType])
    '''
    
    @property
    def cardinalityAndDepth(self):
        if self.aspectValues or self.aspectProgs or self.header() is not None:
            return (1, 1)
        else:
            return (0, 0)
   
    @property
    def propertyView(self):
        return (("id", self.id),
                ("xlink:label", self.xlinkLabel),
                ("header label", self.genLabel()),
                ("header doc", self.genLabel(role="http://www.xbrl.org/2008/role/documentation")),
                ("header code", self.genLabel(role="http://www.eurofiling.info/role/2010/coordinate-code")),
                ("abstract", self.abstract),
                ("ordinate", self.ordinateView))
        
    def __repr__(self):
        return ("explicitAxisMember[{0}]{1})".format(self.objectId(),self.propertyView))

class ModelCompositionAxis(ModelPredefinedAxis):
    def init(self, modelDocument):
        super(ModelCompositionAxis, self).init(modelDocument)
        
class ModelRelationshipAxis(ModelPredefinedAxis):
    def init(self, modelDocument):
        super(ModelRelationshipAxis, self).init(modelDocument)

    @property
    def conceptQname(self):
        name = self.getStripped("conceptname")
        return qname(self, name, noPrefixIsNoNamespace=True) if name else None
        
    @property
    def relationshipSourceQname(self):
        sourceQname = XmlUtil.child(self, XbrlConst.table, "relationshipSource")
        if sourceQname is not None:
            return qname( sourceQname, XmlUtil.text(sourceQname) )
        return None
    
    @property
    def linkrole(self):
        return XmlUtil.childText(self, XbrlConst.table, "linkrole")

    @property
    def axis(self):
        a = XmlUtil.childText(self, XbrlConst.table, "axis")
        if not a: a = 'child'  # would be an XML error
        return a
    
    @property
    def isOrSelfAxis(self):
        return self.axis.endswith('-or-self')

    @property
    def generations(self):
        try:
            return _INT( XmlUtil.childText(self, XbrlConst.table, "generations") )
        except (TypeError, ValueError):
            if self.axis in ('sibling', 'child', 'parent'): 
                return 1
            return 0

    @property
    def relationshipSourceQnameExpression(self):
        return XmlUtil.childText(self, XbrlConst.table, "relationshipSourceExpression")

    @property
    def linkroleExpression(self):
        return XmlUtil.childText(self, XbrlConst.table, "linkroleExpression")

    @property
    def axisExpression(self):
        return XmlUtil.childText(self, XbrlConst.table, "axisExpression")

    @property
    def generationsExpression(self):
        return XmlUtil.childText(self, XbrlConst.table, "generationsExpression")

    def compile(self):
        if not hasattr(self, "relationshipSourceQnameExpressionProg"):
            self.relationshipSourceQnameExpressionProg = XPathParser.parse(self, self.relationshipSourceQnameExpression, self, "relationshipSourceQnameExpressionProg", Trace.VARIABLE)
            self.linkroleExpressionProg = XPathParser.parse(self, self.linkroleExpression, self, "linkroleQnameExpressionProg", Trace.VARIABLE)
            self.axisExpressionProg = XPathParser.parse(self, self.axisExpression, self, "axisExpressionProg", Trace.VARIABLE)
            self.generationsExpressionProg = XPathParser.parse(self, self.generationsExpression, self, "generationsExpressionProg", Trace.VARIABLE)
            super(ModelRelationshipAxis, self).compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        if self.relationshipSourceQname and self.relationshipSourceQname != XbrlConst.qnXfiRoot:
            if varRefSet is None: varRefSet = set()
            varRefSet.add(self.relationshipSourceQname)
        return super(ModelRelationshipAxis, self).variableRefs(
                                                [p for p in (self.relationshipSourceQnameExpressionProg,
                                                             self.linkroleExpressionProg, self.axisExpressionProg,
                                                             self.generationsExpressionProg)
                                        if p], varRefSet)

    def evalRrelationshipSourceQname(self, xpCtx, fact):
        try:
            if self.relationshipSourceQname:
                return self.relationshipSourceQname
            return xpCtx.evaluateAtomicValue(self.relationshipSourceQnameExpressionProg, 'xs:QName', fact)
        except:
            return None
    
    def evalLinkrole(self, xpCtx, fact):
        try:
            if self.linkrole:
                return self.linkrole
            return xpCtx.evaluateAtomicValue(self.linkroleExpressionProg, 'xs:anyURI', fact)
        except:
            return None
    
    def evalAxis(self, xpCtx, fact):
        try:
            if self.axis:
                return self.axis
            return xpCtx.evaluateAtomicValue(self.axisExpressionProg, 'xs:token', fact)
        except:
            return None
    
    def evalGenerations(self, xpCtx, fact):
        try:
            if self.generations:
                return self.generations
            return xpCtx.evaluateAtomicValue(self.generationsExpressionProg, 'xs:integer', fact)
        except:
            return None

    @property
    def cardinalityAndDepth(self):
        return self.lenDepth(self.relationships(self.modelXbrl.rendrCntx), 
                             self.axis.endswith('-or-self'))
    
    def lenDepth(self, nestedRelationships, includeSelf):
        l = 0
        d = 1
        for rel in nestedRelationships:
            if isinstance(rel, list):
                nl, nd = self.lenDepth(rel, False)
                l += nl
                nd += 1 # returns 0 if sublist is not nested
                if nd > d:
                    d = nd
            else:
                l += 1
                if includeSelf:
                    l += 1 # root relationships include root in addition
        if includeSelf:
            d += 1
        return (l, d)
    
    @property
    def propertyView(self):
        return (("id", self.id),
                ("xlink:label", self.xlinkLabel),
                ("header label", self.genLabel()),
                ("header doc", self.genLabel(role="http://www.xbrl.org/2008/role/documentation")),
                ("header code", self.genLabel(role="http://www.eurofiling.info/role/2010/coordinate-code")),
                ("abstract", self.abstract),
                ("ordinate", self.ordinateView))
        
    def __repr__(self):
        return ("explicitAxisMember[{0}]{1})".format(self.objectId(),self.propertyView))
    
class ModelConceptRelationshipAxis(ModelRelationshipAxis):
    def init(self, modelDocument):
        super(ModelConceptRelationshipAxis, self).init(modelDocument)
    
    def hasAspect(self, aspect):
        return aspect == Aspect.CONCEPT

    @property
    def arcrole(self):
        return XmlUtil.childText(self, XbrlConst.table, "arcrole")

    @property
    def arcQname(self):
        arcnameElt = XmlUtil.child(self, XbrlConst.table, "arcname")
        if arcnameElt is not None:
            return qname( arcnameElt, XmlUtil.text(arcnameElt) )
        return None

    @property
    def linkQname(self):
        linknameElt = XmlUtil.child(self, XbrlConst.table, "linkname")
        if linknameElt is not None:
            return qname( linknameElt, XmlUtil.text(linknameElt) )
        return None
    

    def compile(self):
        if not hasattr(self, "arcroleExpressionProg"):
            self.arcroleExpressionProg = XPathParser.parse(self, self.arcroleExpression, self, "arcroleExpressionProg", Trace.VARIABLE)
            self.linkQnameExpressionProg = XPathParser.parse(self, self.linkQnameExpression, self, "linkQnameExpressionProg", Trace.VARIABLE)
            self.arcQnameExpressionProg = XPathParser.parse(self, self.arcQnameExpression, self, "arcQnameExpressionProg", Trace.VARIABLE)
            super(ModelConceptRelationshipAxis, self).compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        return super(ModelConceptRelationshipAxis, self).variableRefs(
                                                [p for p in (self.arcroleExpressionProg,
                                                             self.linkQnameExpressionProg, self.arcQnameExpressionProg)
                                                 if p], varRefSet)

    def evalArcrole(self, xpCtx, fact):
        try:
            if self.arcrole:
                return self.arcrole
            return xpCtx.evaluateAtomicValue(self.arcroleExpressionProg, 'xs:anyURI', fact)
        except:
            return None
    
    def evalLinkQname(self, xpCtx, fact):
        try:
            if self.linkQname:
                return self.linkQname
            return xpCtx.evaluateAtomicValue(self.linkQnameExpressionProg, 'xs:QName', fact)
        except:
            return None
    
    def evalArcQname(self, xpCtx, fact):
        try:
            if self.arcQname:
                return self.arcQname
            return xpCtx.evaluateAtomicValue(self.arcQnameExpressionProg, 'xs:QName', fact)
        except:
            return None

    @property
    def arcroleExpression(self):
        return XmlUtil.childText(self, XbrlConst.table, "arcroleExpression")

    @property
    def linkQnameExpression(self):
        return XmlUtil.childText(self, XbrlConst.table, "linknameExpression")

    @property
    def arcQnameExpression(self):
        return XmlUtil.childText(self, XbrlConst.table, "arcnameExpression")
    
    def coveredAspect(self, xpCtx=None):
        return Aspect.CONCEPT

    def relationships(self, xpCtx):
        sourceQname = (self.evalRrelationshipSourceQname(xpCtx, None) or XbrlConst.qnXfiRoot)
        linkrole = self.evalLinkrole(xpCtx, None)
        if not linkrole:
            linkrole = "XBRL-all-linkroles"
        linkQname = (self.evalLinkQname(xpCtx, None) or () )
        arcrole = (self.evalArcrole(xpCtx, None) or () )
        arcQname = (self.evalArcQname(xpCtx, None) or () )
        axis = self.axis
        generations = (self.evalGenerations(xpCtx, None) or () )
        return concept_relationships(xpCtx, None, (sourceQname,
                                                   linkrole,
                                                   arcrole,
                                                   axis.replace('-or-self',''),
                                                   generations,
                                                   linkQname,
                                                   arcQname),
                                      True) # return nested lists representing concept tree nesting
    
class ModelDimensionRelationshipAxis(ModelRelationshipAxis):
    def init(self, modelDocument):
        super(ModelDimensionRelationshipAxis, self).init(modelDocument)
    
    def hasAspect(self, aspect):
        return aspect == self.coveredAspect() or aspect == Aspect.DIMENSIONS
    
    def aspectValue(self, aspect, inherit=None):
        if aspect == Aspect.DIMENSIONS:
            return (self.coveredAspect(), )
        return None

    @property
    def dimensionQname(self):
        dimensionElt = XmlUtil.child(self, XbrlConst.table, "dimension")
        if dimensionElt is not None:
            return qname( dimensionElt, XmlUtil.text(dimensionElt) )
        return None

    @property
    def dimensionQnameExpression(self):
        return XmlUtil.childText(self, XbrlConst.table, "dimensionExpression")

    def compile(self):
        if not hasattr(self, "dimensionQnameExpressionProg"):
            self.dimensionQnameExpressionProg = XPathParser.parse(self, self.dimensionQnameExpression, self, "dimensionQnameExpressionProg", Trace.VARIABLE)
            super(ModelDimensionRelationshipAxis, self).compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        return super(ModelDimensionRelationshipAxis, self).variableRefs(self.dimensionQnameExpressionProg, varRefSet)

    def evalDimensionQname(self, xpCtx, fact):
        try:
            if self.dimensionQname:
                return self.dimensionQname
            return xpCtx.evaluateAtomicValue(self.dimensionQnameExpressionProg, 'xs:QName', fact)
        except:
            return None
    
    def coveredAspect(self, xpCtx=None):
        try:
            return self._coveredAspect
        except AttributeError:
            if xpCtx is None: xpCtx = self.modelXbrl.rendrCntx
            self._coveredAspect = self.dimRelationships(xpCtx, getDimQname=True)
            return self._coveredAspect
        
    def relationships(self, xpCtx):
        return self.dimRelationships(xpCtx, getMembers=True)
    
    def dimRelationships(self, xpCtx, getMembers=False, getDimQname=False):
        dimensionQname = self.evalDimensionQname(xpCtx, None)
        sourceQname = self.evalRrelationshipSourceQname(xpCtx, None)
        linkrole = self.evalLinkrole(xpCtx, None)
        if not linkrole and getMembers:
            linkrole = "XBRL-all-linkroles"
        dimConcept = self.modelXbrl.qnameConcepts.get(dimensionQname)
        sourceConcept = self.modelXbrl.qnameConcepts.get(sourceQname)
        axis = self.axis
        generations = (self.evalGenerations(xpCtx, None) or () )
        if ((dimensionQname and (dimConcept is None or not dimConcept.isDimensionItem)) or
            (sourceQname and (sourceConcept is None or not sourceConcept.isItem))):
            return ()
        if dimConcept is not None:
            if getDimQname:
                return dimensionQname
            if sourceConcept is None:
                sourceConcept = dimConcept
        if getMembers:
            return concept_relationships(xpCtx, None, (sourceQname,
                                                       linkrole,
                                                       "XBRL-dimensions",  # all dimensions arcroles
                                                       axis.replace('-or-self',''),
                                                       generations),
                                          True) # return nested lists representing concept tree nesting
        if getDimQname:
            if sourceConcept is not None:
                # look back from member to a dimension
                return self.stepDimRel(sourceConcept, linkrole)
            return None
        
    def stepDimRel(self, stepConcept, linkrole):
        if stepConcept.isDimensionItem:
            return stepConcept.qname
        for rel in self.modelXbrl.relationshipSet("XBRL-dimensions").toModelObject(stepConcept):
            if not linkrole or linkrole == rel.consecutiveLinkrole:
                dim = self.stepDimRel(rel.fromModelObject, rel.linkrole)
                if dim:
                    return dim
        return None
        
coveredAspectToken = {"concept": Aspect.CONCEPT, 
                      "entity-identifier": Aspect.VALUE, 
                      "period-start": Aspect.START, "period-end": Aspect.END, 
                      "period-instant": Aspect.INSTANT, "period-instant-end": Aspect.INSTANT_END, 
                      "unit": Aspect.UNIT}

class ModelSelectionAxis(ModelOpenAxis):
    def init(self, modelDocument):
        super(ModelSelectionAxis, self).init(modelDocument)
        
    def clear(self):
        XPathParser.clearNamedProg(self, "selectProg")
        super(ModelSelectionAxis, self).clear()
    
    def coveredAspect(self, xpCtx=None):
        try:
            return self._coveredAspect
        except AttributeError:
            coveredAspect = self.get("coveredAspect")
            if coveredAspect in coveredAspectToken:
                self._coveredAspect = coveredAspectToken[coveredAspect]
            else:  # must be a qname
                self._coveredAspect = qname(self, coveredAspect)
            return self._coveredAspect

    @property
    def select(self):
        return self.get("select")
    
    def compile(self):
        if not hasattr(self, "selectProg"):
            self.selectProg = XPathParser.parse(self, self.select, self, "select", Trace.PARAMETER)
            super(ModelSelectionAxis, self).compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        return super(ModelSelectionAxis, self).variableRefs(self.selectProg, varRefSet)
        
    def evaluate(self, xpCtx, typeQname):
        try:
            return xpCtx.evaluateAtomicValue(self.selectProg, typeQname)
        except AttributeError:
            return None
            
class ModelFilterAxis(ModelOpenAxis):
    def init(self, modelDocument):
        super(ModelFilterAxis, self).init(modelDocument)
        
    @property
    def descendantArcroles(self):        
        return (XbrlConst.tableAxisFilter, XbrlConst.tableAxisMessage)
        
    @property
    def filterRelationships(self):
        try:
            return self._filterRelationships
        except AttributeError:
            rels = [] # order so conceptName filter is first (if any) (may want more sorting in future)
            for rel in self.modelXbrl.relationshipSet(XbrlConst.tableAxisFilter).fromModelObject(self):
                if isinstance(rel.toModelObject, ModelConceptName):
                    rels.insert(0, rel)  # put conceptName filters first
                else:
                    rels.append(rel)
            self._filterRelationships = rels
            return rels
    
class ModelTupleAxis(ModelOpenAxis):
    def init(self, modelDocument):
        super(ModelTupleAxis, self).init(modelDocument)
        
    @property
    def descendantArcroles(self):        
        return (XbrlConst.tableTupleContent, XbrlConst.tableAxisMessage)
        
    @property
    def contentRelationships(self):
        return self.modelXbrl.relationshipSet(XbrlConst.tableTupleContent).fromModelObject(self)
        
from arelle.ModelObjectFactory import elementSubstitutionModelClass
elementSubstitutionModelClass.update((
    (XbrlConst.qnEuTable, ModelEuTable),
    (XbrlConst.qnEuAxisCoord, ModelEuAxisCoord),
    (XbrlConst.qnTableTable, ModelTable),
    (XbrlConst.qnTableRuleAxis, ModelRuleAxis),
    (XbrlConst.qnTableCompositionAxis, ModelCompositionAxis),
    (XbrlConst.qnTableConceptRelationshipAxis, ModelConceptRelationshipAxis),
    (XbrlConst.qnTableDimensionRelationshipAxis, ModelDimensionRelationshipAxis),
    (XbrlConst.qnTableSelectionAxis, ModelSelectionAxis),
    (XbrlConst.qnTableFilterAxis, ModelFilterAxis),
    (XbrlConst.qnTableTupleAxis, ModelTupleAxis),
     ))

# import after other modules resolved to prevent circular references
from arelle.FunctionXfi import concept_relationships
