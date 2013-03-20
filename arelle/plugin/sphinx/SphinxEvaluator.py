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
                           astFormulaRule, astReportRule,
                           astVariableReference)
from .SphinxMethods import (methodImplementation, functionImplementation, 
                            aggreateFunctionImplementation, aggreateFunctionAcceptsFactArgs,
                            moduleInit as SphinxMethodsModuleInit)
from arelle.ModelFormulaObject import Aspect
from arelle.ModelValue import QName
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelXbrl import DEFAULT, NONDEFAULT, DEFAULTorNONDEFAULT
from arelle import XbrlConst, XmlUtil

class SphinxException(Exception):
    def __init__(self, node, code, message, **kwargs ):
        self.node = node
        self.code = code
        self.message = message
        self.kwargs = kwargs
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _('[{0}] exception: {1} at {2}').format(self.code, self.message % self.kwargs, self.node.sourceFileLine)
            
class SphinxSpecialValue:
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return self.name

UNBOUND = SphinxSpecialValue("unbound")
NONE = SphinxSpecialValue("none")


def evaluateRuleBase(sphinxContext):
    
    # clear any residual values
    for constantNode in sphinxContext.constants.values():
        constantNode.value = None
        
    clearEvaluation(sphinxContext)
    
    # check any rule-base preconditions
    for preconditionNode in sphinxContext.ruleBasePreconditionNodes:
        preconditionPasses = evaluate(preconditionNode, sphinxContext)
        clearEvaluation(sphinxContext)
        if not preconditionPasses:
            return
        
    # evaluate rules
    for ruleProg in sphinxContext.rules:
        evaluate(ruleProg, sphinxContext)
        clearEvaluation(sphinxContext)
        
    # dereference constants
    for constantNode in sphinxContext.constants.values():
        constantNode.value = None
        
def clearEvaluation(sphinxContext):
    sphinxContext.tags.clear()
    sphinxContext.localVariables.clear()
    while sphinxContext.hyperspaceBindings:
        sphinxContext.hyperspaceBindings.close() # resets sphinxContext.hyperspaceBindings to parent bindings
        
def evaluate(node, sphinxContext, value=False, fallback=None, hsBoundFact=False):
    if isinstance(node, astNode):
        if fallback is None:
            result = evaluator[node.__class__.__name__](node, sphinxContext)
        else:
            try:
                result = evaluator[node.__class__.__name__](node, sphinxContext)
            except StopIteration:
                if sphinxContext.formulaOptions.traceVariableSetExpressionEvaluation:
                    sphinxContext.modelXbrl.info("sphinx:trace",
                         _("%(node)s has unbound evaluation"), 
                         sourceFileLine=node.sourceFileLine, node=str(node))
                return fallback
        if sphinxContext.formulaOptions.traceVariableSetExpressionEvaluation:
            sphinxContext.modelXbrl.info("sphinx:trace",
                 _("%(node)s evaluation: %(value)s"), 
                 sourceFileLine=node.sourceFileLine, node=str(node), value=result)
        if result is not None:
            if isinstance(result, HyperspaceBinding):
                if hsBoundFact:  # return fact, not the value of fact
                    return result.yieldedFact
                elif value:
                    return result.value
            # dereference nodes to their value
            if (value or hsBoundFact) and isinstance(result, astNode):
                return evaluate(result, sphinxContext, value, fallback, hsBoundFact)
            return result
        return result
    elif isinstance(node, (tuple,list)):
        return [evaluate(item, sphinxContext, value, fallback, hsBoundFact)
                for item in node]
    elif isinstance(node, set):
        return set(evaluate(item, sphinxContext, value, fallback, hsBoundFact)
                   for item in node)
    else:
        return node

def evaluateAnnotationDeclaration(node, sphinxContext):
    return None

def evaluateBinaryOperation(node, sphinxContext):
    leftValue = evaluate(node.leftExpr, sphinxContext, value=True, fallback=UNBOUND)
    rightValue = evaluate(node.rightExpr, sphinxContext, value=True, fallback=UNBOUND)
    op = node.op
    if sphinxContext.formulaOptions.traceVariableExpressionEvaluation:
        sphinxContext.modelXbrl.info("sphinx:trace",
             _("Binary op %(op)s v1: %(leftValue)s, v2: %(rightValue)s"), 
             sourceFileLine=node.sourceFileLine, op=op, leftValue=leftValue, rightValue=rightValue)
    if op == ":=":
        if sphinxContext.ruleNode.bind  == "left":
            if rightValue is UNBOUND: raise StopIteration
        elif sphinxContext.ruleNode.bind  == "right":
            if leftValue is UNBOUND: raise StopIteration
        elif sphinxContext.ruleNode.bind  == "either":
            if leftValue is UNBOUND and rightValue is UNBOUND: raise StopIteration
        else: # both or default
            if leftValue is UNBOUND or rightValue is UNBOUND: raise StopIteration
        return (leftValue, rightValue)
    elif op in {"|+|", "|+", "+|", "+", "|-|", "|-", "-|", "-"}:
        if leftValue is UNBOUND: 
            if op[0] == '|':
                raise StopIteration
            else:
                leftValue = 0
        if rightValue is UNBOUND:
            if op[-1] == '|':
                raise StopIteration
            else:
                rightValue = 0
    else:
        if leftValue is UNBOUND:
            return UNBOUND
        if rightValue is UNBOUND:
            if op == "or" and leftValue:
                return True
            return UNBOUND
        if op == "/" and rightValue == 0:  # prevent divide by zero
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
             _("Operation \"%(op)s\" not implemented for %(node)s"), 
             sourceFileLine=node.sourceFileLine, op=op, node=str(node))
    except (TypeError, ZeroDivisionError) as err:
        sphinxContext.modelXbrl.error("sphinx:error",
             _("Operation \"%(op)s\" raises exception %(error)s for %(node)s"), 
             sourceFileLine=node.sourceFileLine, op=op, node=str(node), error=str(err))
    return None

def evaluateConstant(node, sphinxContext):
    if node.value is None: # first time
        hsBindings = HyperspaceBindings(sphinxContext)  # must have own hsBindings from caller
        previousLocalVariables = sphinxContext.localVariables # save local variables
        sphinxContext.localVariables = {}
        node.value = evaluate(node.expr, sphinxContext)
        if sphinxContext.formulaOptions.traceVariableSetExpressionEvaluation:
            sphinxContext.modelXbrl.info("sphinx:trace",
                 _("Constant %(name)s assigned value: %(value)s"), 
                 sourceFileLine=node.sourceFileLine, name=node.constantName, value=node.value)
        hsBindings.close()
        sphinxContext.localVariables = previousLocalVariables
    return node.value

def evaluateFor(node, sphinxContext):
    # add a hyperspaceBinding to sphinxContext for this node
    hsBindings = sphinxContext.hyperspaceBindings
    forBinding = hsBindings.forBinding(node)
    # set variable here because although needed for next() operation, will be cleared outside of for's context
    sphinxContext.localVariables[node.name] = forBinding.yieldedValue
    return evaluate(node.expr, sphinxContext)

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
    
    if name in aggreateFunctionImplementation:
        return evaluateAggregateFunction(node, sphinxContext, name)

    if name in sphinxContext.functions:  # user defined function
        resolveValues = sphinxContext.functions[name].functionType == "function"
        namedParametersAssignedTo = sphinxContext.localVariables
    else:
        resolveValues = True
        if name in ("error", "warning", "info", "pass"):
            namedParametersAssignedTo = sphinxContext.tags
        else:
            namedParametersAssignedTo = sphinxContext.localVariables
    
    # evaluate local variables
    for localVar in node.localVariables:
        evaluate(localVar, sphinxContext)
    # evaluate args
    args = []
    tagName = None
    l = len(node.args)
    for i in range(l):
        arg = node.args[i]
        if arg == "=":
            if i > 0:
                tagName = node.args[i-1]
        elif i == l - 1 or node.args[i+1] != "=":
            if resolveValues: # macros pass in the argument, not value
                arg = evaluate(arg, sphinxContext, value=True)
            elif (isinstance(arg, astVariableReference) and 
                  getattr(sphinxContext.localVariables.get(arg.variableName),
                          "isMacroParameter", False)):
                # pass original macro parameter, not a reference to it (otherwise causes looping)
                arg = sphinxContext.localVariables[arg.variableName]
            elif isinstance(arg, astNode):
                arg.isMacroParameter = True
            args.append(arg)
            if tagName:
                namedParametersAssignedTo[tagName] = arg
            tagName = None
            
    if name in ("error", "warning", "info", "pass"):
        result = None
    
    # call function here
    elif name in sphinxContext.functions:  # user defined function
        result = evaluateFunctionDeclaration(sphinxContext.functions[name], sphinxContext, args)
        
    # call built-in functions
    elif name in functionImplementation:
        result = functionImplementation[name](node, sphinxContext, args)
    
    else:
        raise SphinxException(node, 
                              "sphinx:functionName", 
                              _("unassigned function name %(name)s"),
                              name=name)
        
    # remove local variables
    for localVar in node.localVariables:
        del sphinxContext.localVariables[localVar.name]
    return result
    
def evaluateAggregateFunction(node, sphinxContext, name):
    # determine if evaluating args found hyperspace (first time)
    args = []
    iterateAbove, bindingsLen = getattr(node, "aggregationHsBindings", (None, None))
    firstTime = bindingsLen is None
    hsBindings = sphinxContext.hyperspaceBindings
    parentAggregationNode = hsBindings.aggregationNode
    parentIsValuesIteration = hsBindings.isValuesIteration
    hsBindings.aggregationNode = node # block removing nested aspect bindings
    hsBindings.isValuesIteration = False
    prevHsBindingsLen = len(hsBindings.hyperspaceBindings)
    hsBoundFact = aggreateFunctionAcceptsFactArgs[name]
    arg = node.args[0]
    try:
        while (True):   # possibly multiple bindings
            # evaluate local variables
            for localVar in node.localVariables:
                evaluate(localVar, sphinxContext)
                
            value = evaluate(arg, sphinxContext, value=True, hsBoundFact=hsBoundFact)
            if isinstance(value, (list,set)):
                for listArg in value:
                    if value is not UNBOUND:
                        args.append(evaluate(listArg, sphinxContext, value=True))
            elif value is not UNBOUND:
                args.append(value)
            if firstTime:
                if len(hsBindings.hyperspaceBindings) == prevHsBindingsLen:
                    # no hs bindings, just scalar
                    break
                else:    # has hs bindings, evaluate rest of them
                    firstTime = False
                    iterateAbove = prevHsBindingsLen - 1
                    bindingsLen = len(hsBindings.hyperspaceBindings)
                    node.aggregationHsBindings = (iterateAbove, bindingsLen)
            hsBindings.next(iterateAbove, bindingsLen)
    except StopIteration:
        pass # no more bindings
    hsBindings.isValuesIteration = parentIsValuesIteration
    hsBindings.aggregationNode = parentAggregationNode
    # remove local variables
    for localVar in node.localVariables:
        if localVar in sphinxContext.localVariables:
            del sphinxContext.localVariables[localVar.name]
    if sphinxContext.formulaOptions.traceVariableExpressionEvaluation:
        sphinxContext.modelXbrl.info("sphinx:trace",
             _("Aggregative function %(name)s arguments: %(args)s"), 
             sourceFileLine=node.sourceFileLine, name=name, 
             args=",".join(str(a) for a in args))
    try:
        return aggreateFunctionImplementation[name](node, sphinxContext, args)
    except (TypeError, ZeroDivisionError) as err:
        sphinxContext.modelXbrl.error("sphinx:error",
             _("Function %(name)s raises exception %(error)s in %(node)s"), 
             sourceFileLine=node.sourceFileLine, name=name, node=str(node), error=str(err))
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

def evaluateMessage(node, sphinxContext, resultTags, hsBindings):
    def evaluateTagExpr(tagExpr, modifier):
        if modifier == "value":
            value = evaluate(tagExpr, sphinxContext, value=True)
        elif modifier == "context":
            value = contextView(sphinxContext, tagExpr)
        else:
            value = "{0} {1}".format(evaluate(tagExpr, sphinxContext, value=True), 
                                     contextView(sphinxContext))
        return value
    
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
                    value = contextView(sphinxContext),
                elif tag in resultTags:
                    value = evaluateTagExpr(resultTags.tags[tag], modifier)
                elif tag in sphinxContext.tags:
                    value = evaluateTagExpr(sphinxContext.tags[tag], modifier)
                elif tag in sphinxContext.taggedConstants:
                    value = evaluateTagExpr(evaluateConstant(sphinxContext.taggedConstants[tag], sphinxContext), modifier)
                elif tag in ("trace", "left", "right", "difference"):
                    value = 'Tag "{0}" is not yet supported'.format(tag)
                else:
                    sphinxContext.modelXbrl.log("ERROR", "sphinx.unboundMessageTag",
                                                _("Validation rule tag %(tag)s is not Bound"),
                                                sourceFileLine=node.sourceFileLine,
                                                tag=tag)
                    value = "${" + tag + "}"
                args.append(value)
                
                i = k + 1
        else:
            text.append(msgstr[i:])
            break
    messageStr = ''.join(text)
    return messageStr.format(*args)

def evaluateMethodReference(node, sphinxContext):
    args = []
    for i, nodeArg in enumerate(node.args):
        arg = evaluate(nodeArg, 
                       sphinxContext, 
                       value=True,
                       hsBoundFact=(i == 0)) # don't deref arg 0
        args.append(arg)
    return methodImplementation.get(node.name,                       # requested method
                                    methodImplementation["unknown"]  # default if missing method
                                    )(node, sphinxContext, args)

def evaluateNoOp(node, sphinxContext):
    return None

def evaluateNumericLiteral(node, sphinxContext):
    return node.value

def evaluatePreconditionDeclaration(node, sphinxContext):
    hsBindings = HyperspaceBindings(sphinxContext)
    result = evaluate(node.expr, sphinxContext, value=True)
    hsBindings.close()
    return result

def evaluatePreconditionReference(node, sphinxContext):
    preconditionPasses = True
    for name in node.names:
        if name in sphinxContext.preconditionNodes:
            if not evaluate(sphinxContext.preconditionNodes[name], sphinxContext, value=True):
                preconditionPasses = False
            clearEvaluation(sphinxContext)
            if not preconditionPasses:
                break
    return preconditionPasses

def evaluateQnameLiteral(node, sphinxContext):
    return node.value

def evaluateReportRule(node, sphinxContext):
    return None

def evaluateRuleBasePrecondition(node, sphinxContext):
    if node.precondition:
        return evaluate(node.precondition, sphinxContext, value=True)
    return True

def evaluateStringLiteral(node, sphinxContext):
    return node.text

def evaluateTagAssignment(node, sphinxContext):
    result = evaluate(node.expr, sphinxContext, value=True)
    sphinxContext.tags[node.tagName] = result
    return result

def evaluateTagReference(node, sphinxContext):
    try:
        return sphinxContext.tags[node.name]
    except KeyError:
        raise SphinxException(node, 
                              "sphinx:tagName", 
                              _("unassigned tag name %(name)s"),
                              name=node.name )

def evaluateRule(node, sphinxContext):
    isFormulaRule = isinstance(node, astFormulaRule)
    isReportRule = isinstance(node, astReportRule)
    name = (node.name or ("sphinx.report" if isReportRule else "sphinx.raise"))
    nodeId = node.nodeTypeName + ' ' + name
    if node.precondition:
        result = evaluate(node.precondition, sphinxContext, value=True)
        if sphinxContext.formulaOptions.traceVariableSetExpressionResult:
            sphinxContext.modelXbrl.info("sphinx:trace",
                 _("%(node)s precondition evaluation: %(value)s"), 
                 sourceFileLine=node.sourceFileLine, node=nodeId, value=result)
        if not result:
            return None 
    # nest hyperspace binding
    sphinxContext.ruleNode = node
    hsBindings = None
    ruleIteration = 0
    try:
        hsBindings = HyperspaceBindings(sphinxContext)
        while True:
            ruleIteration += 1
            sphinxContext.dynamicSeverity = None
            sphinxContext.tags.clear()
            sphinxContext.localVariables.clear()
            if sphinxContext.formulaOptions.traceVariableSetExpressionResult:
                sphinxContext.modelXbrl.info("sphinx:trace",
                     _("%(node)s starting iteration %(iteration)s"), 
                     sourceFileLine=node.sourceFileLine, node=nodeId, iteration=ruleIteration)
            for varAssignNode in node.variableAssignments:
                evaluateVariableAssignment(varAssignNode, sphinxContext)
            result = evaluate(node.expr, sphinxContext, value=True)
            if result is UNBOUND:
                result = None # nothing to do for this pass
            elif isFormulaRule:
                left, right = result
                if left is UNBOUND:
                    difference = UNBOUND
                elif right is UNBOUND:
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
            if sphinxContext.formulaOptions.traceVariableSetExpressionResult:
                sphinxContext.modelXbrl.info("sphinx:trace",
                     _("%(node)s result %(result)s %(severity)s iteration %(iteration)s"), 
                     sourceFileLine=node.sourceFileLine, node=nodeId, iteration=ruleIteration,
                     result=result,
                     severity=(sphinxContext.dynamicSeverity or node.severity or 
                               ("info" if isReportRule else "error")))
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
    except StopIteration:
        if sphinxContext.formulaOptions.traceVariableSetExpressionResult:
            sphinxContext.modelXbrl.info("sphinx:trace",
                 _("%(node)s StopIteration"), 
                 sourceFileLine=node.sourceFileLine, node=nodeId)
    except SphinxException as ex:
        sphinxContext.modelXbrl.log("ERROR",
                                    ex.code,
                                    _("Exception in %(node)s: %(exception)s"),
                                    node=nodeId,
                                    ruleName=name,
                                    exception=ex.message % ex.kwargs,
                                    sourceFileLine=[node.sourceFileLine] + ([ex.node.sourceFileLine] if ex.node is not node else []),
                                    **ex.kwargs)
    if hsBindings is not None:
        hsBindings.close()
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
                  'values': noop,
                  }[node.op](value)
        return result
    except KeyError:
        sphinxContext.modelXbrl.error("sphinx:error",
             _("%(node)s operation %(op)s not implemented"), 
             modelObject=node, op=node.op)
    return None

def evaluateValuesIteration(node, sphinxContext):
    hsBindings = sphinxContext.hyperspaceBindings
    if hsBindings.aggregationNode is None:
        sphinxContext.modelXbrl.error("sphinx:warning",
             _("Values iteration expected to be nested in an aggregating function"), 
             modelObject=node)
    else:
        hsBindings.isValuesIteration = True
    return evaluate(node.expr, sphinxContext)

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
        if node.variableName in sphinxContext.constants:
            return evaluateConstant(sphinxContext.constants[node.variableName], sphinxContext)
        raise SphinxException(node, 
                              "sphinx:variableName", 
                              _("unassigned variable name %(name)s"),
                              name=node.variableName)

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
                                   factAspectValue(fact, aspect, view=True))
                                   for aspect, fact in sphinxContext.hyperspaceBindings.aspectBoundFacts.items()
                                   if factAspectValue(fact, aspect) and aspect != Aspect.CONCEPT))
    else:
        return "[{0}]".format(", ".join("{0}={1}".format(aspectName(aspect), 
                                   factAspectValue(fact, aspect, view=True))
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

def factAspectValue(fact, aspect, view=False):
    if fact is DEFAULT:
        return 'none'
    elif fact is NONDEFAULT:
        return '*'
    elif fact is DEFAULTorNONDEFAULT:
        return '**'
    elif aspect == Aspect.LOCATION:
        parentQname = fact.getparent().qname
        if parentQname == XbrlConst.qnXbrliXbrl: # not tuple
            return NONE
        return parentQname # tuple
    elif aspect == Aspect.CONCEPT:
        return fact.qname
    elif fact.isTuple or fact.context is None:
        return NONE     #subsequent aspects don't exist for tuples
    elif aspect == Aspect.UNIT:
        if fact.unit is None:
            return NONE
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
            if view:
                return context.entityIdentifier[1]
            else:
                return context.entityIdentifier  # (scheme, identifier)
        elif aspect in (Aspect.COMPLETE_SEGMENT, Aspect.COMPLETE_SCENARIO,
                        Aspect.NON_XDT_SEGMENT, Aspect.NON_XDT_SCENARIO):
            return ''.join(XmlUtil.xmlstring(elt, stripXmlns=True, prettyPrint=True)
                           for elt in context.nonDimValues(aspect))
        elif aspect == Aspect.DIMENSIONS:
            return context.dimAspects(fact.xpCtx.defaultDimensionAspects)
        elif isinstance(aspect, QName):
            dimValue = context.dimValue(aspect)
            if dimValue is None:
                return NONE
            else:
                if isinstance(dimValue, QName): #default dim
                    return dimValue
                elif dimValue.isExplicit:
                    return dimValue.memberQname
                else: # explicit
                    return dimValue.typedMember.xValue # typed element value



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
    "astMessage":                 evaluateMessage,
    "astMethodReference":         evaluateMethodReference,
    "astNamespaceDeclaration":    evaluateNoOp,
    "astNode":                    evaluateNoOp,
    "astNoOp":                    evaluateNoOp,
    "astNumericLiteral":          evaluateNumericLiteral,
    "astPreconditionDeclaration": evaluatePreconditionDeclaration,
    "astQnameLiteral":            evaluateQnameLiteral,
    "astReportRule":              evaluateRule,
    "astSourceFile":              evaluateNoOp,
    "astRuleBasePrecondition":    evaluateRuleBasePrecondition,
    "astPreconditionReference":   evaluatePreconditionReference,
    "astStringLiteral":           evaluateStringLiteral,
    "astTagAssignment":           evaluateTagAssignment,
    "astTagReference":            evaluateTagReference,
    "astValidationRule":          evaluateRule,
    "astValuesIteration":         evaluateValuesIteration,
    "astVariableAssignment":      evaluateVariableAssignment,
    "astVariableReference":       evaluateVariableReference,
    "astUnaryOperation":          evaluateUnaryOperation,
    "astWith":                    evaluateWith,
          }
        
SphinxMethodsModuleInit()