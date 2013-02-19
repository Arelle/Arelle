'''
sphinxEvaluator processes the Sphinx language in the context of an XBRL DTS and instance.

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).

Sphinx is a Rules Language for XBRL described by a Sphinx 2 Primer 
(c) Copyright 2012 CoreFiling, Oxford UK. 
Sphinx copyright applies to the Sphinx language, not to this software.
Mark V Systems conveys neither rights nor license for the Sphinx language. 
'''

import operator
from .SphinxContext import HyperspaceBindings, HyperspaceBinding
from .SphinxParser import (astFunctionReference, astHyperspaceExpression, astNode, 
                           astFormulaRule, astReportRule)
from .SphinxMethods import methodImplementation
from arelle.ModelFormulaObject import Aspect
from arelle.ModelValue import QName
from arelle.ModelInstanceObject import ModelFact
from arelle import XbrlConst, XmlUtil

class SphinxException(Exception):
    def __init__(self, node, code, message, objects ):
        self.node = node
        self.code = code
        self.message = message
        self.objects = objects
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _('[{0}] exception at {1} in {2}').format(self.code, self.column, self.message)
            
class UnboundClass:
    def __init__(self, name="unbound"):
        self.name = name
    def __repr__(self):
        return self.name

UNBOUND = UnboundClass()
UNBOUND1 = UnboundClass("unbound1")


def evaluateRuleBase(sphinxContext):
    
    # check any rule-base preconditions
    for file, preconditionNode in sphinxContext.ruleBasePreconditionsNodes:
        if not preconditionNode.evaluate(sphinxContext):
            return
        
    # evaluate rules
    for ruleProg in sphinxContext.rules:
        evaluate(ruleProg, sphinxContext)
        sphinxContext.tags.clear()
        sphinxContext.localVariables.clear()
        sphinxContext.staticSeverity = None
        sphinxContext.dynamicSeverity = None
        
def evaluate(node, sphinxContext, value=False, fallback=None):
    if isinstance(node, astNode):
        if fallback is None:
            result = evaluator[node.__class__.__name__](node, sphinxContext)
        else:
            try:
                result = evaluator[node.__class__.__name__](node, sphinxContext)
            except StopIteration:
                if sphinxContext.formulaOptions.traceVariableSetExpressionResult:
                    sphinxContext.modelXbrl.info("sphinx:trace",
                         _("%(node)s has fallback result"), 
                         modelObject=node, node=str(node))
                return fallback
        if sphinxContext.formulaOptions.traceVariableSetExpressionResult:
            sphinxContext.modelXbrl.info("sphinx:trace",
                 _("%(node)s result: %(result)s"), 
                 modelObject=node, node=str(node), result=result)
        if result is not None and value and isinstance(result, (astNode, HyperspaceBinding)):
            # dereference nodes to their value
            if isinstance(result, astHyperspaceExpression):
                return evaluate(result, sphinxContext, value)
            result = result.value
        return result
    else:
        return node

def evaluateAnnotationDeclaration(node, sphinxContext):
    return None

def evaluateBinaryOperation(node, sphinxContext):
    op = node.op
    leftFallback = rightFallback = 0  # will prevent rule from processing unbound value
    if op == ":=":
        if sphinxContext.ruleNode.bind in ("right", "either"):
            leftFallback = UNBOUND
        else:
            leftFallback = None  # prevent rule from firing if unbound
        if sphinxContext.ruleNode.bind in ("left", "either"):
            rightFallback = UNBOUND
        else:
            rightFallback = None # prevent rule from firing if unbound
    else:
        if op[0] == '|':
            leftFallback = UNBOUND
        if op[-1] == '|':
            rightFallback = UNBOUND
    leftValue = evaluate(node.leftExpr, sphinxContext, value=True, fallback=leftFallback)
    rightValue = evaluate(node.rightExpr, sphinxContext, value=True, fallback=rightFallback)
    if op == ":=":
        return (leftValue, rightValue)
    if leftValue is UNBOUND:
        return UNBOUND
    if rightValue is UNBOUND:
        if op == "or" and leftValue:
            return True
        return UNBOUND
    try:
        result = {'+': operator.add, '-': operator.sub, '*': operator.mul, '/': operator.truediv,
                  '<': operator.lt, '>': operator.gt, '<=': operator.le, '>=': operator.ge,
                  '==': operator.eq, '!=': operator.ne,
                  'and': operator.and_, 'or': operator.or_,
                  }[op](leftValue, rightValue)
        return result
    except KeyError:
        sphinxContext.modelXbrl.error("sphinx:error",
             _("%(node)s operation %(op)s not implemented"), 
             modelObject=node, op=op)
    return None

def evaluateFor(node, sphinxContext):
    collection = evaluate(node.collectionExpr, sphinxContext)
    resultList = []
    priorValue = sphinxContext.localVariables.get(node.name)
    for entry in collection:
        sphinxContext.localVariables[node.name] = entry
        resultList.append(evaluate(node.expr, sphinxContext))
    if priorValue:
        sphinxContext.localVariables[node.name] = priorValue
    return resultList

def evaluateFunctionDeclaration(node, sphinxContext, args):
    overriddenVariables = {}

    if isinstance(args, dict):
        # args may not all be used in the function declaration, just want used ones
        argDict = dict((name, value)
                       for name, value in args.items()
                       if name in node.params)
    else:  # purely positional args      
        # positional parameters named according to function prototype
        if len(args) != len(node.params):
            sphinxContext.modelXbrl.log("ERROR", "sphinx.functionArgumentsMismatch",
                                        _("Function %(name)s requires %(required)s parameters but %(provided)s are provided"),
                                        sourceFileLine=node.sourceFileLine,
                                        name=node.name, required=len(node.params), provided=len(args))
            return None
        argDict = dict((paramName, args[i])
                       for i, paramName in enumerate(node.params))
    for name, value in argDict.items():
        if name in sphinxContext.localVariables:
            overriddenVariables[name] = sphinxContext.localVariables[name]
        sphinxContext.localVariables[name] = value
    
    def clearFunctionArgs():
        for name in argDict.keys():
            del sphinxContext.localVariables[name]
        sphinxContext.localVariables.update(overriddenVariables)
        overriddenVariables.clear()

    try:
        result = evaluate(node.expr, sphinxContext)
        clearFunctionArgs()
        return result
    except StopIteration as ex:
        clearFunctionArgs()
        raise ex  # reraise exception

def evaluateFunctionReference(node, sphinxContext):
    name = node.name
    if name in ("error", "warning", "info", "pass"):
        sphinxContext.dynamicSeverity = node.name
    elif name == "unbound":
        return UNBOUND
    if name in sphinxContext.functions:  # user defined function
        resolveValues = sphinxContext.functions[name].functionType == "function"
    else:
        resolveValues = True
    # evaluate args
    args = []
    tagNames = []
    l = len(node.args)
    for i in range(l):
        arg = node.args[i]
        if arg == "=":
            if i > 0:
                tagNames.append(node.args[i-1])
        elif i == l - 1 or node.args[i+1] != "=":
            arg = evaluate(arg, sphinxContext, value=resolveValues)
            args.append(arg)
            for tag in tagNames:
                sphinxContext.tags[tag] = arg
    # call function here
    if name in sphinxContext.functions:  # user defined function
        return evaluateFunctionDeclaration(sphinxContext.functions[name], sphinxContext, args)
    return None

def evaluateHyperspaceExpression(node, sphinxContext):
    # add a hyperspaceBinding to sphinxContext for this node
    hsBindings = sphinxContext.hyperspaceBindings
    nodeBinding = hsBindings.nodeBinding(node)
    return nodeBinding

def evaluateIf(node, sphinxContext):
    condition = evaluate(node.condition, sphinxContext, value=True)
    if condition:
        expr = node.thenExpr
    else:
        expr = node.elseExpr
    return evaluate(expr, sphinxContext)

def evaluateList(node, sphinxContext):
    collectionExpr = evaluate(node.expr, sphinxContext)
    return list(entry for entry in collectionExpr)

def evaluateMessage(node, sphinxContext, resultTags, hsBindings):
    msgstr = evaluate(node.message, sphinxContext, value=True)
    text = []
    args = []
    i = 0
    while True:
        j = msgstr.find("${", i)
        if j >= 0:
            text.append(msgstr[i:j]) # previous part of string
            k = msgstr.find("}", j+2)
            if k > j:
                text.append("{" + str(len(args)) + "}")
                tag, sep, modifier = msgstr[j+2:k].strip().partition(".")
                if tag == "context":
                    value = sphinxContext(sphinxContext),
                elif tag in resultTags:
                    value = resultTags[tag]
                elif tag in sphinxContext.tags:
                    tagExpr = sphinxContext.tags[tag]
                    if modifier == "value":
                        value = evaluate(tagExpr, sphinxContext, value=True)
                    elif modifier == "context":
                        value = contextView(sphinxContext, tagExpr)
                    else:
                        value = "{0} {1}".format(evaluate(tagExpr, sphinxContext, value=True), 
                                                 contextView(sphinxContext))
                elif tag in ("trace", "left", "right", "difference"):
                    value = 'Tag "{0}" is not yet supported'.format(tag)
                else:
                    sphinxContext.modelXbrl.log("ERROR", "sphinx.unboundMessageTag",
                                                _("Validation rule tag %(tag)s is not Bound"),
                                                sourceFileLine=node.sourceFileLine,
                                                tag=tag)
                    continue
                args.append(value)
                
                i = k + 1
        else:
            text.append(msgstr[i:])
            break
    messageStr = ''.join(text)
    return messageStr.format(*args)

def evaluateMethodReference(node, sphinxContext):
    return methodImplementation.get(node.name,                       # requested method
                                    methodImplementation["unknown"]  # default if missing method
                                    )(node, sphinxContext)

def evaluateNoOp(node, sphinxContext):
    return None

def evaluateNumericLiteral(node, sphinxContext):
    return node.value

def evaluatePreconditionDeclaration(node, sphinxContext):
    return None

def evaluatePreconditionReference(node, sphinxContext):
    return None

def evaluateReportRule(node, sphinxContext):
    return None

def evaluateRuleBasePrecondition(node, sphinxContext):
    return None

def evaluateSet(node, sphinxContext):
    collectionExpr = evaluate(node.expr, sphinxContext)
    return set(entry for entry in collectionExpr)

def evaluateStringLiteral(node, sphinxContext):
    return node.text

def evaluateTagAssignment(node, sphinxContext):
    sphinxContext.tags[node.tagName] = node.expr
    return node.expr

def evaluateTagReference(node, sphinxContext):
    try:
        return sphinxContext.tags[node.name]
    except KeyError:
        raise SphinxException(node, "sphinx:tagName", _("unassigned tag name"))

def evaluateRule(node, sphinxContext):
    isFormulaRule = isinstance(node, astFormulaRule)
    isReportRule = isinstance(node, astReportRule)
    if node.precondition:
        result = evaluate(node.precondition, sphinxContext, value=True)
        if not result:
            return None
    # nest hyperspace binding
    sphinxContext.ruleNode = node
    try:
        hsBindings = HyperspaceBindings(sphinxContext)
        while True:
            for varAssignNode in node.variableAssignments:
                evaluateVariableAssignment(varAssignNode, sphinxContext)
            result = evaluate(node.expr, sphinxContext)
            if isFormulaRule:
                left, right = result
                if isinstance(left, UnboundClass):
                    difference = UNBOUND
                elif isinstance(right, UnboundClass):
                    difference = UNBOUND
                else:
                    difference = abs(left - right)
                result = difference != 0
                resultTags = {"left": left, "right": right, "difference": difference}
                sphinxContext.dynamicSeverity = None
                if node.severity in sphinxContext.functions:
                    evaluateFunctionDeclaration(sphinxContext.functions[node.severity],
                                                sphinxContext,
                                                {"difference": difference, "left": left, "right": right})
                    if sphinxContext.dynamicSeverity is None or sphinxContext.dynamicSeverity == "pass": # don't process pass
                        sphinxContext.dynamicSeverity = None
                        result = False
            else:
                if isReportRule:
                    resultTags = {"value": result}
                else:
                    resultTags = {}
            name = (node.name or ("sphinx.report" if isReportRule else "sphinx.raise"))
            if ((result or isReportRule) or 
                (sphinxContext.dynamicSeverity and sphinxContext.dynamicSeverity != "pass")):
                severity = (sphinxContext.dynamicSeverity or node.severity or 
                            ("info" if isReportRule else "error"))
                if isinstance(severity, astFunctionReference):
                    severity = severity.name
                logSeverity = {"error" : "ERROR", "warning": "WARNING", "info": "INFO"}[severity]
                if node.message:
                    sphinxContext.modelXbrl.log(logSeverity, name, 
                                                evaluateMessage(node.message, sphinxContext, resultTags, hsBindings),
                                                sourceFileLine=[node.sourceFileLine] + 
                                                [(fact.modelDocument.uri, fact.sourceline) for fact in hsBindings.boundFacts],
                                                severity=severity)
                elif isFormulaRule:
                    sphinxContext.modelXbrl.log(logSeverity,
                                                name,
                                                _("Formula %(severity)s difference %(value)s for %(aspects)s"),
                                                sourceFileLine=[node.sourceFileLine] + 
                                                [(fact.modelDocument.uri, fact.sourceline) for fact in hsBindings.boundFacts],
                                                severity=severity,
                                                value=difference,
                                                aspects=contextView(sphinxContext))
                elif isReportRule:
                    sphinxContext.modelXbrl.log(logSeverity,
                                                name,
                                                _("Report %(severity)s %(value)s for %(aspects)s"),
                                                sourceFileLine=[node.sourceFileLine] + 
                                                [(fact.modelDocument.uri, fact.sourceline) for fact in hsBindings.boundFacts],
                                                severity=severity,
                                                value=result,
                                                aspects=contextView(sphinxContext))
                else:
                    sphinxContext.modelXbrl.log(logSeverity,
                                                name,
                                                _("Validation rule %(severity)s for %(aspects)s"),
                                                sourceFileLine=[node.sourceFileLine] + 
                                                [(fact.modelDocument.uri, fact.sourceline) for fact in hsBindings.boundFacts],
                                                severity=severity,
                                                aspects=contextView(sphinxContext))
            hsBindings.next() # raises StopIteration when done
        hsBindings.close()
    except StopIteration:
        pass # no more bindings
    return None

def noop(arg):
    return arg

def evaluateUnaryOperation(node, sphinxContext):
    if node.op == "brackets":  # parentheses around an expression
        return node.expr
    value = evaluate(node.expr, sphinxContext, value=True, fallback=UNBOUND)
    if value is UNBOUND:
        return UNBOUND
    try:
        result = {'+': operator.pos, '-': operator.neg, 'not': operator.not_,
                  'value': noop,
                  }[node.op](value)
        return result
    except KeyError:
        sphinxContext.modelXbrl.error("sphinx:error",
             _("%(node)s operation %(op)s not implemented"), 
             modelObject=node, op=node.op)
    return None

def evaluateVariableAssignment(node, sphinxContext):
    result = evaluate(node.expr, sphinxContext)
    sphinxContext.localVariables[node.variableName] = result
    if node.tagName:
        sphinxContext.tags[node.tagName] = result
    return result

def evaluateVariableReference(node, sphinxContext):
    try:
        return sphinxContext.localVariables[node.variableName]
    except KeyError:
        raise SphinxException(node, "sphinx:variableName", _("unassigned variable name"))

def evaluateWith(node, sphinxContext):
    # covered clauses of withExpr match uncovered aspects of expr
    hsBindings = sphinxContext.hyperspaceBindings
    withRestrictionBinding = hsBindings.nodeBinding(node.restrictionExpr, isWithRestrictionNode=True)
    hsBindings.withRestrictionBindings.append(withRestrictionBinding)
    try:
        for varAssignNode in node.variableAssignments:
            evaluateVariableAssignment(varAssignNode, sphinxContext)
        result = evaluate(node.bodyExpr, sphinxContext)
    except Exception as ex:
        del hsBindings.withRestrictionBindings[-1]
        raise ex    # re-throw the exception after removing withstack entry
    del hsBindings.withRestrictionBindings[-1]
    return result

def contextView(sphinxContext, fact=None):
    if isinstance(fact, ModelFact):
        return "{0}[{1}]".format(fact.qname,
                                 ", ".join("{2}={1}".format(aspectName(aspect), 
                                   factAspectValue(fact, aspect))
                                   for aspect, fact in sphinxContext.hyperspaceBindings.aspectBoundFacts.items()
                                   if factAspectValue(fact, aspect) and aspect != Aspect.CONCEPT))
    else:
        return "[{0}]".format(", ".join("{0}={1}".format(aspectName(aspect), 
                                   factAspectValue(fact, aspect))
                                   for aspect, fact in sphinxContext.hyperspaceBindings.aspectBoundFacts.items()
                                   if factAspectValue(fact, aspect)))
    
def aspectName(aspect):
    if isinstance(aspect, QName):
        return aspect
    return {Aspect.LOCATION: "tuple",
            Aspect.CONCEPT: "primary",
            Aspect.ENTITY_IDENTIFIER: "entity",  
            Aspect.PERIOD: "period", 
            Aspect.UNIT: "unit", 
            Aspect.NON_XDT_SEGMENT: "segment",
            Aspect.NON_XDT_SCENARIO: "scenario",
            }.get(aspect)
    if aspect in Aspect.label:
        return Aspect.label[aspect]
    else:
        return str(aspect)


def factAspectValue(fact, aspect):
    if aspect == Aspect.LOCATION:
        parentQname = fact.getparent().qname
        if parentQname == XbrlConst.qnXbrliXbrl: # not tuple
            return "none"
        return parentQname # tuple
    elif aspect == Aspect.CONCEPT:
        return fact.qname
    elif fact.isTuple or fact.context is None:
        return None     #subsequent aspects don't exist for tuples
    elif aspect == Aspect.UNIT and fact.unit is not None:
        measures = fact.unit.measures
        if measures[1]:
            return "{0} / {1}".format(' '.join(str(m) for m in measures[0]),
                                      ' '.join(str(m) for m in measures[1]))
        else:
            return ' '.join(str(m) for m in measures[0])
    else:
        context = fact.context
        if aspect == Aspect.PERIOD:
            return ("forever" if context.isForeverPeriod else
                XmlUtil.dateunionValue(context.instantDatetime, subtractOneDay=True) if context.isInstantPeriod else
                XmlUtil.dateunionValue(context.startDatetime) + "-" + XmlUtil.dateunionValue(context.endDatetime, subtractOneDay=True))
        elif aspect == Aspect.ENTITY_IDENTIFIER:
            return context.entityIdentifier[1]
        elif aspect in (Aspect.COMPLETE_SEGMENT, Aspect.COMPLETE_SCENARIO,
                        Aspect.NON_XDT_SEGMENT, Aspect.NON_XDT_SCENARIO):
            return ''.join(XmlUtil.xmlstring(elt, stripXmlns=True, prettyPrint=True)
                           for elt in context.nonDimValues(aspect))
        elif aspect == Aspect.DIMENSIONS:
            return context.dimAspects(fact.xpCtx.defaultDimensionAspects)
        elif isinstance(aspect, QName):
            dimValue = context.dimValue(aspect)
            if dimValue is not None:
                if isinstance(dimValue, QName): #default dim
                    return dimValue
                elif dimValue.isExplicit:
                    return dimValue.memberQname
                else: # explicit
                    return XmlUtil.xmlstring(XmlUtil.child(dimValue), stripXmlns=True, prettyPrint=True)



evaluator = {
    "astAnnotationDeclaration":   evaluateAnnotationDeclaration,
    "astBinaryOperation":         evaluateBinaryOperation,
    "astComment":                 evaluateNoOp,
    "astFor":                     evaluateFor,
    "astFormulaRule":             evaluateRule,
    "astFunctionDeclaration":     evaluateFunctionDeclaration,
    "astFunctionReference":       evaluateFunctionReference,
    "astHyperspaceExpression":    evaluateHyperspaceExpression,
    "astIf":                      evaluateIf,
    "astList":                    evaluateList,
    "astMessage":                 evaluateMessage,
    "astMethodReference":         evaluateMethodReference,
    "astNamespaceDeclaration":    evaluateNoOp,
    "astNode":                    evaluateNoOp,
    "astNoOp":                    evaluateNoOp,
    "astNumericLiteral":          evaluateNumericLiteral,
    "astPreconditionDeclaration": evaluatePreconditionDeclaration,
    "astReportRule":              evaluateRule,
    "astSourceFile":              evaluateNoOp,
    "astSet":                     evaluateSet,
    "astRuleBasePrecondition":    evaluateRuleBasePrecondition,
    "astPreconditionReference":   evaluatePreconditionReference,
    "astStringLiteral":           evaluateStringLiteral,
    "astTagAssignment":           evaluateTagAssignment,
    "astTagReference":            evaluateTagReference,
    "astValidationRule":          evaluateRule,
    "astVariableAssignment":      evaluateVariableAssignment,
    "astVariableReference":       evaluateVariableReference,
    "astUnaryOperation":          evaluateUnaryOperation,
    "astWith":                    evaluateWith,
          }
        
