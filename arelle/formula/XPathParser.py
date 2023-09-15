'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

import sys
import time
import traceback
from collections.abc import Iterable
from decimal import Decimal
from typing import Any, List, Sequence, TYPE_CHECKING, Union
from xml.dom import minidom

from pyparsing import (
    CaselessLiteral,
    Combine,
    Forward,
    Group,
    Keyword,
    Literal,
    Opt,
    ParseBaseException,
    ParseException,
    ParseResults,
    ParseSyntaxException,
    ParserElement,
    Regex,
    StringEnd,
    Suppress,
    Word,
    ZeroOrMore,
    alphanums,
    alphas,
    delimitedList as DelimitedList,
    nums,
    quoted_string,
)

from arelle import ModelValue, XbrlConst, XmlUtil
from arelle.Locale import format_string
from arelle.PluginManager import pluginClassMethods

if TYPE_CHECKING:
    from arelle.ModelFormulaObject import ModelFormulaResource
    from arelle.ModelXbrl import ModelXbrl
    from arelle.ModelManager import ModelManager
    from arelle.ModelObject import ModelObject
    from arelle.ModelValue import QName
    from arelle.formula.XPathContext import XPathException
    from arelle.typing import TypeGetText

_: TypeGetText  # Handle gettext

FormulaToken = Union[
    float,
    int,
    str,
    Decimal,
    'Expr',
    'OpDef',
    'OperationDef',
    'ProgHeader',
    'QNameDef',
    'RangeDecl',
    'VariableRef',
]

RecursiveFormulaTokens = Sequence[Union[FormulaToken, 'RecursiveFormulaTokens']]

ExpressionStack = List[FormulaToken]

ixtFunctionNamespaces: set[str] = set()


# Debugging flag can be set to either "debug_flag=True" or "debug_flag=False"
debug_flag = True

exprStack: ExpressionStack = []
xmlElement: ModelObject | None = None
modelXbrl: ModelXbrl | None = None
pluginCustomFunctionQNames: set[QName] | None = None


class ProgHeader:
    def __init__(
            self,
            modelObject: ModelFormulaResource,
            name: str,
            element: ModelObject,
            sourceStr: str,
            traceType: int,
    ) -> None:
        self.modelObject = modelObject
        self.name = name
        self.element: ModelObject | None = element
        self.sourceStr = sourceStr
        self.traceType = traceType

    def __repr__(self) -> str:
        return "ProgHeader({0},{1})".format(self.name, self.modelObject)


def exprStackToksRIndex(toks: ParseResults) -> int:
    toksList: list[FormulaToken] = toks.asList()
    lenToks = len(toksList)
    if exprStack[-lenToks:] == toksList:  # attempt to match from right side
        return -lenToks
    # toks could need flattening to be comparable to exprStack, for now just check tok
    _tok0 = toks[0]
    for i in range(len(exprStack) - 1, 0, -1):
        if exprStack[i] == _tok0:
            return i
    raise Exception("Unable to determine replacement index of ParseResults {} in expression stack {}".format(toks, exprStack))


def exprStackTokRIndex(tok: FormulaToken) -> int:
    for i in range(len(exprStack) - 1, 0, -1):
        if exprStack[i] == tok:
            return i
    raise Exception("Unable to determine replacement index of ParseResult token {} in expression stack {}".format(tok, exprStack))


def pushFirst(sourceStr: str, loc: int, toks: ParseResults) -> None:
    exprStack.append(toks[0])


def pushFloat(sourceStr: str, loc: int, toks: ParseResults) -> float:
    num = float(toks[0])
    exprStack.append(num)
    return num


def pushInt(sourceStr: str, loc: int, toks: ParseResults) -> int:
    num = int(toks[0])
    exprStack.append(num)
    return num


def pushDecimal(sourceStr: str, loc: int, toks: ParseResults) -> Decimal:
    num = Decimal(toks[0])
    exprStack.append(num)
    return num


def pushQuotedString(sourceStr: str, loc: int, toks: ParseResults) -> str:
    _str: str = toks[0]
    q = _str[0]
    dequotedStr = _str[1:-1].replace(q + q, q)
    exprStack.append(dequotedStr)
    return dequotedStr


class QNameDef(ModelValue.QName):
    def __init__(
            self,
            loc: int,
            prefix: str | None,
            namespaceURI: str | None,
            localName: str,
            isAttribute: bool = False,
            axis: str | None = None
    ) -> None:
        super(QNameDef, self).__init__(prefix, namespaceURI, localName)
        self.unprefixed = prefix is None
        self.isAttribute = isAttribute or axis == "attribute"
        self.loc = loc
        self.axis = axis or None  # store "" from rpartition of step as None

    def __hash__(self) -> int:
        return self.qnameValueHash

    def __repr__(self) -> str:
        return "{0}QName({1})".format('@' if self.isAttribute else '', str(self))

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, QNameDef):
            return other.loc == self.loc and super(QNameDef, self).__eq__(other) and other.axis == self.axis
        else:
            return super(QNameDef, self).__eq__(other)

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)


defaultNsmap = {
    "fn": "http://www.w3.org/2005/xpath-functions",
    "xml": "http://www.w3.org/XML/1998/namespace",
}

axesSupported = {
    "",
    "child",
    "descendant",
    "attribute",
    "self",
    "descendant-or-self",
    "following-sibling",
    "following",
    "namespace",
    "parent",
    "ancestor",
    "preceding-sibling",
    "preceding",
    "ancestor-or-self",
}


def pushQName(sourceStr: str, loc: int, toks: ParseResults) -> QNameDef | None:
    assert modelXbrl is not None
    step = toks[0]
    axis, sep, qname = step.rpartition("::")  # axes are not splitting correctly
    if axis not in axesSupported:
        modelXbrl.error("err:XPST0010",
            _("Axis %(axis)s is not supported in %(step)s"),
            modelObject=xmlElement,
            axis=axis, step=step)
        return None
    if xmlElement is not None:
        nsLocalname: tuple[str | None, str, str | None]
        if qname == '*':  # prevent simple wildcard from taking the default namespace
            nsLocalname = (None, '*', None)
        else:
            prefixedNameToNamespaceLocalname = XmlUtil.prefixedNameToNamespaceLocalname(xmlElement, qname, defaultNsmap=defaultNsmap)
            if prefixedNameToNamespaceLocalname is None:
                if qname.startswith("*:"):  # wildcad QName special case
                    prefix, sep, localName = qname.partition(":")
                    q = QNameDef(loc, prefix, prefix, localName, axis=axis)
                    if len(exprStack) == 0 or exprStack[-1] != q:
                        exprStack.append(q)
                    return q
                modelXbrl.error("err:XPST0081",
                    _("QName prefix not defined for %(name)s"),
                    modelObject=xmlElement,
                    name=qname)
                return None
            nsLocalname = prefixedNameToNamespaceLocalname

        if (nsLocalname == (XbrlConst.xff, "uncovered-aspect", "xff") and
            xmlElement.localName not in ("formula", "consistencyAssertion", "valueAssertion", "message")):
                modelXbrl.error("xffe:invalidFunctionUse",
                    _("Function %(name)s cannot be used on an XPath expression associated with a %(name2)s"),
                    modelObject=xmlElement,
                    name=qname, name2=xmlElement.localName)
    else:
        nsLocalname = (None, qname, None)
    q = QNameDef(loc, nsLocalname[2], nsLocalname[0], nsLocalname[1], axis=axis)
    if (qname not in ("INF", "NaN", "for", "some", "every", "return") and
        len(exprStack) == 0 or exprStack[-1] != q):
        exprStack.append(q)
    return q


def pushAttr(sourceStr: str, loc: int, toks: ParseResults) -> QNameDef:
    # usually has QName of attr already on exprstack, get rid of it
    if toks[0] == '@' and len(exprStack) > 0 and len(toks) > 1 and exprStack[-1] == toks[1]:
        exprStack.remove(toks[1])
    if isinstance(toks[1], QNameDef):
        attr = toks[1]
        attr.isAttribute = True
    else:
        # BUG this won't work, wrong arguments !!!!
        # attr = QNameDef(loc, tok[1], isAttribute=True)
        raise ValueError(f"Unable to create QNameDef from attr: loc {loc} sourceStr {sourceStr}")
    exprStack.append(attr)
    return attr


class OpDef:
    def __init__(self, loc: int, toks: ParseResults) -> None:
        self.name: str = toks[0]
        self.loc = loc

    def __repr__(self) -> str:
        return "op({0})".format(self.name)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, OpDef) and other.name == self.name and other.loc == self.loc

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)


def pushOp(sourceStr: str, loc: int, toks: ParseResults) -> OpDef:
    op = OpDef(loc, toks)
    # assure this operand not already on stack
    if len(exprStack) == 0 or exprStack[-1] != op:
        exprStack.append(op)
    return op


class OperationDef:

    args: list[FormulaToken]

    def __init__(self, sourceStr: str, loc: int, name: str | QNameDef, toks: ParseResults | list[FormulaToken], skipFirstTok: bool) -> None:
        self.sourceStr = sourceStr
        self.loc = loc
        self.name = name
        if skipFirstTok:
            toks1 = toks[1] if len(toks) > 1 else None
            if isinstance(toks1, str) and isinstance(name, str) and name in ('/', '//', 'rootChild', 'rootDescendant'):
                if toks1 == '*':
                    toks1 = QNameDef(loc, None, '*', '*')
                elif toks1.startswith('*:'):
                    toks1 = QNameDef(loc, None, '*', toks1[2:])
                elif toks1.endswith(':*'):
                    prefix = toks1[:-2]
                    assert xmlElement is not None
                    ns = XmlUtil.xmlns(xmlElement, prefix)
                    if ns is None:
                        assert modelXbrl is not None
                        modelXbrl.error("err:XPST0081",
                            _("wildcard prefix not defined for %(token)s"),
                            modelObject=xmlElement,
                            token=toks1)
                    toks1 = QNameDef(loc, prefix, ns, '*')
                self.args = [toks1] + toks[2:]  # special case for wildcard path segment
            else:
                self.args = toks[1:]
            '''
            self.args = toks[1:]
            '''
        else:  # for others first token is just op code, no expression
            self.args = toks[:]

    def __repr__(self) -> str:
        if isinstance(self.name, QNameDef):
            return "{0}{1}".format(str(self.name), self.args)
        else:
            # return ("{1} {0}".format(self.name, self.args))
            return "{0}{1}".format(self.name, self.args)


def pushOperation(sourceStr: str, loc: int, toks: ParseResults) -> OperationDef:
    if isinstance(toks[0], str):
        name = toks[0]
        removeOp = False
        tok: FormulaToken
        for tok in toks[1:]:
            if not isinstance(tok, str) and tok in exprStack:
                removeOp = True
                removeFrom = tok
                break
    else:
        name = toks[0].name
        removeOp = toks[0] in exprStack
        removeFrom = toks[0]
    operation = OperationDef(sourceStr, loc, name, toks, name != "if")
    if removeOp:
        # exprStack[exprStack.index(removeFrom):] = [operation]  # replace tokens with production
        exprStack[exprStackTokRIndex(removeFrom):] = [operation]  # replace tokens with production
    else:

        exprStack.append(operation)
    return operation


def pushUnaryOperation(sourceStr: str, loc: int, toks: ParseResults) -> OperationDef:
    if isinstance(toks[0], str):
        operation = OperationDef(sourceStr, loc, 'u' + toks[0], toks, True)
        exprStack.append(operation)
    else:
        operation = OperationDef(sourceStr, loc, 'u' + toks[0].name, toks, True)
        # exprStack[exprStack.index(toks[0]):] = [operation]  # replace tokens with production
        exprStack[exprStackToksRIndex(toks):] = [operation]  # replace tokens with production
    return operation


def pushFunction(sourceStr: str, loc: int, toks: ParseResults) -> OperationDef:
    name = toks[0]
    operation = OperationDef(sourceStr, loc, name, toks, True)
    exprStack[exprStack.index(toks[0]):] = [operation]  # replace tokens with production
    if isinstance(name, QNameDef):  # function call
        ns = name.namespaceURI
        assert modelXbrl is not None
        assert modelXbrl.modelManager.customTransforms is not None
        if (
            not name.unprefixed
            and ns not in {XbrlConst.fn, XbrlConst.xfi, XbrlConst.xff, XbrlConst.xsd}
            and ns not in ixtFunctionNamespaces
            and name not in modelXbrl.modelManager.customTransforms
        ):
            assert pluginCustomFunctionQNames is not None
            # indexed by both [qname] and [qname,arity]
            if name not in modelXbrl.modelCustomFunctionSignatures and name not in pluginCustomFunctionQNames:
                assert xmlElement is not None
                modelXbrl.error("xbrlve:noCustomFunctionSignature",
                    _("No custom function signature for %(custFunction)s in %(resource)s"),
                    modelObject=xmlElement,
                    resource=xmlElement.localName,
                    custFunction=name)
    return operation


def pushSequence(sourceStr: str, loc: int, toks: ParseResults) -> OperationDef:
    operation = OperationDef(sourceStr, loc, 'sequence', toks, False)
    # print ("push seq toks={} \n  op={}\n  exprStk1={}".format(toks, operation, exprStack))
    if len(toks) == 0:  # empty sequence
        exprStack.append(operation)
    else:
        # exprStack[exprStack.index(toks[0]):] = [operation]  # replace tokens with production
        exprStack[exprStackToksRIndex(toks):] = [operation]  # replace tokens with production
    # print ("  exprStk2={}".format(exprStack))
    return operation


def pushPredicate(sourceStr: str, loc: int, toks: ParseResults) -> OperationDef:
    # drop the predicate op, used to clean expression stack
    predicate = OperationDef(sourceStr, loc, 'predicate', toks[1:], False)
    # exprStack[exprStack.index(toks[0]):] = [predicate]  # replace tokens with production
    exprStack[exprStackToksRIndex(toks):] = [predicate]  # replace tokens with production
    return predicate


def pushRootStep(sourceStr: str, loc: int, toks: ParseResults) -> OperationDef | None:
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
        return None
    rootStep = OperationDef(sourceStr, loc, op, toks[1:], False)
    # tok[1] or tok[2] is in exprStack (the predicate or next step), replace with composite rootStep
    tok: FormulaToken
    for tok in toks:
        if tok in exprStack:
            exprStack[exprStack.index(tok):] = [rootStep]
            break
    return rootStep


class VariableRef:
    def __init__(self, loc: int, qname: QName) -> None:
        self.name = qname
        self.loc = loc

    def __repr__(self) -> str:
        return "variableRef('{0}')".format(self.name)


def pushVarRef(sourceStr: str, loc: int, toks: ParseResults) -> VariableRef:
    qname = ModelValue.qname(xmlElement, toks[0][1:], noPrefixIsNoNamespace=True)  # type: ignore[arg-type]
    if qname is None:
        assert modelXbrl is not None
        modelXbrl.error("err:XPST0081",
            _("QName prefix not defined for variable reference $%(variable)s"),
            modelObject=xmlElement,
            variable=toks[0][1:])
        qname = ModelValue.qname(XbrlConst.xpath2err, "XPST0081")  # use as qname to allow parsing to complete
    varRef = VariableRef(loc, qname)
    exprStack.append(varRef)
    return varRef


class RangeDecl:
    def __init__(self, loc: int, toks: ParseResults) -> None:
        self.rangeVar: VariableRef = toks[0]
        self.bindingSeq: list[FormulaToken] = toks[2:]
        self.loc = loc

    def __repr__(self) -> str:
        return _("rangeVar('{0}' in {1})").format(self.rangeVar.name, self.bindingSeq)


def pushRangeVar(sourceStr: str, loc: int, toks: ParseResults) -> RangeDecl:
    rangeDecl = RangeDecl(loc, toks)
    exprStack[exprStack.index(rangeDecl.rangeVar) :] = [rangeDecl]  # replace tokens with production
    return rangeDecl


class Expr:
    def __init__(self, loc: int, toks: ParseResults) -> None:
        self.name: str = toks[0].name
        self.expr: RecursiveFormulaTokens = toks[1:]
        self.loc = loc

    def __repr__(self) -> str:
        return "{0}{1}".format(self.name, self.expr)


def pushExpr(sourceStr: str, loc: int, toks: ParseResults) -> Expr:
    expr = Expr(loc, toks)
    # exprStack[exprStack.index(toks[0]):] = [expr]  # replace tokens with production
    exprStack[exprStackToksRIndex(toks):] = [expr]  # replace tokens with production
    return expr


# define grammar
variableRef = Regex(
    "[$]"  # variable prefix
    # optional prefix part
    "([A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD_]"
    "[A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040\xB7_.-]*:)?"
    # localname part
    "([A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD_]"
    "[A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040\xB7_.-]*)"
)
# for now :: axis step is expected in QName production (processed in parser's QName structure)
# qName = Word(alphas + '_',alphanums + ':_-.*') # note: this will pick up forward and reverse axes and handle by pushQName

# try to match axis step, prefix, and localname, allowin wildcard prefix or localname
# don't grab occurence indicator if on qname, e.g., not * of xs:string*
qName = Regex(
    "([A-Za-z-]+::)?"  # axis step part (just ansi characters)
    # prefix or wildcard-prefix part
    "([A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD_]"
    "[A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040\xB7_.-]*:|[*]:)?"
    # localname or wildcard-localname part
    "([A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD_]"
    "[A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040\xB7_.-]*|[*])"
)
# above qName definition allows double :: and excludes non-ascii letters
# qName = Regex("[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
#               r"[_\-\."
#               "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*"
#               "[:]?"
#               r"[_\-\."
#               "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*")

ncName = Word(alphas + '_', alphanums + '_-.')
prefixOp = Literal(":")

exponentLiteralStr = r"[eE]"
plusorminusLiteralStr = r"[+-]"
digitsStr = r"\d+"
optionalDigitsStr = r"\d*"
decimalPointStr = r"\."
nanLiteralStr = r"NaN"
integerLiteralStr = plusorminusLiteralStr + r"?" + digitsStr
decimalFractionLiteralStr = plusorminusLiteralStr + "?" + decimalPointStr + digitsStr
infLiteralStr = plusorminusLiteralStr + r"?INF"

decimalPoint = Literal('.')
exponentLiteral = Regex(exponentLiteralStr)
plusorminusLiteral = Literal('+') | Literal('-')
digits = Word(nums)
integerLiteral = Regex(integerLiteralStr)
decimalFractionLiteral = Regex(decimalFractionLiteralStr)
infLiteral = Regex(infLiteralStr)
nanLiteral = Regex(nanLiteralStr)
floatLiteral = Regex(
    integerLiteralStr
    + r"(" + decimalPointStr + optionalDigitsStr + ")?"
    + exponentLiteralStr + integerLiteralStr
    + r"|"
    + decimalFractionLiteralStr + exponentLiteralStr + integerLiteralStr
    + r"|"
    + infLiteralStr
    + r"|"
    + nanLiteralStr
)
decimalLiteral = Regex(
    integerLiteralStr + decimalPointStr + optionalDigitsStr
    + r"|"
    + decimalFractionLiteralStr
)

# emptySequence = Literal( "(" ) + Literal( ")" )
lParen = Literal("(")
rParen = Literal(")")
lPred = Literal("[")
rPred = Literal("]")
expOp = Literal("^")

commaOp = Literal(",")
forOp = Keyword("for").set_parse_action(pushOp)
someOp = Keyword("some")
everyOp = Keyword("every")
quantifiedOp = (someOp | everyOp).set_parse_action(pushOp)
inOp = Keyword("in")
returnOp = Keyword("return").set_parse_action(pushOp)
satisfiesOp = Keyword("satisfies").set_parse_action(pushOp)
ifOp = Keyword("if").set_parse_action(pushOp)
thenOp = Keyword("then").set_parse_action(pushOp)
elseOp = Keyword("else").set_parse_action(pushOp)
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
generalCompOp = neGeneralOp | leGeneralOp | ltGeneralOp | geGeneralOp | gtGeneralOp | eqGeneralOp
comparisonOp = (nodeCompOp | valueCompOp | generalCompOp).set_parse_action(pushOp)
toOp = Keyword("to").set_parse_action(pushOp)
plusOp = Literal("+")
minusOp = Literal("-")
plusMinusOp = (plusOp | minusOp).set_parse_action(pushOp)
multOp = Literal("*")
divOp = Keyword("div")
idivOp = Keyword("idiv")
modOp = Keyword("mod")
multDivOp = (multOp | divOp | idivOp | modOp).set_parse_action(pushOp)
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
unaryOp = plusOp | minusOp
occurOptionalOp = Literal("?")
occurAnyOp = multOp
occurAtLeastOnceOp = plusOp
occurrenceOp = occurOptionalOp | occurAnyOp | occurAtLeastOnceOp
wildOp = multOp
typeName = qName
elementName = qName
attributeName = qName
elementDeclaration = elementName
schemaElementTest = (
    Keyword("schema-element")
    + Suppress(lParen)
    + elementDeclaration
    + Suppress(rParen)
).set_parse_action(pushOperation)
elementNameOrWildcard = elementName | wildOp
elementTest = (
    Keyword("element")
    + Suppress(lParen)
    + Opt(
        elementNameOrWildcard
        + Opt(
            Suppress(commaOp)
            + typeName
            + Opt(Literal("?"))
        )
    )
    + Suppress(rParen)
).set_parse_action(pushOperation)
attributeDeclaration = attributeName
schemaAttributeTest = (
    Keyword("schema-attribute")
    + Suppress(lParen)
    + attributeDeclaration
    + Suppress(rParen)
).set_parse_action(pushOperation)
attribNameOrWildcard = attributeName | wildOp
attributeTest = (
    Keyword("attribute")
    + Suppress(lParen)
    + Opt(attribNameOrWildcard + Opt(commaOp + typeName))
    + Suppress(rParen)
).set_parse_action(pushOperation)
PITest = (
    Keyword("processing-instruction")
    + Suppress(lParen)
    + Opt(ncName | quoted_string)
    + Suppress(rParen)
).set_parse_action(pushOperation)
commentTest = (
        Keyword("comment")
        + Suppress(lParen)
        + Suppress(rParen)
).set_parse_action(pushOperation)
textTest = (
        Keyword("text")
        + Suppress(lParen)
        + Suppress(rParen)
).set_parse_action(pushOperation)
documentTest = (
    Keyword("document-node")
    + Suppress(lParen)
    + Opt(elementTest | schemaElementTest)
    + Suppress(rParen)
).set_parse_action(pushOperation)
anyKindTest = (
        Keyword("node")
        + Suppress(lParen)
        + Suppress(rParen)
).set_parse_action(pushOperation)
kindTest = (
    documentTest
    | elementTest
    | attributeTest
    | schemaElementTest
    | schemaAttributeTest
    | PITest
    | commentTest
    | textTest
    | anyKindTest
)
wildcard = Combine(ncName + prefixOp + wildOp) | Combine(wildOp + prefixOp + ncName) | wildOp
nameTest = qName | wildcard
nodeTest = kindTest | nameTest
abbrevForwardStep = (Literal("@") + nodeTest).set_parse_action(pushAttr) | (nodeTest)
atomicType = qName
itemType = kindTest | Keyword("item") + lParen + rParen | atomicType
occurrenceIndicator = occurOptionalOp | multOp | plusOp  # one_of("? * +")
sequenceType = (Keyword("empty-sequence") + lParen + rParen) | (itemType + Opt(occurrenceIndicator))
singleType = atomicType + Opt(occurOptionalOp)
contextItem = decimalPoint
pathDescOp = Literal("//")
pathStepOp = Literal("/")
pathOp = pathStepOp | pathDescOp
pathRootOp = Regex(r"(/$|/[^/])")
axisOp = Literal("::")
forwardAxis = (
    (Keyword("child") + axisOp)
    | (Keyword("descendant") + axisOp)
    | (Keyword("attribute") + axisOp)
    | (Keyword("self") + axisOp)
    | (Keyword("descendant-or-self") + axisOp)
    | (Keyword("following-sibling") + axisOp)
    | (Keyword("following") + axisOp)
    | (Keyword("namespace") + axisOp)
)
forwardStep = (forwardAxis + nodeTest) | abbrevForwardStep
reverseAxis = (
    (Keyword("parent") + axisOp)
    | (Keyword("ancestor") + axisOp)
    | (Keyword("preceding-sibling") + axisOp)
    | (Keyword("preceding") + axisOp)
    | (Keyword("ancestor-or-self") + axisOp)
)
abbrevReverseStep = Literal("..")
reverseStep = (reverseAxis + nodeTest) | abbrevReverseStep
step = forwardStep | reverseStep

expr = Forward()
atom = (
    (
        forOp
        - (variableRef + inOp + expr).set_parse_action(pushRangeVar)
        + ZeroOrMore(Suppress(commaOp) + (variableRef + inOp + expr).set_parse_action(pushRangeVar))
        - (returnOp + expr).set_parse_action(pushExpr)
    ).set_parse_action(pushOperation)
    | (
        quantifiedOp
        - (variableRef + inOp + expr).set_parse_action(pushRangeVar)
        + ZeroOrMore(Suppress(commaOp) + (variableRef + inOp + expr).set_parse_action(pushRangeVar))
        - (satisfiesOp + expr).set_parse_action(pushExpr)
    ).set_parse_action(pushOperation)
    | (
        (ifOp - Suppress(lParen) + Group(expr, aslist=True) + Suppress(rParen)).set_parse_action(pushExpr)
        - (thenOp + expr).set_parse_action(pushOperation)
        - (elseOp + expr).set_parse_action(pushOperation)
    ).set_parse_action(pushOperation)
    | (qName + Suppress(lParen) + Opt(DelimitedList(expr)) + Suppress(rParen)).set_parse_action(pushFunction)
    | floatLiteral.set_parse_action(pushFloat)
    | decimalLiteral.set_parse_action(pushDecimal)
    | integerLiteral.set_parse_action(pushInt)
    | quoted_string.set_parse_action(pushQuotedString)
    | variableRef.set_parse_action(pushVarRef)
    | abbrevReverseStep.set_parse_action(pushOperation)
    | contextItem.set_parse_action(pushOperation)
    | qName.set_parse_action(pushQName)
    | (
        Suppress(lParen) - Opt(expr) - ZeroOrMore(commaOp.set_parse_action(pushOp) - expr) - Suppress(rParen)
    ).set_parse_action(pushSequence)
)
# stepExpr = ( ( atom + ZeroOrMore( (lPred.set_parse_action( pushOp ) - expr - Suppress(rPred)).set_parse_action(pushPredicate) ) ) |
#             ( (reverseStep | forwardStep) + ZeroOrMore( (lPred.set_parse_action( pushOp ) - expr - Suppress(rPred)).set_parse_action(pushPredicate) ) ) )
stepExpr = (
    atom + ZeroOrMore((lPred.set_parse_action(pushOp) - expr - Suppress(rPred)).set_parse_action(pushPredicate))
) | (step + ZeroOrMore((lPred.set_parse_action(pushOp) - expr - Suppress(rPred)).set_parse_action(pushPredicate)))
relativePathExpr = stepExpr + ZeroOrMore(((pathDescOp | pathStepOp) + stepExpr).set_parse_action(pushOperation))
pathExpr = (
    (pathDescOp + relativePathExpr).set_parse_action(pushRootStep)
    | (pathStepOp + relativePathExpr).set_parse_action(pushRootStep)
    | (relativePathExpr)
    | ((pathRootOp).set_parse_action(pushRootStep))
)


valueExpr = pathExpr

# filterExpr = ( atom + ZeroOrMore( (Suppress(lPred) - expr - Suppress(rPred)).set_parse_action(pushPredicate) ) )
# axisStep = ( (reverseStep | forwardStep) + ZeroOrMore( (Suppress(lPred) - expr - Suppress(rPred)).set_parse_action(pushPredicate) ) )
# stepExpr = filterExpr | axisStep
# relativePathExpr = ( stepExpr + ZeroOrMore( ( pathStepOp | pathDescOp ) + stepExpr ).set_parse_action( pushOperation ) )
# pathExpr = ( ( pathDescOp + relativePathExpr ) |
#             ( pathStepOp + relativePathExpr ) |
#             ( relativePathExpr ) |
#             ( pathStepOp ) )
# valueExpr = pathExpr
unaryExpr = (plusMinusOp + valueExpr).set_parse_action(pushUnaryOperation) | valueExpr
castExpr = unaryExpr + ZeroOrMore((castOp + asOp + singleType).set_parse_action(pushOperation))
castableExpr = castExpr + ZeroOrMore((castableOp + asOp + singleType).set_parse_action(pushOperation))
treatExpr = castableExpr + ZeroOrMore((treatOp + asOp + sequenceType).set_parse_action(pushOperation))
instanceOfExpr = treatExpr + ZeroOrMore((instanceOp + Suppress(ofOp) + sequenceType).set_parse_action(pushOperation))
intersectExceptExpr = instanceOfExpr + ZeroOrMore((intersectExceptOp + instanceOfExpr).set_parse_action(pushOperation))
unionExpr = intersectExceptExpr + ZeroOrMore((unionOp + intersectExceptExpr).set_parse_action(pushOperation))
multiplicitaveExpr = unionExpr + ZeroOrMore((multDivOp + unionExpr).set_parse_action(pushOperation))
additiveExpr = multiplicitaveExpr + ZeroOrMore((plusMinusOp + multiplicitaveExpr).set_parse_action(pushOperation))
rangeExpr = additiveExpr + ZeroOrMore((toOp + additiveExpr).set_parse_action(pushOperation))
comparisonExpr = rangeExpr + ZeroOrMore((comparisonOp + rangeExpr).set_parse_action(pushOperation))
andExpr = comparisonExpr + ZeroOrMore((andOp + comparisonExpr).set_parse_action(pushOperation))
orExpr = andExpr + ZeroOrMore((orOp + andExpr).set_parse_action(pushOperation))

expr <<= orExpr
# The Forward expression streamline implementation (expr.streamline())
# streamlines the wrapped expression (self.expr.streamline()). However, the
# wrapped expression is reassigned by the left shift bitwise operator, but
# doesn't reset the streamlined setting of the Forward expression instance.
assert isinstance(expr.expr, ParserElement)
expr.streamlined = expr.expr.streamlined
xpathExpr = expr + StringEnd()  # type: ignore[no-untyped-call]


# map operator symbols to corresponding arithmetic operations
opn = {
    "+": (lambda a, b: a + b),
    "-": (lambda a, b: a - b),
    "*": (lambda a, b: a * b),
    "div": (lambda a, b: float(a) / float(b)),
    "idiv": (lambda a, b: int(a) / int(b)),
    "^": (lambda a, b: a**b),
}

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


def normalizeExpr(expr: str) -> str:
    result = []
    prior = None
    commentNesting = 0
    c: str | None
    for c in expr:
        if prior == '\r':
            if c == '\n' or c == '\x85':
                c = '\n'
                prior = None
            else:
                prior = '\n'
        elif c == '\x85' or c == '\u2028':
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


def initializeParser(modelManager: ModelManager) -> bool:
    global isInitialized, ixtFunctionNamespaces
    if not isInitialized:
        from arelle import FunctionIxt
        ixtFunctionNamespaces.update(FunctionIxt.ixtNamespaceFunctions.keys())

        modelManager.showStatus(_("initializing formula xpath2 grammar"))
        startedAt = time.time()
        xpathExpr.parse_string("0", parseAll=True)
        modelManager.addToLog(format_string(modelManager.locale,
                                    _("Formula xpath2 grammar initialized in %.2f secs"),
                                    time.time() - startedAt))
        modelManager.showStatus(None)
        isInitialized = True
        return True  # was initialized on this call
    return False  # had already been initialized


def exceptionErrorIndication(exception: XPathException | ParseBaseException) -> str:
    errorAt = exception.column
    source = ''
    for line in exception.line.split('\n'):
        if len(source) > 0:
            source += '\n'
        assert errorAt is not None
        if 0 <= errorAt <= len(line):
            source += line[:errorAt] + '\u274b' + line[errorAt:]
            source += '\n' + ' ' * (errorAt - 1) + '^ \n'
        else:
            source += line
        errorAt -= len(line) + 1
    return source


_staticExpressionFunctionContext: minidom.Element | None = None


def staticExpressionFunctionContext() -> minidom.Element:
    global _staticExpressionFunctionContext
    if _staticExpressionFunctionContext is None:
        _staticExpressionFunctionContext = minidom.parseString(
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


def parse(
        modelObject: ModelFormulaResource,
        xpathExpression: str | None,
        element: ModelObject | None,
        name: str,
        traceType: int
) -> ExpressionStack | None:
    from arelle.ModelFormulaObject import Trace

    global modelXbrl, pluginCustomFunctionQNames
    modelXbrl = modelObject.modelXbrl
    assert modelXbrl is not None
    global exprStack
    exprStack = []
    global xmlElement
    xmlElement = element
    returnProg = None
    pluginCustomFunctionQNames = set()

    for pluginXbrlMethod in pluginClassMethods("Formula.CustomFunctions"):
        pluginCustomFunctionQNames.update(pluginXbrlMethod().keys())

    # throws ParseException
    if xpathExpression and len(xpathExpression) > 0:
        # normalize End of Line
        try:
            formulaOptions = modelXbrl.modelManager.formulaOptions

            normalizedExpr = normalizeExpr(xpathExpression)

            # for debugging parser looping or stack recursion, uncomment this:
            # modelObject.modelXbrl.modelManager.showStatus(_("Parsing file {0} line {1} expr {2}").format(element.modelDocument.basename,element.sourceline,normalizedExpr))

            # should be option "compiled code"

            if ((formulaOptions.traceVariableSetExpressionSource and traceType == Trace.VARIABLE_SET)
                or (formulaOptions.traceVariableExpressionSource and traceType == Trace.VARIABLE)
                or (formulaOptions.traceCallExpressionSource and traceType == Trace.CALL)
            ):
                modelXbrl.info("formula:trace", "Source %(name)s %(source)s",
                               modelObject=element, name=name, source=normalizedExpr)
            assert element is not None
            exprStack.append(ProgHeader(modelObject, name, element, normalizedExpr, traceType))

            L = xpathExpr.parse_string(normalizedExpr, parseAll=True)

            # modelXbrl.error( _("AST {0} {1}").format(name, L),
            #    "info", "formula:trace")

            # should be option "compiled code"
            if ((formulaOptions.traceVariableSetExpressionCode and traceType == Trace.VARIABLE_SET)
                or (formulaOptions.traceVariableExpressionCode and traceType == Trace.VARIABLE)
                or (formulaOptions.traceCallExpressionCode and traceType == Trace.CALL)
            ):
                modelXbrl.info("formula:trace", _("Code %(name)s %(source)s"),
                               modelObject=element, name=name, source=exprStack)

        except (ParseException, ParseSyntaxException) as err:
            modelXbrl.error("err:XPST0003",
                _("Parse error in %(name)s error: %(error)s \n%(source)s"),
                modelObject=element,
                name=name,
                error=err,
                source=exceptionErrorIndication(err))
            # insert after ProgHeader before ordinary executable expression that may have successfully compiled
            exprStack.insert(1, OperationDef(normalizedExpr, 0,
                                             QNameDef(0, "fn", XbrlConst.fn, "error"),
                                             [OperationDef(normalizedExpr, 0,
                                                           QNameDef(0, "fn", XbrlConst.fn, "QName"),
                                                           [XbrlConst.xpath2err, "err:XPST0003"], False),
                                              str(err)], False))
        except ValueError as err:
            modelXbrl.error("parser:unableToParse",
                _("Parsing terminated in %(name)s due to error: %(error)s \n%(source)s"),
                modelObject=element,
                name=name,
                error=err,
                source=normalizedExpr)
            modelXbrl.debug("debug", str(traceback.format_exception(*sys.exc_info())))

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
        returnProg = exprStack
    exprStack = []  # dereference
    xmlElement = None
    modelXbrl = None
    return returnProg


def variableReferencesSet(
        exprStack: ExpressionStack | None,
        element: ModelFormulaResource,
) -> set[QName]:
    varRefSet: set[QName] = set()
    if exprStack:
        variableReferences(exprStack, varRefSet, element)
    return varRefSet


def variableReferences(
        exprStack: RecursiveFormulaTokens,
        varRefSet: set[QName],
        element: ModelObject,
        rangeVars: list[QName] | None = None,
) -> None:
    localRangeVars = []
    if rangeVars is None:
        rangeVars = []
    from arelle.ModelValue import qname

    for p in exprStack:
        if isinstance(p, ProgHeader):
            assert p.element is not None
            element = p.element
        elif isinstance(p, VariableRef):
            var = qname(element, p.name, noPrefixIsNoNamespace=True)
            if var not in rangeVars:
                varRefSet.add(var)
        elif isinstance(p, OperationDef):
            variableReferences(p.args, varRefSet, element, rangeVars)
        elif isinstance(p, Expr):
            variableReferences(p.expr, varRefSet, element, rangeVars)
        elif isinstance(p, RangeDecl):
            var = p.rangeVar.name
            rangeVars.append(var)
            localRangeVars.append(var)
            variableReferences(p.bindingSeq, varRefSet, element, rangeVars)
        elif isinstance(p, Iterable) and not isinstance(p, str):
            variableReferences(p, varRefSet, element, rangeVars)
    for localRangeVar in localRangeVars:
        if localRangeVar in rangeVars:
            rangeVars.remove(localRangeVar)


def prefixDeclarations(
        exprStack: RecursiveFormulaTokens,
        xmlnsDict: dict[str, str | None],
        element: ModelObject,
) -> None:
    from arelle.ModelValue import qname

    for p in exprStack:
        if isinstance(p, ProgHeader):
            assert p.element is not None
            element = p.element
        elif isinstance(p, VariableRef):
            var = qname(element, p.name, noPrefixIsNoNamespace=True)
            if var.prefix:
                xmlnsDict[var.prefix] = var.namespaceURI
        elif isinstance(p, OperationDef):
            op = p.name
            if isinstance(op, QNameDef) and op.prefix:
                xmlnsDict[op.prefix] = op.namespaceURI
            prefixDeclarations(p.args, xmlnsDict, element)
        elif isinstance(p, Expr):
            prefixDeclarations(p.expr, xmlnsDict, element)
        elif isinstance(p, RangeDecl):
            var = p.rangeVar.name
            if var.prefix:
                xmlnsDict[var.prefix] = var.namespaceURI
            prefixDeclarations(p.bindingSeq, xmlnsDict, element)
        elif isinstance(p, Iterable) and not isinstance(p, str):
            prefixDeclarations(p, xmlnsDict, element)


def clearProg(exprStack: ExpressionStack | None) -> None:
    if exprStack:
        for p in exprStack:
            if isinstance(p, ProgHeader):
                p.element = None
                break
        del exprStack[:]


def clearNamedProg(ownerObject: ModelFormulaResource, progName: str) -> None:
    clearProg(getattr(ownerObject, progName, []))


def clearNamedProgs(ownerObject: ModelFormulaResource, progsListName: str) -> None:
    for prog in getattr(ownerObject, progsListName, []):
        clearProg(prog)


def codeModule(code: Iterable[Any]) -> str:
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


def parser_unit_test() -> None:
    # initialize
    xpathExpr.parse_string("0", parseAll=True)

    test1 = "3*7+5"
    test1a = "5+3*7"
    test1b = "(5+3)*7"
    test2a = "concat('abc','def')"
    test2b = "'abc'"
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
    # tests = [locals()[t] for t in locals().keys() if t.startswith("test")]
    tests = [test1, test1a, test1b, test2a, test2b, test3, test3a]

    log = []
    for test in (
        "concat('abc','def')",
        "a/b",
        "123",
        "0.005",
        ".005",
        "./*[local-name() eq 'a']",
        ".",
        "..",
        "a/*[1]",
        "a/*:z[1]",
        "a/z:*[1]",
        "//*[@id eq 'context-for-xpath-rule']//xbrldi:explicitMember[2]",
    ):
        # Start with a blank exprStack and a blank varStack
        global exprStack, xmlElement
        exprStack = []
        xmlElement = None

        # try parsing the input string
        L: ParseResults | list[Any]
        try:
            L = xpathExpr.parse_string(normalizeExpr(test), parseAll=True)
        except (ParseException, ParseSyntaxException) as err:
            L = ['Parse Failure', test, err]

        # show result of parsing the input string
        if debug_flag:
            log.append("{0}->{1}".format(test, L))
        if len(L) == 0 or L[0] != 'Parse Failure':
            if debug_flag:
                log.append("exprStack={0}".format(exprStack))
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
            log.append('Parse Failure')
            log.append(L[2].line)
            log.append(" " * (L[2].column - 1) + "^")
            log.append(L[2])

    print("see log in c:\\temp\\testLog.txt")
    import io

    with io.open("c:\\temp\\testLog.txt", 'wt', encoding='utf-8') as f:
        f.write('\n'.join(str(l) for l in log))


if __name__ == "__main__":
    parser_unit_test()
