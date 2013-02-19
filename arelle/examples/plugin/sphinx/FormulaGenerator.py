'''
formulaGenerator generates XBRL formula linkbases for a subset of the Sphinx language.

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).

Sphinx is a Rules Language for XBRL described by a Sphinx 2 Primer 
(c) Copyright 2012 CoreFiling, Oxford UK. 
Sphinx copyright applies to the Sphinx language, not to this software.
Mark V Systems conveys neither rights nor license for the Sphinx language. 
'''

import time, sys, io, os.path
from lxml import etree
from arelle.ModelValue import QName
from .SphinxParser import (parse, astNamespaceDeclaration, astRuleBasePreconditions, 
                           astValidationRule, astPreconditionDeclaration,
                           astNumericLiteral, astFunctionReference,
                           astBinaryOperation, astFactPredicate)


def generateFormulaLB(cntlr, sphinxFiles, generatedSphinxFormulasDirectory):

    if sys.version[0] >= '3':
        from arelle.pyparsing.pyparsing_py3 import lineno
    else: 
        from pyparsing import lineno
        
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
    validate(logMessage, sc)
    assertionIDs = set()
        
    for prog in sc.sphinxProgs:
        sphinxFile = prog[0].fileName
        sphinxXmlns = {"xlink": 'http://www.w3.org/1999/xlink',
                        "link": 'http://www.xbrl.org/2003/linkbase',
                        "generic": 'http://xbrl.org/2008/generic',
                        "formula": 'http://xbrl.org/2008/formula',
                        "validation": 'http://xbrl.org/2008/validation',
                        "ca": 'http://xbrl.org/2008/assertion/consistency',
                        "ea": 'http://xbrl.org/2008/assertion/existence',
                        "va": 'http://xbrl.org/2008/assertion/value',
                        "bf": 'http://xbrl.org/2008/filter/boolean',
                        "variable": 'http://xbrl.org/2008/variable',
                        "pf": 'http://xbrl.org/2008/filter/period',
                        "cf": 'http://xbrl.org/2008/filter/concept',
                        "df": 'http://xbrl.org/2008/filter/dimension',
                        "gf": 'http://xbrl.org/2008/filter/general',
                        "label": 'http://xbrl.org/2008/label',
                        "xfi": 'http://www.xbrl.org/2008/function/instance',
                        "xsi": 'http://www.w3.org/2001/XMLSchema-instance',
                        "xs": 'http://www.w3.org/2001/XMLSchema',
                        "uf": 'http://xbrl.org/2008/filter/unit',
                        "msg": 'http://xbrl.org/2010/message',
                        "xbrli": 'http://www.xbrl.org/2003/instance'}
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
        
        print (str(prog))
        
        for node in prog:
            if isinstance(node, astValidationRule):
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
                sc.assertionTest = [] 
                sc.assertionVarNames = {"factVar_"}
                genTestExpr(node.expr, sc, False)
                if sc.assertionTest and sc.assertionTest[0] == '(' and sc.assertionTest[-1] == ')':
                    # assertion fails if sphinx rule is true
                    sc.assertionTest[0] = "not("
                if sc.assertionTest:
                    sc.assertionElt.set("test", " ".join(sc.assertionTest))
        
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
    
def genTestExpr(node, sc, bindAsSeq):
    if isinstance(node, astFactPredicate):
        # generate fact variable and substitute it's reference in text code
        # find pri item for fact var name
        priItemName = "factVar_"
        for axis, value in node.axes.items():
            if axis == "primary":
                priItemName = value.localName
                break
        if priItemName in sc.assertionVarNames:
            for suffixNumber in range(1,10000):
                if priItemName + str(suffixNumber) not in sc.assertionVarNames:
                    priItemName += str(suffixNumber)
                    break
        sc.assertionVarNames.add(priItemName)
        factVarLabel = sc.assertionID + "_" + priItemName
        sc.assertionTest.append("$" + factVarLabel)
        etree.SubElement(sc.genLinkElement,
                         "{http://xbrl.org/2008/variable}factVariable",
                         attrib={"{http://www.w3.org/1999/xlink}type": "resource",
                                 "{http://www.w3.org/1999/xlink}label": factVarLabel,
                                 "bindAsSequence": ("false","true")[bindAsSeq]})
        etree.SubElement(sc.genLinkElement,
                         "{http://xbrl.org/2008/variable}variableArc",
                         attrib={"{http://www.w3.org/1999/xlink}type": "arc",
                                 "{http://www.w3.org/1999/xlink}arcrole": "http://xbrl.org/arcrole/2008/variable-set",
                                 "{http://www.w3.org/1999/xlink}from": sc.assertionID,
                                 "{http://www.w3.org/1999/xlink}to": factVarLabel,
                                 "name": factVarLabel})
        # generate filters
        filterNames = {"filter_"}
        for axis, value in node.axes.items():
            filterName = "filter_"
            if axis == "primary":
                filterName = "concept"
            elif isinstance(axis, QName):
                filterName = "dim_" + axis.localName
            if filterName in filterNames:
                for suffixNumber in range(1,10000):
                    if filterName + str(suffixNumber) not in filterNames:
                        filterName += str(suffixNumber)
                        break
            filterNames.add(filterName)
            filterLabel = factVarLabel  + "_" + filterName
            if axis == "primary":
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
                etree.SubElement(elt, "{http://xbrl.org/2008/filter/concept}qname").text = str(value)
            elif isinstance(axis, QName): # dimension
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
                etree.SubElement(elt, "{http://xbrl.org/2008/variable}dimension}qname").text = str(axis)
                elt = etree.SubElement(elt, "{http://xbrl.org/2008/filter/dimension}member")
                etree.SubElement(elt, "{http://xbrl.org/2008/variable}dimension}qname").text = str(value)
    elif isinstance(node, astBinaryOperation):
        sc.assertionTest.append("(")
        genTestExpr(node.leftExpr, sc, bindAsSeq)
        sc.assertionTest.append({"+": "+", "-": "-", "*": "", "/": "div",
                                 "<": "lt", "<+": "le", ">": "gt", ">=": "ge",
                                 "==": "eq", "!=": "ne", 
                                 }.get(node.op,"$$$opNotImplemented$$$"))
        genTestExpr(node.rightExpr, sc, bindAsSeq)
        sc.assertionTest.append(")")
    elif isinstance(node, astNumericLiteral):
        sc.assertionTest.append(str(node.value))
    elif isinstance(node, astFunctionReference):
        if node.name in {"sum", "count"}:
            nestedBindAsSeq = True
        else:
            nestedBindAsSeq = bindAsSeq
        sc.assertionTest.append({"sum": "sum(",
                                 "count": "count(",
                                 }.get(node.name, "$$$functionNotImplemented_{0}$$$(".format(node.name)))
        for i, arg in enumerate(node.args):
            if i: 
                sc.assertionTest.append(",")
            genTestExpr(arg, sc, nestedBindAsSeq)
        sc.assertionTest.append(")")
            
            