'''
formulaGenerator generates XBRL formula linkbases for a subset of the Sphinx language.

See COPYRIGHT.md for copyright information.

Sphinx is a Rules Language for XBRL described by a Sphinx 2 Primer
(c) Copyright 2012 CoreFiling, Oxford UK.
Sphinx copyright applies to the Sphinx language, not to this software.
Workiva, Inc. conveys neither rights nor license for the Sphinx language.
'''

import time, sys, io, os.path, re
from lxml import etree
from arelle.ModelValue import QName
from .SphinxParser import (parse, astNode, astNamespaceDeclaration,
                           astFormulaRule, astReportRule, astValidationRule,
                           astQnameLiteral)
from .SphinxMethods import aggreateFunctionImplementation


def generateFormulaLB(cntlr, sphinxFiles, generatedSphinxFormulasDirectory):
    from arelle.pyparsing.pyparsing_py3 import lineno
    from .SphinxContext import SphinxContext
    from .SphinxValidator import validate

    msgFile = None
    sourceString = None

    # logMessage operates without an instance document or ModelXbrl, so it simulates log function

    def logMessage(severity, code, text, **kwargs):
        if "sourceFileLines" in kwargs:  # use pairs of file and line number
            fileLines = ", ".join((file + (" " + str(line)) if line else "")
                                  for file, line in kwargs["sourceFileLines"])
        elif "sourceFileLine" in kwargs:
            file, line in kwargs["sourceFileLine"]
            fileLines = file + (" " + str(line)) if line else ""
        else:
            fileLines = ""
        if not fileLines:
            fileLines = ", " + fileLines
        try:
            cntlr.addToLog("[{0}] {1}{2}".format(
                                      code,
                                      text % kwargs,
                                      fileLines))
        except KeyError as err:
            cntlr.addToLog("[{0}] {1}: Missing message parameter: {2}; {3}".format(
                                      code,
                                      text,
                                      err,
                                      fileLines))

    from arelle import XmlUtil

    sc = SphinxContext( parse(cntlr, logMessage, sphinxFiles) )
    sc.logMessage = logMessage
    validate(logMessage, sc)
    assertionIDs = set()

    for prog in sc.sphinxProgs:
        sphinxFile = prog[0].fileName
        sphinxXmlns = { "xlink": 'http://www.w3.org/1999/xlink',
                        "link": 'http://www.xbrl.org/2003/linkbase',
                        "xbrli": 'http://www.xbrl.org/2003/instance',
                        "generic": 'http://xbrl.org/2008/generic',
                        "formula": 'http://xbrl.org/2008/formula',
                        "validation": 'http://xbrl.org/2008/validation',
                        "variable": 'http://xbrl.org/2008/variable',
                        "label": 'http://xbrl.org/2008/label',
                        "ca": 'http://xbrl.org/2008/assertion/consistency',
                        "ea": 'http://xbrl.org/2008/assertion/existence',
                        "va": 'http://xbrl.org/2008/assertion/value',
                        "msg": 'http://xbrl.org/2010/message',
                        "bf": 'http://xbrl.org/2008/filter/boolean',
                        "cf": 'http://xbrl.org/2008/filter/concept',
                        "df": 'http://xbrl.org/2008/filter/dimension',
                        "gf": 'http://xbrl.org/2008/filter/general',
                        "pf": 'http://xbrl.org/2008/filter/period',
                        "uf": 'http://xbrl.org/2008/filter/unit',
                        "xfi": 'http://www.xbrl.org/2008/function/instance',
                        "xsi": 'http://www.w3.org/2001/XMLSchema-instance',
                        "xs": 'http://www.w3.org/2001/XMLSchema',
                        }
        for node in prog:
            if isinstance(node, astNamespaceDeclaration):
                sphinxXmlns[node.prefix] = node.namespace

        formulaFile = sphinxFile.rpartition(".")[0] + "-formula.xml"

        # save in generatedSphinxFormulasDirectory if specified and valid (exists)
        if generatedSphinxFormulasDirectory and os.path.isdir(generatedSphinxFormulasDirectory):
            formulaFile = os.path.join(generatedSphinxFormulasDirectory,
                                       os.path.basename(formulaFile))

        xbrlLBfile = io.StringIO('''
<nsmap>
<link:linkbase

{0}
xsi:schemaLocation="http://www.xbrl.org/2003/linkbase http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd"
>
<link:arcroleRef arcroleURI='http://xbrl.org/arcrole/2008/element-label'
    xlink:href='http://www.xbrl.org/2008/generic-label.xsd#element-label'
    xlink:type='simple'/>
<link:arcroleRef arcroleURI='http://xbrl.org/arcrole/2008/variable-set'
    xlink:href='http://www.xbrl.org/2008/variable.xsd#variable-set'
    xlink:type='simple'/>
<link:arcroleRef arcroleURI='http://xbrl.org/arcrole/2008/variable-filter'
    xlink:href='http://www.xbrl.org/2008/variable.xsd#variable-filter'
    xlink:type='simple'/>
<link:arcroleRef arcroleURI='http://xbrl.org/arcrole/2008/variable-set-precondition'
    xlink:href='http://www.xbrl.org/2008/variable.xsd#variable-set-precondition'
    xlink:type='simple'/>
<link:arcroleRef arcroleURI='http://xbrl.org/arcrole/2008/consistency-assertion-formula'
    xlink:href='http://www.xbrl.org/2008/consistency-assertion.xsd#consistency-assertion-formula'
    xlink:type='simple'/>
<link:roleRef roleURI='http://www.xbrl.org/2008/role/link'
    xlink:href='http://www.xbrl.org/2008/generic-link.xsd#standard-link-role'
    xlink:type='simple'/>
<link:roleRef roleURI='http://www.xbrl.org/2008/role/label'
    xlink:href='http://www.xbrl.org/2008/generic-label.xsd#standard-label'
    xlink:type='simple'/>
<link:roleRef roleURI="http://www.xbrl.org/2010/role/message"
    xlink:type="simple"
    xlink:href="http://www.xbrl.org/2010/generic-message.xsd#standard-message"/>
<link:arcroleRef arcroleURI="http://xbrl.org/arcrole/2010/assertion-unsatisfied-message"
     xlink:type="simple"
     xlink:href="http://www.xbrl.org/2010/validation-message.xsd#assertion-unsatisfied-message"/>
<link:arcroleRef arcroleURI="http://xbrl.org/arcrole/2010/assertion-satisfied-message"
     xlink:type="simple"
     xlink:href="http://www.xbrl.org/2010/validation-message.xsd#assertion-satisfied-message"/>
<link:arcroleRef arcroleURI='http://xbrl.org/arcrole/2008/boolean-filter'
     xlink:href='http://www.xbrl.org/2008/boolean-filter.xsd#boolean-filter'
     xlink:type='simple'/>

<generic:link xlink:type="extended" xlink:role="http://www.xbrl.org/2003/role/link"/>
</link:linkbase>
</nsmap>
<!--  Generated by Arelle(r) http://arelle.org -->
'''.format('\n'.join("xmlns{0}='{1}'".format((":" + prefix) if prefix else "",
                                             namespace)
                     for prefix, namespace in sphinxXmlns.items())
           )
        )
        msgFile = os.path.basename(formulaFile)
        xmlDocument = etree.parse(xbrlLBfile,base_url=formulaFile)
        xbrlLBfile.close()
        nsmapElt = xmlDocument.getroot()
        #xmlDocument.getroot().init(self)  ## is this needed ??
        for lbElement in  xmlDocument.iter(tag="{http://www.xbrl.org/2003/linkbase}linkbase"):
            break
        for e in  xmlDocument.iter(tag="{http://xbrl.org/2008/generic}link"):
            sc.genLinkElement = e
            break

        class DocObj:  # fake ModelDocument for namespaces
            def __init__(self):
                self.xmlRootElement = lbElement
                self.xmlDocument = xmlDocument
        docObj = DocObj()

        numRules = 0
        sc.generatedVarNbr = 1
        sc.xpathCode = None
        sc.bindAsSequence = False
        sc.nodeXpathVarBindings = {}

        for node in prog:
            if isinstance(node, (astFormulaRule, astReportRule, astValidationRule)):
                # form unique ID
                sc.assertionID = node.name
                if sc.assertionID in assertionIDs:
                    for suffixNumber in range(1,10000):
                        if sc.assertionID + str(suffixNumber) not in assertionIDs:
                            sc.assertionID += str(suffixNumber)
                            break
                assertionIDs.add(sc.assertionID)
                sc.assertionElt = etree.SubElement(sc.genLinkElement,
                                                   "{http://xbrl.org/2008/assertion/value}valueAssertion",
                                                   attrib={"{http://www.w3.org/1999/xlink}type": "resource",
                                                           "{http://www.w3.org/1999/xlink}label": sc.assertionID,
                                                           "id": sc.assertionID,
                                                           "aspectModel": "dimensional",
                                                           "implicitFiltering": "true"})
                sc.assertionVarNames = {"factVar_"}
                sc.generalVarNames = {}
                if isinstance(node, astFormulaRule):
                    sc.assertionElt.set("test", xpathCode(node.expr, sc))
                    msgType = "assertion-unsatisfied-message"
                elif isinstance(node, astReportRule):
                    sc.tags["value"] = node.expr  # no test expression needed
                    msgType = "assertion-unsatisfied-message"
                elif isinstance(node, astValidationRule):
                    sc.assertionElt.set("test", "not( " + xpathCode(node.expr, sc) + " )")
                    msgType = "assertion-satisfied-message"
                genMessage(node.message, sc, msgType)

        sc.nodeXpathVarBindings.clear()

        with open(formulaFile, "w", encoding="utf-8") as fh:
            XmlUtil.writexml(fh, xmlDocument, encoding="utf-8")

        logMessage("INFO", "info:compileSphinx",
                 _("Compiled Sphinx of %(sphinxFile)s has %(numberRules)s tables in file %(formulaFile)s."),
                 sphinxFile=sphinxFiles,
                 numberRules=numRules,
                 formulaFile=formulaFile)

    logMessage = None
    sc.close()

    cntlr.showStatus("Finshed sphinx files {0}".format(", ".join(os.path.basename(f)
                                                                 for f in sphinxFiles)),
                     5000)

def evaluate(node, sc):
    if isinstance(node, astNode):
        className = node.__class__.__name__
        if className in evaluationHandler:
            return evaluationHandler[className](node, sc)
        else: # don't evaluate node
            return node
    elif isinstance(node, (tuple,list)):
        return [evaluate(item, sc) for item in node]
    elif isinstance(node, set):
        return set(evaluate(item, sc) for item in node)
    elif callable(node):
        return node()
    else:
        return node

def evaluateFunctionReference(node, sc):
    name = node.name
    if name in {"list", "set"}:
        # evaluate args
        args = [evaluate(arg, sc) for arg in node.args]
        # process args
        if name == "list":
            return list(args)
        elif name == "set":
            return set(args)
    return node

def evaluateQnameLiteral(node, sc):
    return node.value

def evaluateStringLiteral(node, sc):
    return node.text

def evaluateVariableAssignment(node, sc):
    result = evaluate(node.expr, sc)
    sc.localVariables[node.variableName] = result
    if node.tagName:
        sc.tags[node.tagName] = node.expr
    return result

def evaluateVariableReference(node, sc):
    # expand macro variables
    if node.variableName in sc.localVariables:
        return evaluate(sc.localVariables[node.variableName], sc)
    return '$' + node.variableName

def xpathCode(node, sc):
    parentXpathCode = sc.xpathCode
    sc.xpathCode = []
    genNode(node, sc)
    xpathCodeStr = " ".join(sc.xpathCode)
    sc.xpathCode = parentXpathCode
    return xpathCodeStr

def genNode(node, sc):
    if isinstance(node, astNode):
        genNodeHandler[node.__class__.__name__](node, sc)
    elif isinstance(node, (tuple,list)):
        sc.xpathCode.append('[')
        for item in node:
            genNode(item, sc)
        sc.xpathCode.append(']')
    elif isinstance(node, set):
        sc.xpathCode.append("set(")
        for item in node:
            genNode(item, sc)
        sc.xpathCode.append(")")
    elif callable(node):
        node()
    else:
        sc.xpathCode.append(str(node))

def genBinaryOperation(node, sc):
    # for now formula := generates a "eq" operation so it fails when conditoin is not met
    sc.xpathCode.append("(")
    genNode(node.leftExpr, sc)
    sc.xpathCode.append({"+": "+", "-": "-", "*": "", "/": "div",
                         "<": "lt", "<=": "le", ">": "gt", ">=": "ge",
                         "==": "eq", "!=": "ne",
                         ":=": "eq",
                         }.get(node.op,"$$$opNotImplemented$$$"))
    genNode(node.rightExpr, sc)
    sc.xpathCode.append(")")

def genFor(node, sc):
    # add a general variable for this node's expression, substitute gen var expression
    generalVarLabel = "generalVariable_" + node.name
    sc.xpathCode.append("$" + node.name)

    def genForSelectCode():
        sc.xpathCode.append("for $_{0} in {1} return ( {2} )".format(
                                node.name,
                                genNode(node.collectionExpr, sc),
                                genNode(node.expr, sc)
                                ))

    etree.SubElement(sc.genLinkElement,
                     "{http://xbrl.org/2008/variable}generalVariable",
                     attrib={"{http://www.w3.org/1999/xlink}type": "resource",
                             "{http://www.w3.org/1999/xlink}label": generalVarLabel,
                             "select": xpathCode(genForSelectCode, sc)})
    etree.SubElement(sc.genLinkElement,
                     "{http://xbrl.org/2008/variable}variableArc",
                     attrib={"{http://www.w3.org/1999/xlink}type": "arc",
                             "{http://www.w3.org/1999/xlink}arcrole": "http://xbrl.org/arcrole/2008/variable-set",
                             "{http://www.w3.org/1999/xlink}from": sc.assertionID,
                             "{http://www.w3.org/1999/xlink}to": generalVarLabel,
                             "name": node.name})

def genFunctionDeclaration(node, sc, args):
    # attempt to expand macros
    if node.functionType == "macro":
        # expand locally
        overriddenVariables = {}

        if isinstance(args, dict):
            # args may not all be used in the function declaration, just want used ones
            argDict = dict((name, value)
                           for name, value in args.items()
                           if name in node.params)
        else:  # purely positional args
            # positional parameters named according to function prototype
            if len(args) != len(node.params):
                sc.modelXbrl.log("ERROR", "sphinx.functionArgumentsMismatch",
                                 _("Function %(name)s requires %(required)s parameters but %(provided)s are provided"),
                                 sourceFileLine=node.sourceFileLine,
                                 name=node.name, required=len(node.params), provided=len(args))
                return None
            argDict = dict((paramName, args[i])
                           for i, paramName in enumerate(node.params))
        for name, value in argDict.items():
            value = evaluate(value, sc)  # resolves variable refs to same variable ref
            if name in sc.localVariables:
                overriddenVariables[name] = sc.localVariables[name]
            sc.localVariables[name] = value
        result = genNode(node.expr, sc)
        for name in argDict.keys():
            del sc.localVariables[name]
        sc.localVariables.update(overriddenVariables)
        overriddenVariables.clear()
    elif node.functionType == "function":
        # generate custom function implementation
        pass

def genFunctionReference(node, sc):
    name = node.name
    if name in sc.functions:  # user defined function
        result = genFunctionDeclaration(sc.functions[name], sc, node.args)

    isAggregateFunction = name in aggreateFunctionImplementation
    if isAggregateFunction:
        priorBindAsSequence = sc.bindAsSequence
        sc.bindAsSequence = True
    formulaFunctionSyntax = formulaFunctionSyntaxPatterns.get(name,
                              ("$notImplemented_{0}(".format(name),")"))
    if isinstance(formulaFunctionSyntax, tuple) and len(formulaFunctionSyntax) == 2:
        sc.xpathCode.append(formulaFunctionSyntax[0]) # before arguments
        for i, arg in enumerate(node.args):
            if i:
                sc.xpathCode.append(",")
            genNode(arg, sc)
        sc.xpathCode.append(formulaFunctionSyntax[1]) # after arguments
    else:
        sc.logMessage("ERROR", "sphinxFormulaGenerator:functionSyntaxPatternError",
                      _("Syntax generator error for function %(name)s."),
                      sourceFileLine=node.sourceFileLine, name=name)
    if isAggregateFunction:
        sc.bindAsSequence = priorBindAsSequence

def genHyperspaceExpression(node, sc):
    # generate fact variable and substitute it's reference in text code
    # find pri item for fact var name
    priItemName = "factVar_"
    for axis in node.axes:
        if axis.name == "primary":
            restriction = evaluate(axis.restriction, sc)
            if len(restriction) == 1:
                priItemName += cleanedName(str(restriction[0]))
            break

    if priItemName in sc.assertionVarNames:
        for suffixNumber in range(1,10000):
            if priItemName + str(suffixNumber) not in sc.assertionVarNames:
                priItemName += str(suffixNumber)
                break
    sc.assertionVarNames.add(priItemName)
    factVarLabel = sc.assertionID + "_" + priItemName
    xpathVar = "$" + factVarLabel
    sc.xpathCode.append(xpathVar)
    sc.nodeXpathVarBindings[node] = xpathVar
    etree.SubElement(sc.genLinkElement,
                     "{http://xbrl.org/2008/variable}factVariable",
                     attrib={"{http://www.w3.org/1999/xlink}type": "resource",
                             "{http://www.w3.org/1999/xlink}label": factVarLabel,
                             "bindAsSequence": ("false","true")[sc.bindAsSequence]})
    etree.SubElement(sc.genLinkElement,
                     "{http://xbrl.org/2008/variable}variableArc",
                     attrib={"{http://www.w3.org/1999/xlink}type": "arc",
                             "{http://www.w3.org/1999/xlink}arcrole": "http://xbrl.org/arcrole/2008/variable-set",
                             "{http://www.w3.org/1999/xlink}from": sc.assertionID,
                             "{http://www.w3.org/1999/xlink}to": factVarLabel,
                             "name": factVarLabel})
    # generate filters
    filterNames = {"filter_"}
    for axis in node.axes:
        filterName = "filter_"
        axisName = evaluate(axis.name, sc)
        if axisName == "primary":
            axisRestriction = evaluate(axis.restriction, sc)[0]
            filterName = "concept"
        elif isinstance(axisName, QName):
            axisRestriction = evaluate(axis.restriction, sc)[0]
            filterName = "dim_" + axisRestriction.localName
        if filterName in filterNames:
            for suffixNumber in range(1,10000):
                if filterName + str(suffixNumber) not in filterNames:
                    filterName += str(suffixNumber)
                    break
        filterNames.add(filterName)
        filterLabel = factVarLabel  + "_" + filterName
        if axis.name == "primary":
            elt = etree.SubElement(sc.genLinkElement, "{http://xbrl.org/2008/filter/concept}conceptName",
                                   attrib={"{http://www.w3.org/1999/xlink}type": "resource",
                                           "{http://www.w3.org/1999/xlink}label": filterLabel})
            etree.SubElement(sc.genLinkElement, "{http://xbrl.org/2008/variable}variableFilterArc",
                             attrib={"{http://www.w3.org/1999/xlink}type": "arc",
                                     "{http://www.w3.org/1999/xlink}arcrole": "http://xbrl.org/arcrole/2008/variable-filter",
                                     "{http://www.w3.org/1999/xlink}from": factVarLabel,
                                     "{http://www.w3.org/1999/xlink}to": filterLabel,
                                     "complement": "false",
                                     "cover": "true"})
            elt = etree.SubElement(elt, "{http://xbrl.org/2008/filter/concept}concept")
            etree.SubElement(elt, "{http://xbrl.org/2008/filter/concept}qname").text = str(axisRestriction)
        elif isinstance(axis.name, QName): # dimension
            elt = etree.SubElement(sc.genLinkElement, "{http://xbrl.org/2008/filter/dimension}explicitDimension",
                                   attrib={"{http://www.w3.org/1999/xlink}type": "resource",
                                           "{http://www.w3.org/1999/xlink}label": filterLabel})
            etree.SubElement(sc.genLinkElement, "{http://xbrl.org/2008/variable}variableFilterArc",
                             attrib={"{http://www.w3.org/1999/xlink}type": "arc",
                                     "{http://www.w3.org/1999/xlink}arcrole": "http://xbrl.org/arcrole/2008/variable-filter",
                                     "{http://www.w3.org/1999/xlink}from": factVarLabel,
                                     "{http://www.w3.org/1999/xlink}to": filterLabel,
                                     "complement": "false",
                                     "cover": "true"})
            elt = etree.SubElement(elt, "{http://xbrl.org/2008/filter/dimension}dimension")
            etree.SubElement(elt, "{http://xbrl.org/2008/variable}dimension}qname").text = str(axisName)
            elt = etree.SubElement(elt, "{http://xbrl.org/2008/filter/dimension}member")
            etree.SubElement(elt, "{http://xbrl.org/2008/variable}dimension}qname").text = str(axisRestriction)

def genIf(node, sc):
    sc.xpathCode.append("if (")
    genNode(node.condition, sc)
    sc.xpathCode.append(") then (")
    genNode(node.thenExpr, sc)
    sc.xpathCode.append(") else  (")
    genNode(node.elseExpr, sc)
    sc.xpathCode.append(")")

def genMessage(node, sc, msgType):
    def taggedVarGenVar(node):
        tagGenVarLabel = "tagGeneralVariable_" + str(sc.generatedVarNbr)
        sc.generatedVarNbr += 1
        tagGenVarName = "$" + tagGenVarLabel
        sc.nodeXpathVarBindings[node] = tagGenVarName
        etree.SubElement(sc.genLinkElement,
                         "{http://xbrl.org/2008/variable}generalVariable",
                         attrib={"{http://www.w3.org/1999/xlink}type": "resource",
                                 "{http://www.w3.org/1999/xlink}label": tagGenVarLabel,
                                 "select": xpathCode(node, sc)})
        etree.SubElement(sc.genLinkElement,
                         "{http://xbrl.org/2008/variable}variableArc",
                         attrib={"{http://www.w3.org/1999/xlink}type": "arc",
                                 "{http://www.w3.org/1999/xlink}arcrole": "http://xbrl.org/arcrole/2008/variable-set",
                                 "{http://www.w3.org/1999/xlink}from": sc.assertionID,
                                 "{http://www.w3.org/1999/xlink}to": tagGenVarLabel,
                                 "name": tagGenVarName})

    msgLabel = sc.assertionID + "_" + msgType
    # generate mesage text
    if node and node.message:
        msgstr = evaluate(node.message, sc)
    else:
        msgstr = "Result ${value}"
    text = []
    i = 0
    while True:
        j = msgstr.find("${", i)
        if j >= 0:
            text.append(msgstr[i:j]) # previous part of string
            k = msgstr.find("}", j+2)
            if k > j:
                tagstr = msgstr[j+2:k].strip()
                tag, sep, modifier = tagstr.partition(".")
                if tag == "context":
                    text.append("{{${0}@contextRef}}".format(tag))
                elif tag in sc.tags:
                    taggedNode = sc.tags[tag]
                    if taggedNode not in sc.nodeXpathVarBindings:
                        taggedVarGenVar(taggedNode) # add a gen var for this tagged expression
                    text.append("{{{0}}}".format(sc.nodeXpathVarBindings[taggedNode]))
                else:
                    text.append('"{0}" is not supported for formula message generation'.format(tagstr))
                i = k + 1
        else:
            text.append(msgstr[i:])
            break
    messageStr = ''.join(text)
    etree.SubElement(sc.genLinkElement,
                     "{http://xbrl.org/2010/message}message",
                     attrib={"{http://www.w3.org/1999/xlink}type": "resource",
                             "{http://www.w3.org/1999/xlink}label": msgLabel,
                             "{http://www.w3.org/1999/xlink}role": "http://www.xbrl.org/2010/role/message",
                             "{http://www.w3.org/XML/1998/namespace}lang": "en"
                             }).text = messageStr
    etree.SubElement(sc.genLinkElement,
                     "{http://xbrl.org/2008/generic}arc",
                     attrib={"{http://www.w3.org/1999/xlink}type": "arc",
                             "{http://www.w3.org/1999/xlink}arcrole": "http://xbrl.org/arcrole/2010/" + msgType,
                             "{http://www.w3.org/1999/xlink}from": sc.assertionID,
                             "{http://www.w3.org/1999/xlink}to": msgLabel})

def genMethodReference(node, sc):
    formulaMethodSyntax = formulaMethodSyntaxPatterns.get(node.name,
                              ("$notImplemented_{0}(".format(node.name),")"))
    if isinstance(formulaMethodSyntax, tuple) and len(formulaMethodSyntax) == 2:
        sc.xpathCode.append(formulaMethodSyntax[0]) # before arguments
        for i, arg in enumerate(node.args):
            if i:
                sc.xpathCode.append(",")
            genNode(arg, sc)
        sc.xpathCode.append(formulaMethodSyntax[1]) # after arguments
    else:
        sc.logMessage("ERROR", "sphinxFormulaGenerator:methodSyntaxPatternError",
                      _("Syntax generator error for method %(name)s."),
                      sourceFileLine=node.sourceFileLine, name=node.name)

def genNoOp(node, sc):
    pass

def genNumericLiteral(node, sc):
    sc.xpathCode.append(str(node.value))

def genQnameLiteral(node, sc):
    sc.xpathCode.append(str(node.value))

def genStringLiteral(node, sc):
    sc.xpathCode.append('"' + node.text.replace('"', '""') + '"')

def genTagAssignment(node, sc):
    genNode(node.expr, sc) # expand syntax in place
    sc.tags[node.tagName] = node.expr

def genUnaryOperation(node, sc):
    sc.xpathCode.append("(")
    sc.xpathCode.append({"+": "+",
                         "-": "-",
                         "brackets": "",
                        }.get(node.op,"$$$opNotImplemented$$$"))
    genNode(node.expr, sc)
    sc.xpathCode.append(")")

def genValuesIteration(node, sc):
    pass

def genVariableAssignment(node, sc):
    # add a general variable for this node's expression, substitute gen var expression
    generalVarLabel = "generalVariable_" + node.variableName
    sc.xpathCode.append("$" + node.variableName)
    if node.tagName:
        sc.tags[node.tagName] = node.expr

    etree.SubElement(sc.genLinkElement,
                     "{http://xbrl.org/2008/variable}generalVariable",
                     attrib={"{http://www.w3.org/1999/xlink}type": "resource",
                             "{http://www.w3.org/1999/xlink}label": generalVarLabel,
                             "select": xpathCode(node.expr, sc)})
    etree.SubElement(sc.genLinkElement,
                     "{http://xbrl.org/2008/variable}variableArc",
                     attrib={"{http://www.w3.org/1999/xlink}type": "arc",
                             "{http://www.w3.org/1999/xlink}arcrole": "http://xbrl.org/arcrole/2008/variable-set",
                             "{http://www.w3.org/1999/xlink}from": sc.assertionID,
                             "{http://www.w3.org/1999/xlink}to": generalVarLabel,
                             "name": node.variableName})

def genVariableReference(node, sc):
    # if a macro reference, substitute the actual node
    if node.variableName in sc.localVariables:
        genNode(sc.localVariables[node.variableName], sc)
    else:
        sc.xpathCode.append("$" + node.variableName)

def genWith(node, sc):
    # with-dependent code goes into a fake general variable
    withExprGeneralVarLabel = "withExpressionGeneralVariable_" + str(sc.generatedVarNbr)
    sc.generatedVarNbr += 1
    sc.xpathCode.append("$" + withExprGeneralVarLabel)

    def genWithGenVarCode():
        # partition facts according to restriction
        sc.xpathCode.append(" if (false()) then (")
        # forces dependency by fake hyperspace fact variable reference
        genNode(node.restrictionExpr)
        sc.xpathCode.append(") else (")
        for varAssignNode in node.variableAssignments:
            genNode(node.varAssignNode, sc)
        genNode(node.bodyExpr)
        sc.xpathCode.append(")")

    etree.SubElement(sc.genLinkElement,
                     "{http://xbrl.org/2008/variable}generalVariable",
                     attrib={"{http://www.w3.org/1999/xlink}type": "resource",
                             "{http://www.w3.org/1999/xlink}label": withExprGeneralVarLabel,
                             "select": xpathCode(genWithGenVarCode, sc)})
    etree.SubElement(sc.genLinkElement,
                     "{http://xbrl.org/2008/variable}variableArc",
                     attrib={"{http://www.w3.org/1999/xlink}type": "arc",
                             "{http://www.w3.org/1999/xlink}arcrole": "http://xbrl.org/arcrole/2008/variable-set",
                             "{http://www.w3.org/1999/xlink}from": sc.assertionID,
                             "{http://www.w3.org/1999/xlink}to": withExprGeneralVarLabel,
                             "name": node.variableName})

def cleanedName(name):
    return re.sub(r"\W", "_", name)

genNodeHandler = {
    "astAnnotationDeclaration":   genNoOp,
    "astBinaryOperation":         genBinaryOperation,
    "astComment":                 genNoOp,
    "astFor":                     genFor,
    "astFunctionReference":       genFunctionReference,
    "astHyperspaceExpression":    genHyperspaceExpression,
    "astIf":                      genIf,
    "astMethodReference":         genMethodReference,
    "astNamespaceDeclaration":    genNoOp,
    "astNode":                    genNoOp,
    "astNoOp":                    genNoOp,
    "astNumericLiteral":          genNumericLiteral,
    "astQnameLiteral":            genQnameLiteral,
    "astSourceFile":              genNoOp,
    "astStringLiteral":           genStringLiteral,
    "astTagAssignment":           genTagAssignment,
    "astValuesIteration":         genValuesIteration,
    "astVariableAssignment":      genVariableAssignment,
    "astVariableReference":       genVariableReference,
    "astUnaryOperation":          genUnaryOperation,
    "astWith":                    genWith,
    }

evaluationHandler = {
    "astFunctionReference":       evaluateFunctionReference,
    "astQnameLiteral":            evaluateQnameLiteral,
    "astStringLiteral":           evaluateStringLiteral,
    "astVariableAssignment":      evaluateVariableAssignment,
    "astVariableReference":       evaluateVariableReference,
    }
formulaMethodSyntaxPatterns = {
    #"abs":          _abs,
    #"add-time-period": _addTimePeriod,
    #"balance":      _balance,
    #"concept":      _concept,
    #"concepts":     _concepts,
    #"contains":     _contains,
    #"credit":       _credit,
    #"days":         _days,
    #"debit":        _debit,
    #"decimals":     _decimals,
    #"dimension":    _dimension,
    #"dts-document-locations": _dtsDocumentLocations,
    #"duration":     _duration,
    #"end-date":     _endDate,
    #"ends-with":    _endsWith,
    #"entity":       _entityMethod,
    #"exp":          _exp,
    #"has-decimals": _hasDecimals,
    #"has-precision":_hasPrecision,
    #"identifier":   _identifier,
    #"index-of":     _indexOf,
    #"instant":      _instant,
    #"is-forever":   _isForever,
    #"is-monetary":  _isMonetary,
    #"is-numeric":   _isNumeric,
    #"last-index-of":_lastIndexOf,
    #"ln":           _ln,
    #"length":       _length,
    #"local-part":   _localPart,
    #"log":          _log,
    #"log10":        _log10,
    #"lower-case":   _lowerCase,
    #"name":         _name,
    #"period":       _period,
    #"period-type":  _periodType,
    #"power":        _power,
    #"precision":    _precision,
    #"primary":      _primary,
    #"replace":      _replace,
    #"round":        _roundItem,
    #"round-by-decimals": _roundDecimals,
    #"round-by-precision": _roundPrecision,
    #"scenario":     _scenario,
    #"schema-type":  _schemaTypeMethod,
    #"scheme":       _scheme,
    #"segment":      _segment,
    #"signum":       _signum,
    #"size":         _size,
    #"sqrt":         _sqrt,
    #"start-date":   _startDate,
    #"starts-with":  _startsWith,
    #"subtract-time-period": _subtractTimePeriod,
    #"taxonomy":     _taxonomy,
    #"to-list":      _toList,
    #"to-set":       _toSet,
    #"tuple":        _tuple,
    #"unit":         _unitMethod,
    #"unknown":      _notImplemented,
    #"upper-case":   _upperCase,
    #"xbrl-type":    _xbrlTypeMethod,

    #networks
    #"concept-hypercube-all":                _conceptHypercubeAll,
    #"concept-hypercube-all-networks":       _conceptHypercubeAllNetworks,
    #"concept-hypercube-not-all":            _conceptHypercubeNotAll,
    #"concept-hypercube-not-all-networks":   _conceptHypercubeNotAllNetworks,
    #"dimension-default":                    _dimensionDefault,
    #"dimension-default-networks":           _dimensionDefaultNetworks,
    #"dimension-domain":                     _dimensionDomain,
    #"dimension-domain-networks":            _dimensionDomainNetworks,
    #"domain-member":                        _domainMember,
    #"domain-member-networks":               _domainMemberNetworks,
    #"essence-alias":                        _essenceAlias,
    #"essence-alias-networks":               _essenceAliasNetworks,
    #"general-special":                      _generalSpecial,
    #"general-special-networks":             _generalSpecialNetworks,
    #"generic-link":                         _genericLink,
    #"generic-link-networks":                _genericLinkNetworks,
    #"hypercube-dimension":                  _hypercubeDimension,
    #"hypercube-dimension-networks":         _hypercubeDimensionNetworks,
    #"network":                              _network,
    #"networks":                             _networks,
    #"parent-child":                         _parentChild,
    #"parent-child-networks":                _parentChildNetworks,
    #"requires-element":                     _requiresElement,
    #"requires-element-networks":            _requiresElementNetworks,
    #"similar-tuples":                       _similarTuples,
    #"similar-tuples-networks":              _similarTuplesNetworks,
    #"summation-item":                       _summationItem,
    #"summation-item-networks":              _summationItemNetworks,

    #network methods
    #"ancestors":                            _ancestors,
    #"ancestor-relationships":               _ancestorRelationships,
    #"arc-name":                             _arcName,
    #"arcrole":                              _arcrole,
    #"children":                             _children,
    #"concepts":                             _concepts,
    #"descendant-relationships":             _descendantRelationships,
    #"descendants":                          _descendants,
    #"extended-link-name":                   _extendedLinkName,
    #"incoming-relationships":               _incomingRelationships,
    #"outgoing-relationships":               _outgoingRelationships,
    #"parents":                              _parents,
    #"relationships":                        _relationships,
    #"role":                                 _linkRole,
    #"source-concepts":                      _sourceConcepts,
    #"target-concepts":                      _targetConcepts,

    #relationship methods
    #"order":                                _order,
    #"preferred-label":                      _preferredLabel,
    #"source":                               _source,
    #"target":                               _target,
    #"weight":                               _weight,
    }

formulaFunctionSyntaxPatterns = {
    "boolean":      ("xs:boolean(", ")"),
    #"current-date-as-utc": _todayUTC,
#    "duration":     _durationFunction,
    "entity":       ("(", ")"),
    #"forever":      _foreverFunction,
    "instant":      ("xs:date(", ")"),
    "number":       ("number(", ")"),
    #"schema-type":  _schemaTypeFunction,
    #"time-period":  _timePeriodFunction,
    #"unit":         _unitFunction,
    }

aggreativeFunctions = {
    "all":          ("every $test in (", ") satisfies $test)"),
    "any":          ("some $test in (", ") satisfies $test)"),
    "avg":          ("avg(", ")"),
    "count":        ("count(", ")"),
    "exists":       ("exists(", ")"),
    "first":        ("(", ")[1]"),
    "list":         ("(", ")"),
    "max":          ("max(", ")"),
    #"median":       _median,
    "min":          ("min(", ")"),
    "missing":      ("empty(", ")"),
    #"mode":         _mode,
    #"modes":        _modes,
    #"set":          _set,
    #"stdevp":       _stdevp,
    "sum":          ("sum(", ")"),
    #"var":          _var,
    #"varp":         _varp,
    }
