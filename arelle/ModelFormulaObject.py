'''
Created on Dec 9, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from collections import defaultdict
import datetime, re
from arelle import (XmlUtil, XbrlConst, XPathParser, XPathContext)
from arelle.ModelValue import (qname, QName)
from arelle.ModelObject import ModelObject
from arelle.ModelDtsObject import ModelResource
from arelle.ModelInstanceObject import ModelFact
from arelle.XbrlUtil import (typedValue)

class Aspect:
    LOCATION = 1
    CONCEPT = 2
    ENTITY_IDENTIFIER = 3; VALUE = 31; SCHEME = 32
    PERIOD = 4; PERIOD_TYPE = 41; START = 42; END = 43; INSTANT = 44
    UNIT = 5; UNIT_MEASURES = 51; MULTIPLY_BY = 52; DIVIDE_BY = 53; AUGMENT = 54
    COMPLETE_SEGMENT = 6
    COMPLETE_SCENARIO = 7
    NON_XDT_SEGMENT = 8
    NON_XDT_SCENARIO = 9
    DIMENSIONS = 10  # all dimensions; individual dimensions by their QNames
    OMIT_DIMENSIONS = 11 # dimensions with omit specified
    PRECISION = 95  # not real aspects, just for common processing
    DECIMALS = 96

    label = {
        LOCATION: "location",
        CONCEPT: "concept",
        ENTITY_IDENTIFIER: "entity identifier",  VALUE:"identifier value", SCHEME: "scheme",
        PERIOD: "period", PERIOD_TYPE: "period type", START: "period start", END: "period end", INSTANT: "period instant",
        UNIT: "unit", MULTIPLY_BY: "multiply by", DIVIDE_BY: "divide by", AUGMENT: "augment",
        COMPLETE_SEGMENT: "complete segment",
        COMPLETE_SCENARIO: "complete scenario",
        NON_XDT_SEGMENT: "nonXDT segment",
        NON_XDT_SCENARIO: "nonXDT scenario",
        DIMENSIONS: "all dimensions",
        OMIT_DIMENSIONS: "omit dimensions",
        PRECISION: "precision",
        DECIMALS: "decimals",
        }
    
aspectModelAspect = {   # aspect of the model that corresponds to retrievable aspects
    Aspect.VALUE: Aspect.ENTITY_IDENTIFIER, Aspect.SCHEME:Aspect.ENTITY_IDENTIFIER,
    Aspect.PERIOD_TYPE: Aspect.PERIOD, 
    Aspect.START: Aspect.PERIOD, Aspect.END: Aspect.PERIOD, 
    Aspect.INSTANT: Aspect.PERIOD,
    Aspect.UNIT_MEASURES: Aspect.UNIT, Aspect.MULTIPLY_BY: Aspect.UNIT, Aspect.DIVIDE_BY: Aspect.UNIT
    }

aspectModels = {
     "dimensional": {
             Aspect.LOCATION, Aspect.CONCEPT, Aspect.ENTITY_IDENTIFIER, Aspect.PERIOD, Aspect.UNIT,
             Aspect.DIMENSIONS,
             Aspect.NON_XDT_SEGMENT, Aspect.NON_XDT_SCENARIO},
     "non-dimensional": {
             Aspect.LOCATION, Aspect.CONCEPT, Aspect.ENTITY_IDENTIFIER, Aspect.PERIOD, Aspect.UNIT,
             Aspect.COMPLETE_SEGMENT, Aspect.COMPLETE_SCENARIO},
     }

aspectFromToken = {
     "location": Aspect.LOCATION, "concept": Aspect.CONCEPT, 
     "entityIdentifier": Aspect.ENTITY_IDENTIFIER, "entity-identifier": Aspect.ENTITY_IDENTIFIER, 
     "period": Aspect.PERIOD, "unit": Aspect.UNIT,
     "nonXDTSegment": Aspect.NON_XDT_SEGMENT, "non-XDT-segment": Aspect.NON_XDT_SEGMENT, 
     "nonXDTScenario": Aspect.NON_XDT_SCENARIO, "non-XDT-scenario": Aspect.NON_XDT_SCENARIO,
     "dimension": Aspect.DIMENSIONS, "dimensions": Aspect.DIMENSIONS,
     "segment": Aspect.COMPLETE_SEGMENT, "complete-segment": Aspect.COMPLETE_SEGMENT, 
     "scenario": Aspect.COMPLETE_SCENARIO, "complete-scenario": Aspect.COMPLETE_SCENARIO,
     }

aspectElementNameAttrValue = {
        Aspect.LOCATION: ("location", None, None),
        Aspect.CONCEPT: ("concept", None, None),
        Aspect.ENTITY_IDENTIFIER: ("entityIdentifier", None, None),
        Aspect.SCHEME: ("entityIdentifier", None, None),
        Aspect.VALUE: ("entityIdentifier", None, None),
        Aspect.PERIOD: ("period", None, None),
        Aspect.PERIOD_TYPE: ("period", None, None),
        Aspect.INSTANT: ("period", None, None),
        Aspect.START: ("period", None, None),
        Aspect.END: ("period", None, None),
        Aspect.UNIT: ("unit", None, None),
        Aspect.UNIT_MEASURES: ("unit", None, None),
        Aspect.MULTIPLY_BY: ("multiplyBy", "source", "*"),
        Aspect.DIVIDE_BY: ("divideBy", "source", "*"),
        Aspect.COMPLETE_SEGMENT: (("occFragments", "occXpath"), "occ", "segment"),
        Aspect.COMPLETE_SCENARIO: (("occFragments", "occXpath"), "occ", "scenario"),
        Aspect.NON_XDT_SEGMENT: (("occFragments", "occXpath"), "occ", "segment"),
        Aspect.NON_XDT_SCENARIO: (("occFragments", "occXpath"), "occ", "scenario"),
        }

class FormulaOptions():
    def __init__(self):
        self.parameterValues = {} # index is QName, value is typed value
        self.traceParameterExpressionResult = True
        self.traceParameterInputValue = True
        self.traceCallExpressionSource = False
        self.traceCallExpressionCode = False
        self.traceCallExpressionEvaluation = False
        self.traceCallExpressionResult = True
        self.traceVariableSetExpressionSource = False
        self.traceVariableSetExpressionCode = False
        self.traceVariableSetExpressionEvaluation = False
        self.traceVariableSetExpressionResult = False
        self.traceAssertionResultCounts = False
        self.traceFormulaRules = False
        self.traceVariablesDependencies = False
        self.traceVariablesOrder = False
        self.traceVariableFilterWinnowing = False
        self.traceVariableFiltersResult = False
        self.traceVariableExpressionSource = False
        self.traceVariableExpressionCode = False
        self.traceVariableExpressionEvaluation = False
        self.traceVariableExpressionResult = True
        
        # Note: if adding to this list keep DialogFormulaParameters in sync
    def traceSource(self, traceType):
        if traceType in (Trace.VARIABLE_SET, Trace.FORMULA_RULES): 
            return self.traceVariableSetExpressionSource
        elif traceType == Trace.VARIABLE: 
            return self.traceVariableExpressionSource
        else:
            return False
            
    def traceEvaluation(self, traceType):
        if traceType in (Trace.VARIABLE_SET, Trace.FORMULA_RULES): 
            return self.traceVariableSetExpressionEvaluation
        elif traceType == Trace.VARIABLE: 
            return self.traceVariableExpressionEvaluation
        else:
            return False
               
class Trace():
    PARAMETER = 1
    VARIABLE_SET = 2
    MESSAGE = 3
    FORMULA_RULES = 4
    VARIABLE = 5
    CUSTOM_FUNCTION = 6
    CALL = 7 #such as testcase call or API formula call
    TEST = 8 #such as testcase test or API formula test

class ModelFormulaResource(ModelResource):
    def _init(self):
        return super()._init()
        
    @property
    def descendantArcroles(self):
        return ()
    
    def compile(self):
        for arcrole in self.descendantArcroles:
            for modelRel in self.modelXbrl.relationshipSet(arcrole).fromModelObject(self):
                toModelObject = modelRel.toModelObject
                if isinstance(toModelObject,ModelFormulaResource):
                    toModelObject.compile()
                else:
                    self.modelXbrl.error( _("Invalid formula object {0}").format( toModelObject ),
                                          "error", "formula:internalError")

        
    def variableRefs(self, progs=[], varRefSet=None):
        if varRefSet is None: varRefSet = set()
        if progs:
            XPathParser.variableReferences(progs, varRefSet, self)
        for arcrole in self.descendantArcroles:
            for modelRel in self.modelXbrl.relationshipSet(arcrole).fromModelObject(self):
                toModelObject = modelRel.toModelObject
                if isinstance(toModelObject,ModelFormulaResource):
                    modelRel.toModelObject.variableRefs(varRefSet=varRefSet)
        return varRefSet
    
class ModelAssertionSet(ModelFormulaResource):
    def _init(self):
        if super()._init():
            self.modelXbrl.hasFormulae = True
            return True
        return False

    @property
    def descendantArcroles(self):
        return (XbrlConst.assertionSet,)
                
    @property
    def propertyView(self):
        return (("id", self.id),
                ("label", self.xlinkLabel))
        
    def __repr__(self):
        return ("modelAssertionSet[{0}]{1})".format(self.objectId(),self.propertyView))

class ModelVariableSet(ModelFormulaResource):
    def _init(self):
        if super()._init():
            self.modelXbrl.modelVariableSets.add(self)
            self.modelXbrl.hasFormulae = True
            return True
        return False
        
    @property
    def descendantArcroles(self):        
        return (XbrlConst.variableSet, XbrlConst.variableSetFilter, XbrlConst.variableSetPrecondition)
                
    @property
    def aspectModel(self):
        return self.get("aspectModel")

    @property
    def implicitFiltering(self):
        return self.get("implicitFiltering")

    @property
    def groupFilterRelationships(self):
        return self.modelXbrl.relationshipSet(XbrlConst.variableSetFilter).fromModelObject(self)
        
    @property
    def propertyView(self):
        return (("id", self.id),
                ("label", self.xlinkLabel),
                ("aspectModel", self.aspectModel),
                ("implicitFiltering", self.implicitFiltering))
        
    def __repr__(self):
        return ("modelVariableSet[{0}]{1})".format(self.objectId(),self.propertyView))

class ModelFormula(ModelVariableSet):
    def _init(self):
        return super()._init()
    
    def compile(self):
        if not hasattr(self, "valueProg"):
            self.valueProg = XPathParser.parse(self, self.value, self, "value", Trace.VARIABLE_SET)
            self.hasPrecision = False
            self.hasDecimals = False
            self.aspectValues = defaultdict(list)
            self.aspectProgs = defaultdict(list)
            exprs = []
            for ruleElt in self.iterdescendants():
                if isinstance(ruleElt,ModelObject):
                    name = ruleElt.localName
                    if name == "qname":
                        value = qname(ruleElt, ruleElt.text)
                        if ruleElt.getparent().localName == "concept":
                            self.aspectValues[Aspect.CONCEPT] = value
                        elif ruleElt.getparent().getparent().get("dimension") is not None:
                            self.aspectValues[qname(ruleElt.getparent().getparent(), ruleElt.getparent().getparent().get("dimension"))] = value
                    elif name == "qnameExpression":
                        if ruleElt.getparent().localName == "concept":
                            exprs = [(Aspect.CONCEPT, XmlUtil.text(ruleElt))]
                        elif ruleElt.getparent().getparent().get("dimension") is not None:
                            exprs = [(qname(ruleElt.getparent().getparent(), ruleElt.getparent().getparent().get("dimension")), XmlUtil.text(ruleElt))]
                    elif name == "omit" and ruleElt.getparent().hasAttribute("dimension"):
                        self.aspectValues[Aspect.OMIT_DIMENSIONS].append(qname(ruleElt.getparent(), ruleElt.getparent().get("dimension")))
                    elif name == "value" and ruleElt.getparent().get("dimension") is not None:
                        self.aspectValues[qname(ruleElt.getparent(), ruleElt.getparent().get("dimension"))] = XmlUtil.child(ruleElt,'*','*')
                    elif name == "entityIdentifier":
                        if ruleElt.get("scheme") is not None:
                            exprs.append((Aspect.SCHEME, ruleElt.get("scheme")))
                        if ruleElt.hasAttribute("value"):
                            exprs.append((Aspect.VALUE, ruleElt.get("value")))
                    elif name == "instant":
                        self.aspectValues[Aspect.PERIOD_TYPE] = name
                        if ruleElt.get("value") is not None:
                            exprs = [(Aspect.INSTANT, ruleElt.get("value"))]
                    elif name == "duration":
                        self.aspectValues[Aspect.PERIOD_TYPE] = name
                        if ruleElt.get("start") is not None:
                            exprs.append((Aspect.START, ruleElt.get("start")))
                        if ruleElt.get("end") is not None:
                            exprs.append((Aspect.END, ruleElt.get("end")))
                    elif name == "forever":
                        self.aspectValues[Aspect.PERIOD_TYPE] = name
                    elif name == "unit" and ruleElt.get("augment") is not None:
                        self.aspectValues[Aspect.AUGMENT] = ruleElt.get("augment")
                    elif name == "multiplyBy":
                        if ruleElt.get("measure") is not None:
                            exprs = [(Aspect.MULTIPLY_BY, ruleElt.get("measure"))]
                        if ruleElt.getparent().getparent().hasAttribute("source"):
                            self.aspectValues[Aspect.MULTIPLY_BY].append(qname(ruleElt, ruleElt.get("source"), noPrefixIsNoNamespace=True))
                    elif name == "divideBy":
                        if ruleElt.hasAttribute("measure"):
                            exprs = [(Aspect.DIVIDE_BY, ruleElt.get("measure"))]
                        if ruleElt.getparent().getparent().get("source") is not None:
                            self.aspectValues[Aspect.DIVIDE_BY].append(qname(ruleElt, ruleElt.get("source"), noPrefixIsNoNamespace=True))
                    elif name in ("occEmpty", "occFragments", "occXpath"):
                        if ruleElt.get("occ") == "segment":
                            if self.aspectModel == "dimensional": aspect = Aspect.NON_XDT_SEGMENT
                            else: aspect = Aspect.COMPLETE_SEGMENT
                        else:
                            if self.aspectModel == "dimensional": aspect = Aspect.NON_XDT_SCENARIO
                            else: aspect = Aspect.COMPLETE_SCENARIO
                        if name == "occFragments":
                            for occFragment in XmlUtil.children(ruleElt, None, "*"):
                                self.aspectValues[aspect].append(occFragment)
                        elif name == "occXpath":
                            exprs = [(aspect, ruleElt.get("select"))]
                        elif name == "occEmpty":
                            self.aspectValues[aspect].insert(0, XbrlConst.qnFormulaOccEmpty)
                    elif name in ("explicitDimension", "typedDimension") and ruleElt.get("dimension") is not None:
                        qnDim = qname(ruleElt, ruleElt.get("dimension"))
                        self.aspectValues[Aspect.DIMENSIONS].append(qnDim)
                        if not XmlUtil.hasChild(ruleElt, XbrlConst.formula, ("omit","member","value")):
                            self.aspectValues[qnDim] = XbrlConst.qnFormulaDimensionSAV
                    elif name == "precision":
                        exprs = [(Aspect.PRECISION, XmlUtil.text(ruleElt))]
                        self.hasPrecision = True
                    elif name == "decimals":
                        exprs = [(Aspect.DECIMALS, XmlUtil.text(ruleElt))]
                        self.hasDecimals = True
                        
                    if len(exprs) > 0:
                        for aspectExpr in exprs:
                            aspect, expr = aspectExpr
                            self.aspectProgs[aspect].append(XPathParser.parse(self, expr, ruleElt, ruleElt.localName, Trace.FORMULA_RULES))
                        exprs = []
            super().compile()

    def variableRefs(self, progs=[], varRefSet=None):
        return super().variableRefs([self.valueProg] + [v for vl in self.aspectProgs.values() for v in vl], varRefSet)

    def evaluate(self, xpCtx):
        return xpCtx.atomize( xpCtx.progHeader, xpCtx.evaluate( self.valueProg ) )

    def evaluateRule(self, xpCtx, aspect):
        if aspect in (Aspect.COMPLETE_SEGMENT, Aspect.COMPLETE_SCENARIO,
                        Aspect.NON_XDT_SEGMENT, Aspect.NON_XDT_SCENARIO):
            if not xpCtx: return None
            values = []
            if aspect in self.aspectValues:
                values.extend(self.aspectValues[aspect])
            values.extend(xpCtx.evaluate(prog) for prog in self.aspectProgs[aspect])
            return xpCtx.flattenSequence(values)
        if aspect in self.aspectValues:
            return (self.aspectValues[aspect])
        if aspect in (Aspect.CONCEPT, Aspect.MULTIPLY_BY, Aspect.DIVIDE_BY) or isinstance(aspect, QName):
            type = 'xs:QName'
        elif aspect == Aspect.ENTITY_IDENTIFIER:
            type = 'xs:string'
        elif aspect in (Aspect.INSTANT, Aspect.START, Aspect.END):
            type = 'xs:XBRLI_DATEUNION'
        elif aspect in (Aspect.DECIMALS, Aspect.PRECISION):
            type = 'xs:float'
        else:
            type = 'xs:string'
        if aspect in (Aspect.MULTIPLY_BY, Aspect.DIVIDE_BY): # return list of results
            return [xpCtx.evaluateAtomicValue(prog, type) for prog in self.aspectProgs[aspect]]
        elif xpCtx: # return single result
            for prog in self.aspectProgs[aspect]:
                return xpCtx.evaluateAtomicValue(prog, type)
        return None
                
    def hasRule(self, aspect):
        return aspect in self.aspectValues or aspect in self.aspectProgs

    @property
    def value(self):
        return self.get("value") if self.get("value") else None

    def source(self, aspect=None, ruleElement=None, acceptFormulaSource=True):
        if aspect is None and ruleElement is None:
            return qname(self, self.get("source"), noPrefixIsNoNamespace=True) if self.get("source") else None
        # find nearest source
        if ruleElement is None:
            if aspect == Aspect.DIMENSIONS:  # SAV is the formula element
                return self.source()
            ruleElements = self.aspectRuleElements(aspect)
            if len(ruleElements) > 0: ruleElement = ruleElements[0]
        if ruleElement is None and aspect not in (Aspect.MULTIPLY_BY, Aspect.DIVIDE_BY):
            ruleElement = self
        while (isinstance(ruleElement,ModelObject) and (acceptFormulaSource or ruleElement != self)):
            if ruleElement.get("source") is not None:
                return qname(ruleElement, ruleElement.get("source"), noPrefixIsNoNamespace=True)
            if ruleElement == self: break
            ruleElement = ruleElement.getparent()
        return None
    
    def aspectRuleElements(self, aspect):
        if aspect in aspectElementNameAttrValue:
            eltName, attrName, attrValue = aspectElementNameAttrValue[aspect]
            return XmlUtil.descendants(self, XbrlConst.formula, eltName, attrName, attrValue)
        elif isinstance(aspect,QName):
            return XmlUtil.descendants(self, XbrlConst.formula, 
                                      ("explicitDimension", "typedDimension"), 
                                      "dimension", aspect)
        return []
        
    @property
    def propertyView(self):
        return super().propertyView + (("value", self.value),)
        
    def __repr__(self):
        return ("formula({0}, '{1}')".format(self.id if self.id else self.xlinkLabel, self.value))

    @property
    def viewExpression(self):
        return self.value
                
class ModelVariableSetAssertion(ModelVariableSet):
    def _init(self):
        return super()._init()
    
    def compile(self):
        if not hasattr(self, "testProg"):
            self.testProg = XPathParser.parse(self, self.test, self, "test", Trace.VARIABLE_SET)
            super().compile()

    def variableRefs(self, progs=[], varRefSet=None):
        return super().variableRefs(self.testProg, varRefSet)

    @property
    def test(self):
        return self.get("test")

    def message(self,satisfied,preferredMessage=None,lang=None):
        if preferredMessage is None: preferredMessage = XbrlConst.standardMessage
        msgsRelationshipSet = self.modelXbrl.relationshipSet(XbrlConst.assertionSatisfiedMessage if satisfied else XbrlConst.assertionUnsatisfiedMessage)
        if msgsRelationshipSet:
            msg = msgsRelationshipSet.label(self, preferredMessage, lang, returnText=False)
            if msg is not None:
                return msg
        return None
    
    @property
    def propertyView(self):
        return super().propertyView + (("test", self.test),)
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__,self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.get("test")
                
class ModelExistenceAssertion(ModelVariableSetAssertion):
    def _init(self):
        self.evaluationsCount = 0
        return super()._init()
                
class ModelValueAssertion(ModelVariableSetAssertion):
    def _init(self):
        return super()._init()
                
    def evaluate(self, xpCtx):
        try:
            return xpCtx.evaluate(self.testProg) 
        except AttributeError:
            return None
            
class ModelConsistencyAssertion(ModelFormulaResource):
    def _init(self):
        if super()._init():
            self.modelXbrl.hasFormulae = True
            return True
        return False
                
    def compile(self):
        if not hasattr(self, "radiusProg"):
            self.radiusProg = XPathParser.parse(self, self.viewExpression, self, "radius", Trace.VARIABLE_SET)
            super().compile()

    def evalRadius(self, xpCtx, factValue):
        try:
            return xpCtx.evaluateAtomicValue(self.radiusProg, 'xs:float', factValue)
        except:
            return None
    @property
    def descendantArcroles(self):
        return (XbrlConst.consistencyAssertionFormula,)
        
    @property
    def hasProportionalAcceptanceRadius(self):
        return self.get("proportionalAcceptanceRadius") is not None
        
    @property
    def hasAbsoluteAcceptanceRadius(self):
        return self.get("absoluteAcceptanceRadius") is not None

    @property
    def isStrict(self):
        return self.get("strict") == "true"

    def message(self,satisfied,preferredMessage=None,lang=None):
        if preferredMessage is None: preferredMessage = XbrlConst.standardMessage
        msgsRelationshipSet = self.modelXbrl.relationshipSet(XbrlConst.assertionSatisfiedMessage if satisfied else XbrlConst.assertionUnsatisfiedMessage)
        if msgsRelationshipSet:
            msg = msgsRelationshipSet.label(self, preferredMessage, lang, returnText=False)
            if msg is not None:
                return msg
        return None
    
    @property
    def viewExpression(self):
        return self.get("proportionalAcceptanceRadius") + \
                self.get("absoluteAcceptanceRadius")

    @property
    def propertyView(self):
        return (("id", self.id),
                ("label", self.xlinkLabel),
                ("proportional radius", self.get("proportionalAcceptanceRadius")) if self.get("proportionalAcceptanceRadius") else (),
                ("absolute radius", self.get("absoluteAcceptanceRadius")) if self.get("absoulteAcceptanceRadius") else () ,
                ("strict", str(self.isStrict).lower()))
        
    def __repr__(self):
        return ("modelConsistencyAssertion[{0}]{1})".format(self.objectId(),self.propertyView))
                
class ModelParameter(ModelFormulaResource):
    def _init(self):
        if super()._init():
            if self.qname in self.modelXbrl.qnameParameters:
                self.modelXbrl.error(
                    _("Parameter name used on multiple parameters {0}").format(self.qname), 
                    "err", "xbrlve:parameterNameClash")
            else:
                self.modelXbrl.qnameParameters[self.qname] = self
            return True
        return False
    
    def compile(self):
        if not hasattr(self, "selectProg"):
            self.selectProg = XPathParser.parse(self, self.select, self, "select", Trace.PARAMETER)
            super().compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        return super().variableRefs(self.selectProg, varRefSet)
        
    def evaluate(self, xpCtx, typeQname):
        try:
            return xpCtx.evaluateAtomicValue(self.selectProg, typeQname)
        except AttributeError:
            return None
            
    @property
    def name(self):
        return self.get("name")
    
    @property
    def qname(self):
        try:
            return self._qname
        except AttributeError:
            self._qname = self.prefixedNameQname(self.name)
            return self._qname
    
    @property
    def select(self):
        return self.get("select")
    
    @property
    def required(self):
        return self.get("as")
    
    @property
    def asType(self):
        try:
            return self._asType
        except AttributeError:
            self._asType = self.prefixedNameQname(self.get("as"))
            return self._asType
    
    @property
    def propertyView(self):
        return (("id", self.id),
                ("label", self.xlinkLabel),
                ("name", self.name),
                ("select", self.select) if self.select else () ,
                ("required", self.required) if self.required else () ,
                ("as", self.asType) if self.asType else () )
        
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.select

class ModelInstance(ModelParameter):
    def _init(self):
        return super()._init()

class ModelVariable(ModelFormulaResource):
    def _init(self):
        return super()._init()
        
    def compile(self):
        super().compile()

    @property
    def bindAsSequence(self):
        return self.get("bindAsSequence")

class ModelFactVariable(ModelVariable):
    def _init(self):
        return super()._init()
    
    def compile(self):
        if not hasattr(self, "fallbackValueProg"):
            self.fallbackValueProg = XPathParser.parse(self, self.fallbackValue, self, "fallbackValue", Trace.VARIABLE)
            super().compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        try:
            return self._variableRefs
        except AttributeError:
            self._variableRefs = super().variableRefs(self.fallbackValueProg, varRefSet)
            return self._variableRefs
        
    @property
    def descendantArcroles(self):        
        return (XbrlConst.variableFilter,)
        
    @property
    def nils(self):
        return self.get("nils") if self.get("nils") else "false"
    
    @property
    def matches(self):
        return self.get("matches") if self.get("matches") else "false"
    
    @property
    def fallbackValue(self):
        return self.get("fallbackValue")
    
    @property
    def filterRelationships(self):
        return self.modelXbrl.relationshipSet(XbrlConst.variableFilter).fromModelObject(self)
    
    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("nils", self.nils),
                ("matches", self.matches),
                ("fallbackValue", self.fallbackValue),
                ("bindAsSequence", self.bindAsSequence) )

    def __repr__(self):
        return ("modelFactVariable[{0}]{1})".format(self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return ("fallbackValue =" + self.fallbackValue) if self.fallbackValue else ""

class ModelGeneralVariable(ModelVariable):
    def _init(self):
        return super()._init()
    
    def compile(self):
        if not hasattr(self, "selectProg"):
            self.selectProg = XPathParser.parse(self, self.select, self, "select", Trace.VARIABLE)
            super().compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        return super().variableRefs(self.selectProg, varRefSet)
        
    @property
    def select(self):
        return self.get("select")
    
    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("select", self.select) if self.select else () ,
                ("bindAsSequence", self.bindAsSequence) )
    
    def __repr__(self):
        return ("modelGeneralVariable[{0}]{1})".format(self.objectId(),self.propertyView))

    @property
    def viewExpression(self):
        return self.select

class ModelPrecondition(ModelFormulaResource):
    def _init(self):
        return super()._init()
    
    def compile(self):
        if not hasattr(self, "testProg"):
            self.testProg = XPathParser.parse(self, self.test, self, "test", Trace.VARIABLE)
            super().compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        return super().variableRefs(self.testProg, varRefSet)
        
    @property
    def test(self):
        return self.get("test")
    
    def evalTest(self, xpCtx):
        try:
            return xpCtx.evaluateBooleanValue(self.testProg)
        except AttributeError:
            return True # true if no test attribute because predicate has no filtering action
    
    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("test", self.test) )

    def __repr__(self):
        return ("modelPrecondition[{0}]{1})".format(self.objectId(),self.propertyView))
        
    @property
    def viewExpression(self):
        return self.test

class ModelFilter(ModelFormulaResource):
    def _init(self):
        return super()._init()
        
    def aspectsCovered(self, varBinding):
        return set()    #enpty set
        
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return facts
    
    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),)
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))

class ModelTestFilter(ModelFilter):
    def _init(self):
        return super()._init()

    def compile(self):
        if not hasattr(self, "testProg"):
            self.testProg = XPathParser.parse(self, self.test, self, "test", Trace.VARIABLE)
            super().compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        return super().variableRefs(self.testProg, varRefSet)
        
    @property
    def test(self):
        return self.get("test")
    
    def evalTest(self, xpCtx, fact):
        try:
            return xpCtx.evaluateBooleanValue(self.testProg, fact)
        except AttributeError:
            return True # true if no test attribute because predicate has no filtering action
    
    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("test", self.test) )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.test

class ModelPatternFilter(ModelFilter):
    def _init(self):
        return super()._init()

    @property
    def pattern(self):
        return self.get("pattern")
    
    @property
    def rePattern(self):
        try:
            return self._rePattern
        except AttributeError:
            self._rePattern = re.compile(self.pattern)
            return self._rePattern
        
    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("pattern", self.pattern) )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.pattern

class ModelAspectCover(ModelFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding, xpCtx=None):
        try:
            return self._aspectsCovered
        except AttributeError:
            self._aspectsCovered = set()
            self._dimsExcluded = set()
            self.isAll = False
            self.allDimensions = False
            for aspectElt in XmlUtil.children(self, XbrlConst.acf, "aspect"):
                aspect = XmlUtil.text(aspectElt)
                if aspect == "all":
                    self.isAll = True
                    self.allDimensions = True
                    self._aspectsCovered |= {
                     Aspect.LOCATION, Aspect.CONCEPT, Aspect.ENTITY_IDENTIFIER, Aspect.PERIOD, Aspect.UNIT,
                     Aspect.NON_XDT_SEGMENT, Aspect.NON_XDT_SCENARIO, 
                     Aspect.COMPLETE_SEGMENT, Aspect.COMPLETE_SCENARIO}
                elif aspect == "dimensions":
                    self.allDimensions = True
                else:
                    self._aspectsCovered.add( aspectFromToken[aspect] )
            for dimElt in XmlUtil.descendants(self, XbrlConst.acf, "qname"):
                dimAspect = qname( dimElt, XmlUtil.text(dimElt) )
                if dimElt.getparent().localName == "excludedDimension":
                    self._dimsExcluded.add(dimAspect)
                else:
                    self._aspectsCovered.add(dimAspect)
            if xpCtx:   # provided during validate formula checking
                for dimProgs, isExcluded in ((self.includedDimQnameProgs, False),(self.excludedDimQnameProgs, True)):
                    for dimProg in dimProgs:
                        dimAspect = xpCtx.evaluateAtomicValue(dimProg, 'xs:QName')
                        if isExcluded:
                            self._dimsExcluded.add(dimAspect)
                        else:
                            self._aspectsCovered.add(dimAspect)
            return self._aspectsCovered
        
    def dimAspectsCovered(self, varBinding):
        # if DIMENSIONS are provided then return all varBinding's dimensions less excluded dimensions
        dimsCovered = set()
        if self.allDimensions:
            for varBoundAspect in varBinding.aspectsDefined:
                if isinstance(varBoundAspect, QName) and varBoundAspect not in self._dimsExcluded:
                    dimsCovered.add(varBoundAspect)
        return dimsCovered
        
    def compile(self):
        if not hasattr(self, "includedDimQnameProgs"):
            self.includedDimQnameProgs = []
            self.excludedDimQnameProgs = []
            i = 1
            for qnameExpression in XmlUtil.descendants(self, XbrlConst.acf, "qnameExpression"):
                qNE = "qnameExpression_{0}".format(i)
                prog = XPathParser.parse( self, XmlUtil.text(qnameExpression), qnameExpression, qNE, Trace.VARIABLE )
                if qnameExpression.getparent().localName == "excludeDimension":
                    self.excludedDimQnameProgs.append(prog)
                else:
                    self.includedDimQnameProgs.append(prog)
                i += 1
            super().compile()
        
    @property
    def viewExpression(self):
        return XmlUtil.innerTextList(self)

class ModelBooleanFilter(ModelFilter):
    def _init(self):
        return super()._init()
        
    @property
    def descendantArcroles(self):        
        return (XbrlConst.booleanFilter,)

    @property
    def filterRelationships(self):
        return self.modelXbrl.relationshipSet(XbrlConst.booleanFilter).fromModelObject(self)
    
class ModelAndFilter(ModelBooleanFilter):
    def _init(self):
        return super()._init()

    def filter(self, xpCtx, varBinding, facts, cmplmt):
        from arelle.FormulaEvaluator import filterFacts
        return filterFacts(xpCtx, varBinding, facts, self.filterRelationships, "and")
        
class ModelOrFilter(ModelBooleanFilter):
    def _init(self):
        return super()._init()

    def filter(self, xpCtx, varBinding, facts, cmplmt):
        from arelle.FormulaEvaluator import filterFacts
        return filterFacts(xpCtx, varBinding, facts, self.filterRelationships, "or")

class ModelConceptName(ModelFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.CONCEPT}
        
    def compile(self):
        if not hasattr(self, "qnameExpressionProgs"):
            self.qnameExpressionProgs = []
            i = 1
            for qnameExpression in XmlUtil.descendants(self, XbrlConst.cf, "qnameExpression"):
                qNE = "qnameExpression_{0}".format(i)
                self.qnameExpressionProgs.append( XPathParser.parse( self, XmlUtil.text(qnameExpression), qnameExpression, qNE, Trace.VARIABLE ) )
                i += 1
            super().compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        return super().variableRefs(self.qnameExpressionProgs, varRefSet)

    @property
    def conceptQnames(self):
        try:
            return self._conceptQnames
        except AttributeError:
            self._conceptQnames = set()
            for qnameElt in XmlUtil.descendants(self, XbrlConst.cf, "qname"):
                self._conceptQnames.add( qname( qnameElt, XmlUtil.text(qnameElt) ) )
            return self._conceptQnames
    
    @property
    def qnameExpressions(self):
        return [XmlUtil.text(qnameExpression)
                for qnameExpression in XmlUtil.descendants(self, XbrlConst.cf, "qnameExpression")]
    
    def evalQnames(self, xpCtx, fact):
        try:
            return set(xpCtx.evaluateAtomicValue(exprProg, 'xs:QName', fact) for exprProg in self.qnameExpressionProgs)
        except AttributeError:
            return set()
    
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ (fact.qname in self.conceptQnames | self.evalQnames(xpCtx,fact))] 
    
    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("names", self.viewExpression) )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return XmlUtil.innerTextList(self)

class ModelConceptPeriodType(ModelFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.CONCEPT}
        
    @property
    def periodType(self):
        return self.get("periodType")
    
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ (fact.concept.periodType == self.periodType)] 
    
    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("periodType", self.periodType) )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.periodType

class ModelConceptBalance(ModelFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.CONCEPT}
        
    @property
    def balance(self):
        return self.get("balance")
    
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ ((fact.concept.balance == self.balance) if fact.concept.balance else (self.balance == "none"))] 
       
    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("balance", self.balance) )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.balance

class ModelConceptFilterWithQnameExpression(ModelFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.CONCEPT}
        
    @property
    def filterQname(self):
        qnameElt = XmlUtil.descendant(self, XbrlConst.cf, "qname")
        if qnameElt:
            return qname( qnameElt, XmlUtil.text(qnameElt) )
        return None
    
    @property
    def qnameExpression(self):
        qnExprElt = XmlUtil.descendant(self, XbrlConst.cf, "qnameExpression")
        return XmlUtil.text(qnExprElt) if qnExprElt else None
    
    def compile(self):
        if not hasattr(self, "qnameExpressionProg"):
            qnExprElt = XmlUtil.descendant(self, XbrlConst.cf, "qnameExpression")
            qnExpr = XmlUtil.text(qnExprElt) if qnExprElt else None
            self.qnameExpressionProg = XPathParser.parse(self, qnExpr, qnExprElt, "qnameExpression", Trace.VARIABLE)
            super().compile()
        
    def evalQname(self, xpCtx, fact):
        if self.filterQname:
            return self.filterQname
        return xpCtx.evaluateAtomicValue(self.qnameExpressionProg, 'xs:QName', fact)

    def variableRefs(self, progs=[], varRefSet=None):
        return super().variableRefs(self.qnameExpressionProg, varRefSet)

class ModelConceptCustomAttribute(ModelConceptFilterWithQnameExpression):
    def _init(self):
        return super()._init()

    @property
    def value(self):
        return self.get("value")

    def compile(self):
        if not hasattr(self, "valueProg"):
            self.valueProg = XPathParser.parse(self, self.value, self, "value", Trace.VARIABLE)
            super().compile()
       
    def evalValue(self, xpCtx, fact):
        if not self.value:
            return None
        try:
            return xpCtx.evaluateAtomicValue(self.valueProg, None, fact)
        except:
            return None
        
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                for qn in (self.evalQname(xpCtx,fact),)
                for v in (self.evalValue(xpCtx,fact),)
                for c in (fact.concept,)
                if cmplmt ^ (c.get(qn.nsname) and
                             (v is None or v == typedValue(xpCtx.modelXbrl, c, attrQname=qn)))] 

    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("value", self.value) if self.value else () ,
                ("qname", self.qname) if self.qname else () ,
                ("qnameExpr", self.qnameExpression) if self.qnameExpression else () )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.qname if self.qname else self.qnameExpression + \
                (" = " + self.value) if self.value else ""

class ModelConceptDataType(ModelConceptFilterWithQnameExpression):
    def _init(self):
        return super()._init()

    @property
    def strict(self):
        return self.get("strict")
       
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        notStrict = self.strict != "true"
        return [fact for fact in facts 
                for qn in (self.evalQname(xpCtx,fact),)
                for c in (fact.concept,)
                if cmplmt ^ (c.typeQname == qn or (notStrict and c.type.isDerivedFrom(qn)))] 

    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("strict", self.strict),
                ("type", self.qname) if self.qname else () ,
                ("typeExpression", self.qnameExpression) if self.qnameExpression else () )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.qname if self.qname else self.qnameExpression

class ModelConceptSubstitutionGroup(ModelConceptFilterWithQnameExpression):
    def _init(self):
        return super()._init()

    @property
    def strict(self):
        return self.get("strict")
    
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        if self.strict == "true":
            return [fact for fact in facts 
                    if cmplmt ^ (fact.concept.substitutionGroupQname == self.evalQname(xpCtx,fact))] 
        return [fact for fact in facts 
                if cmplmt ^ fact.concept.substitutesForQname(self.evalQname(xpCtx,fact))]
    
    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("strict", self.strict),
                ("subsGrp", self.qname) if self.qname else () ,
                ("subsGrpExpr", self.qnameExpression) if self.qnameExpression else () )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.qname if self.qname else self.qnameExpression

class ModelConceptRelation(ModelFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.CONCEPT}
        
    @property
    def variable(self):
        variableElt = XmlUtil.child(self, XbrlConst.crf, "variable")
        if variableElt:
            return qname( variableElt, XmlUtil.text(variableElt), noPrefixIsNoNamespace=True )
        return None
    
    @property
    def sourceQname(self):
        sourceQname = XmlUtil.child(self, XbrlConst.crf, "qname")
        if sourceQname:
            return qname( sourceQname, XmlUtil.text(sourceQname) )
        return None
    
    @property
    def linkrole(self):
        return XmlUtil.childText(self, XbrlConst.crf, "linkrole")

    @property
    def linkQname(self):
        linkname = XmlUtil.child(self, XbrlConst.crf, "linkname")
        if linkname:
            return qname( linkname, XmlUtil.text(linkname) )
        return None

    @property
    def arcrole(self):
        return XmlUtil.childText(self, XbrlConst.crf, "arcrole")

    @property
    def axis(self):
        a = XmlUtil.childText(self, XbrlConst.crf, "axis")
        if not a: a = 'child'  # would be an XML error
        return a

    @property
    def generations(self):
        try:
            return int( XmlUtil.childText(self, XbrlConst.crf, "generations") )
        except (TypeError, ValueError):
            if self.axis in ('sibling', 'child', 'parent'): 
                return 1
            return 0
    
    @property
    def test(self):
        return self.get("test")

    @property
    def arcQname(self):
        arcname = XmlUtil.child(self, XbrlConst.crf, "arcname")
        if arcname:
            return qname( arcname, XmlUtil.text(arcname) )
        return None

    @property
    def sourceQnameExpression(self):
        return XmlUtil.childText(self, XbrlConst.crf, "qnameExpression")

    @property
    def linkroleExpression(self):
        return XmlUtil.childText(self, XbrlConst.crf, "linkroleExpression")

    @property
    def linknameExpression(self):
        return XmlUtil.childText(self, XbrlConst.crf, "linknameExpression")

    @property
    def arcroleExpression(self):
        return XmlUtil.childText(self, XbrlConst.crf, "arcroleExpression")

    @property
    def arcnameExpression(self):
        return XmlUtil.childText(self, XbrlConst.crf, "arcnameExpression")

    def compile(self):
        if not hasattr(self, "sourceQnameExpressionProg"):
            self.sourceQnameExpressionProg = XPathParser.parse(self, self.sourceQnameExpression, self, "sourceQnameExpressionProg", Trace.VARIABLE)
            self.linkroleExpressionProg = XPathParser.parse(self, self.linkroleExpression, self, "linkroleQnameExpressionProg", Trace.VARIABLE)
            self.linknameExpressionProg = XPathParser.parse(self, self.linknameExpression, self, "linknameQnameExpressionProg", Trace.VARIABLE)
            self.arcroleExpressionProg = XPathParser.parse(self, self.arcroleExpression, self, "arcroleQnameExpressionProg", Trace.VARIABLE)
            self.arcnameExpressionProg = XPathParser.parse(self, self.arcnameExpression, self, "arcnameQnameExpressionProg", Trace.VARIABLE)
            self.testExpressionProg = XPathParser.parse(self, self.test, self, "testExpressionProg", Trace.VARIABLE)
            super().compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        if self.variable and self.variable != XbrlConst.qnXfiRoot:
            if varRefSet is None: varRefSet = set()
            varRefSet.add(self.variable)
        return super().variableRefs([p for p in (self.sourceQnameExpressionProg,
                                                 self.linkroleExpressionProg, self.linknameExpressionProg,
                                                 self.arcroleExpressionProg, self.arcnameExpressionProg)
                                        if p], varRefSet)

    def evalSourceQname(self, xpCtx, fact):
        try:
            if self.sourceQname:
                return self.sourceQname
            return xpCtx.evaluateAtomicValue(self.sourceQnameExpressionProg, 'xs:QName', fact)
        except:
            return None
    
    def evalLinkrole(self, xpCtx, fact):
        try:
            if self.linkrole:
                return self.linkrole
            return xpCtx.evaluateAtomicValue(self.linkroleExpressionProg, 'xs:anyURI', fact)
        except:
            return None
    
    def evalLinkQname(self, xpCtx, fact):
        try:
            if self.linkQname:
                return self.linkQname
            return xpCtx.evaluateAtomicValue(self.linkQnameExpressionProg, 'xs:QName', fact)
        except:
            return None
    
    def evalArcrole(self, xpCtx, fact):
        try:
            if self.arcrole:
                return self.arcrole
            return xpCtx.evaluateAtomicValue(self.arcroleExpressionProg, 'xs:anyURI', fact)
        except:
            return None
    
    def evalArcQname(self, xpCtx, fact):
        try:
            if self.arcQname:
                return self.arcQname
            return xpCtx.evaluateAtomicValue(self.arcQnameExpressionProg, 'xs:QName', fact)
        except:
            return None
    
    def evalTest(self, xpCtx, fact):
        try:
            return xpCtx.evaluateBooleanValue(self.testExpressionProg, fact)
        except:
            return None
    
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        if self.variable:
            otherFact = xpCtx.inScopeVars.get(self.variable)
            sourceQname = otherFact.qname if otherFact else None
        else:
            sourceQname = self.evalSourceQname(xpCtx, None)
        if not sourceQname:
            return []
        linkrole = self.evalLinkrole(xpCtx, None)
        linkQname = self.evalLinkQname(xpCtx, None)
        if linkQname is None: linkQname = ()
        arcrole = self.evalArcrole(xpCtx, None)
        arcQname = self.evalArcQname(xpCtx, None)
        if arcQname is None: arcQname = ()
        hasNoTest = self.test is None
        axis = self.axis
        isFromAxis = axis.startswith('parent') or axis.startswith('ancestor')
        from arelle.FunctionXfi import concept_relationships
        relationships = concept_relationships(xpCtx, None, (sourceQname,
                                                            linkrole,
                                                            arcrole,
                                                            axis.replace('-or-self',''),
                                                            self.generations,
                                                            linkQname,
                                                            arcQname))
        outFacts = []
        for fact in facts:
            factOk = False
            factQname = fact.qname
            for modelRel in relationships:
                if (((isFromAxis and factQname == modelRel.fromModelObject.qname) or
                     (not isFromAxis and factQname == modelRel.toModelObject.qname)) and
                     (hasNoTest or self.evalTest(xpCtx, modelRel))):
                    factOk = True
                    break
            if (not factOk and
                axis.startswith('sibling') and
                factQname != sourceQname and 
                not concept_relationships(xpCtx, None, (sourceQname, linkrole, arcrole, 'parent', 1, linkQname, arcQname)) and
                not concept_relationships(xpCtx, None, (factQname, linkrole, arcrole, 'parent', 1, linkQname, arcQname)) and
                concept_relationships(xpCtx, None, (factQname, linkrole, arcrole, 'child', 1, linkQname, arcQname))):
                factOk = True
            if (not factOk and
                axis.endswith('-or-self')):
                if sourceQname == XbrlConst.qnXfiRoot:
                    if (not concept_relationships(xpCtx, None, (factQname, linkrole, arcrole, 'parent', 1, linkQname, arcQname)) and
                        concept_relationships(xpCtx, None, (factQname, linkrole, arcrole, 'child', 1, linkQname, arcQname))):
                        factOk = True
                else:
                    if factQname == sourceQname:
                        factOk = True
            if cmplmt ^ (factOk):
                outFacts.append(fact)
        return outFacts 
    
    def viewExpression(self):
        return XmlUtil.innerTextList(self)

class ModelEntityIdentifier(ModelTestFilter):
    def _init(self):
        return super()._init()

    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ (not fact.isItem or
                             self.evalTest(xpCtx, 
                                           XmlUtil.child(fact.context.entity, XbrlConst.xbrli, "identifier")))] 
    
    def aspectsCovered(self, varBinding):
        return {Aspect.ENTITY_IDENTIFIER}
        
class ModelEntitySpecificIdentifier(ModelFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.ENTITY_IDENTIFIER}
        
    @property
    def scheme(self):
        return self.get("scheme")
    
    @property
    def value(self):
        return self.get("value")
    
    def compile(self):
        if not hasattr(self, "schemeProg"):
            self.schemeProg = XPathParser.parse(self, self.scheme, self, "scheme", Trace.VARIABLE)
            self.valueProg = XPathParser.parse(self, self.value, self, "value", Trace.VARIABLE)
            super().compile()
        
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ (not fact.isItem or ( 
                             fact.context.entityIdentifier[0] == xpCtx.evaluateAtomicValue(self.schemeProg, 'xs:string', fact) and 
                             fact.context.entityIdentifier[1] == xpCtx.evaluateAtomicValue(self.valueProg, 'xs:string', fact)))] 

    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("scheme", self.scheme),
                ("value", self.value) )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return "{0} {1}".format(self.scheme, self.value)

class ModelEntityScheme(ModelFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.ENTITY_IDENTIFIER}
        
    @property
    def scheme(self):
        return self.get("scheme")
    
    def compile(self):
        if not hasattr(self, "schemeProg"):
            self.schemeProg = XPathParser.parse(self, self.scheme, self, "scheme", Trace.VARIABLE)
            super().compile()
        
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ (not fact.isItem or 
                             fact.context.entityIdentifier[0] == xpCtx.evaluateAtomicValue(self.schemeProg, 'xs:string', fact))] 

    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("scheme", self.scheme) )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.scheme

class ModelEntityRegexpIdentifier(ModelPatternFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.ENTITY_IDENTIFIER}
        
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ (not fact.isItem or 
                             self.rePattern.search(fact.context.entityIdentifier[1]) is not None)] 

class ModelEntityRegexpScheme(ModelPatternFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.ENTITY_IDENTIFIER}
        
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ (not fact.isItem or 
                             self.rePattern.search(fact.context.entityIdentifier[0]) is not None)] 

class ModelGeneral(ModelTestFilter):
    def _init(self):
        return super()._init()

    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ (self.evalTest(xpCtx, fact))] 
    
    
class ModelMatchFilter(ModelFilter):
    def _init(self):
        return super()._init()

    @property
    def aspectName(self):
        try:
            return self._aspectName
        except AttributeError:
            self._aspectName = self.localName[5].lower() + self.localName[6:]
            return self._aspectName
            
    @property
    def dimension(self):
        return qname( self, self.get("dimension")) if self.get("dimension") else None
    
    @property
    def aspect(self):
        try:
            return self._aspect
        except AttributeError:
            self._aspect = aspectFromToken[self.aspectName]
            if self._aspect == Aspect.DIMENSIONS:
                self._aspect = self.dimension
            return self._aspect
        
    def aspectsCovered(self, varBinding):
        return {self.aspect}
        
    @property
    def variable(self):
        return qname( self, self.get("variable"), noPrefixIsNoNamespace=True ) if self.get("variable") else None
    
    def variableRefs(self, progs=[], varRefSet=None):
        if self.variable: 
            if varRefSet is None: varRefSet = set()
            varRefSet.add(self.variable)
        return super().variableRefs(None, varRefSet)

    def filter(self, xpCtx, varBinding, facts, cmplmt):
        from arelle.FormulaEvaluator import aspectMatches
        aspect = self.aspect
        otherFact = xpCtx.inScopeVars.get(self.variable)
        return [fact for fact in facts 
                if cmplmt ^ (aspectMatches(fact, otherFact, aspect))] 

    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("aspect", self.aspectName),
                ("dimension", self.dimension) if self.dimension else (),
                ("variable", self.variable),
                 )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.dimension

class ModelPeriod(ModelTestFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.PERIOD}
        
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ (not fact.isItem or 
                             self.evalTest(xpCtx, fact.context.period))] 
    
class ModelDateTimeFilter(ModelFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.PERIOD}
        
    @property
    def date(self):
        return self.get("date")
    
    @property
    def time(self):
        return self.get("time")
    
    def compile(self):
        if not hasattr(self, "dateProg"):
            self.dateProg = XPathParser.parse(self, self.date, self, "date", Trace.VARIABLE)
            if self.time and not hasattr(self, "timeProg"):
                self.timeProg = XPathParser.parse(self, self.time, self, "time", Trace.VARIABLE)
            super().compile()
        
    def evalDatetime(self, xpCtx, fact, addOneDay=False):
        date = xpCtx.evaluateAtomicValue(self.dateProg, 'xs:date', fact)
        if hasattr(self,"timeProg"):
            time = xpCtx.evaluateAtomicValue(self.timeProg, 'xs:time', fact)
            return date + time
        if addOneDay:
            return date + datetime.timedelta(1)
        return date
    
    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("date", self.date),
                ("time", self.time) if self.time else () )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.date + (" " + self.time) if self.time else ""

    
class ModelPeriodStart(ModelDateTimeFilter):
    def _init(self):
        return super()._init()

    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ (not fact.isItem or 
                             fact.context.startDatetime == self.evalDatetime(xpCtx, fact, addOneDay=False))] 

class ModelPeriodEnd(ModelDateTimeFilter):
    def _init(self):
        return super()._init()

    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ (not fact.isItem or (fact.context.isStartEndPeriod 
                             and fact.context.endDatetime == self.evalDatetime(xpCtx, fact, addOneDay=True)))] 

class ModelPeriodInstant(ModelDateTimeFilter):
    def _init(self):
        return super()._init()

    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ (not fact.isItem or 
                             fact.context.instantDatetime == self.evalDatetime(xpCtx, fact, addOneDay=True))] 
    
class ModelForever(ModelFilter):
    def _init(self):
        return super()._init()

    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ (not fact.isItem or fact.context.isForeverPeriod)] 

    def aspectsCovered(self, varBinding):
        return {Aspect.PERIOD}
        
class ModelInstantDuration(ModelFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.PERIOD}
        
    @property
    def variable(self):
        return qname( self, self.get("variable"), noPrefixIsNoNamespace=True ) if self.get("variable") else None
    
    def variableRefs(self, progs=[], varRefSet=None):
        if self.variable: 
            if varRefSet is None: varRefSet = set()
            varRefSet.add(self.variable)
        return super().variableRefs(None, varRefSet)

    @property
    def boundary(self):
        return self.get("boundary")
    
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        otherFact = xpCtx.inScopeVars.get(self.variable)
        if otherFact and isinstance(otherFact,ModelFact) and otherFact.isItem and \
            otherFact.context.isStartEndPeriod:
            if self.boundary == 'start':
                otherDatetime = otherFact.context.startDatetime
            else:
                otherDatetime = otherFact.context.endDatetime
            return [fact for fact in facts 
                    if cmplmt ^ (not fact.isItem or (fact.context.isInstantPeriod and \
                                 fact.context.instantDatetime == otherDatetime))] 
        return facts # couldn't filter

    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("variable", self.variable),
                ("boundary", self.boundary) )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.variable

class MemberModel():
    def __init__(self, qname, qnameExprProg, variable, linkrole, arcrole, axis):
        self.qname = qname
        self.qnameExprProg = qnameExprProg
        self.variable = variable
        self.linkrole = linkrole
        self.arcrole = arcrole
        self.axis = axis
    
class ModelExplicitDimension(ModelFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {self.dimQname}
        
    @property
    def dimQname(self):
        dimQname = XmlUtil.child(XmlUtil.child(self,XbrlConst.df,"dimension"), XbrlConst.df, "qname")
        if dimQname:
            return qname( dimQname, XmlUtil.text(dimQname) )
        return None
    
    @property
    def dimQnameExpression(self):
        qnameExpression = XmlUtil.descendant(XmlUtil.child(self,XbrlConst.df,"dimension"), XbrlConst.df, "qnameExpression")
        if qnameExpression:
            return XmlUtil.text(qnameExpression)
        return None    

    def compile(self):
        if not hasattr(self, "dimQnameExpressionProg"):
            self.dimQnameExpressionProg = XPathParser.parse(self, self.dimQnameExpression, self, "dimQnameExpressionProg", Trace.VARIABLE)
            self.memberProgs = []
            for memberElt in XmlUtil.children(self, XbrlConst.df, "member"):
                qnameElt = XmlUtil.child(memberElt, XbrlConst.df, "qname")
                qnameExpr = XmlUtil.child(memberElt, XbrlConst.df, "qnameExpression")                
                variableElt = XmlUtil.child(memberElt, XbrlConst.df, "variable")
                linkrole = XmlUtil.child(memberElt, XbrlConst.df, "linkrole")
                arcrole = XmlUtil.child(memberElt, XbrlConst.df, "arcrole")
                axis = XmlUtil.child(memberElt, XbrlConst.df, "axis")
                memberModel = MemberModel(
                    qname( qnameElt, XmlUtil.text(qnameElt) ) if qnameElt else None,
                    XPathParser.parse(self, XmlUtil.text(qnameExpr), memberElt, "memQnameExpressionProg", Trace.VARIABLE) if qnameExpr else None,
                    qname( variableElt, XmlUtil.text(variableElt), noPrefixIsNoNamespace=True ) if variableElt else None,
                    XmlUtil.text(linkrole) if linkrole else None,
                    XmlUtil.text(arcrole) if arcrole else None,
                    XmlUtil.text(axis) if axis else None)
                self.memberProgs.append(memberModel)
            super().compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        if varRefSet is None: varRefSet = set()
        memberModelMemberProgs = []
        for memberModel in self.memberProgs:
            if memberModel.variable:
                varRefSet.add(memberModel.variable)
            elif memberModel.qnameExprProg:
                memberModelMemberProgs.append(memberModel.qnameExprProg)
        return super().variableRefs(memberModelMemberProgs, varRefSet)

    def evalDimQname(self, xpCtx, fact):
        try:
            if self.dimQname:
                return self.dimQname
            return xpCtx.evaluateAtomicValue(self.dimQnameExpressionProg, 'xs:QName', fact)
        except:
            return None
    
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        outFacts = []
        for fact in facts:
            factOk = True
            dimQname = self.evalDimQname(xpCtx, fact)
            dimConcept = xpCtx.modelXbrl.qnameConcepts.get(dimQname)
            if not dimConcept or not dimConcept.isExplicitDimension:
                self.modelXbrl.error(_("{0} is not an explicit dimension concept QName.").format(dimQname), 
                                     "err", "xfie:invalidExplicitDimensionQName")
                return []
            if fact.isItem:
                memQname = fact.context.dimMemberQname(dimQname)
                if memQname:
                    if len(self.memberProgs) > 0:
                        factOk = False
                        domainMembersExist = False
                        for memberModel in self.memberProgs:
                            matchMemQname = None
                            if memberModel.qname:
                                matchMemQname = memberModel.qname
                            elif memberModel.variable:
                                otherFact = xpCtx.inScopeVars.get(memberModel.variable)
                                if otherFact and isinstance(otherFact,ModelFact) and otherFact.isItem:
                                    matchMemQname = otherFact.context.dimMemberQname(dimQname)
                            elif memberModel.qnameExprProg:
                                matchMemQname = xpCtx.evaluateAtomicValue(memberModel.qnameExprProg, 'xs:QName', fact)
                            memConcept = xpCtx.modelXbrl.qnameConcepts.get(matchMemQname)
                            if not memConcept:
                                #self.modelXbrl.error(_("{0} is not a domain item concept.").format(matchMemQname), 
                                #                     "err", "xbrldfe:invalidDomainMember")
                                return []
                            if (not memberModel.axis or memberModel.axis.endswith('-self')) and \
                                matchMemQname == memQname:
                                    factOk = True
                                    break
                            elif memberModel.axis and memberModel.linkrole and memberModel.arcrole:
                                relSet = fact.modelXbrl.relationshipSet(memberModel.arcrole, memberModel.linkrole)
                                if relSet:
                                    ''' removed by Erratum 2011-03-10
                                    # check for ambiguous filter member network
                                    linkQnames = set()
                                    arcQnames = set()
                                    fromRels = relSet.fromModelObject(memConcept)
                                    if fromRels:
                                        from arelle.FunctionXfi import filter_member_network_members
                                        filter_member_network_members(relSet, fromRels, memberModel.axis.startswith("descendant"), set(), linkQnames, arcQnames)
                                        if len(linkQnames) > 1 or len(arcQnames) > 1:
                                            self.modelXbrl.error(_('Network of linkrole {0} and arcrole {1} dimension {2} contains ambiguous links {3} or arcs {4}').format(
                                                                 memberModel.linkrole, memberModel.arcrole, self.dimQname, linkQnames, arcQnames) ,
                                                                 "err", "xbrldfe:ambiguousFilterMemberNetwork")
                                            return []
                                    '''
                                    if relSet.isRelated(matchMemQname, memberModel.axis, memQname):
                                        factOk = True
                                        break
                                    elif not domainMembersExist and relSet.isRelated(matchMemQname, memberModel.axis):
                                        domainMembersExist = True # don't need to throw an error
                            ''' removed by erratum 2011-03-10
                            else: # check dynamic mem qname for validity
                                from arelle.ValidateXbrlDimensions import checkPriItemDimValueValidity
                                if not checkPriItemDimValueValidity(self, fact.concept, dimConcept, memConcept):
                                    self.modelXbrl.error(_("{0} is not a valid domain member for dimension {1} of primary item {2}.").format(matchMemQname, dimConcept.qname, fact.qname), 
                                                         "err", "xbrldfe:invalidDomainMember")
                                    return []
                            '''
                        '''
                        if not factOk:
                            if not domainMembersExist and memberModel.axis:
                                self.modelXbrl.error(_("No member found in the network of explicit dimension concept {0}").format(dimQname), 
                                                     "err", "xbrldfe:invalidDomainMember")
                                return []
                        '''
                else: # no member for dimension
                    factOk = False
            else:
                factOk = True # don't filter facts which are tuples
            if cmplmt ^ (factOk):
                outFacts.append(fact)
        return outFacts 
    
    @property
    def viewExpression(self):
        return XmlUtil.innerTextList(self)

class ModelTypedDimension(ModelTestFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {self.dimQname}
        
    @property
    def dimQname(self):
        dimQname = XmlUtil.descendant(self, XbrlConst.df, "qname")
        if dimQname:
            return qname( dimQname, XmlUtil.text(dimQname) )
        return None
    
    @property
    def dimQnameExpression(self):
        qnameExpression = XmlUtil.descendant(self, XbrlConst.df, "qnameExpression")
        if qnameExpression:
            return XmlUtil.text(qnameExpression)
        return None    
   
    def compile(self):
        if not hasattr(self, "dimQnameExpressionProg"):
            self.dimQnameExpressionProg = XPathParser.parse(self, self.dimQnameExpression, self, "dimQnameExpressionProg", Trace.VARIABLE)
            super().compile()
        
    def evalDimQname(self, xpCtx, fact):
        try:
            if self.dimQname:
                return self.dimQname
            return xpCtx.evaluateAtomicValue(self.dimQnameExpressionProg, 'xs:QName', fact)
        except:
            return None
    
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        outFacts = []
        for fact in facts:
            dimQname = self.evalDimQname(xpCtx, fact)
            dim = fact.context.qnameDims.get(dimQname)
            if cmplmt ^ (not fact.isItem or(
                         dim is not None and
                         (not self.test or
                          self.evalTest(xpCtx, dim.typedMember)))):
                outFacts.append(fact)
        return outFacts 
    
    @property
    def viewExpression(self):
        return XmlUtil.innerTextList(self)

class ModelRelativeFilter(ModelFilter):
    def _init(self):
        return super()._init()

    @property
    def variable(self):
        return qname(self, self.get("variable"), noPrefixIsNoNamespace=True) if self.get("variable") else None
    
    def variableRefs(self, progs=[], varRefSet=None):
        if self.variable: 
            if varRefSet is None: varRefSet = set()
            varRefSet.add(self.variable)
        return super().variableRefs(None, varRefSet)

    def aspectsCovered(self, varBinding):
        return varBinding.aspectsDefined

    def filter(self, xpCtx, varBinding, facts, cmplmt):
        from arelle.FormulaEvaluator import aspectMatchFilter
        return aspectMatchFilter(xpCtx, 
                                 facts, 
                                 (varBinding.aspectsDefined - varBinding.aspectsCovered), 
                                 xpCtx.varBindings.get(self.variable), 
                                 "relative")
        
    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("variable", self.variable) )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.variable

class ModelSegmentFilter(ModelTestFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.COMPLETE_SEGMENT}
        
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ (not fact.isItem or 
                             (fact.context.hasSegment and self.evalTest(xpCtx, fact.context.segment)))] 
    
class ModelScenarioFilter(ModelTestFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.COMPLETE_SCENARIO}
        
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ (not fact.isItem or
                             (fact.context.hasScenario and self.evalTest(xpCtx, fact.context.scenario)))] 
    
class ModelAncestorFilter(ModelFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.LOCATION}
        
    @property
    def ancestorQname(self):
        ancestorQname = XmlUtil.descendant(self, XbrlConst.tf, "qname")
        if ancestorQname:
            return qname( ancestorQname, XmlUtil.text(ancestorQname) )
        return None
    
    @property
    def qnameExpression(self):
        qnameExpression = XmlUtil.descendant(self, XbrlConst.tf, "qnameExpression")
        if qnameExpression:
            return XmlUtil.text(qnameExpression)
        return None    
   
    def compile(self):
        if not hasattr(self, "qnameExpressionProg"):
            self.qnameExpressionProg = XPathParser.parse(self, self.qnameExpression, self, "qnameExpressionProg", Trace.VARIABLE)
            super().compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        return super().variableRefs(self.qnameExpressionProg, varRefSet)

    def evalQname(self, xpCtx, fact):
        ancestorQname = self.ancestorQname
        if ancestorQname:
            return ancestorQname
        try:
            return xpCtx.evaluateAtomicValue(self.qnameExpressionProg, 'xs:QName', fact)
        except:
            return None
    
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts if cmplmt ^ ( self.evalQname(xpCtx,fact) in fact.ancestorQnames ) ]
    
    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("ancestor", self.ancestorQname) if self.ancestorQname else () ,
                ("ancestorExpression", self.qnameExpression) if self.qnameExpression else () )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.ancestorQname if self.ancestorQname else self.qnameExpression

class ModelParentFilter(ModelFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.LOCATION}
        
    @property
    def parentQname(self):
        parentQname = XmlUtil.descendant(self, XbrlConst.tf, "qname")
        if parentQname:
            return qname( parentQname, XmlUtil.text(parentQname) )
        return None
    
    @property
    def qnameExpression(self):
        qnameExpression = XmlUtil.descendant(self, XbrlConst.tf, "qnameExpression")
        if qnameExpression:
            return XmlUtil.text(qnameExpression)
        return None
    
    def compile(self):
        if not hasattr(self, "qnameExpressionProg"):
            self.qnameExpressionProg = XPathParser.parse(self, self.qnameExpression, self, "qnameExpressionProg", Trace.VARIABLE)
            super().compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        return super().variableRefs(self.qnameExpressionProg, varRefSet)

    def evalQname(self, xpCtx, fact):
        parentQname = self.parentQname
        if parentQname:
            return parentQname
        try:
            return xpCtx.evaluateAtomicValue(self.qnameExpressionProg, 'xs:QName', fact)
        except:
            return None
    
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts if cmplmt ^ ( self.evalQname(xpCtx,fact) == fact.parentQname ) ]
    
   
    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("parent", self.parentQname) if self.parentQname else () ,
                ("parentExpression", self.qnameExpression) if self.qnameExpression else () )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.parentQname if self.parentQname else self.qnameExpression

class ModelLocationFilter(ModelFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.LOCATION}
        
    @property
    def location(self):
        return self.get("location")
    
    @property
    def variable(self):
        return qname(self, self.get("variable"), noPrefixIsNoNamespace=True) if self.get("variable") else None
    
    def compile(self):
        if not hasattr(self, "locationProg"):
            self.locationProg = XPathParser.parse(self, self.location, self, "locationProg", Trace.VARIABLE)
            super().compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        if self.variable: 
            if varRefSet is None: varRefSet = set()
            varRefSet.add(self.variable)
        return super().variableRefs(None, varRefSet)

    def evalLocation(self, xpCtx, fact):
        try:
            return set(xpCtx.flattenSequence(xpCtx.evaluate(self.locationProg, fact)))
        except:
            return set()
    
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        varFacts = xpCtx.inScopeVars.get(self.variable,[])
        if isinstance(varFacts,ModelFact):
            candidateElts = {varFacts}
        elif isinstance(varFacts,(list,tuple)):
            candidateElts = set(f for f in varFacts if isinstance(f,ModelFact)) 
        return [fact for fact in facts 
                if cmplmt ^ ( len(candidateElts & self.evalLocation(xpCtx,fact) ) > 0 ) ]
   
    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("location", self.location),
                ("variable", self.variable) )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return "{0} {1}".format(self.location, self.variable)

class ModelSiblingFilter(ModelFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.LOCATION}
        
    @property
    def variable(self):
        return qname(self, self.get("variable"), noPrefixIsNoNamespace=True) if self.get("variable") else None
    
    def variableRefs(self, progs=[], varRefSet=None):
        if self.variable: 
            if varRefSet is None: varRefSet = set()
            varRefSet.add(self.variable)
        return super().variableRefs(None, varRefSet)

    def filter(self, xpCtx, varBinding, facts, cmplmt):
        otherFact = xpCtx.inScopeVars.get(self.variable)
        if isinstance(otherFact,(list,tuple)) and len(otherFact) > 0:
            otherFactParent = otherFact[0].parentElement
        elif isinstance(otherFact,ModelFact):
            otherFactParent = otherFact.parentElement
        else:
            otherFactParent = None
        return [fact for fact in facts 
                if cmplmt ^ (fact.parentElement == otherFactParent)] 

    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("variable", self.variable) )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.variable

class ModelGeneralMeasures(ModelTestFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.UNIT}
        
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ (not fact.isItem or 
                             (fact.isNumeric and self.evalTest(xpCtx, fact.unit)))] 
    
class ModelSingleMeasure(ModelFilter):
    def _init(self):
        return super()._init()

    def aspectsCovered(self, varBinding):
        return {Aspect.UNIT}
        
    @property
    def measureQname(self):
        measureQname = XmlUtil.descendant(self, XbrlConst.uf, "qname")
        if measureQname:
            return qname( measureQname, XmlUtil.text(measureQname) )
        return None
    
    @property
    def qnameExpression(self):
        qnameExpression = XmlUtil.descendant(self, XbrlConst.uf, "qnameExpression")
        if qnameExpression:
            return XmlUtil.text(qnameExpression)
        return None
    
    def compile(self):
        if not hasattr(self, "qnameExpressionProg"):
            self.qnameExpressionProg = XPathParser.parse(self, self.qnameExpression, self, "qnameExpressionProg", Trace.VARIABLE)
            super().compile()
        
    def evalQname(self, xpCtx, fact):
        measureQname = self.measureQname
        if measureQname:
            return measureQname
        try:
            return xpCtx.evaluateAtomicValue(self.qnameExpressionProg, 'xs:QName', fact)
        except:
            return None
    
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ (fact.isNumeric and 
                             fact.unit.isSingleMeasure and
                             (fact.unit.measures[0][0] == self.evalQname(xpCtx,fact)))] 
    
    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("measure", self.qname) if self.qname else () ,
                ("measureExpr", self.qnameExpression) if self.qnameExpression else () )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.qname if self.qname else self.qnameExpression

class ModelNilFilter(ModelFilter):
    def _init(self):
        return super()._init()

    def filter(self, xpCtx, varBinding, facts, cmplmt):
        return [fact for fact in facts 
                if cmplmt ^ fact.isNil] 
    
class ModelPrecisionFilter(ModelFilter):
    def _init(self):
        return super()._init()

    @property
    def minimum(self):
        return self.get("minimum")
    
    def filter(self, xpCtx, varBinding, facts, cmplmt):
        from arelle.ValidateXbrlCalcs import inferredPrecision
        minimum = self.minimum
        numMinimum = float('INF') if minimum == 'INF' else int(minimum)
        return [fact for fact in facts 
                if cmplmt ^ (self.minimum != 'INF' and
                             not fact.isNil and
                             fact.isNumeric and not fact.isFraction and
                             inferredPrecision(fact) >= numMinimum)] 

    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("minimum", self.minimum) )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.minimum

class ModelMessage(ModelFormulaResource):
    def _init(self):
        return super()._init()

    @property
    def separator(self):
        return self.get("separator")
    
    def compile(self):
        if not hasattr(self, "expressionProgs") and hasattr(self, "expressions"):
            self.expressionProgs = []
            i = 1
            for expression in self.expressions:
                name = "qnameExpression_{0}".format(i)
                self.expressionProgs.append( XPathParser.parse( self, expression, self, name, Trace.MESSAGE ) )
                i += 1
            super().compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        try:
            return super().variableRefs(self.expressionProgs, varRefSet)
        except AttributeError:
            return set()    # no expressions

    def evaluate(self, xpCtx):
        return self.formatString.format([xpCtx.evaluateAtomicValue(p, 'xs:string') for p in self.expressionProgs])

    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("separator", self.separator) if self.separator else (),
                ("text", self.text) )
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return self.minimum

class ModelCustomFunctionSignature(ModelFormulaResource):
    def _init(self):
        if super()._init():
            self.modelXbrl.modelCustomFunctionSignatures[self.qname] = self
            self.customFunctionImplementation = None
            return True
        return False

    @property
    def descendantArcroles(self):
        return (XbrlConst.functionImplementation,)
        
    @property
    def name(self):
        try:
            return self._name
        except AttributeError:
            self._name = self.get("name")
            return self._name
    
    @property
    def qname(self):
        try:
            return self._qname
        except AttributeError:
            self._qname = self.prefixedNameQname(self.name)
            return self._qname
    
    @property
    def outputType(self):
        try:
            return self._outputType
        except AttributeError:
            self._outputType = self.get("output")
            return self._outputType
    
    @property
    def inputTypes(self):
        try:
            return self._inputTypes
        except AttributeError:
            self._inputTypes = [elt.get("type")
                                for elt in XmlUtil.children(self, XbrlConst.variable, "input")]
            return self._inputTypes
    
    @property
    def propertyView(self):
        return (("label", self.xlinkLabel),
                ("name", self.name),
                ("output type", self.outputType) ) + \
                tuple((_("input {0}").format(i+1), type) for i,type in enumerate(self.inputTypes))
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
    @property
    def viewExpression(self):
        return _("{0}({1}) as {2}").format(self.name, ", ".join(self.inputTypes), self.outputType)


class ModelCustomFunctionImplementation(ModelFormulaResource):
    def _init(self):
        if super()._init():
            self.modelXbrl.modelCustomFunctionImplementations.add(self)
            return True
        return False

    @property
    def inputNames(self):
        try:
            return self._inputNames
        except AttributeError:
            self._inputNames = [qname(elt, elt.get("name"))
                                for elt in XmlUtil.children(self, XbrlConst.cfi, "input")]
            return self._inputNames
    
    @property
    def stepExpressions(self):
        try:
            return self._stepExpressions
        except AttributeError:
            self._stepExpressions = [(qname(elt, elt.get("name")), elt.text)
                                     for elt in XmlUtil.children(self, XbrlConst.cfi, "step")]
            return self._stepExpressions
    
    @property
    def outputExpression(self):
        try:
            return self._outputExpression
        except AttributeError:
            outputElt = XmlUtil.child(self, XbrlConst.cfi, "output")
            self._outputExpression = XmlUtil.text(outputElt) if outputElt else None
            return self._outputExpression
    
    def compile(self):
        if not hasattr(self, "outputProg"):
            elt = XmlUtil.child(self, XbrlConst.cfi, "output")
            self.outputProg = XPathParser.parse( self, XmlUtil.text(elt), elt, "output", Trace.CUSTOM_FUNCTION )
            self.stepProgs = []
            for elt in XmlUtil.children(self, XbrlConst.cfi, "step"):
                name = "qnameExpression_{0}".format(qname(elt, elt.get("name")))
                self.stepProgs.append( XPathParser.parse( self, elt.text, elt, name, Trace.CUSTOM_FUNCTION ) )
            super().compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        return super().variableRefs([self.outputProg] + self.stepProgs, varRefSet)

    @property
    def propertyView(self):
        return ((("label", self.xlinkLabel),) + \
                tuple((_("input {0}").format(i+1), str(name)) for i,name in enumerate(self.inputNames)) + \
                tuple((_("step {0}").format(str(qname)), expr) for qname,expr in enumerate(self.stepExpressions)) + \
                (("output", self.outputExpression),))
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))

    @property
    def viewExpression(self):
        return ' \n'.join([_("step ${0}: \n{1}").format(str(qname),expr) for qname,expr in self.stepExpressions] +
                          [_("output: \n{0}").format(self.outputExpression)])
    

from arelle.ModelObjectFactory import elementSubstitutionModelClass
elementSubstitutionModelClass.update((
     (XbrlConst.qnAssertionSet, ModelAssertionSet),
     (XbrlConst.qnConsistencyAssertion, ModelConsistencyAssertion),
     (XbrlConst.qnExistenceAssertion, ModelExistenceAssertion),
     (XbrlConst.qnValueAssertion, ModelValueAssertion),
     (XbrlConst.qnFormula, ModelFormula),
     (XbrlConst.qnParameter, ModelParameter),
     (XbrlConst.qnInstance, ModelInstance),
     (XbrlConst.qnFactVariable, ModelFactVariable),
     (XbrlConst.qnGeneralVariable, ModelGeneralVariable),
     (XbrlConst.qnPrecondition, ModelPrecondition),
     (XbrlConst.qnAspectCover, ModelAspectCover),
     (XbrlConst.qnAndFilter, ModelAndFilter),
     (XbrlConst.qnOrFilter, ModelOrFilter),
     (XbrlConst.qnConceptName, ModelConceptName),
     (XbrlConst.qnConceptBalance, ModelConceptBalance),
     (XbrlConst.qnConceptPeriodType, ModelConceptPeriodType),
     (XbrlConst.qnConceptCustomAttribute, ModelConceptCustomAttribute),
     (XbrlConst.qnConceptDataType, ModelConceptDataType),
     (XbrlConst.qnConceptSubstitutionGroup, ModelConceptSubstitutionGroup),
     (XbrlConst.qnConceptRelation, ModelConceptRelation),
     (XbrlConst.qnExplicitDimension, ModelExplicitDimension),
     (XbrlConst.qnTypedDimension, ModelTypedDimension),
     (XbrlConst.qnEntityIdentifier, ModelEntityIdentifier),
     (XbrlConst.qnEntitySpecificIdentifier, ModelEntitySpecificIdentifier),
     (XbrlConst.qnEntitySpecificScheme, ModelEntityScheme),
     (XbrlConst.qnEntityRegexpIdentifier, ModelEntityRegexpIdentifier),
     (XbrlConst.qnEntityRegexpScheme, ModelEntityRegexpScheme),
     (XbrlConst.qnGeneral, ModelGeneral),
     (XbrlConst.qnMatchConcept, ModelMatchFilter),
     (XbrlConst.qnMatchDimension, ModelMatchFilter),
     (XbrlConst.qnMatchEntityIdentifier, ModelMatchFilter),
     (XbrlConst.qnMatchLocation, ModelMatchFilter),
     (XbrlConst.qnMatchNonXDTScenario, ModelMatchFilter),
     (XbrlConst.qnMatchNonXDTSegment, ModelMatchFilter),
     (XbrlConst.qnMatchPeriod, ModelMatchFilter),
     (XbrlConst.qnMatchScenario, ModelMatchFilter),
     (XbrlConst.qnMatchSegment, ModelMatchFilter),
     (XbrlConst.qnMatchUnit, ModelMatchFilter),
     (XbrlConst.qnPeriod, ModelPeriod),
     (XbrlConst.qnPeriodStart, ModelPeriodStart),
     (XbrlConst.qnPeriodEnd, ModelPeriodEnd),
     (XbrlConst.qnPeriodInstant, ModelPeriodInstant),
     (XbrlConst.qnForever, ModelForever),
     (XbrlConst.qnInstantDuration, ModelInstantDuration),
     (XbrlConst.qnRelativeFilter, ModelRelativeFilter),
     (XbrlConst.qnSegmentFilter, ModelSegmentFilter),
     (XbrlConst.qnScenarioFilter, ModelScenarioFilter),
     (XbrlConst.qnAncestorFilter, ModelAncestorFilter),
     (XbrlConst.qnLocationFilter, ModelLocationFilter),
     (XbrlConst.qnSiblingFilter, ModelSiblingFilter),
     (XbrlConst.qnParentFilter, ModelParentFilter),
     (XbrlConst.qnSingleMeasure, ModelSingleMeasure),
     (XbrlConst.qnGeneralMeasures, ModelGeneralMeasures),
     (XbrlConst.qnNilFilter, ModelNilFilter),
     (XbrlConst.qnPrecisionFilter, ModelPrecisionFilter),
     (XbrlConst.qnMessage, ModelMessage),
     (XbrlConst.qnCustomFunctionSignature, ModelCustomFunctionSignature),
     (XbrlConst.qnCustomFunctionImplementation, ModelCustomFunctionImplementation),
     ))

