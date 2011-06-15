'''
Created on Dec 20, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle.pyparsing.pyparsing_py3 import (Word, Keyword, alphas, ParseException, ParseSyntaxException,
                 Literal, CaselessLiteral,
                 Combine, Optional, nums, Or, Forward, Group, ZeroOrMore, StringEnd, alphanums,
                 ParserElement, quotedString, delimitedList, Suppress, Regex)
from arelle.Locale import format_string
import time, xml.dom
from arelle import (XmlUtil, ModelValue, XbrlConst)


# Debugging flag can be set to either "debug_flag=True" or "debug_flag=False"
debug_flag=True

exprStack = []
xmlElement = None
modelXbrl = None
xbrlResource = None

class ProgHeader:
    def __init__(self, modelObject, name, element, sourceStr, traceType):
        self.modelObject = modelObject
        self.name = name
        self.element = element
        self.sourceStr = sourceStr
        self.traceType = traceType
    def __repr__(self):
        return ("ProgHeader({0},{1})".format(self.name,self.modelObject))

def pushFirst( sourceStr, loc, toks ):
    exprStack.append( toks[0] )

def pushFloat( sourceStr, loc, toks ):
    num = float(toks[0])
    exprStack.append( num )
    return num

def pushInt( sourceStr, loc, toks ):
    num = int(toks[0])
    exprStack.append( num )
    return num

def pushQuotedString( sourceStr, loc, toks ):
    str = toks[0]
    q = str[0]
    dequotedStr = str[1:-1].replace(q+q,q)
    exprStack.append( dequotedStr )
    return dequotedStr

class QNameDef(ModelValue.QName):
    def __init__(self, loc, prefix, namespaceURI, localName, isAttribute=False):
        super().__init__(prefix, namespaceURI, localName)
        self.unprefixed = prefix is None
        self.isAttribute = isAttribute
        self.loc = loc
    def __hash__(self):
        return self.hash
    def __repr__(self):
        return ("{0}QName({1})".format('@' if self.isAttribute else '',str(self)))
    def __eq__(self,other):
        if isinstance(other,QNameDef):
            return other.loc == self.loc and super().__eq__(other) 
        else:
            return super().__eq__(other)
    def __ne__(self,other):
    	return not self.__eq__(other)

def pushQName( sourceStr, loc, toks ):
    qname = toks[0]
    if xmlElement is not None:
        nsLocalname = XmlUtil.prefixedNameToNamespaceLocalname(xmlElement, qname)
        if nsLocalname is None:
            modelXbrl.error(
                _("QName prefix not defined for {0}").format(qname),
                  "err","err:XPST0081")
            return
        if (nsLocalname == (XbrlConst.xff,"uncovered-aspect") and
            xmlElement.localName not in ("formula", "consistencyAssertion", "valueAssertion")):
                modelXbrl.error(
                    _("Function {0} cannot be used on an XPath expression associated with a {1}").format(qname, xmlElement.localName),
                      "err","xffe:invalidFunctionUse")
    else:
        nsLocalname = (None,qname)
    q = QNameDef(loc, nsLocalname[2], nsLocalname[0], nsLocalname[1])
    if qname not in ("INF", "NaN", "for", "some", "every", "return") and \
        len(exprStack) == 0 or exprStack[-1] != q:
        exprStack.append( q )
    return q

def pushAttr( sourceStr, loc, toks ):
    # usually has QName of attr already on exprstack, get rid of it
    if toks[0] == '@' and len(exprStack) > 0 and len(toks) > 1 and exprStack[-1] == toks[1]:
        exprStack.remove(toks[1])
    if isinstance(toks[1],QNameDef):
        attr = toks[1]
        attr.isAttribute = True
    else:
        ##### BUG this won't work, wrong arguments !!!!
        attr = QNameDef(loc, toks[1], isAttribute=True)
    exprStack.append( attr )
    return attr
    
class OpDef:
    def __init__(self, loc, toks):
        self.name = toks[0]
        self.loc = loc
    def __repr__(self):
        return ("op({0})".format(self.name))
    def __eq__(self,other):
        return isinstance(other,OpDef) and other.name == self.name and other.loc == self.loc
    def __ne__(self,other):
    	return not self.__eq__(other)

def pushOp( sourceStr, loc, toks ):
    op = OpDef(loc, toks)
    # assure this operand not already on stack
    if len(exprStack) == 0 or exprStack[-1] != op: 
        exprStack.append( op )
    return op

class OperationDef:
    def __init__(self, sourceStr, loc, name, toks, skipFirstTok):
        self.sourceStr = sourceStr
        self.loc = loc
        self.name = name
        if skipFirstTok:
            toks1 = toks[1] if len(toks) > 1 else None
            if (isinstance(toks1,str) and isinstance(name,str) and
                name in ('/', '//', 'rootChild', 'rootDescendant')):
                if toks1 == '*': 
                    toks1 = QNameDef(loc,None,'*','*')
                elif toks1.startswith('*:'):
                    toks1 = QNameDef(loc,None,'*',toks1[2:])
                elif toks1.endswith(':*'):
                    prefix = toks1[:-2]
                    ns = XmlUtil.xmlns(xmlElement, prefix)
                    if ns is None:
                        modelXbrl.error(
                            _("wildcard prefix not defined for {0}").format(toks1),
                              "err","err:XPST0081")
                    toks1 = QNameDef(loc,prefix,ns,'*')
                self.args = [toks1] + toks[2:] # special case for wildcard path segment
            else:
                self.args = toks[1:]
            '''
            self.args = toks[1:]
            '''
        else:               # for others first token is just op code, no expression
            self.args = toks
    def __repr__(self):
        if isinstance(self.name,QNameDef):
            return ("{0}{1}".format(str(self.name), self.args))
        else:
            return ("{1} {0}".format(self.name, self.args))

def pushOperation( sourceStr, loc, toks ):
    if isinstance(toks[0], str):
        name = toks[0]
        removeOp = False
        for tok in toks[1:]:
            if not isinstance(tok,str) and tok in exprStack:
                removeOp = True
                removeFrom = tok
                break
    else:
        name = toks[0].name
        removeOp = toks[0] in exprStack
        removeFrom = toks[0]
    operation = OperationDef(sourceStr, loc, name, toks, name != "if")
    if removeOp:
        exprStack[exprStack.index(removeFrom):] = [operation]  # replace tokens with production
    else:
        
        exprStack.append(operation)
    return operation

def pushUnaryOperation( sourceStr, loc, toks ):
    if isinstance(toks[0], str):
        operation = OperationDef(sourceStr, loc, 'u' + toks[0], toks, True)
        exprStack.append(operation)
    else:
        operation = OperationDef(sourceStr, loc, 'u' + toks[0].name, toks, True)
        exprStack[exprStack.index(toks[0]):] = [operation]  # replace tokens with production
    return operation

def pushFunction( sourceStr, loc, toks ):
    name = toks[0]
    operation = OperationDef(sourceStr, loc, name, toks, True)
    exprStack[exprStack.index(toks[0]):] = [operation]  # replace tokens with production
    return operation

def pushSequence( sourceStr, loc, toks ):
    operation = OperationDef(sourceStr, loc, 'sequence', toks, False)
    if len(toks) == 0:  # empty sequence
        exprStack.append(operation)
    else:
        exprStack[exprStack.index(toks[0]):] = [operation]  # replace tokens with production
    return operation

def pushPredicate( sourceStr, loc, toks ):
    # drop the predicate op, used to clean expression stack
    predicate = OperationDef(sourceStr, loc, 'predicate', toks[1:], False)
    exprStack[exprStack.index(toks[0]):] = [predicate]  # replace tokens with production
    return predicate

def pushRootStep( sourceStr, loc, toks ):
    # drop the predicate op, used to clean expression stack
    if toks[0] == '/':
        op = 'rootChild'
    elif toks[0] == '//':
        op = 'rootDescendant'
    elif toks[0] == '.':
        op = 'contextItem'
    elif toks[0] == '..':
        op = 'contextItemParent'
    else:
        return
    rootStep = OperationDef(sourceStr, loc, op, toks[1:], False)
    # tok[1] or tok[2] is in exprStack (the predicate or next step), replace with composite rootStep
    for tok in toks:
        if tok in exprStack:
            exprStack[exprStack.index(tok):] = [rootStep]
            break
    return rootStep

class VariableRef:
    def __init__(self, loc, qname):
        self.name = qname
        self.loc = loc
    def __repr__(self):
        return ("variableRef('{0}')".format(self.name))

def pushVarRef( sourceStr, loc, toks ):
    qname = ModelValue.qname(xmlElement, toks[0][1:], noPrefixIsNoNamespace=True)
    if qname is None:
        modelXbrl.error(
            _("QName prefix not defined for variable reference ${0}").format(toks[0][1:]),
              "err","err:XPST0081")
        qname = ModelValue.qname(XbrlConst.xpath2err,"XPST0081") # use as qname to allow parsing to complete
    varRef = VariableRef(loc, qname)
    exprStack.append( varRef )
    return varRef

class RangeDecl:
    def __init__(self, loc, toks):
        self.rangeVar = toks[0]
        self.bindingSeq = toks[2:]
        self.loc = loc
    def __repr__(self):
        return _("rangeVar('{0}' in {1})").format(self.rangeVar.name,self.bindingSeq)

def pushRangeVar( sourceStr, loc, toks ):
    rangeDecl = RangeDecl(loc, toks)
    exprStack[exprStack.index(rangeDecl.rangeVar):] = [rangeDecl]  # replace tokens with production
    return rangeDecl

class Expr:
    def __init__(self, loc, toks):
        self.name = toks[0].name
        self.expr = toks[1:]
        self.loc = loc
    def __repr__(self):
        return "{0}{1}".format(self.name,self.expr)

def pushExpr( sourceStr, loc, toks ):
    expr = Expr(loc, toks)
    exprStack[exprStack.index(toks[0]):] = [expr]  # replace tokens with production
    return expr

ParserElement.enablePackrat()
# define grammar
decimalPoint = Literal('.')
exponentLiteral = CaselessLiteral('e')
plusorminusLiteral = Literal('+') | Literal('-')
digits = Word(nums) 
integerLiteral = Combine( Optional(plusorminusLiteral) + digits )
infLiteral = Combine( Optional(plusorminusLiteral) + Literal("INF") )
nanLiteral = Literal("NaN")
floatLiteral = ( Combine( integerLiteral +
                     ( ( decimalPoint + Optional(digits) + exponentLiteral + integerLiteral ) |
                       ( exponentLiteral + integerLiteral ) |
                       ( decimalPoint + Optional(digits) ) )
                     ) | infLiteral | nanLiteral ) 


variableRef = Word( '$', alphanums + ':_-')
qName = Word(alphas + '_',alphanums + ':_-')
ncName = Word(alphas + '_',alphanums + '_-')
prefixOp = Literal(":")

#emptySequence = Literal( "(" ) + Literal( ")" )
lParen  = Literal( "(" )
rParen  = Literal( ")" )
lPred  = Literal( "[" )
rPred  = Literal( "]" )
expOp = Literal( "^" )

commaOp = Literal(",")
forOp = Keyword("for").setParseAction(pushOp)
someOp = Keyword("some")
everyOp = Keyword("every")
quantifiedOp = ( someOp | everyOp ).setParseAction(pushOp)
inOp = Keyword("in")
returnOp = Keyword("return").setParseAction(pushOp)
satisfiesOp = Keyword("satisfies").setParseAction(pushOp)
ifOp = Keyword("if").setParseAction(pushOp)
thenOp = Keyword("then").setParseAction(pushOp)
elseOp = Keyword("else").setParseAction(pushOp)
andOp = Keyword("and")
orOp = Keyword("or")
eqValueOp = Keyword("eq")
neValueOp = Keyword("ne")
ltValueOp = Keyword("lt")
leValueOp = Keyword("le")
gtValueOp = Keyword("gt")
geValueOp = Keyword("ge")
valueCompOp = eqValueOp | neValueOp | ltValueOp | leValueOp | gtValueOp | geValueOp
isNodeOp = Keyword("is")
precedesNodeOp = Literal("<<")
followsNodeOp = Literal(">>")
nodeCompOp = isNodeOp | precedesNodeOp | followsNodeOp
neGeneralOp = Literal("!=")
leGeneralOp = Literal("<=")
ltGeneralOp = Literal("<")
geGeneralOp = Literal(">=")
gtGeneralOp = Literal(">")
eqGeneralOp = Literal("=")
generalCompOp = neGeneralOp | ltGeneralOp | leGeneralOp | gtGeneralOp | geGeneralOp | eqGeneralOp
comparisonOp = ( nodeCompOp | valueCompOp | generalCompOp ).setParseAction(pushOp)
toOp = Keyword("to").setParseAction(pushOp)
plusOp  = Literal("+")
minusOp = Literal("-")
plusMinusOp  = ( plusOp | minusOp ).setParseAction(pushOp)
multOp  = Literal("*")
divOp   = Keyword("div")
idivOp  = Keyword("idiv")
modOp  = Keyword("mod")
multDivOp = ( multOp | divOp | idivOp | modOp ).setParseAction(pushOp)
unionWordOp = Keyword("union")
unionSymbOp = Literal("|")
unionOp = unionWordOp | unionSymbOp
intersectOp = Keyword("intersect")
exceptOp = Keyword("except")
intersectExceptOp = intersectOp | exceptOp
instanceOp = Keyword("instance")
ofOp = Keyword("of")
treatOp = Keyword("treat")
asOp = Keyword("as")
castableOp = Keyword("castable")
castOp = Keyword("cast")
unaryOp  = plusOp | minusOp
occurOptionalOp = Literal("?")
occurAnyOp = multOp
occurAtLeastOnceOp = plusOp
occurrenceOp = occurOptionalOp | occurAnyOp | occurAtLeastOnceOp
wildOp = multOp
typeName = qName
elementName = qName
attributeName = qName
elementDeclaration = elementName
schemaElementTest = ( Keyword("schema-element") + Suppress(lParen) + elementDeclaration + Suppress(rParen) ).setParseAction(pushOperation)
elementNameOrWildcard = ( elementName | wildOp )
elementTest = ( Keyword("element") + Suppress(lParen) + Optional( elementNameOrWildcard + Optional( Suppress(commaOp) + typeName + Optional( Literal("?") ) ) ) + Suppress(rParen) ).setParseAction(pushOperation)
attributeDeclaration = ( attributeName )
schemaAttributeTest = ( Keyword("schema-attribute") + Suppress(lParen) + attributeDeclaration + Suppress(rParen) ).setParseAction(pushOperation)
attribNameOrWildcard = ( attributeName | wildOp )
attributeTest = ( Keyword("attribute") + Suppress(lParen) + Optional( attribNameOrWildcard + Optional( commaOp + typeName ) ) + Suppress(rParen) ).setParseAction(pushOperation)
PITest = ( Keyword("processing-instruction") + Suppress(lParen) + Optional( ncName | quotedString ) + Suppress(rParen) ).setParseAction(pushOperation)
commentTest = ( Keyword("comment") + Suppress(lParen) + Suppress(rParen) ).setParseAction(pushOperation)
textTest = ( Keyword("text") + Suppress(lParen) + Suppress(rParen) ).setParseAction(pushOperation)
documentTest = ( Keyword("document-node") + Suppress(lParen) + Optional(elementTest | schemaElementTest) + Suppress(rParen) ).setParseAction(pushOperation)
anyKindTest = ( Keyword("node") + Suppress(lParen) + Suppress(rParen) ).setParseAction(pushOperation)
kindTest = ( documentTest | elementTest | attributeTest | schemaElementTest | 
             schemaAttributeTest | PITest | commentTest | textTest | anyKindTest )
wildcard = ( Combine( ncName + prefixOp + wildOp ) | Combine( wildOp + prefixOp + ncName ) | wildOp )
nameTest = ( qName | wildcard )
nodeTest = ( kindTest | nameTest )
abbrevForwardStep = ( ( Literal("@") + nodeTest).setParseAction(pushAttr) |
                      ( nodeTest ) )
atomicType = qName
itemType = ( kindTest | Keyword("item") + lParen + rParen | atomicType )
occurrenceIndicator = ( occurOptionalOp | multOp | plusOp ) # oneOf("? * +")
sequenceType = ( ( Keyword("empty-sequence") + lParen + rParen ) | 
                 ( itemType + Optional(occurrenceIndicator) ) )
singleType  = ( atomicType + Optional( occurOptionalOp ) )
contextItem = decimalPoint
pathDescOp = Literal("//")
pathStepOp = Literal("/")
pathOp = pathStepOp | pathDescOp
pathRootOp = Regex(r"(/$|/[^/])")
axisOp = Literal("::")
forwardAxis = ((Keyword("child") + axisOp) |
               (Keyword("descendant") + axisOp) |
               (Keyword("attribute") + axisOp) |
               (Keyword("self") + axisOp) |
               (Keyword("descendant-or-self") + axisOp) |
               (Keyword("following-sibling") + axisOp) |
               (Keyword("following") + axisOp) |
               (Keyword("namespace") + axisOp))
forwardStep = ( ( forwardAxis + nodeTest) | abbrevForwardStep )
reverseAxis = ((Keyword("parent") + axisOp) |
               (Keyword("ancestor") + axisOp) |
               (Keyword("preceding-sibling") + axisOp) |
               (Keyword("preceding") + axisOp) |
               (Keyword("ancestor-or-self") + axisOp))
abbrevReverseStep = Literal("..")
reverseStep = ( ( reverseAxis + nodeTest ) | abbrevReverseStep )

expr = Forward()
atom = ( 
         ( forOp - (variableRef + inOp + expr).setParseAction(pushRangeVar) + 
                 ZeroOrMore( Suppress(commaOp) + (variableRef + inOp + expr).setParseAction(pushRangeVar) ) - 
                 (returnOp + expr).setParseAction(pushExpr) ).setParseAction(pushOperation) |
         ( quantifiedOp - (variableRef + inOp + expr).setParseAction(pushRangeVar) + 
                 ZeroOrMore( Suppress(commaOp) + (variableRef + inOp + expr ).setParseAction(pushRangeVar) ) - 
                 (satisfiesOp + expr).setParseAction(pushExpr) ).setParseAction(pushOperation) |
         ( (ifOp - Suppress(lParen) + Group(expr) + Suppress(rParen)).setParseAction(pushExpr) - 
           (thenOp + expr).setParseAction(pushOperation) - 
           (elseOp + expr).setParseAction(pushOperation) ).setParseAction(pushOperation) |
         ( qName + Suppress(lParen) + Optional(delimitedList(expr)) + Suppress(rParen) ).setParseAction(pushFunction) |
         ( floatLiteral ).setParseAction(pushFloat) |
         ( integerLiteral ).setParseAction(pushInt) |
         ( quotedString ).setParseAction(pushQuotedString) |
         ( variableRef ).setParseAction(pushVarRef)  |
         ( abbrevReverseStep ).setParseAction(pushOperation)  |
         ( contextItem ).setParseAction(pushOperation)  |
         ( qName ).setParseAction(pushQName) |
         ( Suppress(lParen) - Optional(expr) - ZeroOrMore( commaOp.setParseAction(pushOp) - expr ) - Suppress(rParen) ).setParseAction(pushSequence)
       )
stepExpr = ( ( atom + ZeroOrMore( (lPred.setParseAction( pushOp ) - expr - Suppress(rPred)).setParseAction(pushPredicate) ) ) | 
             ( (reverseStep | forwardStep) + ZeroOrMore( (lPred.setParseAction( pushOp ) - expr - Suppress(rPred)).setParseAction(pushPredicate) ) ) )
relativePathExpr = stepExpr + ZeroOrMore( ( ( pathDescOp | pathStepOp ) + stepExpr ).setParseAction( pushOperation ) )
pathExpr = ( ( pathDescOp + relativePathExpr ).setParseAction( pushRootStep ) |
             ( pathStepOp + relativePathExpr ).setParseAction( pushRootStep ) |
             ( relativePathExpr ) |
             ( ( pathRootOp ).setParseAction( pushRootStep ) ) 
           )

             
valueExpr = pathExpr

#filterExpr = ( atom + ZeroOrMore( (Suppress(lPred) - expr - Suppress(rPred)).setParseAction(pushPredicate) ) )
#axisStep = ( (reverseStep | forwardStep) + ZeroOrMore( (Suppress(lPred) - expr - Suppress(rPred)).setParseAction(pushPredicate) ) )         
#stepExpr = filterExpr | axisStep
#relativePathExpr = ( stepExpr + ZeroOrMore( ( pathStepOp | pathDescOp ) + stepExpr ).setParseAction( pushOperation ) )
#pathExpr = ( ( pathDescOp + relativePathExpr ) |
#             ( pathStepOp + relativePathExpr ) |
#             ( relativePathExpr ) |
#             ( pathStepOp ) )
#valueExpr = pathExpr
unaryExpr = ( plusMinusOp + valueExpr ).setParseAction( pushUnaryOperation ) | valueExpr
castExpr = unaryExpr + ZeroOrMore( ( castOp + asOp + singleType ).setParseAction( pushOperation ) )
castableExpr = castExpr + ZeroOrMore( ( castableOp + asOp + singleType ).setParseAction( pushOperation ) )
treatExpr = castableExpr + ZeroOrMore( ( treatOp + asOp + sequenceType ).setParseAction( pushOperation ) )
instanceOfExpr = treatExpr + ZeroOrMore( ( instanceOp + Suppress(ofOp) + sequenceType ).setParseAction( pushOperation ) )
intersectExceptExpr = instanceOfExpr + ZeroOrMore( ( intersectExceptOp + instanceOfExpr ).setParseAction( pushOperation ) )
unionExpr = intersectExceptExpr + ZeroOrMore( ( unionOp + intersectExceptExpr ).setParseAction( pushOperation ) )
multiplicitaveExpr = unionExpr + ZeroOrMore( ( multDivOp + unionExpr ).setParseAction( pushOperation ) )
additiveExpr = multiplicitaveExpr + ZeroOrMore( ( plusMinusOp + multiplicitaveExpr ).setParseAction( pushOperation ) )
rangeExpr = additiveExpr + ZeroOrMore( ( toOp + additiveExpr ).setParseAction( pushOperation ) )
comparisonExpr = rangeExpr + ZeroOrMore( ( comparisonOp + rangeExpr ).setParseAction( pushOperation ) )
andExpr = comparisonExpr + ZeroOrMore( ( andOp + comparisonExpr ).setParseAction( pushOperation ) )
orExpr = andExpr + ZeroOrMore( ( orOp + andExpr ).setParseAction( pushOperation ) )

expr << orExpr
xpathExpr = expr + StringEnd()

    
# map operator symbols to corresponding arithmetic operations
opn = { "+" : ( lambda a,b: a + b ),
        "-" : ( lambda a,b: a - b ),
        "*" : ( lambda a,b: a * b ),
        "div" : ( lambda a,b: float(a) / float(b) ),
        "idiv" : ( lambda a,b: int(a) / int(b) ),
        "^" : ( lambda a,b: a ** b ) }

# Recursive function that evaluates the stack
'''
def evaluateStack( self, s ):
    op = s.pop()
    if isinstance(op,FunctionDef):
        f = op
        args = []
        for i in range(f.argcount):
            args.insert(0, self.evaluateStack( s ))
        if f.name == "sum":
            return sum(args)
        elif f.name == "concat":
            return "".join(str(arg) for arg in args)
    elif isinstance(op,VariableRef):
        v = op
        if v.name in variables:
            return variables[v.name]
        else:
            return None
    else:
        if op in ("+","-","*","div","idiv","^"):
            op2 = self.evaluateStack( s )
            op1 = self.evaluateStack( s )
            if op1 and op2:
                return self.opn[op]( op1, op2 )
            else:
                return None
        elif op == "(":
            return self.evaluateStack( s )
        else:
            return op
'''
        
def normalizeExpr(expr):
    result = []
    prior = None
    commentNesting = 0
    for c in expr:
        if prior == '\r':
            if c == '\n' or c == '\x85':
                c = '\n'
                prior = None
            else:
                prior = '\n'
        elif c == '\85' or c == '\u2028':
            c = '\n'
        elif prior == '(' and c == ':':
            commentNesting += 1
        elif commentNesting > 0 and prior == ':' and c == ')':
            commentNesting -= 1
            prior = None
            c = None
        if prior and commentNesting <= 0:
            result.append(prior)
        prior = c
    if prior:
        if prior == '\r':
            prior = '\n'
        result.append(prior)
    return ''.join(result)

isInitialized = False

def initializeParser(modelObject):
    global isInitialized
    if not isInitialized:
        modelManager = modelObject.modelXbrl.modelManager
        modelManager.showStatus(_("Initializing formula xpath2 grammar"))
        startedAt = time.time()
        xpathExpr.parseString( "0", parseAll=True )
        modelManager.addToLog(format_string(modelManager.locale, 
                                    _("Formula xpath2 grammar initialized in %.2f secs"), 
                                    time.time() - startedAt))
        modelManager.showStatus(None)
        isInitialized = True

def exceptionErrorIndication(exception):
    errorAt = exception.column
    source = ''
    for line in exception.line.split('\n'):
        if len(source) > 0: source += '\n'
        if errorAt >= 0 and errorAt <= len(line):
            source += line[:errorAt] + '\u274b' + line[errorAt:]
            source += '\n' + ' '*(errorAt-1) + '^'
        else:
            source += line
        errorAt -= len(line) + 1
    return source

_staticExpressionFunctionContext = None
def staticExpressionFunctionContext():
    global _staticExpressionFunctionContext
    if _staticExpressionFunctionContext is None:
        _staticExpressionFunctionContext = xml.dom.minidom.parseString(
            '<?xml version="1.0" encoding="UTF-8"?>' 
            '<randomRootElement'
            ' xmlns:xlink="http://www.w3.org/1999/xlink"'
            ' xmlns:link="http://www.xbrl.org/2003/linkbase"'
            ' xmlns:xfi="http://www.xbrl.org/2008/function/instance"' 
            ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
            ' xmlns:xs="http://www.w3.org/2001/XMLSchema"'
            ' xmlns:fn="http://www.w3.org/2005/xpath-functions"'
            '/>'
             ).documentElement
    return _staticExpressionFunctionContext
    
def parse(modelObject, xpathExpression, element, name, traceType):
    from arelle.ModelFormulaObject import Trace
    global modelXbrl
    modelXbrl = modelObject.modelXbrl
    global exprStack
    exprStack = []
    global xmlElement
    xmlElement = element

    # throws ParseException
    if xpathExpression and len(xpathExpression) > 0:
        # normalize End of Line
        try:
            formulaOptions = modelXbrl.modelManager.formulaOptions

            normalizedExpr = normalizeExpr( xpathExpression )

            # should be option "compiled code"
            
            if ((formulaOptions.traceVariableSetExpressionSource and traceType == Trace.VARIABLE_SET) or
                (formulaOptions.traceVariableExpressionSource and traceType == Trace.VARIABLE) or
                (formulaOptions.traceCallExpressionSource and traceType == Trace.CALL)):
                modelXbrl.error( _("Source {0} {1}").format(name, normalizedExpr),
                    "info", "formula:trace")
            exprStack.append( ProgHeader(modelObject,name,element,normalizedExpr,traceType) )

            L = xpathExpr.parseString( normalizedExpr, parseAll=True )
            
            #modelXbrl.error( _("AST {0} {1}").format(name, L),
            #    "info", "formula:trace")

            # should be option "compiled code"
            if ((formulaOptions.traceVariableSetExpressionCode and traceType == Trace.VARIABLE_SET) or
                (formulaOptions.traceVariableExpressionCode and traceType == Trace.VARIABLE) or
                (formulaOptions.traceCallExpressionCode and traceType == Trace.CALL)):
                modelXbrl.error( _("Code {0} {1}").format(name, exprStack),
                    "info", "formula:trace")

        except (ParseException, ParseSyntaxException) as err:
            modelXbrl.error(
                _("Parse error in {0} error: {1} \n{2}").format(name,
                     err, exceptionErrorIndication(err)), 
                "err", "err:XPST0003")
        except (ValueError) as err:
            modelXbrl.error(
                _("Parsing terminated in {0} due to error: {1} \n{2}").format(name,
                     err, normalizedExpr), 
                "err", "parser:unableToParse")
        
        '''
        code = []
        compile(exprStack, code)
        pyCode = ''.join(code)
        val.modelXbrl.error(
            _("PyCode {0} {1}").format(
                 name,
                 pyCode),
            "info", "formula:trace")
        return pyCode
        '''
        return exprStack
    return None

def variableReferencesSet(exprStack, element):
    varRefSet = set()
    if exprStack:
        variableReferences(exprStack, varRefSet, element)
    return varRefSet

def variableReferences(exprStack, varRefSet, element, rangeVars=None):
    localRangeVars = []
    if rangeVars is None: rangeVars = []
    from arelle.ModelValue import qname
    for p in exprStack:
        if isinstance(p, ProgHeader):
            element = p.element
        elif isinstance(p,VariableRef):
            var = qname(element, p.name, noPrefixIsNoNamespace=True)
            if var not in rangeVars:
                varRefSet.add(var)
        elif isinstance(p,OperationDef):
            variableReferences(p.args, varRefSet, element, rangeVars)
        elif isinstance(p,Expr):
            variableReferences(p.expr, varRefSet, element, rangeVars)
        elif isinstance(p,RangeDecl):
            var = p.rangeVar.name
            rangeVars.append(var)
            localRangeVars.append(var)
            variableReferences(p.bindingSeq, varRefSet, element, rangeVars)
        elif hasattr(p, '__iter__') and not isinstance(p, str):
            variableReferences(p, varRefSet, element, rangeVars)
    for localRangeVar in localRangeVars:
        if localRangeVar in rangeVars:
            rangeVars.remove(localRangeVar)

'''
pyOpForXPathOp = {
    '+': '+', '-':'-', '*':'*', ',':',',
    'div': '/', 'idiv': '/', 'mod':'%', 
    'gt': '>', 'ge': '>=', 'eq':'==', 'ne':'!=', 'lt':'<', 'le':'<=',
    '>': '>', '>=': '>=', '=':'==', '!=':'!=', '<':'<', '<=':'<=',
    }
pyGeneratorExprOp = { 'for':'flatten(tuple(', 'some':'any(', 'every':'all('}
pyGeneratorExprEnd = { 'for':'))', 'some':')', 'every':')'}

def compile(exprStack, code, inScopeVars=None):
    if inScopeVars is None: inScopeVars = []
    codeStartIndex = len(code)
    for p in exprStack:
        if isinstance(p,str):
            code.append(p.__repr__())
        elif isinstance(p,int) or isinstance(p,float):
            code.append(str(p))
        elif isinstance(p,VariableRef):
            code.append((" {0} ","variables.get({0})")[p.name in inScopeVars].format(p.name))
        elif isinstance(p,QNameDef):
            code.append(" '{0}' ".format(p.name))
        elif isinstance(p,OperationDef):
            op = p.name
            if isinstance(op, QNameDef):
                code.append("{0}(".format(op.name))
                compile(p.args, code)
                code.append(")")
            elif op in pyOpForXPathOp:
                code.append(" {0} ".format(pyOpForXPathOp[p.name]))
                compile(p.args, code)
            elif op in ('u+', 'u-'):
                code.append(" {0}".format(op[1]))
                compile(p.args, code)
            elif op == "sequence":
                code.append('(')
                compile(p.args, code)
                code.append(')')
            elif op == "predicate":
                code.append('predicate(')
                compile(p.args, code)
                code.append(')')
            elif op == "range":
                code.insert(codeStartIndex, 'range(')
                code.append(', ')
                compile(p.args, code)
                code.append(' + 1 )')
            elif op in pyGeneratorExprOp: # for, some, every
                code.append('{0}'.format(pyGeneratorExprOp[op]))
                rangeVars = tuple(rv.rangeVar.name for rv in p.args[0:-1])
                # operation has all in-scope variables
                for rv in rangeVars: inScopeVars.append(rv)
                compile(p.args[-1:], code)   # return expression
                for rv in rangeVars: inScopeVars.remove(rv)
                # for clauses have prior in-scope variables
                for i in range(len(p.args) - 1):
                    if i > 0: inScopeVars.append(rangeVars[i-1])
                    compile(p.args[i:i+1], code) # for expression
                for i in range(len(p.args) - 2): inScopeVars.remove(rangeVars[i])
                code.append(pyGeneratorExprEnd[op])
            elif op == "pathRoot":
                code.append(" self.stepAxis(self.inputXbrlInstance.xmlRootElement) ")
                compile(p.args, code)
            elif op == "/":
                code.append(" .stepAxis('child::' ")
                compile(p.args, code)
                code.append(" )")
            elif op == "//":
                code.append(" .stepAxis('descendant::' ")
                compile(p.args, code)
                code.append(" )")
        elif isinstance(p,OpDef):
            op = p.name
            if op in pyOpForXPathOp:
                code.append("{0}".format(pyOpForXPathOp[p.name]))
        elif isinstance(p,RangeDecl):
            code.append(' for {0} in '.format(p.rangeVar.name))
            compile(p.bindingSeq, code)
        elif isinstance(p,Expr):
            if p.name in ("return","satisfies"):
                compile(p.expr, code)
'''
                
def codeModule(code):
    return \
        '''
        def flatten(x):
            result = []
            for el in x:
                if hasattr(el, "__iter__") and not isinstance(el, basestring):
                    result.extend(flatten(el))
                else:
                    result.append(el)
            return result
        ''' + \
        ''.join(code)

def parser_unit_test():

    test1 = "3*7+5"
    test1a = "5+3*7"
    test1b = "(5+3)*7"
    test2a ="concat('abc','def')" 
    test2b ="'abc'" 
    test3 = "if (sum(1,2,3) gt 123) then 33 else 44"
    test3a = "sum(1,2,3,min(4,5,6))"
    
    '''
                 "for $a in $b, $c in $d, $e in $f return 'foo'",
                 "for $a in $b, $c in $d return (3 + 4)",
                 "some $a in $b, $c in $d satisfies (3 * $a + 4 * $b)",
                 "every $a in $b, $c in $d satisfies (3 + 4)",
                 "for $a in $b return 'foo'",
                 "for $a in $b return for $c in $d return $e",
                 "if ($a) then $b else $c",
                 "if $a then $b else $c",
                 "if ($a) then (1,2,3) else (4,5,6)",
                 "if ($a + 4) then (1,2,3) else (4,5,6)",
                 "if ($a) then $b else for $a in $b return 'foo'",
                 "3 eq 3", "3=3", "3>2", "3 gt 2",
                 "3 (: :) eq 3", "$ab(: (: xxx :) :)+$cd",
                 "123", "'abc'",
                 "(1,2,3)",
                 "(1)",
                 "$a * 3 div 4",
                 "$p:a + $p:b",
                 "(3 * 5) + (4)",
                 "3 gt 5 * 4",
                 "$a + INF", "$a + -INF", "NaN * 2",
                 "$ab_cd + 2", "$a-bc + 2", " 2 - $a-bc",
                 "if ($a) then 33 else 44",
                 "(( 1 + 2) * ( -3 + 1)) + 1",
                 "$a+$b+$c",
                 "(1,2,3)", "((1+2*3),(4))", "for $a in ($b,4,5) return ('foo','bar')",
                 "$a/b/c", 
                 "-$a", 
                 "$a[2]", "$a[id=$b]", "/a/b/c [ @id='abc' ]",
                 "foo/bar", 
                 "/",
                 "//foo/bar", 
                 "/foo/bar", 
                 "/foo/bar[@id=3]", 
                 "/foo[@x='y']/bar[@id=3]", 
                 "//foo/bar", 
                 "/foo/bar", 
                 "/foo/bar[@id=3]", 
                 "/foo[@x='y']/bar[@id=3]", 
                 "/foo[@x='y']",
                 "/foo/bar[@id=3]", 
                 "/foo[@x='y']/bar[@id=3]", 
                 "123", "123.45", "123e6", "123.45e6", "'abc'",
                 "(1,2,3)",
                 "(1)",
                 "$a * 3 div 4",
                 "(3 * 5) + (4)",
                 "3 gt 5 * 4",
                 "$a + INF", "$a + -INF", "NaN * 2",
                 "$p:a + $p:b",
                 "some $j in ('a','b','c') satisfies $j eq 'a'",
                 "every $j in ('a','b','c') satisfies len($j) ge 1",
                 "sum(1+2+3)",
                 "sum(1+2,3*4)",
                 "sum((1+2,3*4))",
                 "sum( $a, $b )",
                 "concat ('abc' , 'def', 'a''s')",
                 "for $a in $b, $c in $d, $e in $f return 'foo'",
                  for $pd in $v:PDkids,
                      $ev in $v:EVkids[
                         xfi:fact-dimension-s-equal2(., $pd,
                              QName('http://www.example.com/wgt-avg',
                             'ExposuresDimension'))
                          ]
                      return $pd * $ev
                 "/a/b/c",
                 "//", "//a", "a//b",
                 "/", "/a", "a",
                 "/a/b/c", "/a//b/c", "a/b//c", "a//b/c",
                 "/a/b/c[@id='abc']",
                 "$a[2]", "$a[id=$b]", 
                 "/a/b/c",
                 "//", "//a", "a//b",
                 "/", "/a", "a",
                 "/a/b/c", "/a//b/c", "a/b//c", "a//b/c",
                 "23 to 24",
                 "for $i in 3 to 5 return 999",
                 "$a instance of element(foo)",
                 "$a instance of node()",
                 "$a instance of text()",
                 "$a instance of document-node(element(foo))",
                 "$a instance of element(foo, bar?)",
                 "$a instance of element(*, bar?)",
                 "/a/b/c[@id='abc']",
                 "$a[2]", "$a[id=$b]", 
                 "$a is /a/b/c",
                 "$a is //b[2]",
                 "//b[2]", "/b[2] * 2 = $a", 
                 "../a/b",
                 "/a/b/text( ) eq 'z'",
                 "/a/b/node()",
                 "/a/b/item()",
                 "/a/b/element(c)",
                 "$a instance of element(foo)+",
                 "$a instance of node()+",
                 "node-name(.)",
                 "node-name(./a)",
                 "node-name(/)",
                 "node-name(/a/b/c)",
                 "()", "(1)",
                 "empty( () )",
    '''
    #tests = [locals()[t] for t in locals().keys() if t.startswith("test")]
    tests = [test1, test1a, test1b, test2a, test2b, test3, test3a]
    for test in (
                 "./*[local-name() eq 'a']",
                 ".",
                 "..",
                 "a/*[1]",
                 "a/*:z[1]",
                 "a/z:*[1]",
                 "//*[@id eq 'context-for-xpath-rule']//xbrldi:explicitMember[2]",
                 ):
        # Start with a blank exprStack and a blank varStack
        exprStack = []
        xmlElement = None

        # try parsing the input string
        try:
            L=xpathExpr.parseString( normalizeExpr( test ), parseAll=True )
        except (ParseException, ParseSyntaxException) as err:
            L=['Parse Failure',test,err]
        
        # show result of parsing the input string
        if debug_flag: print (test, "->", L)
        if len(L)==0 or L[0] != 'Parse Failure':
            if debug_flag: 
                print ("exprStack=", exprStack)
                '''
                code = []
                compile(exprStack, code)
                print ("code=", ''.join(code))
                '''
            # calculate result , store a copy in ans , display the result to user
            '''
            result=evaluateStack(exprStack)
            variables['ans']=result
            print (result)
    
            # Assign result to a variable if required
            if debug_flag: print ("var=",varStack)
            if len(varStack)==1:
                variables[varStack.pop()]=result
            if debug_flag: print ("variables=",variables)
            '''
        else:
            print ('Parse Failure')
            print (L[2].line)
            print (" "*(L[2].column-1) + "^")
            print (L[2])


if __name__ == "__main__":
    parser_unit_test()