"""
FormulaParser.py - pyparsing grammar for the XBRL Query and Rules Language.

Parses `.xule` source files into an AST represented as nested dicts/lists that
the FormulaInterpreter can walk.  The grammar closely follows the Xule language
specification and the reference Xule pyparsing grammar (xule_grammar.py) from
the XBRL-US DQC rule set, adapted to target the OIM XbrlModel data model.

Grammar overview
----------------
Program       := Statement*
Statement     := NamespaceDecl | ConstantDecl | OutputRule | AssertRule | VersionDecl

NamespaceDecl := 'namespace' NCName '<' URI '>'
ConstantDecl  := 'constant' '$'VarName '=' Expr
OutputRule    := 'output' RuleName Expr ['message' StringExpr] ['severity' SeverityKw]
AssertRule    := 'assert' RuleName Expr ['message' StringExpr] ['severity' SeverityKw]
VersionDecl   := 'version' StringLiteral

Expr          := ... (see buildExprGrammar)

See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import datetime
import hashlib
import os
import sys
import threading
from pathlib import Path
from queue import Queue
from typing import Any

from pyparsing import (
    CaselessKeyword, Combine, Empty, Forward, Group, Literal,
    OneOrMore, Opt, OpAssoc, ParserElement, Regex, Suppress, Word,
    ZeroOrMore, alphanums, alphas, c_style_comment, delimited_list,
    line_end, one_of, printables, pyparsing_common, infix_notation,
    QuotedString, CharsNotIn, SkipTo
)

from .FormulaRuleSet import (
    FormulaRuleSet, NamespaceDecl, ConstantDecl, OutputRule, AssertRule
)


# ---------------------------------------------------------------------------
# Module-level grammar (built once, reused for all files)
# ---------------------------------------------------------------------------
_grammar = None
_grammarLock = threading.Lock()


def _getGrammar():
    global _grammar
    if _grammar is None:
        with _grammarLock:
            if _grammar is None:
                _grammar = _buildGrammar()
    return _grammar


# ---------------------------------------------------------------------------
# Grammar builder
# ---------------------------------------------------------------------------

def _buildGrammar():
    """Construct and return the complete Xule pyparsing grammar."""

    ParserElement.enable_packrat()

    # ---- Whitespace / comments ----
    comment = c_style_comment | (Literal("//") + SkipTo(line_end))

    # ---- Expression forward references ----
    expr = Forward()
    blockExpr = Forward()

    # ---- Keywords ----
    assertKw        = CaselessKeyword("assert")
    outputKw        = CaselessKeyword("output")
    namespaceKw     = CaselessKeyword("namespace")
    constantKw      = CaselessKeyword("constant")
    functionKw      = CaselessKeyword("function")
    versionKw       = CaselessKeyword("version")
    messageKw       = CaselessKeyword("message")
    severityKw      = CaselessKeyword("severity")
    returnKw        = CaselessKeyword("returns")
    forKw           = CaselessKeyword("for")
    inKw            = CaselessKeyword("in")
    ifKw            = CaselessKeyword("if")
    thenKw          = CaselessKeyword("then")
    elseKw          = CaselessKeyword("else")
    whereKw         = CaselessKeyword("where")
    trueKw          = CaselessKeyword("true")
    falseKw         = CaselessKeyword("false")
    noneKw          = CaselessKeyword("none")
    skipKw          = CaselessKeyword("skip")
    andKw           = CaselessKeyword("and")
    orKw            = CaselessKeyword("or")
    notKw           = CaselessKeyword("not")
    nilsKw          = CaselessKeyword("nils")
    nonilsKw        = CaselessKeyword("nonils")
    coveredKw       = CaselessKeyword("covered")
    uncoveredKw     = CaselessKeyword("uncovered")
    errorKw         = CaselessKeyword("error")
    warningKw       = CaselessKeyword("warning")
    okKw            = CaselessKeyword("ok")
    passKw          = CaselessKeyword("pass")

    declKeywords = (assertKw | outputKw | namespaceKw | constantKw | functionKw | versionKw)

    # ---- Identifiers ----
    _ncNameStart = r"[A-Za-z_\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
    _ncNameCont  = r"[A-Za-z0-9_\-.\u00B7\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0300-\u036F\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u203F-\u2040\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]*"
    ncName   = Regex(_ncNameStart + _ncNameCont)
    simpleName = Regex(r"[A-Za-z_][A-Za-z0-9_\-]*")

    # ---- QNames ----
    qnameExpr = Group(
        Opt(Combine(ncName + Suppress(Literal(":"))) , default="*").setResultsName("prefix")
        + ncName.setResultsName("localName")
    ).setResultsName("qname")

    # ---- Literals ----
    intLiteral    = pyparsing_common.signed_integer()
    # Do not accept trailing-dot forms like "1." because expressions like
    # "1.all" should parse as integer 1 with property "all", not float 1.0
    # followed by stray identifier "all".
    floatLiteral  = Regex(
        r"[+-]?(?:(?:\d+\.\d+|\.\d+)(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+)"
    ).addParseAction(lambda t: float(t[0]))

    # String literals with embedded {expr} interpolations
    _strEscape = Suppress(Literal("\\")) + Regex(".")
    _strInterp = Suppress(Literal("{")) + blockExpr + Suppress(Literal("}"))
    _strPart   = Regex(r"[^\\'{}\n]+")
    _sqString  = (
        Suppress(Literal("'"))
        + Group(ZeroOrMore(
            Group(_strEscape.setResultsName("escape"))
            | Group(_strInterp.setResultsName("interp"))
            | Group(_strPart.setResultsName("text"))
        )).setResultsName("parts")
        + Suppress(Literal("'"))
    )
    _dqString  = (
        Suppress(Literal('"'))
        + Group(ZeroOrMore(
            Group(_strEscape.setResultsName("escape"))
            | Group(_strInterp.setResultsName("interp"))
            | Group(Regex(r'[^\\"{}]+').setResultsName("text"))
        )).setResultsName("parts")
        + Suppress(Literal('"'))
    )
    stringLiteral = Group(
        (_sqString | _dqString).setResultsName("stringParts")
    ).setResultsName("string")

    boolLiteral = Group(
        (trueKw | falseKw).setResultsName("value")
    ).setResultsName("boolean")

    noneLiteral = Group(noneKw.setResultsName("value")).setResultsName("none")
    skipLiteral = Group(skipKw.setResultsName("value")).setResultsName("skip")

    severityLiteral = Group(
        (errorKw | warningKw | okKw | passKw).setResultsName("value")
    ).setResultsName("severity")

    # ---- Variable reference ----
    varRef = Group(
        Suppress(Literal("$")) + simpleName.setResultsName("varName")
    ).setResultsName("varRef")

    # ---- Tag reference  (#tag) ----
    tagOp   = Suppress(Literal("#"))
    tagName = simpleName

    # ---- Fact query:  @QName[filters] #tag ----
    # Dimension filter:  dim=value  or  dim!=value  etc.
    dimFilter = Group(
        qnameExpr.setResultsName("dim")
        + one_of("== != <= < >= > =").setResultsName("op")
        + expr.setResultsName("value")
    )
    factFilters = (
        Suppress(Literal("["))
        + Group(delimited_list(dimFilter, delim=",")).setResultsName("filters")
        + Suppress(Literal("]"))
    )
    nilsFlag = Group(nilsKw | nonilsKw).setResultsName("nilsFlag")
    coveredFlag = Group(coveredKw | uncoveredKw).setResultsName("coveredFlag")

    factQuery = Group(
        Opt(nilsFlag)
        + Opt(coveredFlag)
        + Suppress(Literal("@@") | Literal("@"))
        + qnameExpr.setResultsName("concept")
        + Opt(factFilters)
        + Opt(tagOp + tagName.setResultsName("tag"))
        + Opt(nilsFlag)
        + Opt(coveredFlag)
    ).setResultsName("factQuery")

    # ---- Function call ----
    funcCall = Group(
        simpleName.setResultsName("funcName")
        + Suppress(Literal("("))
        + Opt(Group(delimited_list(blockExpr)).setResultsName("args"))
        + Suppress(Literal(")"))
    ).setResultsName("funcCall")

    # ---- Property access  (expr.propName  or  expr.propName(args)) ----
    propAccess = Group(
        Suppress(Literal("."))
        + simpleName.setResultsName("propName")
        + Opt(
            Suppress(Literal("("))
            + Opt(Group(delimited_list(blockExpr)).setResultsName("propArgs"))
            + Suppress(Literal(")"))
        )
    ).setResultsName("propAccess")

    indexAccess = Group(
        Suppress(Literal("["))
        + blockExpr.setResultsName("indexExpr")
        + Suppress(Literal("]"))
    ).setResultsName("indexAccess")

    # ---- Collections ----
    setLiteral  = Group(
        Suppress(Literal("{"))
        + Opt(Group(delimited_list(blockExpr)).setResultsName("items"))
        + Suppress(Literal("}"))
    ).setResultsName("setLiteral")

    listLiteral = Group(
        Suppress(Literal("["))
        + Opt(Group(delimited_list(blockExpr)).setResultsName("items"))
        + Suppress(Literal("]"))
    ).setResultsName("listLiteral")

    # ---- If-then-else ----
    ifExpr = Group(
        Suppress(ifKw)
        + blockExpr.setResultsName("condition")
        + Suppress(thenKw)
        + blockExpr.setResultsName("thenExpr")
        + Opt(Suppress(elseKw) + blockExpr.setResultsName("elseExpr"))
    ).setResultsName("ifExpr")

    # ---- For loop ----
    _forHeader = (
        Suppress(Literal("("))
        + Suppress(Literal("$")) + simpleName.setResultsName("varName")
        + Suppress(inKw)
        + expr.setResultsName("collection")
        + Suppress(Literal(")"))
    ) | (
        Suppress(Literal("$")) + simpleName.setResultsName("varName")
        + Suppress(inKw)
        + expr.setResultsName("collection")
    )
    forExpr = Group(
        Suppress(forKw)
        + _forHeader
        + blockExpr.setResultsName("body")
    ).setResultsName("forExpr")

    # ---- Parenthesised expression ----
    parenExpr = Suppress(Literal("(")) + blockExpr + Suppress(Literal(")"))

    # ---- Atom ----
    atom = (
        factQuery
        | ifExpr
        | forExpr
        | funcCall
        | varRef
        | setLiteral
        | listLiteral
        | boolLiteral
        | noneLiteral
        | skipLiteral
        | severityLiteral
        | stringLiteral
        | floatLiteral
        | intLiteral
        | qnameExpr
        | parenExpr
    )

    # ---- Property chain on any atom ----
    atomWithProps = Group(
        atom.setResultsName("base")
        + Group(ZeroOrMore(propAccess | indexAccess)).setResultsName("props")
    ).setResultsName("atomWithProps")

    # ---- Infix expression grammar (precedence via infix_notation) ----
    expr <<= infix_notation(
        atomWithProps,
        [
            (one_of("+ -"),          1, OpAssoc.RIGHT, _mkUnary),
            (Literal("*") | Literal("/"), 2, OpAssoc.LEFT, _mkBinary),
            (one_of("+ - <+ <+> +> <- <-> ->"), 2, OpAssoc.LEFT, _mkBinary),
            (Literal("^"),           2, OpAssoc.LEFT, _mkBinary),   # symmetric difference
            (Literal("&") | CaselessKeyword("intersect"), 2, OpAssoc.LEFT, _mkBinary),
            (one_of("== = != <= < >= >") | inKw | (notKw + inKw), 2, OpAssoc.LEFT, _mkBinary),
            (notKw,                  1, OpAssoc.RIGHT, _mkUnary),
            (andKw,                  2, OpAssoc.LEFT, _mkBinary),
            (orKw,                   2, OpAssoc.LEFT, _mkBinary),
        ],
    )

    # ---- Block expression and assignment ----
    #   $x = 3; $x + 1
    #   abs($y = (3 + 4) * -1; $y)
    assignExpr = Group(
        Suppress(Literal("$"))
        + simpleName.setResultsName("varName")
        + Suppress(Literal("="))
        + expr.setResultsName("valueExpr")
    ).addParseAction(_mkAssign)

    blockStmt = (~declKeywords + (assignExpr | expr))
    blockExpr <<= Group(
        Group(
            OneOrMore(blockStmt + Opt(Suppress(Literal(";"))))
        ).setResultsName("steps")
    ).addParseAction(_mkBlockExpr)

    # ---- Message clause ----
    messageClause = Group(
        Suppress(messageKw)
        + stringLiteral.setResultsName("msgExpr")
    ).setResultsName("message")

    # ---- Severity clause ----
    severityClause = Group(
        Suppress(severityKw)
        + severityLiteral.setResultsName("severity")
    ).setResultsName("severity")

    # ---- Where clause ----
    whereClause = Group(
        Suppress(whereKw)
        + blockExpr.setResultsName("cond")
    ).setResultsName("where")

    # ---- Rule name ----
    ruleName = simpleName

    # ---- Output rule ----
    outputRule = Group(
        Suppress(outputKw)
        + ruleName.setResultsName("name")
        + blockExpr.setResultsName("expr")
        + Opt(whereClause)
        + Opt(messageClause)
        + Opt(severityClause)
    ).setResultsName("outputRule").addParseAction(_tagStatement("outputRule"))

    # ---- Assert rule ----
    assertRule = Group(
        Suppress(assertKw)
        + ruleName.setResultsName("name")
        + blockExpr.setResultsName("expr")
        + Opt(whereClause)
        + Opt(messageClause)
        + Opt(severityClause)
    ).setResultsName("assertRule").addParseAction(_tagStatement("assertRule"))

    # ---- Constant declaration ----
    constantDecl = Group(
        Suppress(constantKw)
        + Suppress(Literal("$"))
        + simpleName.setResultsName("name")
        + Suppress(Literal("="))
        + blockExpr.setResultsName("expr")
    ).setResultsName("constantDecl").addParseAction(_tagStatement("constantDecl"))

    # ---- Namespace declaration ----
    uriLiteral = (
        QuotedString("<", endQuoteChar=">")
        | QuotedString("'")
        | QuotedString('"')
    )
    namespaceDecl = Group(
        Suppress(namespaceKw)
        + ncName.setResultsName("prefix")
        + uriLiteral.setResultsName("uri")
    ).setResultsName("namespaceDecl").addParseAction(_tagStatement("namespaceDecl"))

    # ---- Version declaration ----
    versionDecl = Group(
        Suppress(versionKw)
        + stringLiteral.setResultsName("version")
    ).setResultsName("versionDecl").addParseAction(_tagStatement("versionDecl"))

    # ---- Function declaration (user-defined) ----
    funcParam = Group(
        Suppress(Literal("$")) + simpleName.setResultsName("paramName")
    )
    funcDecl = Group(
        Suppress(functionKw)
        + simpleName.setResultsName("name")
        + Suppress(Literal("("))
        + Opt(Group(delimited_list(funcParam)).setResultsName("params"))
        + Suppress(Literal(")"))
        + blockExpr.setResultsName("body")
    ).setResultsName("funcDecl").addParseAction(_tagStatement("funcDecl"))

    # ---- Top-level program ----
    statement = (
        namespaceDecl
        | versionDecl
        | constantDecl
        | outputRule
        | assertRule
        | funcDecl
    )
    program = (
        ZeroOrMore(comment.suppress())
        + ZeroOrMore(statement + ZeroOrMore(comment.suppress()))
    ).setResultsName("program")

    program.ignore(comment)
    return program


# ---------------------------------------------------------------------------
# Parse-action helpers (attached to infix_notation operators)
# ---------------------------------------------------------------------------

def _mkUnary(tokens):
    toks = tokens[0]
    return {"exprName": "unaryExpr", "op": toks[0], "expr": toks[1]}

def _mkBinary(tokens):
    toks = tokens[0]
    # infix_notation returns [left, op, right, op, right, ...]
    result = toks[0]
    i = 1
    while i < len(toks):
        result = {"exprName": "binaryExpr", "leftExpr": result, "op": toks[i], "rightExpr": toks[i+1]}
        i += 2
    return result


def _mkAssign(tokens):
    toks = tokens[0]
    return {
        "exprName": "assignExpr",
        "varName": toks.get("varName", ""),
        "valueExpr": toks.get("valueExpr"),
    }


def _mkBlockExpr(tokens):
    toks = tokens[0]
    steps = list(toks.get("steps", toks))
    if len(steps) == 1 and isinstance(steps[0], dict) and "exprName" in steps[0]:
        return steps[0]
    return {
        "exprName": "blockExpr",
        "steps": steps,
    }


def _tagStatement(kind):
    def _parseAction(tokens):
        data = tokens[0].as_dict()
        data["_kind"] = kind
        return data

    return _parseAction


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parseFormulaFile(filePath: str) -> FormulaRuleSet:
    """
    Parse a single `.xule` formula source file and return a FormulaRuleSet.

    Parsing is performed in a dedicated thread to allow a larger stack size
    (some rule files have deeply nested expressions).
    """
    stackSize = 8 * 1024 * 1024  # 8 MB stack
    resultQueue: Queue = Queue()
    origLimit = sys.getrecursionlimit()
    if origLimit < 5500:
        sys.setrecursionlimit(5500)

    def _parseThread():
        try:
            grammar = _getGrammar()
            parseRes = grammar.parseFile(filePath, parseAll=True).as_dict()
            resultQueue.put(("ok", parseRes))
        except Exception as exc:
            resultQueue.put(("err", exc))

    t = threading.Thread(target=_parseThread, daemon=True)
    t.start()
    t.join()
    sys.setrecursionlimit(origLimit)

    status, payload = resultQueue.get()
    if status == "err":
        raise payload

    return _buildRuleSet(payload, filePath)


def parseFormulaString(source: str, fileName: str = "<string>") -> FormulaRuleSet:
    """Parse a Xule formula string (useful for unit tests)."""
    grammar = _getGrammar()
    parseRes = grammar.parseString(source, parseAll=True).as_dict()
    return _buildRuleSet(parseRes, fileName)


# ---------------------------------------------------------------------------
# AST → FormulaRuleSet conversion
# ---------------------------------------------------------------------------

def _buildRuleSet(parseRes: dict, filePath: str) -> FormulaRuleSet:
    def _normalizeNode(node):
        # pyparsing + as_dict can leave one-element list wrappers around
        # parse-action dict nodes (notably blockExpr). Strip those wrappers
        # so the interpreter sees stable dict AST nodes.
        if isinstance(node, list):
            if len(node) == 1:
                return _normalizeNode(node[0])
            return [_normalizeNode(n) for n in node]
        if isinstance(node, dict):
            return {k: _normalizeNode(v) for k, v in node.items()}
        return node

    ruleSet = FormulaRuleSet(sourceFiles=[filePath])

    for item in parseRes.get("program", []):
        if not isinstance(item, dict):
            continue
        key = item.get("_kind")
        node = item

        if key is None:
            wrappedKey = next(iter(item), None)
            if wrappedKey in {"namespaceDecl", "constantDecl", "outputRule", "assertRule", "funcDecl", "versionDecl"}:
                key = wrappedKey
                node = item[wrappedKey]

        if key == "namespaceDecl":
            ruleSet.namespaces[node["prefix"]] = node["uri"]

        elif key == "constantDecl":
            ruleSet.constants.append(ConstantDecl(name=node["name"], expr=_normalizeNode(node["expr"])))

        elif key == "outputRule":
            rule = OutputRule(
                name=node["name"],
                expr=_normalizeNode(node["expr"]),
                messageExpr=_normalizeNode(node.get("message", {}).get("msgExpr")),
                severity=node.get("severity", {}).get("severity", {}).get("value", "info"),
            )
            ruleSet.outputRules[rule.name] = rule

        elif key == "assertRule":
            rule = AssertRule(
                name=node["name"],
                expr=_normalizeNode(node["expr"]),
                messageExpr=_normalizeNode(node.get("message", {}).get("msgExpr")),
                severity=node.get("severity", {}).get("severity", {}).get("value", "error"),
            )
            ruleSet.assertRules[rule.name] = rule

        elif key == "funcDecl":
            # User-defined functions are stored as constant expressions that
            # evaluate to a callable lambda-like object at runtime.
            ruleSet.constants.append(ConstantDecl(
                name=node["name"],
                expr=_normalizeNode({"exprName": "funcDecl", **node})
            ))

    return ruleSet
