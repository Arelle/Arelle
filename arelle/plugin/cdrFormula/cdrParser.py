'''
SphinxParser is an example of a package plug-in parser for the CoreFiling Sphinx language.

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).

Sphinx is a Rules Language for XBRL described by a Sphinx 2 Primer 
(c) Copyright 2012 CoreFiling, Oxford UK. 
Sphinx copyright applies to the Sphinx language, not to this software.
Mark V Systems conveys neither rights nor license for the Sphinx language. 
'''

import time, sys, os, os.path, re, zipfile
from arelle.ModelValue import qname
from arelle.ModelFormulaObject import Aspect, aspectStr
from arelle.ModelXbrl import DEFAULT, NONDEFAULT, DEFAULTorNONDEFAULT
from arelle import XmlUtil
                                       
# Debugging flag can be set to either "debug_flag=True" or "debug_flag=False"
debug_flag=True

logMessage = None
formulaFile = None
lastLoc = 0
lineno = None
xmlns = {}

reservedWords = {"period", "unit", "segment", "scenario",
                 "NaN", "unbound", "none"}

isGrammarCompiled = False

class PrefixError(Exception):
    def __init__(self, qnameToken):
        self.qname = qnameToken
        self.message = "QName prefix undeclared"
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _("QName prefix undeclared: {0}").format(self.qname)

# parse operations ("compile methods") are listed alphabetically

def compileBinaryOperation( sourceStr, loc, toks ):
    if len(toks) == 1:
        return toks
    global lastLoc; lastLoc = loc
    return astBinaryOperation(sourceStr, loc, toks)

def compileBrackets( sourceStr, loc, toks ):
    if len(toks) == 1:  # parentheses around an expression
        return astUnaryOperation(sourceStr, loc, "brackets", toks[0])
    return astFunctionReference(sourceStr, loc, "list", [tok for tok in toks if tok != ','])

def compileFloatLiteral( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    return astNumericLiteral(sourceStr, loc, float(toks[0]))

def compileFunctionReference( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    name = toks[0]
    if isinstance(name, astFunctionReference) and not name.args:
        name = name.name
    # compile any args
    return astFunctionReference(sourceStr, loc, name, toks[1:])

def compileIntegerLiteral( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    return astNumericLiteral(sourceStr, loc, int(toks[0]))

def compilePeriodOffsetExpression( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    # NEED DEBUGGING
    return astPeriodOffset(sourceStr, loc, toks[0], toks[2])

def compileQname( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    qnameTok = toks[0]
    return astQnameLiteral(sourceStr, loc, qnameTok)

def compileRefExpression( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    return astRefExpression(sourceStr, loc, toks[1])

def compileStringLiteral( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    return astStringLiteral(sourceStr, loc, toks[0])

def compileUnaryOperation( sourceStr, loc, toks ):
    if len(toks) == 1:
        return toks
    global lastLoc; lastLoc = loc
    return astUnaryOperation(sourceStr, loc, toks[0], toks[1])

def compileVariableReference( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    return astVariableReference(sourceStr, loc, toks[0][1:])

class astNode:
    def __init__(self, sourceStr=None, loc=None):
        self.formulaFile = formulaFile
        self.sourceStr = sourceStr
        self.loc = loc
        global lastLoc # for exception handling
        lastLoc = loc
        
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
    
    @property
    def nodeTypeName(self):
        return type(self).__name__[3:]
    
    def __repr__(self):
        return "{0}({1})".format(type(self).__name__, "")

# subtypes of astNode are arranged alphabetically
    
class astBinaryOperation(astNode):
    def __init__(self, sourceStr, loc, toks):
        super(astBinaryOperation, self).__init__(sourceStr, loc)
        if len(toks) > 3:
            self.leftExpr = astBinaryOperation(sourceStr, loc, toks[:-2])
        else:
            self.leftExpr = toks[-3]
        self.op = toks[-2].lower()
        self.rightExpr = toks[-1]
    def __repr__(self):
        return "binaryOperation({0} {1} {2})".format(self.leftExpr, self.op, self.rightExpr)

class astConstant(astNode):
    def __init__(self, sourceStr, loc, toks):
        super(astConstant, self).__init__(sourceStr, loc)
        self.constantName = toks[0]
        self.expr = toks[-1]
        self.value = None # dynamically assigned
        self.tagName = None
        if len(toks) > 2 and toks[1] == "#": # has tag
            if len(toks) > 4: # named tag
                self.tagName = toks[2]
            else: # use name for tag
                self.tagName = self.constantName
    def __repr__(self):
        return "constant({0}{1} = {2})".format(self.constantName,
                                               ("#" + self.tagName) if self.tagName else "", 
                                               self.expr)

class astFunctionReference(astNode):
    def __init__(self, sourceStr, loc, name, args):
        super(astFunctionReference, self).__init__(sourceStr, loc)
        self.name = (name.value.localName if isinstance(name, astQnameLiteral) else name).lower()
        self.args = args
    def __repr__(self):
        return "functionReference({0}({1}))".format(self.name,
                                                    ", ".join(str(a) for a in self.args))

class astNoOp(astNode):
    def __init__(self, sourceStr, loc):
        super(astNoOp, self).__init__(sourceStr, loc)
    def __repr__(self):
        return "noOp()"
    
class astNumericLiteral(astNode):
    def __init__(self, sourceStr, loc, value):
        super(astNumericLiteral, self).__init__(sourceStr, loc)
        self.value = value
    def __repr__(self):
        return "numericLiteral({0})".format(self.value)

class astPeriodOffset(astNode):
    def __init__(self, sourceStr, loc, value, periodOffsetToken):
        super(astPeriodOffset, self).__init__(sourceStr, loc)
        self.value = value
        self.periodOffsetToken = periodOffsetToken
    def __repr__(self):
        return "periodOffset({0},{1})".format(self.value, self.periodOffsetToken)

class astQnameLiteral(astNode):
    def __init__(self, sourceStr, loc, qnameToken):
        super(astQnameLiteral, self).__init__(sourceStr, loc)
        try:
            self.value = qname(qnameToken, 
                               xmlns, 
                               prefixException=KeyError,
                               noPrefixIsNoNamespace=(qnameToken.lower() in functionImplementation or 
                                                      qnameToken in reservedWords))
        except KeyError:
            raise PrefixError(qnameToken)
    def __repr__(self):
        return "qnameLiteral({0})".format(self.value)

class astRefExpression(astNode):
    def __init__(self, sourceStr, loc, qnameToken):
        super(astRefExpression, self).__init__(sourceStr, loc)
        self.value = qnameToken
    def __repr__(self):
        return "referenceExpression({0})".format(self.value)

class astSourceFile(astNode):
    def __init__(self, fileName):
        super(astSourceFile, self).__init__(None, 0)
        self.fileName = fileName
    def __repr__(self):
        return "sourceFile({0})".format(self.fileName)

class astStringLiteral(astNode):
    def __init__(self, sourceStr, loc, quotedString):
        super(astStringLiteral, self).__init__(sourceStr, loc)
        self.text = quotedString[1:-1].replace('""','"')
    @property
    def value(self):
        return self.text
    def __repr__(self):
        return "stringLiteral({0})".format(self.text)
class astUnaryOperation(astNode):
    def __init__(self, sourceStr, loc, op, expr):
        super(astUnaryOperation, self).__init__(sourceStr, loc)
        self.op = op
        self.expr = expr
    def __repr__(self):
        return "unaryOperation({0} {1})".format(self.op, self.expr)

class astVariableReference(astNode):
    def __init__(self, sourceStr, loc, variableName):
        super(astVariableReference, self).__init__(sourceStr, loc)
        self.variableName = variableName
    def __repr__(self):
        return "variableReference({0})".format(self.variableName)

debugParsing = True

if sys.version[0] >= '3':
    # python 3 requires modified parser to allow release of global objects when closing DTS
    from arelle.pyparsing.pyparsing_py3 import (Word, Keyword, alphas, 
                 Literal, CaselessLiteral, 
                 Combine, Optional, nums, Or, Forward, Group, ZeroOrMore, StringEnd, alphanums,
                 ParserElement, sglQuotedString, delimitedList, Suppress, Regex, FollowedBy,
                 lineno, restOfLine)
else:
    from pyparsing import (Word, Keyword, alphas, 
                 Literal, CaselessLiteral, 
                 Combine, Optional, nums, Or, Forward, Group, ZeroOrMore, StringEnd, alphanums,
                 ParserElement, sglQuotedString, delimitedList, Suppress, Regex, FollowedBy,
                 lineno, restOfLine)

ParserElement.enablePackrat()


"""
the pyparsing parser constructs are defined in this method to prevent the need to compile
the grammar when the plug in is loaded (which is likely to be when setting up GUI
menus or command line parser).

instead the grammar is compiled the first time that any sphinx needs to be parsed

only the sphinxExpression (result below) needs to be global for the parser
"""


def compileCdrGrammar( cntlr, _logMessage ):
    global isGrammarCompiled, cdrProg, lineno

    if isGrammarCompiled:
        return cdrProg
    
    global logMessage
    logMessage = _logMessage
    
    debugParsing = False #  True
    
    cntlr.showStatus(_("Compiling CDR Grammar"))
    if sys.version[0] >= '3':
        # python 3 requires modified parser to allow release of global objects when closing DTS
        from arelle.pyparsing.pyparsing_py3 import (Word, Keyword, alphas, 
                     Literal, CaselessLiteral, 
                     Combine, Optional, nums, Or, Forward, Group, ZeroOrMore, StringEnd, alphanums,
                     ParserElement, sglQuotedString, delimitedList, Suppress, Regex, FollowedBy,
                     lineno, restOfLine)
    else:
        from pyparsing import (Word, Keyword, alphas, 
                     Literal, CaselessLiteral, 
                     Combine, Optional, nums, Or, Forward, Group, ZeroOrMore, StringEnd, alphanums,
                     ParserElement, sglQuotedString, delimitedList, Suppress, Regex, FollowedBy,
                     lineno, restOfLine)
    
    ParserElement.enablePackrat()
    
    """
    the pyparsing parser constructs are defined in this method to prevent the need to compile
    the grammar when the plug in is loaded (which is likely to be when setting up GUI
    menus or command line parser).
    
    instead the grammar is compiled the first time that any sphinx needs to be parsed
    
    only the sphinxExpression (result below) needs to be global for the parser
    """
    
    # define grammar
    periodOffset = Regex("-?P[1-3]?[0-9][YQMD](/-[1]?[0-9]-([1-3]?[0-9]|end))?")
    qName = Regex("([A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD_]"
                  "[A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040\xB7_.-]*:)?"
                  # localname or wildcard-localname part  
                  "([A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD_]"
                  "[A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040\xB7_.-]*|[*])"
                  ).setName("qName").setDebug(debugParsing)

    ncName = Regex("([A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD_]"
                  "[A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040\xB7_.-]*)"
                  ).setName("ncName").setDebug(debugParsing)
    

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
    lPred  = Literal("[")
    rPred  = Literal("]")
    refOp  = Literal("#")
    
    commaOp = Literal(",")
    neOp = Literal("<>")
    leOp = Literal("<=")
    ltOp = Literal("<")
    geOp = Literal(">=")
    gtOp = Literal(">")
    eqOp = Literal("=")
    eqNeOp = eqOp | neOp
    compOp = leOp | ltOp | geOp | gtOp
    plusOp  = Literal("+")
    minusOp = Literal("-")
    plusMinusOp  = plusOp | minusOp
    expOp  = Literal("^")
    multOp  = Literal("*")
    divOp   = Literal("/")
    multDivOp = multOp | divOp
    concatOp  = Literal("&")
    andOp = CaselessLiteral("And")
    orOp = CaselessLiteral("Or")
    xorOp = CaselessLiteral("Xor")
   
    expr = Forward()
    
    atom = ( 
             ( refOp + qName ).setParseAction(compileRefExpression) |
             ( qName + Suppress(lParen) + Optional(delimitedList( expr )) + Suppress(rParen) ).setParseAction(compileFunctionReference) |
             ( qName.setParseAction(compileQname) + lPred + ( periodOffset | ncName) 
                     + rPred).setParseAction(compilePeriodOffsetExpression) |
             ( floatLiteral ).setParseAction(compileFloatLiteral) |
             ( integerLiteral ).setParseAction(compileIntegerLiteral) |
             ( sglQuotedString ).setParseAction(compileStringLiteral) |
             ( qName ).setParseAction(compileQname) |
             ( Suppress(lParen) - expr - Optional( commaOp - Optional( expr - ZeroOrMore( commaOp - expr ) ) ) - Suppress(rParen) ).setParseAction(compileBrackets)
           )
           
    atom.setName("atom").setDebug(debugParsing)
    
    valueExpr = atom
    negationExpr = ( Optional(minusOp) + valueExpr ).setParseAction(compileUnaryOperation)
    expExpr = ( Optional(expOp) + negationExpr ).setParseAction(compileUnaryOperation)
    multDivExpr = ( expExpr + Optional( multDivOp + expExpr ) ).setParseAction(compileBinaryOperation)
    multDivExpr.setName("multDivExpr").setDebug(debugParsing)
    addSubExpr = ( multDivExpr + ZeroOrMore( plusMinusOp + multDivExpr ) ).setParseAction(compileBinaryOperation) 
    addSubExpr.setName("addSubExpr").setDebug(debugParsing)
    concatExpr = ( addSubExpr + ZeroOrMore( concatOp + addSubExpr ) ).setParseAction(compileBinaryOperation) 
    comparisonExpr = ( concatExpr + Optional( compOp + concatExpr ) ).setParseAction(compileBinaryOperation)
    equalityExpr = ( comparisonExpr + Optional( eqNeOp + comparisonExpr ) ).setParseAction(compileBinaryOperation)
    xorExpr = ( equalityExpr + ZeroOrMore( xorOp + equalityExpr) ).setParseAction(compileBinaryOperation)
    andExpr = ( xorExpr + ZeroOrMore( andOp + xorExpr ) ).setParseAction(compileBinaryOperation)
    orExpr = ( andExpr + ZeroOrMore( orOp + andExpr ) ).setParseAction(compileBinaryOperation)
    orExpr.setName("orExpr").setDebug(debugParsing)

    expr << orExpr
    expr.setName("expr").setDebug(debugParsing)
    
    cdrProg = expr + StringEnd()
    expr.setName("cdrProg").setDebug(debugParsing)
    
    startedAt = time.time()
    cntlr.modelManager.showStatus(_("initializing CDR grammar"))
    cdrProg.parseString( "0", parseAll=True )
    from arelle.Locale import format_string
    _msg = format_string(cntlr.modelManager.locale, 
                             _("CDR grammar initialized in %.2f secs"), 
                             time.time() - startedAt)
    logMessage("INFO", "info", _msg)
    cntlr.modelManager.showStatus(_msg, 5000)
    isGrammarCompiled = True

    return cdrProg

def parse(modelFormula):
    if sys.version[0] >= '3':
        # python 3 requires modified parser to allow release of global objects when closing DTS
        from arelle.pyparsing.pyparsing_py3 import ParseException, ParseSyntaxException
    else: 
        from pyparsing import ParseException, ParseSyntaxException
    modelXbrl = modelFormula.modelXbrl
    global formulaFile, lineno, xmlns, logMessage
    logMessage = modelXbrl.log
    formulaFile = modelFormula.modelDocument.uri
    baseName = modelFormula.modelDocument.basename
    lineno = modelFormula.sourceline
    sourceString = modelFormula.select
    xmlns = modelFormula.nsmap
    # cdr doesn't declare xsd namespace URI prefixes
    for ns, nsDocs in modelXbrl.namespaceDocs.items():
        for nsDoc in nsDocs:
            nsDocPrefix = XmlUtil.xmlnsprefix(nsDoc.xmlRootElement, ns)
            if nsDocPrefix and nsDocPrefix not in xmlns:
                xmlns[nsDocPrefix] = ns
                xmlns[nsDocPrefix.upper()] = ns  # cdr also has upper case prefixes intermixed    
                break
    try:
        modelFormula.prog = cdrProg.parseString( sourceString, parseAll=True )
        successful = True
    except (ParseException, ParseSyntaxException) as err:
        from arelle.XPathParser import exceptionErrorIndication
        logMessage("ERROR", "cdrFormula:syntaxError",
            _("Parse error: \n%(error)s"),
            formulaFile=formulaFile,
            sourceFileLines=((baseName, lineno),),
            error=exceptionErrorIndication(err))
        successful = False
    except (ValueError) as err:
        logMessage("ERROR", "cdrFormula:valueError",
            _("Parsing terminated due to error: \n%(error)s"), 
            formulaFile=formulaFile,
            sourceFileLines=((baseName, lineno),),
            error=err)
        successful = False
    except Exception as err:
        logMessage("ERROR", "cdrFormula:parserException",
            _("Parsing of terminated due to error: \n%(error)s"), 
            formulaFile=formulaFile,
            sourceFileLines=((baseName, lineno),),
            error=err, exc_info=True)
        successful = False
    return successful
        

from .cdrFunctions import functionImplementation