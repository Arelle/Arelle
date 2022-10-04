'''
formula loader for XBRL Formula files.

See COPYRIGHT.md for copyright information.

Loads xbrl formula file syntax into formula linkbase.

To run as a main program and save xbrl formula files (.xf) into xbrl formula linkbase:

   python3.5  formulaLoader.py [--debug] [--omit-sourceline-attributes] {files}
   where {files} are formula files
   loads from {name}.xf file
   saves formula linkbase to {name}-formula.xml file
   if --debug is specified then pyparsing debug trace is printed (helpful to see where parsing got stuck if parse errors)
   if --omit-sourceline-attributes is specified, then resulting linkbase omits "xfs:sourceline" attributes

As a plugin this enables Arelle to load formula files (*.xf) into Arelle's object model for formula linkbases and execute them.
When run from GUI first load the instance/DTS and then import the xf file(s).

'''

import time, sys, traceback, os, io, os.path, re, zipfile
from arelle.Version import authorLabel, copyrightLabel
from lxml import etree

# Debugging flag can be set to either "debug_flag=True" or "debug_flag=False"
debug_flag=True

logMessage = None
xfsFile = None
lastLoc = 0
lineno = col = line = None

lbGen = None

omitSourceLineAttributes = False

reservedWords = {} # words that can't be qnames

isGrammarCompiled = False

class PrefixError(Exception):
    def __init__(self, qnameToken):
        self.qname = qnameToken
        self.message = "QName prefix undeclared"
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _("QName prefix undeclared: {0}").format(self.qname)

def cleanedName(name):
    return re.sub(r"\W", "_", name)

def dequotedString(s):
    q = s[0]
    if q != '"' and q != "'":
        return s # note quoted
    return s[1:-1].replace(q+q,q)

def camelCase(name):
    s = []
    wasDash = False
    for c in name:
        if c == "-":
            wasDash = True
        else:
            if wasDash:
                s.append(c.upper())
                wasDash = False
            else:
                s.append(c)
    return "".join(s)



# parse operations ("compile methods") are listed alphabetically

def compileAspectCoverFilter( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    filterLabel = "filter{}".format(lbGen.labelNbr("filter"))
    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": "variable-filter",
               "xlink:to": filterLabel,
               "complement": "false",
               "cover": "true"}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] = "{}".format(loc)

    filterAttrib = {"xlink:type": "resource",
                    "xlink:label": filterLabel}
    prevTok = None
    for tok in toks:
        if tok == "complemented":
            arcAttrib["complement"] = "true"
        elif tok == "covering":
            arcAttrib["cover"] = "true"
        elif tok == "non-covering":
            arcAttrib["cover"] = "false"
        prevTok = tok
    filterElt = lbGen.subElement(lbGen.genLinkElement, "acf:aspectCover", attrib=filterAttrib)
    # sub-elements of filter
    dimElt = None
    for tok in toks:
        if tok in {"all", "concept", "entity-identifier", "location", "period", "unit",
                   "complete-segment", "complete-scenario", "non-XDT-segment", "non-XDT-scenario",
                   "dimensions"} and dimElt is None:
            lbGen.subElement(filterElt, "acf:aspect", text=tok)
        elif tok == "dimension":
            dimElt = "acf:dimension"
        elif tok == "exclude-dimension":
            dimElt = "acf:excludeDimension"
        elif dimElt is not None:
            if isinstance(tok, XPathExpression):
                lbGen.subElement(filterElt, dimElt, text=str(tok))
            elif ':' in tok: # it's a QName
                lbGen.subElement(filterElt, dimElt, text=tok)
            else: # it's a local name, requires general & aspect cover filter
                lbGen.checkXmlns("xfi")
                lbGen.subElement(filterElt, dimElt,
                                 text="xfi:concepts-from-local-name('{}')".format(tok))
            dimElt = None
    return [FormulaArc("variable:variableFilterArc", attrib=arcAttrib),
            FormulaResourceElt(filterElt)]

def compileAspectRules( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    attrib = {}
    prevTok = None
    for tok in toks:
        if prevTok == "source":
            attrib["source"] = tok
        prevTok = tok
    elt = lbGen.element("formula:aspects", attrib=attrib)
    for tok in toks:
        if isinstance(tok, FormulaAspectElt):
            elt.append(tok.elt)
    return [FormulaAspectElt(elt)]

def compileAspectRuleConcept( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    elt = lbGen.element("formula:concept")
    if isinstance(toks[0], XPathExpression):
        lbGen.subElement(elt, "formula:qnameExpression", text=str(toks[0]))
    else:
        lbGen.subElement(elt, "formula:qname", text=lbGen.checkedQName(toks[0]))
    return [FormulaAspectElt(elt)]

def compileAspectRuleEntityIdentifier( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    attrib = {}
    prevTok = None
    for tok in toks:
        if prevTok == "scheme":
            attrib["scheme"] = str(tok)
        elif prevTok == "identifier":
            attrib["identifier"] = str(tok)
        prevTok = tok
    elt = lbGen.element("formula:entityIdentifier", attrib=attrib)
    return [FormulaAspectElt(elt)]

def compileAspectRulePeriod( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    elt = lbGen.element("formula:period")
    prevTok = None
    for tok in toks:
        if tok in ("forever", "instant", "duration"):
            perElt = lbGen.subElement(elt, "formula:" + tok)
        elif prevTok == "instant":
            perElt.set("value", str(tok))
        elif prevTok == "start":
            perElt.set("start", str(tok))
        elif prevTok == "end":
            perElt.set("end", str(tok))
        prevTok = tok
    return [FormulaAspectElt(elt)]

def compileAspectRuleUnit( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    elt = lbGen.element("formula:unit")
    prevTok = None
    for tok in toks:
        if tok == "augment":
            elt.set("augment", "true")
        elif isinstance(tok, FormulaAspectElt):
            elt.append(tok)
        prevTok = tok
    return [FormulaAspectElt(elt)]

def compileAspectRuleUnitTerm( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    elt = lbGen.element("formula:" + camelCase(tok[0]))
    prevTok = None
    for tok in toks:
        if prevTok == "source":
            elt.set("source", tok)
        elif prevTok == "measure":
            elt.set("measure", str(tok))
        prevTok = tok
    return [FormulaAspectElt(elt)]

def compileAspectRuleExplicitDimension( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    elt = lbGen.element("formula:explicitDimension", attrib={"dimension": tok[0]})
    for tok in toks:
        if isinstance(tok, FormulaAspectElt):
            elt.append(tok)
    return [FormulaAspectElt(elt)]

def compileAspectRuleExplicitDimensionTerm( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    prevTok = None
    for tok in toks:
        if prevTok == "member":
            elt = lbGen.element("formula:member")
            if isinstance(toks, XPathExpression):
                lbGen.subElement(elt, "formula:qnameExpression", text=str(tok))
            else:
                lbGen.subElement(elt, "formula:qname", text=lbGen.checkedQName(tok))
        elif prevTok == "omit":
            elt = lbGen.element("formula:omit")
        prevTok = tok
    return [FormulaAspectElt(elt)]

def compileAspectRuleTypedDimension( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    elt = lbGen.element("formula:typedDimension", attrib={"dimension": tok[0]})
    for tok in toks:
        if isinstance(tok, FormulaAspectElt):
            elt.append(tok)
    return [FormulaAspectElt(elt)]

def compileAspectRuleTypedDimensionTerm( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    prevTok = None
    for tok in toks:
        if prevTok == "xpath":
            elt = lbGen.element("formula:xpath", text=str(tok))
        elif prevTok == "value":
            elt = lbGen.element("formula:value")
            elt.append(etree.fromstring(dequotedString(tok)))
        elif prevTok == "omit":
            elt = lbGen.element("formula:omit")
        prevTok = tok
    return [FormulaAspectElt(elt)]

def compileAssertion( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    assertionLabel = "assertion{}".format(lbGen.labelNbr("assertion"))
    attrib = {"xlink:type": "resource",
              "xlink:label": assertionLabel,
              "aspectModel": "dimensional",
              "implicitFiltering": "true"}
    assertionEltQname = "va:valueAssertion" # default for error situations
    prevTok = None
    for tok in toks:
        if prevTok is None:
            attrib["id"] = tok
        elif prevTok == "test":
            assertionEltQname = "va:valueAssertion"
            attrib["test"] = str(tok)
        elif prevTok == "evaluation-count":
            assertionEltQname = "ea:existenceAssertion"
            attrib["test"] = str(tok)
        elif tok == "aspect-model-non-dimensional":
            attrib["aspectModel"] = "non-dimensional"
        elif tok == "no-implicit-filtering":
            attrib["implicitFiltering"] = "false"
        prevTok = tok
    elt = lbGen.subElement(lbGen.genLinkElement,
             assertionEltQname,
             attrib=attrib)
    for tok in toks:
        if isinstance(tok, FormulaResourceElt):
            tok.elt.addprevious(elt)
            break
    for tok in toks:
        if isinstance(tok, FormulaArc):
            tag = tok.tag
            attrib = tok.attrib.copy()
            if tag == "variable:variableFilterArc":
                tag = "variable:variableSetFilterArc"
                if "cover" in attrib:
                    del attrib["cover"] # no cover on variable set filter arc
            attrib["xlink:from"] = assertionLabel
            lbGen.subElement(lbGen.genLinkElement, tag, attrib)
    arcAttrib =  {"xlink:type": "arc",
                  "xlink:arcrole": "assertion-set",
                  "xlink:to": assertionLabel}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] =  "{}".format(loc)

    return [FormulaArc("generic:arc", attrib=arcAttrib), FormulaResourceElt(elt)]

def compileAssertionSet( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    assertionSetLabel = "assertionSet{}".format(lbGen.labelNbr("assertionSet"))
    attrib = {"xlink:type": "resource",
              "xlink:label": assertionSetLabel}
    prevTok = None
    eltPositioned = False
    for tok in toks:
        if prevTok is None:
            attrib["id"] = tok
        prevTok = tok
    elt = lbGen.element(
             "validation:assertionSet",
             attrib=attrib)
    for tok in toks:
        if isinstance(tok, FormulaResourceElt) and not eltPositioned:
            tok.elt.addprevious(elt)
            elt = None
            eltPositioned = True
    if not eltPositioned:
        lbGen.genLinkElement.append(elt)
        eltPositioned = True
    for tok in toks:
        if isinstance(tok, FormulaArc):
            tok.attrib["xlink:from"] = assertionSetLabel
            lbGen.subElement(lbGen.genLinkElement, tok.tag, tok.attrib)
    return [FormulaResourceElt(elt)]

commentStripPattern = re.compile(r"^\(:\s*|\s*:\)$")
def compileComment( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    if lbGen is not None: # none when compiling grammer first time
        lbGen.genLinkElement.append(etree.Comment(commentStripPattern.sub("", toks[0])))
    return []

def compileBooleanFilter( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    filterLabel = "filter{}".format(lbGen.labelNbr("filter"))
    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": "variable-filter",
               "xlink:to": filterLabel,
               "complement": "false",
               "cover": "true"}

    if not omitSourceLineAttributes:
       arcAttrib["xfs:sourceline"] = "{}".format(loc)

    filterAttrib = {"xlink:type": "resource",
                    "xlink:label": filterLabel}
    prevTok = filterEltQname = None
    isMatchDimension = False
    for tok in toks:
        if tok == "complemented":
            arcAttrib["complement"] = "true"
        elif tok == "covering":
            arcAttrib["cover"] = "true"
        elif tok == "non-covering":
            arcAttrib["cover"] = "false"
        elif filterEltQname is None:
            if tok == "and":
                filterEltQname = "bf:andFilter"
            elif tok == "or":
                filterEltQname = "bf:orFilter"
        prevTok = tok
    filterElt = lbGen.subElement(lbGen.genLinkElement, filterEltQname, attrib=filterAttrib)
    eltPositioned = False
    for tok in toks:
        if isinstance(tok, FormulaResourceElt) and not eltPositioned:
            tok.elt.addprevious(filterElt)
            eltPositioned = True
    if not eltPositioned:
        lbGen.genLinkElement.append(filterElt)
        eltPositioned = True
    for tok in toks:
        if isinstance(tok, FormulaArc):
            tok.attrib["xlink:from"] = filterLabel
            tok.attrib["xlink:arcrole"] = "boolean-filter"
            lbGen.subElement(lbGen.genLinkElement, tok.tag, tok.attrib)
    return [FormulaArc("variable:variableFilterArc", attrib=arcAttrib),
            FormulaResourceElt(filterElt)]

def compileConceptFilter( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    filterLabel = "filter{}".format(lbGen.labelNbr("filter"))
    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": "variable-filter",
               "xlink:to": filterLabel,
               "complement": "false",
               "cover": "true"}
    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] = "{}".format(loc)
    filterAttrib = {"xlink:type": "resource",
                    "xlink:label": filterLabel}
    prevTok = filterEltQname = None
    isName = isPeriodType = isBalance = isDataType = isSubstitution = False
    hasLocalName = False
    for tok in toks:
        if tok == "complemented":
            arcAttrib["complement"] = "true"
        elif tok == "covering":
            arcAttrib["cover"] = "true"
        elif tok == "non-covering":
            arcAttrib["cover"] = "false"
        elif filterEltQname is None:
            if tok == "concept-name":
                isName = True
                filterEltQname = "cf:conceptName"
            elif tok == "concept-period-type":
                isPeriodType = True
                filterEltQname = "cf:conceptPeriodType"
            elif tok == "concept-balance":
                isBalance = True
                filterEltQname = "cf:conceptBalance"
            elif tok == "concept-data-type":
                isDataType = True
                filterEltQname = "cf:conceptDataType"
                filterAttrib["strict"] = "false"
            elif tok == "concept-substitution-group":
                isSubstitution = True
                filterEltQname = "cf:conceptSubstitutionGroup"
        elif isPeriodType and tok in ("instant", "duration"):
            filterAttrib["periodType"] = tok
        elif isBalance and tok in ("credit", "debit", "none"):
            filterAttrib["balance"] = tok
        elif isSubstitution and tok == "strict":
            filterAttrib["strict"] = "true"
        elif isSubstitution and prevTok == "non-strict":
            filterAttrib["strict"] = "false"
        elif isName and not hasLocalName and isinstance(tok, str) and ":" not in tok:
            hasLocalName = True
        prevTok = tok
    filterElt = lbGen.subElement(lbGen.genLinkElement, filterEltQname, attrib=filterAttrib)
    if isDataType:
        subEltParent = lbGen.subElement(filterElt, "cf:type")
    elif isName:
        subEltParent = lbGen.subElement(filterElt, "cf:concept")
    else:
        subEltParent = filterElt
    # sub-elements of filter
    if isName or isSubstitution or isDataType:
        useTok = False
        for tok in toks:
            # "concept-name" (qname | local-name | enclosed-expression)+
            # "concept-data-type" ("strict" | "not-strict") (qname | enclosed-expression)
            # "concept-substitution-group" ("strict" | "not-strict") (qname | enclosed-expression)
            if not useTok and tok in ("concept-name", "strict", "non-strict"):
                useTok = True
            elif useTok:
                if isinstance(tok, XPathExpression):
                    lbGen.subElement(subEltParent, "cf:qnameExpression", text=str(tok))
                elif ':' in tok: # it's a QName
                    lbGen.subElement(subEltParent, "cf:qname", text=lbGen.checkedQName(tok))
                else: # it's a local name, requires general & aspect cover filter
                    lbGen.checkXmlns("xfi")
                    lbGen.subElement(subEltParent, "cf:qnameExpression",
                                     text="xfi:concepts-from-local-name('{}')".format(tok))
    return [FormulaArc("variable:variableFilterArc", attrib=arcAttrib),
            FormulaResourceElt(filterElt)]

def compileConceptRelationFilter( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    filterLabel = "filter{}".format(lbGen.labelNbr("filter"))
    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": "variable-filter",
               "xlink:to": filterLabel,
               "complement": "false",
               "cover": "true"}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] =  "{}".format(loc)

    filterAttrib = {"xlink:type": "resource",
                    "xlink:label": filterLabel}
    prevTok = None
    for tok in toks:
        if tok == "complemented":
            arcAttrib["complement"] = "true"
        elif tok == "covering":
            arcAttrib["cover"] = "true"
        elif tok == "non-covering":
            arcAttrib["cover"] = "false"
        elif prevTok == "test":
            filterAttrib["test"] = str(tok)
        prevTok = tok
    filterElt = lbGen.subElement(lbGen.genLinkElement, "crf:conceptRelation", attrib=filterAttrib)
    # sub-elements of filter
    crfElt = None
    beforeSubElt = True
    afterConceptRel = False
    for tok in toks:
        if tok in {"linkrole", "arcrole"} and crfElt is None:
            crfElt = dequotedString(tok)
            beforeSubElt = False
        elif tok in {"axis", "generations"} and crfElt is None:
            crfElt = tok
            beforeSubElt = False
        elif crfElt is not None:
            if isinstance(tok, XPathExpression):
                lbGen.subElement(filterElt, crfElt + "Expression", text=str(tok))
            else:
                lbGen.subElement(filterElt, crfElt, text=tok)
            crfElt = None
        elif tok == "concept-relation":
            afterConceptRel = True
        elif afterConceptRel and beforeSubElt:
            if isinstance(tok, XPathExpression):
                lbGen.subElement(filterElt, "crf:qnameExpression", text=str(tok))
            elif tok.startswith('$'):
                lbGen.subElement(filterElt, "crf:variable", text=tok)
            elif ':' in tok: # it's a QName
                lbGen.subElement(filterElt, "crf:qname", text=lbGen.checkedQName(tok))
            else: # it's a local name, requires general & aspect cover filter
                lbGen.checkXmlns("xfi")
                lbGen.subElement(filterElt, "crf:qnameExpression",
                                 text="xfi:concepts-from-local-name('{}')".format(tok))
    return [FormulaArc("variable:variableFilterArc", attrib=arcAttrib),
            FormulaResourceElt(filterElt)]

def compileConsistencyAssertion( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    assertionLabel = "assertion{}".format(lbGen.labelNbr("assertion"))
    attrib = {"xlink:type": "resource",
              "xlink:label": assertionLabel,
              "strict": "false"}
    prevTok = None
    for tok in toks:
        if prevTok is None:
            attrib["id"] = tok
        elif tok == "strict":
            attrib["strict"] = "true"
        elif prevTok == "absolute-acceptance-radius":
            attrib["absoluteAcceptanceRadius"] = str(tok)
        elif prevTok == "proportional-acceptance-radius":
            attrib["proportionalAcceptanceRadius"] = str(tok)
        prevTok = tok
    elt = lbGen.subElement(lbGen.genLinkElement,
             "ca:consistencyAssertion",
             attrib=attrib)
    for tok in toks:
        if isinstance(tok, FormulaResourceElt):
            tok.elt.addprevious(elt)
            break
    for tok in toks:
        if isinstance(tok, FormulaArc):
            tok.attrib["xlink:arcrole"] = "consistency-assertion-formula"
            tok.attrib["xlink:from"] = assertionLabel
            lbGen.subElement(lbGen.genLinkElement, tok.tag, tok.attrib)

    arcAttrib = {"xlink:type": "arc",
                 "xlink:arcrole": "assertion-set",
                 "xlink:to": assertionLabel}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] =  "{}".format(loc)

    return [FormulaArc("generic:arc",
                       attrib= arcAttrib),
            FormulaResourceElt(elt)]

def compileDefaults( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    prevTok = None
    for tok in toks:
        if prevTok == "default-language":
            lbGen.defaultLanguage = tok
        elif prevTok == "unsatisfied-severity":
            lbGen.defaultUnsatisfiedMessageSeverity = tok
        prevTok = tok
    return []

def compileDimensionFilter( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    filterLabel = "filter{}".format(lbGen.labelNbr("filter"))
    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": "variable-filter",
               "xlink:to": filterLabel,
               "complement": "false",
               "cover": "true"}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] = "{}".format(loc)

    filterAttrib = {"xlink:type": "resource",
                    "xlink:label": filterLabel}
    prevTok = filterEltQname = None
    isTyped = False
    for tok in toks:
        if tok == "complemented":
            arcAttrib["complement"] = "true"
        elif tok == "covering":
            arcAttrib["cover"] = "true"
        elif tok == "non-covering":
            arcAttrib["cover"] = "false"
        elif filterEltQname is None:
            if tok == "typed-dimension":
                isTyped = True
                filterEltQname = "df:typedDimension"
            elif tok == "explicit-dimension":
                isTyped = False
                filterEltQname = "df:explicitDimension"
        elif prevTok == "test" and isinstance(tok, XPathExpression):
            filterAttrib["test"] = str(tok)
        prevTok = tok
    filterElt = lbGen.subElement(lbGen.genLinkElement, filterEltQname, attrib=filterAttrib)
    # sub-elements of filter
    prevTok = None
    for tok in toks:
        if prevTok in ("explicit-dimension", "typed-dimension"):
            dimElt = lbGen.subElement(filterElt, "df:dimension")
            if isinstance(tok, XPathExpression):
                dimQNameExpr = str(tok)
                lbGen.subElement(dimElt, "df:qnameExpression", text=dimQNameExpr)
            elif ':' in tok: # it's a QName
                lbGen.subElement(dimElt, "df:qname", text=lbGen.checkedQName(tok))
                dimQNameExpr = "resolve-QName({})".format(lbGen.checkedQName(tok))
            else: # it's a local name
                dimQNameExpr = "xfi:concepts-from-local-name('{}')".format(tok)
                lbGen.checkXmlns("xfi")
                lbGen.subElement(dimElt, "df:qnameExpression", text=dimQNameExpr)
        elif prevTok == "member":
            memElt = lbGen.subElement(filterElt, "df:member")
            if isinstance(tok, XPathExpression):
                lbGen.subElement(memElt, "df:qnameExpression", text=str(tok))
            elif tok.startswith('$'):
                lbGen.subElement(memElt, "df:variable", text=tok[1:]) # remove $ from variable name
            elif ':' in tok: # it's a QName
                lbGen.subElement(memElt, "df:qname", text=lbGen.checkedQName(tok))
            else: # it's a local name
                lbGen.checkXmlns("xfi")
                lbGen.subElement(memElt, "df:qnameExpression",
                                 text="xfi:concepts-from-local-name('{}')".format(tok))
        elif prevTok in ("linkrole", "arcrole", "axis"):
            lbGen.subElement(memElt, "df:" + prevTok, text=dequotedString(tok))
        elif tok == "default-member":
            memElt = lbGen.subElement(filterElt, "df:member")
            lbGen.checkXmlns("xfi")
            lbGen.subElement(memElt, "df:qnameExpression",
                             text="xfi:dimension-default('{}')".format(dimQNameExpr))
        prevTok = tok
    return [FormulaArc("variable:variableFilterArc", attrib=arcAttrib),
            FormulaResourceElt(filterElt)]

def compileEntityFilter( sourceStr, loc, toks ):
    filterLabel = "filter{}".format(lbGen.labelNbr("filter"))
    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": "variable-filter",
               "xlink:to": filterLabel,
               "complement": "false",
               "cover": "true"}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] = "{}".format(loc)

    filterAttrib = {"xlink:type": "resource",
                    "xlink:label": filterLabel}
    prevTok = filterEltQname = None
    for tok in toks:
        if tok == "complemented":
            arcAttrib["complement"] = "true"
        elif tok == "covering":
            arcAttrib["cover"] = "true"
        elif tok == "non-covering":
            arcAttrib["cover"] = "false"
        elif filterEltQname is None:
            if tok == "entity":
                filterEltQname = "ef:specificIdentifier"
            elif tok == "entity-scheme":
                filterEltQname = "ef:specificScheme"
            elif tok == "entity-scheme-pattern":
                filterEltQname = "ef:regexpScheme"
            elif tok == "entity-identifier-pattern":
                filterEltQname = "ef:regexpIdentifier"
        elif prevTok == "scheme" and isinstance(tok, XPathExpression):
            filterAttrib["scheme"] = str(tok)
        elif prevTok == "value" and isinstance(tok, XPathExpression):
            filterAttrib["value"] = str(tok)
        elif prevTok == "entity-scheme" and isinstance(tok, XPathExpression):
            filterAttrib["scheme"] = str(tok)
        elif prevTok in ("entity-scheme-pattern", "entity-identifier-pattern"):
            filterAttrib["pattern"] = dequotedString(tok)
        prevTok = tok
    filterElt = lbGen.subElement(lbGen.genLinkElement, filterEltQname, attrib=filterAttrib)
    return [FormulaArc("variable:variableFilterArc", attrib=arcAttrib),
            FormulaResourceElt(filterElt)]

def compileFactVariable( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    varLabel = "variable{}".format(lbGen.labelNbr("variable"))
    attrib = {"xlink:type": "resource",
              "xlink:label": varLabel,
              "bindAsSequence": "false"}
    prevTok = name = None
    for tok in toks:
        if prevTok is None:
            name = tok[1:] # remove $ from variable name
        elif tok == "bind-as-sequence":
            attrib["bindAsSequence"] = "true"
        elif tok == "nils":
            attrib["nils"] = "true"
        elif tok == "matches":
            attrib["matches"] = "true"
        elif prevTok == "fallback":
            attrib["fallbackValue"] = str(tok)
        elif isinstance(tok, FormulaArc):
            tok.attrib["xlink:from"] = varLabel
            lbGen.subElement(lbGen.genLinkElement, tok.tag, tok.attrib)
        prevTok = tok
    fvElt = lbGen.element(
             "variable:factVariable",
             attrib=attrib)
    fvFormulaResource = FormulaResourceElt(fvElt)
    for tok in toks:
        if isinstance(tok, FormulaResourceElt):
            tok.elt.addprevious(fvElt)
            fvElt = None
            break
    if fvElt is not None: # no filter to preceede
        lbGen.genLinkElement.append(fvElt)

    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": "variable-set",
               "xlink:to": varLabel,
               "name": lbGen.checkedQName(name)}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] = "{}".format(loc)

    return [FormulaArc("variable:variableArc", attrib=arcAttrib), fvFormulaResource]

def compileFilterDeclaration( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    return []

def compileFilterReference( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    return []

def compileFormula( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    formulaLabel = "formula{}".format(lbGen.labelNbr("formula"))
    attrib = {"xlink:type": "resource",
              "xlink:label": formulaLabel,
              "aspectModel": "dimensional",
              "implicitFiltering": "true"}
    prevTok = None
    for tok in toks:
        if prevTok is None:
            attrib["id"] = tok
        elif prevTok == "decimals":
            attrib["decimals"] = str(tok)
        elif prevTok == "precision":
            attrib["precision"] = str(tok)
        elif prevTok == "value":
            attrib["value"] = str(tok)
        elif prevTok == "source":
            attrib["source"] = tok
        elif tok == "aspect-model-non-dimensional":
            attrib["aspectModel"] = "non-dimensional"
        elif tok == "no-implicit-filtering":
            attrib["implicitFiltering"] = "false"
        prevTok = tok
    elt = lbGen.subElement(lbGen.genLinkElement, "formula:formula", attrib=attrib)
    for tok in toks:
        if isinstance(tok, FormulaResourceElt):
            tok.elt.addprevious(elt)
            break
    for tok in toks:
        if isinstance(tok, FormulaAspectElt):
            elt.append(tok.elt)
    for tok in toks:
        if isinstance(tok, FormulaArc):
            tag = tok.tag
            attrib = tok.attrib.copy()
            if tag == "variable:variableFilterArc":
                tag = "variable:variableSetFilterArc"
                if "cover" in attrib:
                    del attrib["cover"] # no cover on variable set filter arc
            attrib["xlink:from"] = formulaLabel
            lbGen.subElement(lbGen.genLinkElement, tag, attrib)
    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": "consistency-assertion-formula",
               "xlink:to": formulaLabel}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] = "{}".format(loc)

    return [FormulaArc("generic:arc", attrib=arcAttrib), FormulaResourceElt(elt)]


def compileFunctionDeclaration( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    # first do function signature (may not have an implementation part
    signatureAttrib = {"xlink:type": "resource",
                       "name": lbGen.checkedQName(toks[0])}
    hasImplementation = False
    prevTok = None
    for tok in toks:
        if prevTok == "as":
            signatureAttrib["output"] = tok
        elif tok == "return":
            hasImplementation = "true"
            signatureLabel = "function{}".format(lbGen.labelNbr("function"))
            signatureAttrib["xlink:label"] = signatureLabel
        prevTok = tok
    signatureElt = lbGen.subElement(lbGen.genLinkElement, "variable:function", attrib=signatureAttrib)
    prevTok = None
    for tok in toks:
        if isinstance(tok, FunctionParameter):
            lbGen.subElement(signatureElt, "variable:input", attrib={"type": tok.ptype})
    # function implementation
    if hasImplementation:
        cfiLabel = "functionImplementation{}".format(lbGen.labelNbr("functionImplementation"))
        lbGen.checkXmlns("cfi")
        cfiElt = lbGen.subElement(lbGen.genLinkElement, "cfi:implementation", attrib={
            "xlink:type": "resource",
            "xlink:label": cfiLabel})
        arcAttrib = {
            "xlink:type": "arc",
            "xlink:arcrole": "function-implementation",
            "xlink:from": signatureLabel,
            "xlink:to": cfiLabel
        }

        if not omitSourceLineAttributes:
            arcAttrib["xfs:sourceline"] = "{}".format(loc)

        lbGen.subElement(lbGen.genLinkElement, "generic:arc", attrib= arcAttrib)
        prevTok = None
        for tok in toks:
            if isinstance(tok, FunctionParameter):
                lbGen.subElement(cfiElt, "cfi:input", attrib={"name": lbGen.checkedQName(tok.qname)})
            elif isinstance(tok, FunctionStep):
                lbGen.subElement(cfiElt, "cfi:step", attrib={"name": lbGen.checkedQName(tok.qname)}, text=str(tok.xpathExpression))
            elif prevTok == "return":
                lbGen.subElement(cfiElt, "cfi:output", attrib={}, text=str(tok))
            prevTok = tok
    return []

def compileFunctionParameter( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    return [FunctionParameter(toks[0], toks[1])]

def compileFunctionStep( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    return [FunctionStep(toks[0], toks[1])]

def compileGeneralFilter( sourceStr, loc, toks ):
    filterLabel = "filter{}".format(lbGen.labelNbr("filter"))
    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": "variable-filter",
               "xlink:to": filterLabel,
               "complement": "false",
               "cover": "true"}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] =  "{}".format(loc)

    filterAttrib = {"xlink:type": "resource",
                    "xlink:label": filterLabel}
    prevTok = filterEltQname = None
    for tok in toks:
        if tok == "complemented":
            arcAttrib["complement"] = "true"
        elif prevTok == "general" and isinstance(tok, XPathExpression):
            filterAttrib["test"] = str(tok)
        prevTok = tok
    filterElt = lbGen.subElement(lbGen.genLinkElement, "gf:general", attrib=filterAttrib)
    return [FormulaArc("variable:variableFilterArc", attrib=arcAttrib),
            FormulaResourceElt(filterElt)]

def compileGeneralVariable( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    varLabel = "variable{}".format(lbGen.labelNbr("variable"))
    attrib = {"xlink:type": "resource",
              "xlink:label": varLabel,
              "bindAsSequence": "false"}
    prevTok = name = None
    for tok in toks:
        if prevTok is None:
            name = tok[1:] # remove $ from variable name
        elif tok == "bind-as-sequence":
            attrib["bindAsSequence"] = "true"
        elif prevTok == "select":
            attrib["select"] = str(tok)
        prevTok = tok
    gvElt = lbGen.element(
             "variable:generalVariable",
             attrib=attrib)
    gvFormulaResource = FormulaResourceElt(gvElt)
    for tok in toks:
        if isinstance(tok, FormulaResourceElt):
            tok.elt.addprevious(gvElt)
            gvElt = None
            break
    if gvElt is not None: # no filter to preceede
        lbGen.genLinkElement.append(gvElt)
    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": "variable-set",
               "xlink:to": varLabel,
               "name": lbGen.checkedQName(name)}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] =  "{}".format(loc)

    return [FormulaArc("variable:variableArc", attrib=arcAttrib), gvFormulaResource]

def compileLabel( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    prevTok = langTok = None
    for tok in toks:
        if tok.startswith("(") and tok.endswith(")"):
            langTok = tok[1:-1]
        else:
            if prevTok == "label":
                labelType = "label"
                arcrole = "element-label"
                role = "label"
                labelElt = "generic:label"
                label = tok
            elif prevTok == "satisfied-message":
                labelType = "message"
                arcrole = "assertion-satisfied-message"
                role = "message"
                labelElt = "msg:message"
                label = tok
                lbGen.checkXmlns("msg")
            elif prevTok == "unsatisfied-message":
                labelType = "message"
                arcrole = "assertion-unsatisfied-message"
                role = "message"
                labelElt = "msg:message"
                label = tok
                lbGen.checkXmlns("msg")
            # Don't set prevTok if it was a language
            prevTok = tok
    labelLabel = "{}{}".format(labelType, lbGen.labelNbr(labelType))
    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": arcrole,
               "xlink:to": labelLabel}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] =  "{}".format(loc)

    labelAttrib = {"xlink:type": "resource",
                   "xlink:role": role,
                   "xlink:label": labelLabel,
                   "xml:lang": langTok or "en"}
    labelElt = lbGen.subElement(lbGen.genLinkElement, labelElt, attrib=labelAttrib, text=label)
    return [FormulaArc("generic:arc", attrib=arcAttrib),
            FormulaResourceElt(labelElt)]

def compileMatchFilter( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    filterLabel = "filter{}".format(lbGen.labelNbr("filter"))
    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": "variable-filter",
               "xlink:to": filterLabel,
               "complement": "false",
               "cover": "true"}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] =  "{}".format(loc)

    filterAttrib = {"xlink:type": "resource",
                    "xlink:label": filterLabel}
    prevTok = filterEltQname = None
    isMatchDimension = False
    for tok in toks:
        if tok == "complemented":
            arcAttrib["complement"] = "true"
        elif tok == "covering":
            arcAttrib["cover"] = "true"
        elif tok == "non-covering":
            arcAttrib["cover"] = "false"
        elif filterEltQname is None:
            if tok == "match-concept":
                filterEltQname = "mf:matchConcept"
            elif tok == "match-location":
                filterEltQname = "mf:matchLocation"
            elif tok == "match-entity-identifier":
                filterEltQname = "mf:matchEntityIdentifier"
            elif tok == "match-period":
                filterEltQname = "mf:matchPeriod"
            elif tok == "match-unit":
                filterEltQname = "mf:matchUnit"
            elif tok == "match-dimension":
                filterEltQname = "mf:matchDimension"
                isMatchDimension = True
        elif filterEltQname is not None and "variable" not in filterAttrib:
            filterAttrib["variable"] = tok[1:] # remove $ from variable name
        elif isMatchDimension and prevTok == "dimension":
            filterAttrib["dimension"] = lbGen.checkedQName(tok) # must be a qname in nsmap (not a local name)
        elif tok == "match-any":
            filterAttrib["matchAny"] = "true"
        prevTok = tok
    filterElt = lbGen.subElement(lbGen.genLinkElement, filterEltQname, attrib=filterAttrib)
    return [FormulaArc("variable:variableFilterArc", attrib=arcAttrib),
            FormulaResourceElt(filterElt)]

def compileNamespaceDeclaration( sourceStr, loc, toks ):
    lbGen.checkXmlns(dequotedString(toks[0]), dequotedString(toks[1]))
    return []

def compilePackageDeclaration( sourceStr, loc, toks ):
    return []

def compileParameterDeclaration( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    name = toks[0]
    generalVarLabel = cleanedName(name)
    lbGen.params[name] = generalVarLabel
    attrib = {"xlink:type": "resource",
              "xlink:label": generalVarLabel,
              "name": lbGen.checkedQName(name)}
    prevTok = None
    for tok in toks:
        if tok == "required":
            attrib["required"] = "true"
        elif prevTok == "select":
            attrib["select"] = str(tok)
        elif prevTok == "as":
            attrib["as"] = tok
        prevTok = tok
    paramElt = lbGen.subElement(lbGen.genLinkElement,
             "variable:parameter",
             attrib=attrib)
    return []

def compileParameterReference( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    arcAttrib={
            "xlink:type": "arc",
            "xlink:arcrole": "variable-set",
            "xlink:to": lbGen.params[toks[1]],
            "name": lbGen.checkedQName(toks[0])}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] =  "{}".format(loc)

    return [FormulaArc("variable:variableFilterArc", attrib=arcAttrib)]

dateTimePattern = re.compile("([0-9]{4})-([0-9]{2})-([0-9]{2})[T ]([0-9]{2}):([0-9]{2}):([0-9]{2})")
dateOnlyPattern = re.compile("([0-9]{4})-([0-9]{2})-([0-9]{2})")

def compilePeriodFilter( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    filterLabel = "filter{}".format(lbGen.labelNbr("filter"))
    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": "variable-filter",
               "xlink:to": filterLabel,
               "complement": "false",
               "cover": "true"}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] =  "{}".format(loc)

    filterAttrib = {"xlink:type": "resource",
                    "xlink:label": filterLabel}
    prevTok = filterEltQname = None
    isPeriod = isPeriodDateTime = isInstantDuration = False
    for tok in toks:
        if tok == "complemented":
            arcAttrib["complement"] = "true"
        elif tok == "covering":
            arcAttrib["cover"] = "true"
        elif tok == "non-covering":
            arcAttrib["cover"] = "false"
        elif filterEltQname is None:
            if tok == "period":
                isPeriod = True
                filterEltQname = "pf:period"
            elif tok == "period-start":
                isPeriodDateTime = True
                filterEltQname = "pf:periodStart"
            elif tok == "period-end":
                isPeriodDateTime = True
                filterEltQname = "pf:periodEnd"
            elif tok == "period-instant":
                isPeriodDateTime = True
                filterEltQname = "pf:periodInstant"
            elif tok == "instant-duration":
                isInstantDuration = True
                filterEltQname = "pf:instantDuration"
        elif prevTok == "period" and isinstance(tok, XPathExpression):
            filterAttrib["test"] = str(tok)
        elif isPeriodDateTime:
            if prevTok == "date" and isinstance(tok, XPathExpression):
                filterAttrib["date"] = str(tok)
            elif prevTok == "time" and isinstance(tok, XPathExpression):
                filterAttrib["time"] = str(tok)
            # elif dateTimePattern.match(tok):
            # elif dateOnlyPattern.match(tok):
        elif isInstantDuration and tok in ("start", "end"):
            filterAttrib["boundary"] = tok
        elif isInstantDuration and prevTok in ("start", "end"):
            filterAttrib["variable"] = tok[1:] # remove $ from variable name
        prevTok = tok
    filterElt = lbGen.subElement(lbGen.genLinkElement, filterEltQname, attrib=filterAttrib)
    return [FormulaArc("variable:variableFilterArc", attrib=arcAttrib),
            FormulaResourceElt(filterElt)]

def compilePrecondition( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    precondLabel = "precondition{}".format(lbGen.labelNbr("precondition"))
    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": "variable-set-precondition",
               "xlink:to": precondLabel}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] =  "{}".format(loc)

    precondAttrib = {"xlink:type": "resource",
                    "xlink:label": precondLabel}
    for tok in toks:
        if isinstance(tok, XPathExpression):
            precondAttrib["test"] = str(tok)
    precondElt = lbGen.subElement(lbGen.genLinkElement, "variable:precondition", attrib=precondAttrib)
    return [FormulaArc("generic:arc", attrib=arcAttrib),
            FormulaResourceElt(precondElt)]

def compilePreconditionDeclaration( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    return []

def compileRelativeFilter( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    filterLabel = "filter{}".format(lbGen.labelNbr("filter"))
    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": "variable-filter",
               "xlink:to": filterLabel,
               "complement": "false",
               "cover": "true"}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] =  "{}".format(loc)

    filterAttrib = {"xlink:type": "resource",
                    "xlink:label": filterLabel}
    prevTok = None
    for tok in toks:
        if tok == "complemented":
            arcAttrib["complement"] = "true"
        elif tok == "covering":
            arcAttrib["cover"] = "true"
        elif tok == "non-covering":
            arcAttrib["cover"] = "false"
        elif prevTok == "relative":
            filterAttrib["variable"] = tok[1:] # remove $ from variable name
        prevTok = tok
    filterElt = lbGen.subElement(lbGen.genLinkElement, "rf:relativeFilter", attrib=filterAttrib)
    return [FormulaArc("variable:variableFilterArc", attrib=arcAttrib),
            FormulaResourceElt(filterElt)]

def compileSeverity( sourceStr, loc, toks ):
    return []

def compileTupleFilter( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    filterLabel = "filter{}".format(lbGen.labelNbr("filter"))
    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": "variable-filter",
               "xlink:to": filterLabel,
               "complement": "false",
               "cover": "true"}
    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] =  "{}".format(loc)
    filterAttrib = {"xlink:type": "resource",
                    "xlink:label": filterLabel}
    prevTok = None
    for tok in toks:
        if tok == "complemented":
            arcAttrib["complement"] = "true"
        elif tok == "covering":
            arcAttrib["cover"] = "true"
        elif tok == "non-covering":
            arcAttrib["cover"] = "false"
        elif prevTok == "parent":
            filterEltQname = "tf:parentFilter"
            tupleRelationTok = tok
        elif prevTok == "ancestor":
            filterEltQname = "tf:ancestorFilter"
            tupleRelationTok = tok
        elif prevTok == "sibling":
            filterEltQname = "tf:siblingFilter"
            filterAttrib["variable"] = tok[1:] # remove $ from variable name
        prevTok = tok
    filterElt = lbGen.subElement(lbGen.genLinkElement, filterEltQname, attrib=filterAttrib)
    if filterEltQname in ("tf:parentFilter", "tf:ancestorFilter"):
        relationElt = lbGen.subElement(filterElt, filterEltQname[:-6])
        if isinstance(tupleRelationTok, XPathExpression):
            lbGen.subElement(relationElt, "tf:qnameExpression", text=str(tupleRelationTok))
        else:
            lbGen.subElement(relationElt, "tf:qname", text=lbGen.checkedQName(tupleRelationTok))
    return [FormulaArc("variable:variableFilterArc", attrib=arcAttrib),
            FormulaResourceElt(filterElt)]

def compileUnitFilter( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    filterLabel = "filter{}".format(lbGen.labelNbr("filter"))
    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": "variable-filter",
               "xlink:to": filterLabel,
               "complement": "false",
               "cover": "true"}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] =  "{}".format(loc)

    filterAttrib = {"xlink:type": "resource",
                    "xlink:label": filterLabel}
    prevTok = None
    for tok in toks:
        if tok == "complemented":
            arcAttrib["complement"] = "true"
        elif tok == "covering":
            arcAttrib["cover"] = "true"
        elif tok == "non-covering":
            arcAttrib["cover"] = "false"
        elif prevTok == "unit-general-measures" and isinstance(tok, XPathExpression):
            filterEltQname = "uf:generalMeasures"
            singleMeasureTok = tok
            filterAttrib["test"] = str(tok)
        elif prevTok == "unit-single-measure" and isinstance(tok, XPathExpression):
            filterEltQname = "uf:singleMeasure"
            singleMeasureTok = tok
        elif prevTok == "unit-single-measure" and isinstance(tok, string):
            filterEltQname = "uf:singleMeasure"
            singleMeasureTok = tok
        prevTok = tok
    filterElt = lbGen.subElement(lbGen.genLinkElement, filterEltQname, attrib=filterAttrib)
    if filterEltQname == "uf:singleMeasure":
        measureElt = lbGen.subElement(filterElt, "uf:measure")
        if isinstance(singleMeasureTok, XPathExpression):
            lbGen.subElement(measureElt, "uf:qnameExpression", text=str(singleMeasureTok))
        else:
            lbGen.subElement(measureElt, "uf:qname", text=lbGen.checkedQName(singleMeasureTok))
    return [FormulaArc("variable:variableFilterArc", attrib=arcAttrib),
            FormulaResourceElt(filterElt)]


def compileValueFilter( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    filterLabel = "filter{}".format(lbGen.labelNbr("filter"))
    arcAttrib={"xlink:type": "arc",
               "xlink:arcrole": "variable-filter",
               "xlink:to": filterLabel,
               "complement": "false",
               "cover": "true"}

    if not omitSourceLineAttributes:
        arcAttrib["xfs:sourceline"] =  "{}".format(loc)

    filterAttrib = {"xlink:type": "resource",
                    "xlink:label": filterLabel}
    prevTok = None
    for tok in toks:
        if tok == "complemented":
            arcAttrib["complement"] = "true"
        elif tok == "covering":
            arcAttrib["cover"] = "true"
        elif tok == "non-covering":
            arcAttrib["cover"] = "false"
        elif prevTok == "nilled":
            filterEltQname = "vf:nil"
        prevTok = tok
    filterElt = lbGen.subElement(lbGen.genLinkElement, filterEltQname, attrib=filterAttrib)
    return [FormulaArc("variable:variableFilterArc", attrib=arcAttrib),
            FormulaResourceElt(filterElt)]

def compileVariableAssignment( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    return []

def compileVariableReference( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    return []

def compileXPathExpression( sourceStr, loc, toks ):
    global lastLoc; lastLoc = loc
    return XPathExpression(toks)

def compileXfsGrammar( cntlr, debugParsing ):
    global isGrammarCompiled, xfsProg, lineno, line, col

    if isGrammarCompiled:
        return xfsProg

    cntlr.showStatus(_("Compiling Formula Grammar"))
    from pyparsing import (Word, Keyword, alphas,
                 Literal, CaselessLiteral,
                 Combine, Optional, nums, Or, Forward, Group, ZeroOrMore, OneOrMore, StringEnd, alphanums,
                 ParserElement, quotedString, dblQuotedString, sglQuotedString, QuotedString,
                 delimitedList, Suppress, Regex, FollowedBy,
                 lineno, line, col)

    ParserElement.enablePackrat()

    """
    the pyparsing parser constructs are defined in this method to prevent the need to compile
    the grammar when the plug in is loaded (which is likely to be when setting up GUI
    menus or command line parser).

    instead the grammar is compiled the first time that any formula grammar needs to be parsed
    """

    # define grammar
    xfsComment = Regex(r"[(](?:[:](?:[^:]*[:]+)+?[)])").setParseAction(compileComment)

    nonNegativeInteger = Regex("[0-9]+")

    messageSeverity = (Literal("ERROR") | Literal("WARNING") | Literal("INFO"))

    qName = Regex("([A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD_]"
                  "[A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040\xB7_.-]*:)?"
                  # localname or wildcard-localname part
                  "([A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD_]"
                  "[A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040\xB7_.-]*|[*])"
                  )

    variableRef = Combine( Literal("$") + qName )

    ncName = Regex("([A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD_]"
                  "[A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040\xB7_.-]*)"
                  ).setName("ncName").setDebug(debugParsing)

    dateTime = Regex("([0-9]{4})-([0-9]{2})-([0-9]{2})[T ]([0-9]{2}):([0-9]{2}):([0-9]{2})|"
                     "([0-9]{4})-([0-9]{2})-([0-9]{2})")


    decimalPoint = Literal('.')
    exponentLiteral = CaselessLiteral('e')
    plusorminusLiteral = Literal('+') | Literal('-')
    digits = Word(nums)
    integerLiteral = Combine( Optional(plusorminusLiteral) + digits )
    decimalFractionLiteral = Combine( Optional(plusorminusLiteral) + decimalPoint + digits )
    infLiteral = Combine( Optional(plusorminusLiteral) + Keyword("INF") )
    nanLiteral = Keyword("NaN")
    floatLiteral = ( Combine( integerLiteral +
                         ( ( decimalPoint + Optional(digits) + exponentLiteral + integerLiteral ) |
                           ( exponentLiteral + integerLiteral ) )
                         ) |
                     Combine( decimalFractionLiteral + exponentLiteral + integerLiteral ) |
                     infLiteral | nanLiteral )
    decimalLiteral =  ( Combine( integerLiteral + decimalPoint + Optional(digits) ) |
                        decimalFractionLiteral )
    numberLiteral = (decimalLiteral | floatLiteral | integerLiteral)

    xPathFunctionCall = Combine(qName + Literal("("))

    xPathOp = (Literal("(") | Literal( ")" ) | Literal( "[" ) | Literal( "]" ) |
               Literal( "^" ) | Literal(",") | Literal("<<") | Literal(">>") | Literal("!=") |
               Literal("<=") | Literal("<") | Literal(">=") | Literal(">") | Literal("=") |
               Literal("+") | Literal("-") | Literal("*") | Literal("|") | Literal("?") |
               Literal("@") | Literal("//") | Literal("/") | Literal("::") | Literal("."))

    xpathExpression = (Suppress(Literal("{")) +
                       ZeroOrMore( (dblQuotedString | sglQuotedString | numberLiteral |
                                    xPathFunctionCall | variableRef | qName | xPathOp ) ) +
                       Suppress(Literal("}"))).setParseAction(compileXPathExpression)
    separator = Suppress( Literal(";") )

    namespaceDeclaration = (Suppress(Keyword("namespace")) + ncName + Suppress(Literal("=")) + quotedString + separator
                            ).setParseAction(compileNamespaceDeclaration).ignore(xfsComment)
    defaultDeclaration = (Suppress(Keyword("unsatisfied-severity") | Keyword("default-language")) + ncName + separator
                         ).setParseAction(compileDefaults).ignore(xfsComment)

    parameterDeclaration = (Suppress(Keyword("parameter")) + qName  +
                            Suppress(Literal("{")) +
                            Optional(Keyword("required")) +
                            Optional(Keyword("select") + xpathExpression) +
                            Optional(Keyword("as") + qName) +
                            Suppress(Literal("}")) + separator
                           ).setParseAction(compileParameterDeclaration).ignore(xfsComment)

    occurenceIndicator = Literal("?") | Literal("*") | Literal("+")

    functionParameter = (qName + Suppress(Keyword("as")) + Combine(qName + Optional(occurenceIndicator))
                         ).setParseAction(compileFunctionParameter).ignore(xfsComment)

    functionStep = (Suppress(Keyword("step")) + variableRef + xpathExpression +
                    separator).setParseAction(compileFunctionStep).ignore(xfsComment)

    functionImplementation = (Suppress(Literal("{")) +
                              ZeroOrMore(functionStep) +
                              Keyword("return") + xpathExpression + separator +
                              Suppress(Literal("}"))).ignore(xfsComment)

    functionDeclaration = (Suppress(Keyword("function")) + qName  +
                           Suppress(Literal("(")) + Optional(delimitedList(functionParameter)) + Suppress(Literal(")")) +
                              Keyword("as") + Combine(qName + Optional(occurenceIndicator)) +
                           Optional(functionImplementation) + separator
                           ).setParseAction(compileFunctionDeclaration).ignore(xfsComment)

    packageDeclaration = (Suppress(Keyword("package")) + ncName + separator ).setParseAction(compilePackageDeclaration).ignore(xfsComment)

    severity = ( Suppress(Keyword("unsatisfied-severity")) + ( ncName ) + separator ).setParseAction(compileSeverity).ignore(xfsComment)

    label = ( (Keyword("label") | Keyword("unsatisfied-message") | Keyword("satisfied-message")) +
              Optional( Combine(Literal("(") + Regex("[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*") + Literal(")")) ) +
              (QuotedString('"',multiline=True,escQuote='""') | QuotedString("'",multiline=True,escQuote="''")) +
              separator).setParseAction(compileLabel).ignore(xfsComment)

    aspectRuleConcept = ( Suppress(Keyword("concept")) + (qName | xpathExpression) + separator
                        ).setParseAction(compileAspectRuleConcept).ignore(xfsComment)

    aspectRuleEntityIdentifier = (Suppress(Keyword("entity-identifier")) +
                                  Optional( Keyword("scheme") + xpathExpression) +
                                  Optional( Keyword("identifier") + xpathExpression) + separator
                        ).setParseAction(compileAspectRuleEntityIdentifier).ignore(xfsComment)

    aspectRulePeriod = (Suppress(Keyword("period")) +
                        ( Keyword("forever") |
                          Keyword("instant") +  xpathExpression |
                          Keyword("duration") +
                                  Optional( Keyword("start") + xpathExpression) +
                                  Optional( Keyword("end") + xpathExpression) ) + separator
                        ).setParseAction(compileAspectRulePeriod).ignore(xfsComment)

    aspectRuleUnitTerm = ((Keyword("multiply-by") | Keyword("divide-by")) +
                          Optional( Keyword("source") + qName ) +
                          Optional( Keyword("measure") + xpathExpression ) + separator
                        ).setParseAction(compileAspectRuleUnitTerm).ignore(xfsComment)

    aspectRuleUnit = (Suppress(Keyword("unit")) + Optional(Keyword("augment")) + Suppress(Literal("{")) +
                      ZeroOrMore( aspectRuleUnitTerm ) + Suppress(Literal("}")) + separator
                        ).setParseAction(compileAspectRuleUnit).ignore(xfsComment)

    aspectRuleExplicitDimensionTerm = (
                         (Keyword("member") + (qName | xpathExpression) |
                          Keyword("omit")) + separator
                        ).setParseAction(compileAspectRuleExplicitDimensionTerm).ignore(xfsComment)

    aspectRuleExplicitDimension = (Suppress(Keyword("explicit-dimension")) + qName + Suppress(Literal("{")) +
                      ZeroOrMore( aspectRuleExplicitDimensionTerm ) + Suppress(Literal("}")) + separator
                        ).setParseAction(compileAspectRuleExplicitDimension).ignore(xfsComment)

    aspectRuleTypedDimensionTerm = (
                         (Keyword("xpath") + xpathExpression |
                          Keyword("value") + dblQuotedString |
                          Keyword("omit")) + separator
                        ).setParseAction(compileAspectRuleTypedDimensionTerm).ignore(xfsComment)

    aspectRuleTypedDimension = (Suppress(Keyword("tyoed-dimension")) + qName + Suppress(Literal("{")) +
                      ZeroOrMore( aspectRuleTypedDimensionTerm ) + Suppress(Literal("}")) + separator
                        ).setParseAction(compileAspectRuleTypedDimension).ignore(xfsComment)

    aspectRules = ( Suppress(Keyword("aspect-rules")) +
                    Optional( Keyword("source") + qName ) +
                    Suppress(Literal("{")) +
                    ZeroOrMore( aspectRuleConcept |
                                aspectRuleEntityIdentifier |
                                aspectRulePeriod |
                                aspectRuleUnit |
                                aspectRuleExplicitDimension |
                                aspectRuleTypedDimension ) +
                   Suppress(Literal("}")) + separator
        ).setParseAction(compileAspectRules).ignore(xfsComment).setName("aspect-rules").setDebug(debugParsing)

    filter = Forward()

    conceptFilter = (
        ZeroOrMore( Keyword("complemented") | Keyword("covering") | Keyword("non-covering") ) +
        (Keyword("concept-name") + OneOrMore(qName | xpathExpression) + separator) |
         Keyword("concept-period-type") + (Keyword("instant") | Keyword("duration")) + separator |
         Keyword("concept-balance") + (Keyword("credit") | Keyword("debit") | Keyword("none")) + separator |
         Keyword("concept-data-type") + (Keyword("strict") | Keyword("non-strict")) + (qName | xpathExpression) + separator |
         Keyword("concept-substitution-group") + (Keyword("strict") | Keyword("non-strict")) + (qName | xpathExpression) + separator
        ).setParseAction(compileConceptFilter).ignore(xfsComment).setName("concept-filter").setDebug(debugParsing)


    generalFilter = (
        Optional( Keyword("complemented") ) +
        Keyword("general") + xpathExpression + separator
        ).setParseAction(compileGeneralFilter).ignore(xfsComment).setName("general-filter").setDebug(debugParsing)


    periodFilter = (
        ZeroOrMore( Keyword("complemented") | Keyword("covering") | Keyword("non-covering") ) +
        (Keyword("period") + xpathExpression |
         (Keyword("period-start") | Keyword("period-end") | Keyword("period-instant")) +
           (dateTime | Keyword("date") + xpathExpression + Optional(Keyword("time") + xpathExpression)) |
         Keyword("instant-duration") + (Keyword("start") | Keyword("end")) + variableRef
         ) + separator
        ).setParseAction(compilePeriodFilter).ignore(xfsComment).setName("period-filter").setDebug(debugParsing)

    dimensionAxis = (Keyword("child-or-self") | Keyword("child") | Keyword("descendant") | Keyword("descendant-or-self"))

    dimensionFilter = (
        ZeroOrMore( Keyword("complemented") | Keyword("covering") | Keyword("non-covering") ) +
            (
                (Keyword("explicit-dimension") + (qName | xpathExpression) +
                    ZeroOrMore( Keyword("default-member") |
                       (Keyword("member") + (variableRef | qName | xpathExpression) +
                        Optional(Keyword("linkrole") + quotedString) +
                        Optional(Keyword("arcrole") + quotedString) +
                        Optional(Keyword("axis") + dimensionAxis))) + separator) |
                (Keyword("typed-dimension") + (variableRef | qName | xpathExpression) +
                    Optional( Keyword("test") + xpathExpression )  + separator)
            )
        ).setParseAction(compileDimensionFilter).ignore(xfsComment).setName("dimension-filter").setDebug(debugParsing)

    unitFilter = (
        ZeroOrMore( Keyword("complemented") | Keyword("covering") | Keyword("non-covering") ) +
        (Keyword("unit-single-measure") + (qName | xpathExpression) |
         Keyword("unit-general-measures") + xpathExpression) + separator
        ).setParseAction(compileUnitFilter).ignore(xfsComment).setName("unit-filter").setDebug(debugParsing)


    entityFilter = (
        ZeroOrMore( Keyword("complemented") | Keyword("covering") | Keyword("non-covering") ) +
        (Keyword("entity") + Keyword("scheme") + xpathExpression + Keyword("value") + xpathExpression |
         Keyword("entity-scheme") + xpathExpression |
         Keyword("entity-scheme-pattern") + quotedString |
         Keyword("entity-identifier-pattern") + quotedString) + separator
        ).setParseAction(compileEntityFilter).ignore(xfsComment).setName("entity-filter").setDebug(debugParsing)

    matchFilter = (
        ZeroOrMore( Keyword("complemented") | Keyword("covering") | Keyword("non-covering") ) +
        (Keyword("match-concept") + variableRef |
         Keyword("match-location") + variableRef |
         Keyword("match-entity-identifier") + variableRef |
         Keyword("match-period") + variableRef |
         Keyword("match-unit") + variableRef |
         Keyword("match-dimension") + variableRef + Keyword("dimension") + (qName | xpathExpression)
        ) + Optional( Keyword("match-any") ) + separator
        ).setParseAction(compileMatchFilter).ignore(xfsComment).setName("match-filter").setDebug(debugParsing)

    relativeFilter = (
        Optional( Keyword("complemented") ) +
        Keyword("relative") + variableRef + separator
        ).setParseAction(compileRelativeFilter).ignore(xfsComment).setName("relative-filter").setDebug(debugParsing)


    tupleFilter = (
        ZeroOrMore( Keyword("complemented") | Keyword("covering") | Keyword("non-covering") ) +
        (Keyword("parent") + (qName | xpathExpression) |
         Keyword("ancestor") + (qName | xpathExpression) |
         Keyword("sibling") + variableRef) + separator
        ).setParseAction(compileTupleFilter).ignore(xfsComment).setName("tuple-filter").setDebug(debugParsing)


    valueFilter = (
        Optional( Keyword("complemented") ) +
        Keyword("nilled")
        ).setParseAction(compileValueFilter).ignore(xfsComment).setName("value-filter").setDebug(debugParsing)

    aspectCoverFilter = (
        Optional( Keyword("complemented") ) +
        Keyword("aspect-cover") +
        OneOrMore( Keyword("all") | Keyword("concept") | Keyword("entity-identifier") | Keyword("location") |
                   Keyword("period") | Keyword("unit") | Keyword("dimensions") |
                   Keyword("dimension") + (qName | xpathExpression) |
                   Keyword("exclude-dimension")+ (qName | xpathExpression) ) +
        separator
        ).setParseAction(compileAspectCoverFilter).ignore(xfsComment).setName("aspect-cover-filter").setDebug(debugParsing)


    relationAxis = (Keyword("child-or-self") | Keyword("child") | Keyword("descendant-or-self") | Keyword("descendant") |
                    Keyword("parent-or-self") | Keyword("parent") | Keyword("ancestor-or-self") | Keyword("ancestor") |
                    Keyword("sibling-or-self") | Keyword("sibling-or-descendant") | Keyword("sibling") )

    conceptRelationFilter = (
        Optional( Keyword("complemented") ) +
        Keyword("concept-relation") + (
            (variableRef | qName | xpathExpression) +
            Optional(Keyword("linkrole") + (quotedString | xpathExpression)) +
            Optional(Keyword("arcrole") + (quotedString | xpathExpression)) +
            Optional(Keyword("axis") + relationAxis) +
            Optional(Keyword("generations") + nonNegativeInteger) +
            Optional(Keyword("test") + xpathExpression)
        ) + separator
        ).setParseAction(compileConceptRelationFilter).ignore(xfsComment).setName("concept-relation-filter").setDebug(debugParsing)

    booleanFilter = (
        Optional( Keyword("complemented") ) +
        (Keyword("and") | Keyword("or")) + Suppress(Literal("{")) +
         OneOrMore(filter) +
        Suppress(Literal("}")) +
        separator
        ).setParseAction(compileBooleanFilter).ignore(xfsComment).setName("boolean-filter").setDebug(debugParsing)

    declaredFilterReference = ( Keyword("filter") + variableRef ).setParseAction(compileFilterReference).ignore(xfsComment).setName("filter-reference").setDebug(debugParsing)

    filters = ( conceptFilter |
                generalFilter |
                periodFilter |
                dimensionFilter |
                unitFilter |
                entityFilter |
                matchFilter |
                relativeFilter |
                tupleFilter |
                valueFilter |
                booleanFilter |
                aspectCoverFilter |
                conceptRelationFilter |
                declaredFilterReference )

    filter << filters
    filter.setName("filter").setDebug(debugParsing)

    filterDeclaration = (Suppress(Keyword("filter")) + qName + Suppress(Literal("{")) +
                         OneOrMore(filter) +
                         Suppress(Literal("}"))).setParseAction(compileFilterDeclaration).ignore(xfsComment).setName("fact-variable").setDebug(debugParsing)

    factVariable = (Suppress(Keyword("variable")) + variableRef + Suppress(Literal("{")) +
                    ZeroOrMore( Keyword("bind-as-sequence") | Keyword("nils") | Keyword("matches") |
                                ( Keyword("fallback") + xpathExpression ) ) +
                    ZeroOrMore( filter ) +
                    Suppress(Literal("}")) + separator).setParseAction(compileFactVariable).ignore(xfsComment).setName("fact-variable").setDebug(debugParsing)


    generalVariable = (Suppress(Keyword("variable")) + variableRef + Suppress(Literal("{")) +
                       Optional( Keyword("bind-as-sequence") ) +
                       Keyword("select") + xpathExpression + separator +
                       Suppress(Literal("}")) + separator).setParseAction(compileGeneralVariable).ignore(xfsComment).setName("general-variable").setDebug(debugParsing)

    referencedParameter = (Suppress(Keyword("parameter")) + variableRef + Suppress(Keyword("references")) + qName
                        + separator).setParseAction(compileParameterReference).ignore(xfsComment).setName("renamed-parameter").setDebug(debugParsing)

    precondition = ( Suppress(Keyword("precondition")) + xpathExpression + separator
                   ).setParseAction(compilePrecondition).ignore(xfsComment).setName("precondition").setDebug(debugParsing)

    formula = ( Suppress(Keyword("formula")) + ncName + Suppress(Literal("{")) +
                  ZeroOrMore( label | severity |
                              Keyword("aspect-model-non-dimensional") +separator |
                              Keyword("no-implicit-filtering") + separator |
                              Keyword("decimals") + xpathExpression + separator |
                              Keyword("precision") + xpathExpression + separator |
                              Keyword("value") + xpathExpression + separator |
                              Keyword("source") + qName + separator ) +
                  ZeroOrMore( aspectRules ) +
                  ZeroOrMore( filter ) +
                  ZeroOrMore( generalVariable | factVariable | referencedParameter) +
                  ZeroOrMore( precondition ) +
                  Suppress(Literal("}") + separator)
               ).setParseAction(compileFormula).ignore(xfsComment).setName("formula").setDebug(debugParsing)

    assertion = ( Suppress(Keyword("assertion")) + ncName + Suppress(Literal("{")) +
                  ZeroOrMore( label | severity |
                              Keyword("aspect-model-non-dimensional") +separator |
                              Keyword("no-implicit-filtering") + separator ) +
                  ZeroOrMore( filter ) +
                  ZeroOrMore( generalVariable | factVariable | referencedParameter) +
                  ZeroOrMore( precondition ) +
                  Optional( ( Keyword("test") | Keyword("evaluation-count") ) + xpathExpression + separator) +
                  Suppress(Literal("}") + separator)).setParseAction(compileAssertion).ignore(xfsComment).setName("assertion").setDebug(debugParsing)

    consistencyAssertion = ( Suppress(Keyword("consistency-assertion")) + ncName + Suppress(Literal("{")) +
                  ZeroOrMore( label | severity |
                              Keyword("strict") + separator |
                              (Keyword("absolute-acceptance-radius") | Keyword("proportional-acceptance-radius")) +
                                  xpathExpression + separator ) +
                  ZeroOrMore( formula ) +
                  Suppress(Literal("}") + separator)).setParseAction(compileConsistencyAssertion).ignore(xfsComment).setName("assertion").setDebug(debugParsing)

    assertionSet = ( Suppress(Keyword("assertion-set")) + ncName + Suppress(Literal("{")) +
                   ZeroOrMore( label ) +
                   (ZeroOrMore( consistencyAssertion | assertion ) ) +
                   Suppress(Literal("}") + separator)).setParseAction( compileAssertionSet ).ignore(xfsComment).setName("assertionSet").setDebug(debugParsing)

    xfsProg = ( ZeroOrMore( namespaceDeclaration | xfsComment ) +
                ZeroOrMore( defaultDeclaration | xfsComment ) +
                ZeroOrMore( parameterDeclaration | filterDeclaration | generalVariable | factVariable | functionDeclaration | xfsComment ) +
                ZeroOrMore( assertionSet | consistencyAssertion | assertion | formula | xfsComment )
              ) + StringEnd()
    xfsProg.ignore(xfsComment)

    startedAt = time.time()
    cntlr.showStatus(_("initializing Formula Grammar"))
    xfsProg.parseString( "(: force initialization :)\n", parseAll=True )
    initializing_time = "%.2f" % (time.time() - startedAt)
    logMessage("INFO", "info",
               _("Formula syntax grammar initialized in %(secs)s secs"),
               secs=initializing_time)
    cntlr.showStatus(_("initialized Formula Grammar in {0} seconds").format(initializing_time))

    isGrammarCompiled = True

    return xfsProg

def parse(cntlr, _logMessage, xfFiles, modelXbrl=None, debugParsing=False):
    from pyparsing import ParseException, ParseSyntaxException

    global xc, logMessage
    logMessage = _logMessage

    xfsGrammar = compileXfsGrammar(cntlr, debugParsing)

    successful = True


    def parseSourceString(sourceString):
        global lastLoc, currentPackage
        successful = True
        cntlr.showStatus("Compiling formula syntax file {0}".format(os.path.basename(xfsFile)))

        try:
            lastLoc = 0
            currentPackage = None
            xfsGrammar.parseString( sourceString, parseAll=True )
        except (ParseException, ParseSyntaxException) as err:
            file = os.path.basename(xfsFile)
            codeLines = []
            lineStart = sourceString.rfind("\n", 0, err.loc) + 1
            linesAfterErr = 0
            errAt = max(lastLoc, err.loc)
            atEnd = False
            while(1):
                if errAt < lineStart:
                    linesAfterErr += 1
                nextLine = sourceString.find("\n", lineStart)
                if nextLine < 0:
                    nextLine = len(sourceString)
                    atEnd = True
                if lineStart <= errAt < nextLine:
                    codeLines.append(sourceString[lineStart:errAt] + '\u274b' + sourceString[errAt:nextLine])
                else:
                    codeLines.append(sourceString[lineStart:nextLine])
                lineStart = nextLine + 1
                if linesAfterErr >= 2 or atEnd:
                    break
            # trim code to show
            if len(codeLines) > 5:
                del codeLines[2:len(codeLines)-3]
                codeLines.insert(2,"...")
            logMessage("ERROR", "formulaSyntax:syntaxError",
                _("Parse error after line %(lineno)s col %(col)s:\n%(lines)s"),
                xfsFile=xfsFile,
                sourceFileLines=((file, lineno(err.loc,err.pstr)),),
                lineno=lineno(lastLoc,sourceString),
                col=col(lastLoc,sourceString),
                lines="\n".join(codeLines))
            successful = False
        except (ValueError) as err:
            file = os.path.basename(xfsFile)
            logMessage("ERROR", "formulaSyntax:valueError",
                _("Parsing terminated due to error: \n%(error)s"),
                xfsFile=xfsFile,
                sourceFileLines=((file,lineno(lastLoc,sourceString)),),
                error=str(err))
            successful = False
        except Exception as err:
            file = os.path.basename(xfsFile)
            logMessage("ERROR", "formulaSyntax:parserException",
                _("Parsing of terminated due to error: \n%(error)s"),
                xfsFile=xfsFile,
                sourceFileLines=((file,lineno(lastLoc,sourceString)),),
                error=str(err), exc_info=True)
            print(traceback.format_tb(sys.exc_info()[2]))
            successful = False

        cntlr.showStatus("Compiled formula files {0}".format({True:"successful",
                                                              False:"with errors"}[successful]),
                         clearAfter=5000)
        return successful

    def parseFile(filename):
        successful = True
        # parse the xrb zip or individual xsr files
        global lbGen, xfsFile
        if os.path.isdir(filename):
            for root, dirs, files in os.walk(filename):
                for file in files:
                    xfsFile = os.path.join(root, file)
                    parseFile(xfsFile)
        elif filename.endswith(".zip"): # zip archive
            archive = zipfile.ZipFile(filename, mode="r")
            for zipinfo in archive.infolist():
                zipcontent = zipinfo.filename
                if zipcontent.endswith(".xfr"):
                    xfsFile = os.path.join(filename, zipcontent)
                    if not parseSourceString( archive.read(zipcontent).decode("utf-8") ):
                        successful = False
            archive.close()
        elif filename.endswith(".xf"):
            xfsFile = filename
            lbGen = FormulaLbGenerator(xfsFile, modelXbrl)
            lbGen.newLb() # start new output LB
            with open(filename, "r", encoding="utf-8") as fh:
                if not parseSourceString( fh.read() ):
                    successful = False
                else:
                    lbGen.saveLb()
        return successful

    successful = True
    for filename in xfFiles:
        if not parseFile(filename):
            successful = False

    logMessage = None # dereference

    if modelXbrl is not None:
        # plugin operation, return modelDocument
        return lbGen.modelDocument
    return None

formulaPrefixes = {
    "xlink": ('http://www.w3.org/1999/xlink',),
    "link": ('http://www.xbrl.org/2003/linkbase', 'http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd'),
    "xbrli": ('http://www.xbrl.org/2003/instance',),
    "generic": ('http://xbrl.org/2008/generic', 'http://www.xbrl.org/2008/generic-link.xsd'),
    "formula": ('http://xbrl.org/2008/formula', 'http://www.xbrl.org/2008/formula.xsd'),
    "validation": ('http://xbrl.org/2008/validation', 'http://www.xbrl.org/2008/validation.xsd'),
    "variable": ('http://xbrl.org/2008/variable', 'http://www.xbrl.org/2008/variable.xsd'),
    "label": ('http://xbrl.org/2008/label', 'http://www.xbrl.org/2008/generic-label.xsd'),
    "msg": ('http://xbrl.org/2010/message', 'http://www.xbrl.org/2010/generic-message.xsd'),
    "ca": ('http://xbrl.org/2008/assertion/consistency', 'http://www.xbrl.org/2008/consistency-assertion.xsd'),
    "ea": ('http://xbrl.org/2008/assertion/existence', 'http://www.xbrl.org/2008/existence-assertion.xsd'),
    "va": ('http://xbrl.org/2008/assertion/value', 'http://www.xbrl.org/2008/value-assertion.xsd'),
    "bf": ('http://xbrl.org/2008/filter/boolean', 'http://www.xbrl.org/2008/boolean-filter.xsd'),
    "cf": ('http://xbrl.org/2008/filter/concept', 'http://www.xbrl.org/2008/concept-filter.xsd'),
    "df": ('http://xbrl.org/2008/filter/dimension', 'http://www.xbrl.org/2008/dimension-filter.xsd'),
    "ef": ('http://xbrl.org/2008/filter/entity', 'http://www.xbrl.org/2008/entity-filter.xsd'),
    "gf": ('http://xbrl.org/2008/filter/general', 'http://www.xbrl.org/2008/general-filter.xsd'),
    "mf": ('http://xbrl.org/2008/filter/match', 'http://www.xbrl.org/2008/match-filter.xsd'),
    "pf": ('http://xbrl.org/2008/filter/period', 'http://www.xbrl.org/2008/period-filter.xsd'),
    "rf": ('http://xbrl.org/2008/filter/relative', 'http://www.xbrl.org/2008/relative-filter.xsd'),
    "tf": ('http://xbrl.org/2008/filter/tuple', 'http://www.xbrl.org/2008/tuple-filter.xsd'),
    "uf": ('http://xbrl.org/2008/filter/unit', 'http://www.xbrl.org/2008/unit-filter.xsd'),
    "vf": ('http://xbrl.org/2008/filter/value', 'http://www.xbrl.org/2008/value-filter.xsd'),
    "acf": ('http://xbrl.org/2010/filter/aspect-cover', 'http://www.xbrl.org/2010/aspect-cover-filter.xsd'),
    "crf": ('http://xbrl.org/2010/filter/concept-relation', 'http://www.xbrl.org/2010/concept-relation-filter.xsd'),
    "cfi": ('http://xbrl.org/2010/custom-function', 'http://www.xbrl.org/2010/custom-function-implementation.xsd'),
    "xfi": ('http://www.xbrl.org/2008/function/instance',),
    "xsi": ('http://www.w3.org/2001/XMLSchema-instance',),
    "xs": ('http://www.w3.org/2001/XMLSchema',),
    "xfs": ('http://arelle.org/2016/xfs',)
    }

formulaArcroleRefs = {
    "assertion-set": ("http://xbrl.org/arcrole/2008/assertion-set", "http://www.xbrl.org/2008/validation.xsd#assertion-set"),
    "element-label": ('http://xbrl.org/arcrole/2008/element-label','http://www.xbrl.org/2008/generic-label.xsd#element-label'),
    "variable-filter": ('http://xbrl.org/arcrole/2008/variable-filter', 'http://www.xbrl.org/2008/variable.xsd#variable-filter'),
    "variable-set": ('http://xbrl.org/arcrole/2008/variable-set', 'http://www.xbrl.org/2008/variable.xsd#variable-set'),
    "variable-set-precondition": ('http://xbrl.org/arcrole/2008/variable-set-precondition', 'http://www.xbrl.org/2008/variable.xsd#variable-set-precondition'),
    "consistency-assertion-formula": ('http://xbrl.org/arcrole/2008/consistency-assertion-formula', 'http://www.xbrl.org/2008/consistency-assertion.xsd#consistency-assertion-formula'),
    "assertion-unsatisfied-message": ("http://xbrl.org/arcrole/2010/assertion-unsatisfied-message", "http://www.xbrl.org/2010/validation-message.xsd#assertion-unsatisfied-message"),
    "assertion-satisfied-message": ("http://xbrl.org/arcrole/2010/assertion-satisfied-message", "http://www.xbrl.org/2010/validation-message.xsd#assertion-satisfied-message"),
    "boolean-filter": ('http://xbrl.org/arcrole/2008/boolean-filter', 'http://www.xbrl.org/2008/boolean-filter.xsd#boolean-filter'),
    "function-implementation": ('http://xbrl.org/arcrole/2010/function-implementation','http://www.xbrl.org/2010/custom-function-implementation.xsd#cfi-implementation')
    }

formulaRoleRefs = {
    "label": ('http://xbrl.org/role/2008/label','http://www.xbrl.org/2008/generic-label.xsd#standard-label'),
    "message": ("http://www.xbrl.org/2010/role/message", "http://www.xbrl.org/2010/generic-message.xsd#standard-message")
    }

fnNamespaceFunctions = {
    'node-name', 'nilled', 'string', 'data', 'base-uri', 'document-uri', 'error', 'trace', 'dateTime',
    'abs', 'ceiling', 'floor', 'round', 'round-half-to-even',
    'codepoints-to-string', 'string-to-codepoints', 'compare', 'codepoint-equal', 'concat', 'string-join',
    'substring', 'string-length', 'normalize-space', 'normalize-unicode', 'upper-case', 'lower-case', 'translate',
    'encode-for-uri', 'iri-to-uri', 'escape-html-uri',
    'contains', 'starts-with', 'ends-with', 'substring-before', 'substring-after', 'matches', 'replace', 'tokenize',
    'resolve-uri', 'true', 'false', 'not', 'years-from-duration', 'months-from-duration', 'days-from-duration',
    'hours-from-duration', 'minutes-from-duration', 'seconds-from-duration', 'year-from-dateTime',
    'month-from-dateTime', 'day-from-dateTime', 'hours-from-dateTime', 'minutes-from-dateTime',
    'seconds-from-dateTime', 'timezone-from-dateTime', 'year-from-date', 'month-from-date', 'day-from-date',
    'timezone-from-date', 'hours-from-time', 'minutes-from-time', 'seconds-from-time', 'timezone-from-time',
    'adjust-dateTime-to-timezone', 'adjust-date-to-timezone', 'adjust-time-to-timezone',
    'resolve-QName', 'QName', 'prefix-from-QName', 'local-name-from-QName', 'namespace-uri-from-QName',
    'namespace-uri-for-prefix', 'in-scope-prefixes', 'name', 'local-name', 'namespace-uri',
    'number', 'lang', 'root', 'boolean', 'index-of', 'empty', 'exists', 'distinct-values',
    'insert-before', 'remove', 'reverse', 'subsequence', 'unordered', 'zero-or-one', 'one-or-more', 'exactly-one',
    'deep-equal', 'count', 'avg', 'max', 'min', 'sum', 'id', 'idref', 'doc', 'doc-available', 'collection',
    'position', 'last', 'current-dateTime', 'current-date', 'current-time', 'implicit-timezone',
    'default-collation', 'static-base-uri', 'format-number'
    }

class XPathExpression:
    def __init__(self, xpathTokens):
        self.xpathTokens = xpathTokens
    def __repr__(self):
        return " ".join(self.xpathTokens)

class FormulaArc:
    def __init__(self, tag, attrib):
        self.tag = tag
        self.attrib = attrib

class FormulaResourceElt:
    def __init__(self, elt):
        self.elt = elt

class FormulaAspectElt:
    def __init__(self, elt):
        self.elt = elt

class FunctionParameter:
    def __init__(self, qname, ptype):
        self.qname = qname[1:] if qname.startswith("$") else qname
        self.ptype = ptype

class FunctionStep:
    def __init__(self, qname, xpathExpression):
        self.qname = qname[1:] if qname.startswith("$") else qname
        self.xpathExpression = xpathExpression

class FormulaLbGenerator:
    def __init__(self, xfsFile, modelXbrl):
        self.xfsFile = xfsFile
        self.modelXbrl = modelXbrl # null when running stand alone
        self.lbFile = xfsFile.rpartition(".")[0] + "-formula.xml"
        self.defaultUnsatisfiedMessageSeverity = None
        self.lbDoc = None
        self.params = {} # qname of parameter xlink:label
        self.labels = {}
        self.definedArcroles = {"variable-set"}
        self.definedRoles = set()
        self.defaultLanguage = None

    def newLb(self):
        initialXml = '''
<!--  Generated by Arelle(r) http://arelle.org -->
<link:linkbase
{0}
xsi:schemaLocation=""
>
<link:roleRef roleURI='http://www.xbrl.org/2008/role/link'
    xlink:href='http://www.xbrl.org/2008/generic-link.xsd#standard-link-role'
    xlink:type='simple'/>
<link:roleRef roleURI='http://www.xbrl.org/2008/role/label'
    xlink:href='http://www.xbrl.org/2008/generic-label.xsd#standard-label'
    xlink:type='simple'/>
<link:arcroleRef arcroleURI='http://xbrl.org/arcrole/2008/variable-set'
    xlink:href='http://www.xbrl.org/2008/variable.xsd#variable-set'
    xlink:type='simple'/>

<generic:link xlink:type="extended" xlink:role="http://www.xbrl.org/2003/role/link"/>
</link:linkbase>
'''.format('\n'.join("xmlns{0}='{1}'".format((":" + prefix) if prefix else "",
                                             namespace)
                     for prefix in ("xlink", "link", "xbrli", "xsi", "xs", "generic", "xfi")
                     for namespace in (formulaPrefixes[prefix][0],))
           )
        if self.modelXbrl is None:
            _xbrlLBfile = io.StringIO(initialXml)
            self.xmlParser = etree.XMLParser(remove_blank_text=True, recover=True, huge_tree=True)
            self.lbDocument = etree.parse(_xbrlLBfile,base_url=self.lbFile,parser=self.xmlParser)
            _xbrlLBfile.close()
        else:
            from arelle.ModelDocument import Type, create as createModelDocument
            from arelle.XmlUtil import setXmlns
            self.arelleSetXmlns = setXmlns
            self.modelXbrl.blockDpmDBrecursion = True
            self.modelDocument = createModelDocument(
                  self.modelXbrl,
                  Type.LINKBASE,
                  self.lbFile,
                  initialXml=initialXml,
                  initialComment="generated from XBRL Formula {}".format(os.path.basename(self.lbFile)),
                  documentEncoding="utf-8")
            self.lbDocument = self.modelDocument.xmlDocument
            self.xmlParser = self.modelDocument.parser
        self.lbElement = next(self.lbDocument.iter(tag=self.clarkName("link:linkbase")))
        self.roleRef = next(self.lbDocument.iter(tag=self.clarkName("link:arcroleRef")))
        self.genLinkElement = next(self.lbDocument.iter(tag=self.clarkName("generic:link")))

    def saveLb(self):
        if self.modelXbrl is None:
            # main program stand-alone mode
            if self.lbDocument is not None:
                with open(self.lbFile, "wb") as fh:
                    fh.write(etree.tostring(self.lbDocument, encoding="utf-8", pretty_print=True))
        elif hasattr(self, "modelDocument"):
            # arelle plugin mode
            self.modelDocument.linkbaseDiscover(self.lbElement)

    def checkXmlns(self, prefix, ns=None):
        root = self.lbDocument.getroot()
        if prefix not in root.nsmap:
            schemaLoc = None
            if prefix in formulaPrefixes:
                nsAndSchemaloc = formulaPrefixes[prefix]
                ns = nsAndSchemaloc[0]
                if len(nsAndSchemaloc) > 1 and nsAndSchemaloc[1]:
                    schemaLoc = nsAndSchemaloc[1]
            if self.modelXbrl is not None:
                self.arelleSetXmlns(self.modelDocument, prefix, ns)
                if schemaLoc:
                    self.modelDocument.xmlRootElement.set(
                        "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation",
                        self.modelDocument.xmlRootElement.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation", "")
                        + " {} {}".format(ns, schemaLoc))
                return
            newmap = root.nsmap
            newmap[prefix] = ns
            attr = dict((k,v) for k,v in root.items())
            if schemaLoc:
                attr["{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"] += " {} {}".format(
                    ns, schemaLoc)
            newroot = etree.Element(root.tag, attrib=attr, nsmap=newmap)
            newroot.extend(root)
            self.lbDocument._setroot(newroot)

    def clarkName(self, prefixedName):
        if prefixedName.startswith("{") or ":" not in prefixedName:
            return prefixedName
        prefix,_sep,localName = prefixedName.partition(":")
        if prefix == "xml":
            return "{http://www.w3.org/XML/1998/namespace}" + localName
        if prefix not in self.lbDocument.getroot().nsmap:
            if prefix not in formulaPrefixes:
                logMessage("ERROR", "formulaSyntax:prefixUndefined",
                    _("Prefix undefined: \n%(qname)s"),
                    xfsFile=self.xfsFile,
                    qname=prefixedName)
                return prefixedName
            else:
                self.checkXmlns(prefix)
        return "{{{}}}{}".format(self.lbDocument.getroot().nsmap[prefix], localName)

    def clarkAttrib(self, attrib):
        if attrib:
            _attrib = {}
            for attribTag, attribValue in attrib.items():
                if attribTag == "xlink:arcrole" and attribValue in formulaArcroleRefs:
                    attribValue = self.arcrole(attribValue)
                elif attribTag == "xlink:role" and attribValue in formulaRoleRefs:
                    attribValue = self.role(attribValue)
                _attrib[self.clarkName(attribTag)] = attribValue
            return _attrib
        else:
            return None

    def checkedQName(self, prefixedName):
        # convert prefix to nsmap prefix if needed
        if ":" not in prefixedName:
            return prefixedName
        if prefixedName.startswith("{"):
            logMessage("ERROR", "formulaSyntax:qnameFormat",
                _("Expecting prefxed QName but appears to be Clark Name: \n%(qname)s"),
                xfsFile=self.xfsFile,
                qname=prefixedName)
            return prefixedName
        prefix,_sep,localName = prefixedName.partition(":")
        if prefix == "xml":
            return prefixedName
        if prefix not in self.lbDocument.getroot().nsmap:
            if prefix not in formulaPrefixes:
                logMessage("ERROR", "formulaSyntax:prefixUndefined",
                    _("Prefix undefined: \n%(qname)s"),
                    xfsFile=self.xfsFile,
                    qname=prefixedName)
                return prefixedName
            else:
                self.checkXmlns(prefix)
        return prefixedName

    def element(self, tag, attrib=None, text=None):
        elt = self.xmlParser.makeelement(self.clarkName(tag), attrib=self.clarkAttrib(attrib), nsmap=self.lbDocument.getroot().nsmap)
        if self.modelXbrl is not None:
            elt.init(self.modelDocument) # modelObject in arelle
        if text:
            elt.text = text
        return elt

    def subElement(self, parentElt, tag, attrib=None, text=None):
        elt = self.element(tag, attrib, text)
        parentElt.append(elt)
        if self.modelXbrl is not None:
            elt.setNamespaceLocalName() # correct prefixed name after adding to parent
        return elt

    def arcrole(self, arcrole):
        if arcrole in formulaArcroleRefs:
            if arcrole not in self.definedArcroles:
                self.definedArcroles.add(arcrole)
                elt = self.element("link:arcroleRef", attrib={
                    "arcroleURI": formulaArcroleRefs[arcrole][0],
                    "xlink:href": formulaArcroleRefs[arcrole][1],
                    "xlink:type": "simple"})
                self.roleRef.addnext(elt)
                self.roleRef = elt
            return formulaArcroleRefs[arcrole][0]
        return arcrole

    def role(self, role):
        if role in formulaRoleRefs:
            if role not in self.definedRoles:
                self.definedRoles.add(role)
                elt = self.element("link:roleRef", attrib={
                    "roleURI": formulaRoleRefs[role][0],
                    "xlink:href": formulaRoleRefs[role][1],
                    "xlink:type": "simple"})
                self.roleRef.addnext(elt)
                self.roleRef = elt
            return formulaRoleRefs[role][0]
        return role

    def labelNbr(self, prefix):
        _labelNbr = self.labels[prefix] = self.labels.get(prefix,0) + 1
        return _labelNbr

# interfaces for Arelle plugin operation
def isXfLoadable(modelXbrl, mappedUri, normalizedUri, filepath, **kwargs):
    return os.path.splitext(mappedUri)[1] == ".xf"

def xfLoader(modelXbrl, mappedUri, filepath, *args, **kwargs):
    if os.path.splitext(filepath)[1] != ".xf":
        return None # not an XBRL formula syntax file

    cntlr = modelXbrl.modelManager.cntlr
    cntlr.showStatus(_("Loading XBRL Formula file: {0}").format(os.path.basename(filepath)))
    doc = parse(cntlr, modelXbrl.log, (filepath,), modelXbrl=modelXbrl)
    if doc is None:
        return None # not an OIM file
    doc.loadedFromXbrlFormula = True
    modelXbrl.loadedFromXbrlFormula = True
    return doc

def guiXbrlLoaded(cntlr, modelXbrl, attach, *args, **kwargs):
    #return
    #### disabled for future less annoying option
    if cntlr.hasGui and getattr(modelXbrl, "loadedFromXbrlFormula", False):
        from arelle import ModelDocument
        from tkinter.filedialog import askdirectory
        for doc in modelXbrl.urlDocs.values():
            if getattr(doc,"loadedFromXbrlFormula", False):
                linkbaseFile = cntlr.uiFileDialog("save",
                        title=_("arelle - Save XBRL formula linkbase"),
                        initialdir=cntlr.config.setdefault("outputInstanceDir","."),
                        filetypes=[(_("XBRL linkbase .xml"), "*.xml")],
                        defaultextension=".xml")
                if not linkbaseFile:
                    return False
                cntlr.config["outputLinkbaseDir"] = os.path.dirname(linkbaseFile)
                cntlr.saveConfig()
                if linkbaseFile:
                    modelXbrl.modelDocument.save(linkbaseFile, updateFileHistory=False)
                    cntlr.showStatus(_("Saving XBRL formula linkbase: {0}").format(os.path.basename(linkbaseFile)))
        cntlr.showStatus(_("XBRL formula loading completed"), 3500)

def cmdLineXbrlLoaded(cntlr, options, modelXbrl, *args, **kwargs):
    if options.saveFormulaLinkbase:
        for doc in modelXbrl.urlDocs.values():
            if getattr(doc,"loadedFromXbrlFormula", False):
                doc.save(options.saveFormulaLinkbase)
                cntlr.showStatus(_("Saving XBRL formula linkbase: {0}").format(doc.basename))

def cmdLineFilingStart(cntlr, options, *args, **kwargs):
    global omitSourceLineAttributes
    omitSourceLineAttributes = options.omitSourceLineAttributes

def cmdLineOptionExtender(parser, *args, **kwargs):
    parser.add_option("--save-formula-linkbase",
                      action="store",
                      dest="saveFormulaLinkbase",
                      help=_("Save a linkbase loaded from formula syntax into this file name."))

    parser.add_option("--omit-sourceline-attributes",
                      action="store_true",
                      dest="omitSourceLineAttributes",
                      help=_("Do not include attributes identifying the source lines in the .xf files."))


__pluginInfo__ = {
    'name': 'XBRL Formula File Loader',
    'version': '0.9',
    'description': "This plug-in loads XBRL formula files into formula linkbase.  ",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'ModelDocument.IsPullLoadable': isXfLoadable,
    'ModelDocument.PullLoader': xfLoader,
    'CntlrWinMain.Xbrl.Loaded': guiXbrlLoaded,
    'CntlrCmdLine.Options': cmdLineOptionExtender,
    'CntlrCmdLine.Xbrl.Loaded': cmdLineXbrlLoaded,
    'CntlrCmdLine.Filing.Start': cmdLineFilingStart,
}

if __name__ == "__main__":
    global _
    import gettext
    _ = gettext.gettext

    class _cntlr:
        def showStatus(self, msg, clearAfter=0):
            print(msg)

    def _logMessage(severity, code, message, **kwargs):
        print("[{}] {}".format(code, message % kwargs))

    debugParsing = False
    xfFiles = []

    for arg in sys.argv[1:]:
        if arg in ("-a", "--about"):
            print("\narelle(r) xf formula loader"
                  f"{copyrightLabel}\n"
                  "All rights reserved\nhttp://www.arelle.org\nsupport@arelle.org\n\n"
                  "Licensed under the Apache License, Version 2.0 (the \"License\"); "
                  "you may not \nuse this file except in compliance with the License.  "
                  "You may obtain a copy \nof the License at "
                  "'http://www.apache.org/licenses/LICENSE-2.0'\n\n"
                  "Unless required by applicable law or agreed to in writing, software \n"
                  "distributed under the License is distributed on an \"AS IS\" BASIS, \n"
                  "WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  \n"
                  "See the License for the specific language governing permissions and \n"
                  "limitations under the License.")
        elif arg in ("-h", "-?", "--help"):
            print("command line arguments: \n"
                  "  --debug: specifies a pyparsing debug trace \n"
                  "  {file}: parse and save as linkbase named {file}-formula.xml")
        elif arg == "--debug":
            debugParsing = True
        elif arg == "--omit-sourceline-attributes":
            omitSourceLineAttributes = True
        else:
            if os.path.exists(arg):
                xfFiles.append(arg)
            else:
                print("file named {} not found".format(arg))

    # load xf formula files
    if xfFiles:
        xfsProgs = parse(_cntlr(), _logMessage, xfFiles, debugParsing=debugParsing)
