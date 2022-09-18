'''
cdrValidator validates CDR Formula select expressions in the context of an XBRL DTS and instance.

(c) Copyright 2014 Mark V Systems Limited, California US, All rights reserved.  
'''
import operator
from arelle.ModelFormulaObject import Aspect
from arelle.ModelValue import QName
from arelle.ModelInstanceObject import ModelFact
from arelle import XbrlConst, XmlUtil
from .cdrParser import (astBinaryOperation, astSourceFile, 
                        astConstant, astStringLiteral, 
                        astFunctionReference, astNode,
                        )
from .cdrFunctions import (functionImplementation, 
                           moduleInit as CdrFunctionsModuleInit)

class CdrException(Exception):
    def __init__(self, node, code, message, **kwargs ):
        self.node = node
        self.code = code
        self.message = message
        self.kwargs = kwargs
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _('[{0}] exception: {1} at {2}').format(self.code, self.message % self.kwargs, self.node.sourceFileLine)
            
class CdrSpecialValue:
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return self.name

UNBOUND = CdrSpecialValue("unbound")
NONE = CdrSpecialValue("none")

def evaluateFormulas(cdrContext):
    
    clearEvaluation(cdrContext)
    
    # evaluate rules
    for formulaQname in cdrContext.orderedFormulaQnames:
        formula = cdrContext.cdrFormulas[formulaQname]
        evaluate(formula, cdrContext)
        clearEvaluation(cdrContext)
                
def clearEvaluation(cdrContext):
    while cdrContext.hyperspaceBindings:
        cdrContext.hyperspaceBindings.close() # resets cdrContext.hyperspaceBindings to parent bindings


def evaluate(node, cdrContext, value=False, fallback=None, boundFact=False):
    if isinstance(node, astNode):
        if fallback is None:
            result = evaluator[node.__class__.__name__](node, cdrContext)
        else:
            try:
                result = evaluator[node.__class__.__name__](node, cdrContext)
            except StopIteration:
                if cdrContext.formulaOptions.traceVariableSetExpressionEvaluation:
                    cdrContext.modelXbrl.info("cdrFormula:trace",
                         _("%(node)s has unbound evaluation"), 
                         sourceFileLine=node.sourceFileLine, node=str(node))
                return fallback
        if cdrContext.formulaOptions.traceVariableSetExpressionEvaluation:
            cdrContext.modelXbrl.info("cdrFormula:trace",
                 _("%(node)s evaluation: %(value)s"), 
                 sourceFileLine=node.sourceFileLine, node=str(node), value=result)
        if result is not None:
            # dereference nodes to their value
            if (value or boundFact) and isinstance(result, astNode):
                return evaluate(result, cdrContext, value, fallback, boundFact)
            return result
        return result
    elif isinstance(node, (tuple,list)):
        return [evaluate(item, cdrContext, value, fallback, boundFact)
                for item in node]
    elif isinstance(node, set):
        return set(evaluate(item, cdrContext, value, fallback, boundFact)
                   for item in node)
    else:
        return node

def evaluateAnnotationDeclaration(node, cdrContext):
    return None

def evaluateBinaryOperation(node, cdrContext):
    leftValue = evaluate(node.leftExpr, cdrContext, value=True, fallback=UNBOUND)
    rightValue = evaluate(node.rightExpr, cdrContext, value=True, fallback=UNBOUND)
    op = node.op
    if cdrContext.formulaOptions.traceVariableExpressionEvaluation:
        cdrContext.modelXbrl.info("cdrFormula:trace",
             _("Binary op %(op)s v1: %(leftValue)s, v2: %(rightValue)s"), 
             sourceFileLine=node.sourceFileLine, op=op, leftValue=leftValue, rightValue=rightValue)
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
                  '=': operator.eq, '<>': operator.ne,
                  'and': operator.and_, 'or': operator.or_,  'xor': operator.xor,
                  }[op](leftValue, rightValue)
        return result
    except KeyError:
        cdrContext.modelXbrl.error("cdrFormula:error",
             _("Operation \"%(op)s\" not implemented for %(node)s"), 
             sourceFileLine=node.sourceFileLine, op=op, node=str(node))
    except (TypeError, ZeroDivisionError) as err:
        cdrContext.modelXbrl.error("cdrFormula:error",
             _("Operation \"%(op)s\" raises exception %(error)s for %(node)s"), 
             sourceFileLine=node.sourceFileLine, op=op, node=str(node), error=str(err))
    return None

def evaluateConstant(node, cdrContext):
    if node.value is None: # first time
        bindings = EvaluationBindings(cdrContext)  # must have own hsBindings from caller
        node.value = evaluate(node.expr, cdrContext)
        if cdrContext.formulaOptions.traceVariableSetExpressionEvaluation:
            cdrContext.modelXbrl.info("cdrFormula:trace",
                 _("Constant %(name)s assigned value: %(value)s"), 
                 sourceFileLine=node.sourceFileLine, name=node.constantName, value=node.value)
        bindings.close()
    return node.value

def evaluateFor(node, cdrContext):
    # add a hyperspaceBinding to cdrContext for this node
    hsBindings = cdrContext.hyperspaceBindings
    forBinding = hsBindings.forBinding(node)
    # set variable here because although needed for next() operation, will be cleared outside of for's context
    cdrContext.localVariables[node.name] = forBinding.yieldedValue
    return evaluate(node.expr, cdrContext)



def evaluateFunctionReference(node, cdrContext):
    name = node.name
    if name in ("error", "warning", "info", "pass"):
        cdrContext.dynamicSeverity = node.name
    elif name == "unbound":
        return UNBOUND
    
    if name in cdrContext.functions:  # user defined function
        resolveValues = cdrContext.functions[name].functionType == "function"
        namedParametersAssignedTo = cdrContext.localVariables
    else:
        resolveValues = True
        if name in ("error", "warning", "info", "pass"):
            namedParametersAssignedTo = cdrContext.tags
        else:
            namedParametersAssignedTo = cdrContext.localVariables
    
    # evaluate local variables
    for localVar in node.localVariables:
        evaluate(localVar, cdrContext)
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
                arg = evaluate(arg, cdrContext, value=True)
            elif isinstance(arg, astNode):
                arg.isMacroParameter = True
            args.append(arg)
            if tagName:
                namedParametersAssignedTo[tagName] = arg
            tagName = None
            
    if name in ("error", "warning", "info", "pass"):
        result = None
    
    # call built-in functions
    elif name in functionImplementation:
        result = functionImplementation[name](node, cdrContext, args)
    
    else:
        raise CdrException(node, 
                              "cdrFormula:functionName", 
                              _("unassigned function name %(name)s"),
                              name=name)
        
    # remove local variables
    for localVar in node.localVariables:
        del cdrContext.localVariables[localVar.name]
    return result
    

def evaluateHyperspaceExpression(node, cdrContext):
    # add a hyperspaceBinding to cdrContext for this node
    hsBindings = cdrContext.hyperspaceBindings
    nodeBinding = hsBindings.nodeBinding(node)
    return nodeBinding

def evaluateIf(node, cdrContext):
    condition = evaluate(node.condition, cdrContext, value=True)
    if condition:
        expr = node.thenExpr
    else:
        expr = node.elseExpr
    return evaluate(expr, cdrContext)


def evaluateNoOp(node, cdrContext):
    return None

def evaluateNumericLiteral(node, cdrContext):
    return node.value

def evaluateQnameLiteral(node, cdrContext):
    return node.value

def evaluateStringLiteral(node, cdrContext):
    return node.text

def noop(arg):
    return arg

def evaluateUnaryOperation(node, cdrContext):
    if node.op == "brackets":  # parentheses around an expression
        return node.expr
    value = evaluate(node.expr, cdrContext, value=True, fallback=UNBOUND)
    if value is UNBOUND:
        return UNBOUND
    try:
        result = {'+': operator.pos, '-': operator.neg, 'not': operator.not_,
                  'values': noop,
                  }[node.op](value)
        return result
    except KeyError:
        cdrContext.modelXbrl.error("cdrFormula:error",
             _("%(node)s operation %(op)s not implemented"), 
             modelObject=node, op=node.op)
    return None

def contextView(cdrContext, fact=None):
    if isinstance(fact, ModelFact):
        return "{0}[{1}]".format(fact.qname,
                                 ", ".join("{2}={1}".format(aspectName(aspect), 
                                   factAspectValue(fact, aspect, view=True))
                                   for aspect, fact in cdrContext.hyperspaceBindings.aspectBoundFacts.items()
                                   if factAspectValue(fact, aspect) and aspect != Aspect.CONCEPT))
    else:
        return "[{0}]".format(", ".join("{0}={1}".format(aspectName(aspect), 
                                   factAspectValue(fact, aspect, view=True))
                                   for aspect, fact in cdrContext.hyperspaceBindings.aspectBoundFacts.items()
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
    if aspect == Aspect.LOCATION:
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


evaluator = {
    "astBinaryOperation":         evaluateBinaryOperation,
    "astComment":                 evaluateNoOp,
    "astFunctionReference":       evaluateFunctionReference,
    "astNode":                    evaluateNoOp,
    "astNoOp":                    evaluateNoOp,
    "astNumericLiteral":          evaluateNumericLiteral,
    "astQnameLiteral":            evaluateQnameLiteral,
    "astStringLiteral":           evaluateStringLiteral,
    "astUnaryOperation":          evaluateUnaryOperation,
          }
        
CdrFunctionsModuleInit()