'''
sphinxEvaluator processes the Sphinx language in the context of an XBRL DTS and instance.

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).

Sphinx is a Rules Language for XBRL described by a Sphinx 2 Primer 
(c) Copyright 2012 CoreFiling, Oxford UK. 
Sphinx copyright applies to the Sphinx language, not to this software.
Mark V Systems conveys neither rights nor license for the Sphinx language. 
'''

from .SphinxContext import HyperspaceBindings

class SphinxException(Exception):
    def __init__(self, node, code, message, objects ):
        self.node = node
        self.code = code
        self.message = message
        self.objects = objects
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _('[{0}] exception at {1} in {2}').format(self.code, self.column, self.message)
            

def evaluateRuleBase(sphinxContext):
    
    # check any rule-base preconditions
    for file, preconditionNode in sphinxContext.rulebasePreconditions:
        if not preconditionNode.evaluate(sphinxContext):
            return
        
    # evaluate rules
    for ruleProg in sphinxContext.rules:
        evaluate(sphinxContext, ruleProg)
def evaluate(sphinxContext, ruleProg):
    if ruleProg:
            for node in ruleProg:
                evaluator[node.__class__.__name__](node, sphinxContext)
                sphinxContext.ruleTags.clear()
                sphinxContext.inScopeVars.clear()
    

def evaluateAnnotationDeclaration(node, sphinxContext):
    return None

def evaluateBinaryOperation(node, sphinxContext):
    leftExpr = node.leftExpr
    rightExpr = node.rightExpr
    if node.op == "*":
        return leftExpr * rightExpr
    elif node.op == "/":
        return leftExpr / rightExpr
    elif node.op == "+":
        # handle +| and |+
        return leftExpr + rightExpr
    elif node.op == "-":
        # handle |- and -|
        return leftExpr - rightExpr
    return None

def evaluateFactPredicate(node, sphinxContext):
    # add a hyperspaceBinding to sphinxContext for this node
    hsBindings = sphinxContext.hyperspaceBindings
    nodeBinding = hsBindings.nodeBinding(node)
    return nodeBinding

def evaluateFor(node, sphinxContext):
    return None

def evaluateFunctionDeclaration(node, sphinxContext):
    return None

def evaluateFunctionReference(node, sphinxContext):
    return None

def evaluateIf(node, sphinxContext):
    return None

def evaluateList(node, sphinxContext):
    return None

def evaluateMessage(node, sphinxContext):
    return None

def evaluateMethodReference(node, sphinxContext):
    return None

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
    return None

def evaluateSeverity(node, sphinxContext):
    return None

def evaluateStringLiteral(node, sphinxContext):
    return node.text

def evaluateTagReference(node, sphinxContext):
    try:
        return sphinxContext.ruleTags[node.name]
    except KeyError:
        raise SphinxException(node, "sphinx:tagName", _("unassigned tag name"))

def evaluateValidationRule(node, sphinxContext):
    if node.precondition:
        result = evaluatePreconditionReference(node.precondition, sphinxContext)
        if not result:
            return None
    # nest hyperspace binding
    try:
        hsBindings = HyperspaceBindings(sphinxContext)
        while True:
            boolResult = evaluate(node.expr, sphinxContext)
            if boolResult:
                sphinxContext.log("ERROR", node.name,
                                    _("Validation rule failed"),
                                    sourceFileLine=node.sourceFileLine)
            hsBindings.next() # raises StopIteration when done
    except StopIteration:
        pass # no more bindings
    return None

def evaluateUnaryOperation(node, sphinxContext):
    expr = node.expr
    if node.op == "+":
        return expr
    elif node.op == "-":
        # check if numeric?
        return -expr
    elif node.op == "values":
        pass
        # return fact values
    return expr

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
    return None

evaluator = {
    "astAnnotationDeclaration":   evaluateAnnotationDeclaration,
    "astBinaryOperation":         evaluateBinaryOperation,
    "astComment":                 evaluateNoOp,
    "astFactPredicate":           evaluateFactPredicate,
    "astFor":                     evaluateFor,
    "astFunctionDeclaration":     evaluateFunctionDeclaration,
    "astFunctionReference":       evaluateFunctionReference,
    "astIf":                      evaluateIf,
    "astList":                    evaluateList,
    "astMessage":                 evaluateMessage,
    "astMethodReference":         evaluateMethodReference,
    "astNamespaceDeclaration":    evaluateNoOp,
    "astNode":                    evaluateNoOp,
    "astNoOp":                    evaluateNoOp,
    "astNumericLiteral":          evaluateNumericLiteral,
    "astPreconditionDeclaration": evaluatePreconditionDeclaration,
    "astReportRule":              evaluateReportRule,
    "astSourceFile":              evaluateNoOp,
    "astSet":                     evaluateSet,
    "astSeverity":                evaluateSeverity,
    "astRuleBasePrecondition":    evaluateRuleBasePrecondition,
    "astPreconditionReference":   evaluatePreconditionReference,
    "astStringLiteral":           evaluateStringLiteral,
    "astTagReference":            evaluateTagReference,
    "astValidationRule":          evaluateValidationRule,
    "astVariableAssignment":      evaluateVariableAssignment,
    "astVariableReference":       evaluateVariableReference,
    "astUnaryOperation":          evaluateUnaryOperation,
    "astWith":                    evaluateWith,
          }
        
