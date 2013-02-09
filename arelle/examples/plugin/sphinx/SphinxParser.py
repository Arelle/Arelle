'''
SphinxParser is an example of a package plug-in parser for the CoreFiling Sphinx language.

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).

Sphinx is a Rules Language for XBRL described by a Sphinx 2 Primer 
(c) Copyright 2012 CoreFiling, Oxford UK. 
Sphinx copyright applies to the Sphinx language, not to this software.
Mark V Systems conveys neither rights nor license for the Sphinx language. 
'''

import time, sys, os, re
from arelle.ModelValue import qname
from arelle.ModelFormulaObject import Aspect, aspectStr
                                       
# Debugging flag can be set to either "debug_flag=True" or "debug_flag=False"
debug_flag=True

logMessage = None
sphinxFile = None
lineno = None
xmlns = {}

isGrammarCompiled = False

class PrefixError(Exception):
    def __init__(self, qnameToken):
        self.qname = qnameToken
        self.message = "QName prefix undeclared"
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _("QName prefix undeclared: {0}").format(self.qname)

# parse operations ("compile methods") are listed alphabetically
    
def compileAnnotation( sourceStr, loc, toks ):
    return None

def compileAnnotationDeclaration( sourceStr, loc, toks ):
    return astAnnotationDeclaration(sourceStr, loc, toks[0], toks[1] if len(toks) > 1 else None)

def compileBinaryOperation( sourceStr, loc, toks ):
    if len(toks) == 1:
        return toks[0]
    return astBinaryOperation(sourceStr, loc, toks[0], toks[1], toks[2])

def compileBrackets( sourceStr, loc, toks ):
    return astUnaryOperation(sourceStr, loc, "brackets", toks[0])

def compileComment( sourceStr, loc, toks ):
    return astComment(sourceStr, loc, toks[0])

def compileConstant( sourceStr, loc, toks ):
    return astFunctionDeclaration(sourceStr, loc, "constant", toks[0], [], toks[1])

def compileFactPredicate( sourceStr, loc, toks ):
    try:
        return astFactPredicate(sourceStr, loc, toks)
    except PrefixError as err:
        logMessage("ERROR", "sphinxCompiler:missingXmlnsDeclarations",
            _("Missing xmlns for prefix in %(qname)s"),
            sourceFileLines=((sphinxFile, lineno(loc, sourceStr)),), 
            qname=err.qname)
        return None

def compileFloatLiteral( sourceStr, loc, toks ):
    return astNumericLiteral(sourceStr, loc, float(toks[0]))

def compileFor( sourceStr, loc, toks ):
    return astFor(sourceStr, loc, toks[1], toks[2], toks[3])

def compileFormulaRule( sourceStr, loc, toks ):
    return astFormulaRule(sourceStr, loc, toks)

def compileFunctionDeclaration( sourceStr, loc, toks ):
    return astFunctionDeclaration(sourceStr, loc, toks[0], toks[1], toks[3:-2], toks[-1])

def compileFunctionReference( sourceStr, loc, toks ):
    name = toks[0]
    if isinstance(name, astFunctionReference) and not name.args:
        name = name.name
    if name == "list":
        return astList(sourceStr, loc, toks[1:])
    if name == "set":
        return astSet(sourceStr, loc, toks[1:])
    if name == "unit":
        try:
            return astFunctionReference(sourceStr, loc, name, toks[compileQname(toks[1])])
        except PrefixError as err:
            logMessage("ERROR", "sphinxCompiler:missingXmlnsDeclarations",
                _("Missing xmlns for prefix in unit %(qname)s"),
                sourceFileLines=((sphinxFile, lineno(loc, sourceStr)),), 
                qname=err.qname)
            return None
    # compile any args
    return astFunctionReference(sourceStr, loc, name, toks[1:])

def compileIf( sourceStr, loc, toks ):
    return astIf(sourceStr, loc, toks[1], toks[2], toks[3])

def compileIntegerLiteral( sourceStr, loc, toks ):
    return astNumericLiteral(sourceStr, loc, int(toks[0]))

def compileList( sourceStr, loc, toks ):
    return astList(sourceStr, loc, toks)

def compileMessage( sourceStr, loc, toks ):
    # construct a message object and return it
    return astMessage(sourceStr, loc, toks[0])

def compileMethodReference( sourceStr, loc, toks ):
    if len(toks) > 1 and toks[0] == "::":  # method with no object, e.g., ::taxonomy
        return astMethodReference(sourceStr, loc, toks[1], [None] + toks[2:])
    elif len(toks) > 2 and toks[1] == "::":
        return astMethodReference(sourceStr, loc, toks[2], [toks[0]] + toks[3:])
    return toks

def compileNamespaceDeclaration( sourceStr, loc, toks ):
    prefix = None if len(toks) == 2 else toks[1]
    namespaceNode = toks[-1]
    if prefix in xmlns:
        logMessage("ERROR", "sphinxCompiler:multipleXmlnsDeclarations",
            _("Duplicate xmlns for prefix %(prefix)s"),
            sourceFileLines=((sphinxFile, lineno(loc, sourceStr)),), 
            prefix=prefix)
    elif not isinstance(namespaceNode, astStringLiteral):
        logMessage("ERROR", "sphinxCompiler:xmlnsNotStringConstant",
            _("Xmlns for prefix %(prefix)s does not assign a string constant."),
            sourceFileLines=((sphinxFile, lineno(loc, sourceStr)),), 
            prefix=prefix)
    else:
        namespace = namespaceNode.text
        xmlns[prefix] = namespace
        return astNamespaceDeclaration(sourceStr, loc, prefix, namespace)
    return astNoOp(sourceStr, loc)

def compileOp( sourceStr, loc, toks ):
    op = toks[0]
    if op in {"error", "warning", "info", "pass"}:
        return astFunctionReference(sourceStr, loc, op, [])
    return toks

def compilePackageDeclaration( sourceStr, loc, toks ):
    global currentPackage
    currentPackage = toks[0]
    return None

def compilePrecondition( sourceStr, loc, toks ):
    # construct a precondition object and return it
    if len(toks) >= 2 and toks[-2] == "otherwise": # has otherwise
        return astPreconditionReference(sourceStr, loc, toks[0:-2], toks[-1])
    return astPreconditionReference(sourceStr, loc, toks, None)

def compilePreconditionDeclaration( sourceStr, loc, toks ):
    return astPreconditionDeclaration(sourceStr, loc, toks[0], toks[1])

def compileQname( qnameToken ):
    try:
        return qname(qnameToken, xmlns, prefixException=KeyError)
    except KeyError:
        raise PrefixError(qnameToken)

def compileReportRule( sourceStr, loc, toks ):
    return astReportRule(sourceStr, loc, toks)

def compileRuleBase( sourceStr, loc, toks ):
    result = [tok for tok in toks if isinstance(tok, astTransform)]
    if any(isinstance(tok, astPreconditionReference) for tok in toks):
        result.append(astRuleBasePreconditions(sourceStr, loc, 
                                               [tok for tok in toks if isinstance(tok, astPreconditionReference)]))
    return result

def compileSeverity( sourceStr, loc, toks ):
    # construct a severity object and return it
    return astSeverity(sourceStr, loc, toks[0])

def compileStringLiteral( sourceStr, loc, toks ):
    return astStringLiteral(sourceStr, loc, toks[0])

def compileTagAssignment( sourceStr, loc, toks ):
    if len(toks) == 1:
        return toks[0]
    return astTagAssignment(sourceStr, loc, toks[2], toks[0])

def compileTransform( sourceStr, loc, toks ):
    return astTransform(sourceStr, loc, toks[0], toks[1], toks[2])

def compileUnaryOperation( sourceStr, loc, toks ):
    if len(toks) == 1:
        return toks[0]
    return astUnaryOperation(sourceStr, loc, toks[0], toks[1])

def compileValidationRule( sourceStr, loc, toks ):
    return astValidationRule(sourceStr, loc, toks)

def compileVariableAssignment( sourceStr, loc, toks ):
    if len(toks) == 1:
        return toks[0]
    return astVariableAssignment(sourceStr, loc, toks)

def compileVariableReference( sourceStr, loc, toks ):
    return astVariableReference(sourceStr, loc, toks[0][1:])

def compileWith( sourceStr, loc, toks ):
    return astWith(sourceStr, loc, toks[1], toks[2])

class astNode:
    def __init__(self, sourceStr=None, loc=None):
        self.sphinxFile = sphinxFile
        self.sourceStr = sourceStr
        self.loc = loc
        
    def clear(self):
        self.__dict__.clear()  # delete local attributes
        
    @property
    def sourceLine(self):
        if self.sourceStr and self.loc:
            return lineno(self.loc, self.sourceStr)
        return None # no line number available
    
    @property
    def sourceFileLine(self):
        return (self.sphinxFile, self.sourceLine)
    
    def __repr__(self):
        return "{0}({1})".format(type(self).__name__, "")

# subtypes of astNode are arranged alphabetically
    
class astAnnotationDeclaration(astNode):
    def __init__(self, sourceStr, loc, name, annotationType):
        super(astAnnotationDeclaration, self).__init__(sourceStr, loc)
        self.name = name
        self.annotationType = annotationType # "string"
    def __repr__(self):
        return "annotationDeclaration({0}{2}(".format(self.name, 
                                                      (" as " + self.annotationType) if self.annotationType else "")

class astBinaryOperation(astNode):
    def __init__(self, sourceStr, loc, leftExpr, op, rightExpr):
        super(astBinaryOperation, self).__init__(sourceStr, loc)
        self.op = op
        self.leftExpr = leftExpr
        self.rightExpr = rightExpr
    def __repr__(self):
        return "binaryOperation({0} {1} {2})".format(self.leftExpr, self.op, self.rightExpr)

class astComment(astNode):
    def __init__(self, sourceStr, loc, text):
        super(astComment, self).__init__(sourceStr, loc)
        self.text = text
    def __repr__(self):
        return "comment({0})".format(self.text)

namedAxes = {"primary": Aspect.CONCEPT, 
             "segment": Aspect.NON_XDT_SEGMENT, 
             "scenario":Aspect.NON_XDT_SCENARIO, 
             "unit":    Aspect.UNIT}

class astFactPredicate(astNode):
    def __init__(self, sourceStr, loc, axes):
        super(astFactPredicate, self).__init__(sourceStr, loc)
        self.axes = {}
        prev1 = prev2 = None
        for axis in axes:
            if axis == '[' and prev1 is not None:
                self.axes[Aspect.CONCEPT] = compileQname(prev1)
                prev1 = None
            elif ']' and prev1 is not None:
                if prev1 not in namedAxes: prev = compileQname(prev1)
                self.axes[prev1] = None
            elif prev1 == '=' and prev2 is not None:
                if prev2 in namedAxes: 
                    prev = namedAxes[prev2]  # use Aspect.XXX token value
                else:
                    prev = compileQname(prev2)
                self.axes[prev] = compileQname(axis)
                prev2 = prev1 = None
            elif prev1 is not None:
                if prev1 in namedAxes: 
                    prev = namedAxes[prev1]  # use Aspect.XXX token value
                else:
                    prev = compileQname(prev1)
                self.axes[prev] = None
                prev2 = None
                prev1 = axis
            else:
                prev2 = prev1
                prev1 = axis
    def __repr__(self):
        return "factPredicate({0})".format(", ".join((aspectStr(key) + ("=" + str(value) if value is not None else "")
                                                      for key,value in self.axes.items())))

class astFor(astNode):
    def __init__(self, sourceStr, loc, name, range, expr):
        super(astFor, self).__init__(sourceStr, loc)
        self.op = "for"
        self.name = name
        self.range = range
        self.expr = expr
    def __repr__(self):
        return "for({0} in {1}, {2})".format(self.name, self.range, self.expr)

class astFunctionDeclaration(astNode):
    def __init__(self, sourceStr, loc, functionType, name, params, expr):
        try:
            super(astFunctionDeclaration, self).__init__(sourceStr, loc)
            self.functionType = functionType # "function", "macro", "constant"
            self.name = name
            self.params = params
            if (expr) == "unit": # expr is a QName
                self.expr = compileQname(expr)
            else:
                self.expr = expr
        except PrefixError as err:
            logMessage("ERROR", "sphinxCompiler:missingXmlnsDeclarations",
                _("Missing xmlns for prefix in %(qname)s"),
                sourceFileLines=((sphinxFile, lineno(loc, sourceStr)),), 
                qname=err.qname)
            return None
    def __repr__(self):
        return "functionDeclaration({0}({1})) {2}".format(self.name, 
                                                          ", ".join(str(p) for p in self.params),
                                                          self.expr)

class astFunctionReference(astNode):
    def __init__(self, sourceStr, loc, name, args):
        super(astFunctionReference, self).__init__(sourceStr, loc)
        self.name = name
        self.args = args
    def __repr__(self):
        return "functionReference({0}({1}))".format(self.name, ", ".join(str(a) for a in self.args))

class astIf(astNode):
    def __init__(self, sourceStr, loc, condition, thenExpr, elseExpr):
        super(astIf, self).__init__(sourceStr, loc)
        self.op = "for"
        self.condition = condition
        self.thenExpr = thenExpr
        self.elseExpr = elseExpr
    def __repr__(self):
        return "if(({0}) {1} else {2})".format(self.condition, self.thenExpr, self.elseExpr)

class astList(astNode):
    def __init__(self, sourceStr, loc, toks):
        super(astList, self).__init__(sourceStr, loc)
        self.list = list(toks)
    def __repr__(self):
        return "list({0})".format(", ".join(str(t) for t in self.list))

class astMessage(astNode):
    def __init__(self, sourceStr, loc, message):
        super(astMessage, self).__init__(sourceStr, loc)
        self.message = message
    def __repr__(self):
        return "message({0})".format(self.message)

class astMethodReference(astNode):
    def __init__(self, sourceStr, loc, name, args):
        super(astMethodReference, self).__init__(sourceStr, loc)
        self.name = name
        self.args = args
    def __repr__(self):
        return "methodReference({0}({1}))".format(self.name,
                                                     ", ".join(str(a) for a in self.args))

class astNamespaceDeclaration(astNode):
    def __init__(self, sourceStr, loc, prefix, namespace):
        super(astNamespaceDeclaration, self).__init__(sourceStr, loc)
        self.prefix = prefix
        self.namespace = namespace
    def __repr__(self):
        return "xmlns{0}={1}".format((":" + self.prefix) if self.prefix else "",
                                     self.namespace)

class astNoOp(astNode):
    def __init__(self, fileName):
        super(astNoOp, self).__init__(None, 0)
    def __repr__(self):
        return "noOp()"
    
class astNumericLiteral(astNode):
    def __init__(self, sourceStr, loc, value):
        super(astNumericLiteral, self).__init__(sourceStr, loc)
        self.value = value
    def __repr__(self):
        return "{0}({1})".format(type(self).__name__, self.value)

class astPreconditionDeclaration(astNode):
    def __init__(self, sourceStr, loc, name, expr):
        super(astPreconditionDeclaration, self).__init__(sourceStr, loc)
        self.name = name
        self.expr = expr
    def __repr__(self):
        return "preconditionDeclaration({0}, {1}(".format(self.name, self.expr)

class astPreconditionReference(astNode):
    def __init__(self, sourceStr, loc, names, otherwiseExpr):
        super(astPreconditionReference, self).__init__(sourceStr, loc)
        self.names = names
        self.otherwiseExpr = otherwiseExpr
    def __repr__(self):
        return "preconditionRef({0}{1})".format(self.names,
                                                 (" otherwise " + str(self.otherwiseExpr)) if self.otherwiseExpr else "")

class astRuleBasePreconditions(astNode):
    def __init__(self, sourceStr, loc, preconditionReferences):
        super(astRuleBasePreconditions, self).__init__(sourceStr, loc)
        self.preconditionReferences = preconditionReferences
    def __repr__(self):
        return "ruleBasePreconditions({0})".format(", ".join(str(p) for p in self.preconditionReferences))

class astSet(astNode):
    def __init__(self, sourceStr, loc, toks):
        super(astSet, self).__init__(sourceStr, loc)
        self.set = set(toks)
    def __repr__(self):
        return "set({0})".format(", ".join(str(t) for t in self.list))

class astSeverity(astNode):
    def __init__(self, sourceStr, loc, severity):
        super(astSeverity, self).__init__(sourceStr, loc)
        self.severity = severity
    def __repr__(self):
        return "severity({0})".format(self.severity)

class astSourceFile(astNode):
    def __init__(self, fileName):
        super(astSourceFile, self).__init__(None, 0)
        self.fileName = fileName
    def __repr__(self):
        return "fileName({0})".format(self.fileName)

class astStringLiteral(astNode):
    def __init__(self, sourceStr, loc, quotedString):
        super(astStringLiteral, self).__init__(sourceStr, loc)
        # dequote leading/trailing quotes and backslashed characters in sphinx table
        self.text = re.sub(r"\\[ntbrf\\'\"]",lambda m: m.group[0][1], quotedString[1:-1])
    @property
    def value(self):
        return self.text
    def __repr__(self):
        return "{0}({1})".format(type(self).__name__, self.text)

class astTagAssignment(astNode):
    def __init__(self, sourceStr, loc, tagName, expr):
        super(astTagAssignment, self).__init__(sourceStr, loc)
        self.tagName = tagName
        self.expr = expr
    def __repr__(self):
        return "tagAssignment({0}#{1})".format(self.expr, self.name)

class astTransform(astNode):
    def __init__(self, sourceStr, loc, transformType, fromExpr, toExpr):
        super(astTransform, self).__init__(sourceStr, loc)
        self.transformType = transformType
        self.fromExpr = fromExpr
        self.toExpr = toExpr
    def __repr__(self):
        return "transform({0}, {1}, {2})".format(self.transformType, self.fromTransform, self.toTransform)

class astUnaryOperation(astNode):
    def __init__(self, sourceStr, loc, op, expr):
        super(astUnaryOperation, self).__init__(sourceStr, loc)
        self.op = op
        self.expr = expr
    def __repr__(self):
        return "unaryOperation({0} {1})".format(self.op, self.expr)

class astRule(astNode):
    def __init__(self, sourceStr, loc, nodes):
        super(astRule, self).__init__(sourceStr, loc)
        self.name = None
        self.precondition = None
        self.severity = None
        self.message = None
        prev = None
        for node in nodes:
            if isinstance(node, astPreconditionReference):
                self.precondition = node
            elif isinstance(node, astSeverity):
                self.severity = node.severity
            elif isinstance(node, astMessage):
                self.message = node
            else:
                if prev in ("report", "raise"):
                    self.name = node
                    self.expr = None
                    exprName = "expr"
                elif prev == "formula":
                    self.name = node
                    self.leftExpr = None
                    self.rightExpr = None
                    exprName = "leftExpr"
                elif prev == "bind":  # formula only
                    self.bind = node
                elif node == ":=":
                    exprName = "rightExpr"
                elif node not in ("bind", "formula", "report", "raise"):
                    setattr(self, exprName, node)
                prev = node

class astFormulaRule(astRule):
    def __init__(self, sourceStr, loc, nodes):
        self.bind = None
        super(astFormulaRule, self).__init__(sourceStr, loc, nodes)
    def __repr__(self):
        return "formula({0}name={1}, {2}{3}{4} := {5}{6})".format(
                  (str(self.precondition) + ", " ) if self.precondition else "",
                  self.name,
                  (str(self.severity) + ", ") if self.severity else "",
                  ("bind=" + str(self.bind) + ", ") if self.bind else "",
                  self.leftExpr,
                  self.rightExpr,
                  (", " + str(self.message)) if self.message else "")

class astReportRule(astRule):
    def __init__(self, sourceStr, loc, nodes):
        super(astReportRule, self).__init__(sourceStr, loc, nodes)
    def __repr__(self):
        return "reportRule({0}report={1}, {2}{3}{4})".format(
                  (str(self.precondition) + ", " ) if self.precondition else "",
                  self.name,
                  (str(self.severity) + ", ") if self.severity else "",
                  self.expr,
                  (", " + str(self.message)) if self.message else "")

class astValidationRule(astRule):
    def __init__(self, sourceStr, loc, nodes):
        super(astValidationRule, self).__init__(sourceStr, loc, nodes)
    def __repr__(self):
        return "validationRule({0}raise={1}, {2}{3}{4})".format(
                  (str(self.precondition) + ", " ) if self.precondition else "",
                  self.name,
                  (str(self.severity) + ", ") if self.severity else "",
                  self.expr,
                  (", " + str(self.message)) if self.message else "")

class astVariableAssignment(astNode):
    def __init__(self, sourceStr, loc, toks):
        super(astVariableAssignment, self).__init__(sourceStr, loc)
        self.variableName = toks[0]
        self.expr = toks[-1]
        self.tagName = None
        if len(toks) > 2 and toks[1] == "#": # has tag
            if len(toks) > 3: # named tag
                self.tagName = toks[2]
            else: # use name for tag
                self.tagName = self.variableName
    def __repr__(self):
        return "variableAssignment({0}{1} = {2})".format(self.variableName,
                                                         ("#" + self.tagName) if self.tagName else "", 
                                                         self.expr)

class astVariableReference(astNode):
    def __init__(self, sourceStr, loc, variableName):
        super(astVariableReference, self).__init__(sourceStr, loc)
        self.variableName = variableName
    def __repr__(self):
        return "variableReference({0})".format(self.variableName)

class astWith(astNode):
    def __init__(self, sourceStr, loc, withExpr, expr):
        super(astWith, self).__init__(sourceStr, loc)
        self.op = "with"
        self.withExpr = withExpr
        self.expr = expr
    def __repr__(self):
        return "with({0}, {1})".format(self.withExpr, self.expr)

def compileSphinxGrammar( cntlr ):
    global isGrammarCompiled, sphinxProg, lineno

    if isGrammarCompiled:
        return sphinxProg
    
    debugParsing = False
    
    cntlr.showStatus(_("Compiling Sphinx Grammar"))
    if sys.version[0] >= '3':
        # python 3 requires modified parser to allow release of global objects when closing DTS
        from arelle.pyparsing.pyparsing_py3 import (Word, Keyword, alphas, 
                     Literal, CaselessLiteral, 
                     Combine, Optional, nums, Or, Forward, Group, ZeroOrMore, StringEnd, alphanums,
                     ParserElement, quotedString, delimitedList, Suppress, Regex,
                     lineno)
    else:
        from pyparsing import (Word, Keyword, alphas, 
                     Literal, CaselessLiteral, 
                     Combine, Optional, nums, Or, Forward, Group, ZeroOrMore, StringEnd, alphanums,
                     ParserElement, quotedString, delimitedList, Suppress, Regex,
                     lineno)
    
    ParserElement.enablePackrat()
    
    """
    the pyparsing parser constructs are defined in this method to prevent the need to compile
    the grammar when the plug in is loaded (which is likely to be when setting up GUI
    menus or command line parser).
    
    instead the grammar is compiled the first time that any sphinx needs to be parsed
    
    only the sphinxExpression (result below) needs to be global for the parser
    """
    
    # define grammar
    sphinxComment = Regex(r"/(?:\*(?:[^*]*\*+)+?/|/[^\n]*(?:\n[^\n]*)*?(?:(?<!\\)|\Z))").setParseAction(compileComment)
    
    variableRef = Regex("[$]"  # variable prefix
                        # localname part
                        "([A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD_]"
                        "[A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040\xB7_.-]*)"
                        )

    
    qName = Regex("([A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD_]"
                  "[A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040\xB7_.-]*:)?"
                  # localname or wildcard-localname part  
                  "([A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD_]"
                  "[A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040\xB7_.-]*|[*])"
                  )

    ncName = Regex("([A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD_]"
                  "[A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040\xB7_.-]*)"
                  ).setName("ncName").setDebug(debugParsing)
    
    annotationName = Word("@",alphanums + '_-.').setName("annotationName").setDebug(debugParsing)
    

    decimalPoint = Literal('.')
    exponentLiteral = CaselessLiteral('e')
    plusorminusLiteral = Literal('+') | Literal('-')
    digits = Word(nums) 
    integerLiteral = Combine( Optional(plusorminusLiteral) + digits )
    decimalFractionLiteral = Combine( Optional(plusorminusLiteral) + decimalPoint + digits )
    infLiteral = Combine( Optional(plusorminusLiteral) + Literal("INF") )
    nanLiteral = Literal("NaN")
    floatLiteral = ( Combine( integerLiteral +
                         ( ( decimalPoint + Optional(digits) + exponentLiteral + integerLiteral ) |
                           ( exponentLiteral + integerLiteral ) |
                           ( decimalPoint + Optional(digits) ) )
                         ) | 
                     Combine( decimalFractionLiteral + exponentLiteral + integerLiteral ) |
                     decimalFractionLiteral |
                     infLiteral | nanLiteral ) 
    
    
    #emptySequence = Literal( "(" ) + Literal( ")" )
    lParen  = Literal( "(" )
    rParen  = Literal( ")" )
    lPred  = Literal( "[" )
    rPred  = Literal( "]" )
    
    commaOp = Literal(",")
    ifOp = Keyword("if")
    elseOp = Keyword("else")
    forOp = Keyword("for")
    inOp = Keyword("in")
    withOp = Keyword("with")
    notOp = Keyword("not")
    valuesOp = Keyword("values")
    andOp = Keyword("and")
    orOp = Keyword("or")
    neOp = Literal("!=")
    leOp = Literal("<=")
    ltOp = Literal("<")
    geOp = Literal(">=")
    gtOp = Literal(">")
    eqOp = Literal("==")
    compOp = leOp | ltOp | geOp | gtOp
    plusOp  = Literal("|+|") | Literal("|+") | Literal("+|") | Literal("+")
    minusOp = Literal("|-|") | Literal("|-") | Literal("-|") | Literal("-")
    plusMinusOp  = ( plusOp | minusOp ).setParseAction(compileOp)
    multOp  = Literal("*")
    divOp   = Literal("/")
    varAssign = Literal("=")
    tagOp = Literal("#")
    asOp = Keyword("as")
    whereOp = Keyword("where")
    wildOp = multOp
    methodOp = Literal("::")
   
    namespaceDeclaration = (Literal("xmlns") + Optional( Suppress(Literal(":")) + ncName ) + Suppress(Literal("=")) + quotedString ).setParseAction(compileNamespaceDeclaration).ignore(sphinxComment)
    annotationDeclaration = (Suppress(Keyword("annotation")) + ncName + Optional( Suppress(Keyword("as")) + ncName )).setParseAction(compileAnnotationDeclaration).ignore(sphinxComment)
    
    packageDeclaration = (Suppress(Keyword("package")) + ncName ).setParseAction(compilePackageDeclaration).ignore(sphinxComment)
    
    rule = Forward()  # rule is referenced recursively by precondition
    precondition = ( Suppress(Keyword("require")) + delimitedList(ncName) +
                     Optional(Keyword("otherwise") + rule) ).setParseAction(compilePrecondition).ignore(sphinxComment).setName("precondition").setDebug(debugParsing)
    severity = ( Suppress(Keyword("severity")) + ( ncName ) ).setParseAction(compileSeverity).ignore(sphinxComment) 
                
     
    expr = Forward()
    
    atom = ( 
             ( forOp - Suppress(lParen) - ncName - Suppress(inOp) - expr - Suppress(rParen) - expr ).setParseAction(compileFor) |
             ( withOp - Suppress(lParen) - expr - Suppress(rParen) - expr ).setParseAction(compileWith) |
             ( ifOp - Suppress(lParen) - expr - Suppress(rParen) -  expr - Suppress(elseOp) - expr ).setParseAction(compileIf) | 
             ( ncName + Suppress(lParen) + Optional(delimitedList( Optional( ncName + varAssign ) + expr
                                                                   )) + Suppress(rParen) ).setParseAction(compileFunctionReference) |
             ( floatLiteral ).setParseAction(compileFloatLiteral) |
             ( integerLiteral ).setParseAction(compileIntegerLiteral) |
             ( quotedString ).setParseAction(compileStringLiteral) |
             ( variableRef ).setParseAction(compileVariableReference)  |
             ( Optional(qName) + lPred + Optional(delimitedList( qName + Optional( tagOp + Optional(ncName) ) +
                                                                 Optional( (varAssign + (wildOp | expr) | 
                                                                           (inOp + expr) | 
                                                                           (asOp + ncName + varAssign + (wildOp | expr) + whereOp + expr) ) ), 
                                                                 delim=';')) + rPred).setParseAction(compileFactPredicate) |
            # does this need to be qName or just ncName?
             ( ncName ).setParseAction(compileOp) |
             ( Suppress(lParen) - expr - Suppress(commaOp) - Suppress(rParen) ).setParseAction(compileList) |
             ( Suppress(lParen) - expr  - Suppress(rParen) ).setParseAction(compileBrackets) |
             ( Suppress(lParen) - delimitedList(expr) - Suppress(rParen) ).setParseAction(compileList)
           ).ignore(sphinxComment)
    
    valueExpr = atom
    taggedExpr = ( valueExpr - Optional(tagOp - ncName) ).setParseAction(compileTagAssignment).ignore(sphinxComment)
    
    #filterExpr = ( atom + ZeroOrMore( (Suppress(lPred) - expr - Suppress(rPred)).setParseAction(pushPredicate) ) )
    #axisStep = ( (reverseStep | forwardStep) + ZeroOrMore( (Suppress(lPred) - expr - Suppress(rPred)).setParseAction(pushPredicate) ) )         
    #stepExpr = filterExpr | axisStep
    #relativePathExpr = ( stepExpr + ZeroOrMore( ( pathStepOp | pathDescOp ) + stepExpr ).setParseAction( pushOperation ) )
    #pathExpr = ( ( pathDescOp + relativePathExpr ) |
    #             ( pathStepOp + relativePathExpr ) |
    #             ( relativePathExpr ) |
    #             ( pathStepOp ) )
    #valueExpr = pathExpr
    methodExpr = ( ( taggedExpr - Optional( methodOp - ncName - Optional( Suppress(lParen) - delimitedList(expr) - Suppress(rParen)) )).setParseAction(compileMethodReference) |
                   ( methodOp + ncName ).setParseAction(compileMethodReference) ).ignore(sphinxComment)
    unaryExpr = ( Optional(plusMinusOp) + methodExpr ).setParseAction(compileUnaryOperation).ignore(sphinxComment)
    negateExpr = ( Optional(notOp) + unaryExpr ).setParseAction(compileUnaryOperation).ignore(sphinxComment)
    valuesExpr = ( Optional(valuesOp) + negateExpr ).setParseAction(compileUnaryOperation).ignore(sphinxComment)
    multiplyExpr = ( valuesExpr + Optional( multOp + valuesExpr ) ).setParseAction(compileBinaryOperation).ignore(sphinxComment)
    divideExpr = ( multiplyExpr + Optional( divOp + multiplyExpr ) ).setParseAction(compileBinaryOperation).ignore(sphinxComment)
    addExpr = ( divideExpr + Optional( plusOp + divideExpr ) ).setParseAction(compileBinaryOperation).ignore(sphinxComment)
    subtractExpr = ( addExpr + Optional( minusOp + addExpr ) ).setParseAction(compileBinaryOperation).ignore(sphinxComment)
    equalityExpr = ( subtractExpr + Optional( eqOp + subtractExpr ) ).setParseAction(compileBinaryOperation).ignore(sphinxComment)
    inequalityExpr = ( equalityExpr + Optional( neOp + equalityExpr ) ).setParseAction(compileBinaryOperation).ignore(sphinxComment)
    comparisonExpr = ( inequalityExpr + Optional( compOp + inequalityExpr ) ).setParseAction(compileBinaryOperation).ignore(sphinxComment)
    andExpr = ( comparisonExpr + Optional( andOp + comparisonExpr ) ).setParseAction(compileBinaryOperation ).ignore(sphinxComment)
    orExpr = ( andExpr + Optional( orOp + andExpr ) ).setParseAction(compileBinaryOperation).ignore(sphinxComment)
    parsedExpr = orExpr

    expr << parsedExpr
    expr.setName("expr").setDebug(debugParsing)
    
    annotation = ( annotationName + Optional( Suppress(lParen) + Optional(delimitedList(expr)) + Suppress(rParen) ) ).setParseAction(compileAnnotation).ignore(sphinxComment).setName("annotation").setDebug(debugParsing)

    ruleBase = (Optional( precondition ) +
                Suppress(Keyword("rule-base")) +
                ZeroOrMore( (Suppress(Keyword("transform")) +
                             (Keyword("namespace") + expr + Suppress(Keyword("to")) + expr) | 
                             (Keyword ("qname") + expr + Suppress(Keyword("to")) + expr)
                             ).setParseAction(compileTransform)
                           )
                ).setParseAction(compileRuleBase).ignore(sphinxComment).setName("ruleBase").setDebug(debugParsing)

    constant = ( Suppress(Keyword("constant")) + ncName + Suppress( Literal("=") ) + expr ).setParseAction(compileConstant).ignore(sphinxComment)
    
    functionDeclaration = ( (Keyword("function") | Keyword("macro")) + ncName + lParen + Optional(delimitedList(ncName)) + rParen + expr ).setParseAction(compileFunctionDeclaration).ignore(sphinxComment)
    
    preconditionDeclaration = ( Suppress(Keyword("precondition")) + ncName + expr ).setParseAction(compilePreconditionDeclaration).ignore(sphinxComment)

    assignedExpr = ( ncName + Optional( tagOp + ncName ) + varAssign + expr + Suppress(Literal(";")) ).setParseAction(compileVariableAssignment).ignore(sphinxComment)
    
    message = ( Suppress(Keyword("message")) + expr ).setParseAction(compileMessage)
    
    formulaRule = ( Optional( precondition ) +
                    Keyword("formula") + ncName + 
                    Optional( severity ) + 
                    Optional( ( Keyword("bind") + expr ) ) +
                    expr + Literal(":=") + expr +
                    Optional( message )).setParseAction(compileFormulaRule).ignore(sphinxComment)
    reportRule = ( Optional( precondition ) +
                   Keyword("report") + ncName + 
                   Optional( severity ) +
                   expr + 
                   Optional( message )).setParseAction( compileReportRule).ignore(sphinxComment)
    validationRule = ( Optional( precondition ) +
                       Keyword("raise") + ncName + 
                       Optional( severity ) +
                       ZeroOrMore( assignedExpr ) +
                       expr + 
                       Optional( message )).setParseAction(compileValidationRule).ignore(sphinxComment)
    rule << ( validationRule | formulaRule | reportRule )
    
    sphinxProg = ( ZeroOrMore( namespaceDeclaration | sphinxComment ) + 
                   ZeroOrMore( annotationDeclaration |
                               annotation |
                               constant |
                               preconditionDeclaration |
                               packageDeclaration |
                               functionDeclaration |
                               ruleBase |
                               rule  |
                               sphinxComment
                               )
                   ) + StringEnd()
    sphinxProg.ignore(sphinxComment)
    
    startedAt = time.time()
    cntlr.modelManager.showStatus(_("initializing sphinx grammar"))
    sphinxProg.parseString( "// force initialization\n", parseAll=True )
    from arelle.Locale import format_string
    logMessage("INFO", "info",
               format_string(cntlr.modelManager.locale, 
                             _("Sphinx grammar initialized in %.2f secs"), 
                             time.time() - startedAt))

    isGrammarCompiled = True

    return sphinxProg

def parse(cntlr, _logMessage, sphinxFiles):
    if sys.version[0] >= '3':
        # python 3 requires modified parser to allow release of global objects when closing DTS
        from arelle.pyparsing.pyparsing_py3 import ParseException, ParseSyntaxException
    else: 
        from pyparsing import ParseException, ParseSyntaxException
    
    global logMessage, sphinxFile
    logMessage = _logMessage
    
    sphinxGrammar = compileSphinxGrammar(cntlr)
    
    sphinxProgs = []
    
    successful = True
    for sphinxFile in sphinxFiles:
        cntlr.showStatus("Compiling sphinx file {0}".format(os.path.basename(sphinxFile)))
        
        with open(sphinxFile, "r", encoding="utf-8") as fh:
            sourceString = fh.read()
            try:
                prog = sphinxGrammar.parseString( sourceString, parseAll=True )
                xmlns.clear()  # dereference xmlns definitions
                prog.insert(0, astSourceFile(sphinxFile)) # keep the source file name
                sphinxProgs.append( prog )
            except (ParseException, ParseSyntaxException) as err:
                from arelle.XPathParser import exceptionErrorIndication
                logMessage("ERROR", "sphinxCompiler:syntaxError",
                    _("Parse error in %(sphinxFile)s error:\n%(error)s"),
                    sphinxFile=os.path.basename(sphinxFile),
                    sourceFileLines=((sphinxFile, lineno(err.loc,err.pstr)),),
                    error=exceptionErrorIndication(err))
                successful = False
            except (ValueError) as err:
                logMessage("ERROR", "sphinxCompiler:valueError",
                    _("Parsing of %(sphinxFile)s terminated due to error: %(error)s"), 
                    sphinxFileLines=((os.path.basename(sphinxFile),0),),
                    error=err)
                successful = False

        cntlr.showStatus("Compiled sphinx files {0}".format({True:"successful", 
                                                             False:"with errors"}[successful]),
                         clearAfter=5000)
                
    logMessage = None # dereference
                    
    return sphinxProgs

