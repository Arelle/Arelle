'''
Save formula linkbase into XBRL Formula (syntax) files.

See COPYRIGHT.md for copyright information.

Loads xbrl formula file syntax into formula linkbase.

To run from command line, loading formula linkbase and saving formula syntax files:

  python3.5 arelleCmdLine.py
     -f {DTS, instance, entry file, or formula linkbase file}
    --plugins formulaSaver.py
    --save-xbrl-formula {formula syntax output file.xf}

'''
from arelle.ViewUtilFormulae import rootFormulaObjects, formulaObjSortKey
from arelle.ModelFormulaObject import (ModelValueAssertion, ModelExistenceAssertion, ModelConsistencyAssertion,
                                       ModelAssertionSet,
                                       ModelFactVariable, ModelGeneralVariable, ModelFormula, ModelParameter,
                                       ModelFilter, ModelConceptName, ModelConceptPeriodType, ModelConceptBalance,
                                       ModelConceptCustomAttribute, ModelConceptDataType, ModelConceptSubstitutionGroup,
                                       ModelTestFilter, ModelGeneral, ModelGeneralMeasures, ModelInstantDuration,
                                       ModelDateTimeFilter, ModelSingleMeasure, ModelExplicitDimension, ModelTypedDimension,
                                       ModelEntitySpecificIdentifier, ModelEntityScheme, ModelEntityRegexpScheme,
                                       ModelEntityRegexpIdentifier, ModelMatchFilter, ModelRelativeFilter,
                                       ModelAncestorFilter, ModelParentFilter, ModelSiblingFilter, ModelNilFilter,
                                       ModelAspectCover, ModelConceptRelation,
                                       ModelCustomFunctionSignature, ModelCustomFunctionImplementation,
                                       ModelPeriod,
                                       ModelAndFilter, ModelOrFilter, ModelMessage, ModelAssertionSeverity)
from arelle import XbrlConst, XmlUtil, XPathParser
from arelle.Version import authorLabel, copyrightLabel
import os, datetime

class NotExportable(Exception):
    def __init__(self, message):
        self.message = message

def kebabCase(name):
    return "".join("-" + c.lower() if c.isupper() else c for c in name)

def strQuote(s):
    return '"' + s.replace('"', '""') + '"'

class GenerateXbrlFormula:
    def __init__(self, cntlr, xfFile):
        self.modelXbrl = cntlr.modelManager.modelXbrl
        self.xfFile = xfFile
        self.xfLines = []
        self.xmlns = {}
        self.eltTypeCount = {}
        self.nextIdDupNbr = {}

        cntlr.showStatus(_("Initializing Formula Grammar"))
        XPathParser.initializeParser(cntlr.modelManager)
        cntlr.showStatus(None)

        for cfQnameArity in sorted(qnameArity
                                   for qnameArity in self.modelXbrl.modelCustomFunctionSignatures.keys()
                                   if isinstance(qnameArity, (tuple,list))):
            cfObject = self.modelXbrl.modelCustomFunctionSignatures[cfQnameArity]
            self.doObject(cfObject, None, "", set())

        rootObjects = rootFormulaObjects(self) # sets var sets up

        # put parameters at root regardless of whether linked to
        for qn, param in sorted(self.modelXbrl.qnameParameters.items(), key=lambda i:i[0]):
            self.doObject(param, None, "", set())

        for rootObject in sorted(rootObjects, key=formulaObjSortKey):
            self.doObject(rootObject, None, "", set())

        if self.xmlns:
            self.xfLines.insert(0, "")
            for prefix, ns in sorted(self.xmlns.items(), reverse=True):
                self.xfLines.insert(0, "namespace {} = \"{}\";".format(prefix, ns))

        self.xfLines.insert(0, "")
        self.xfLines.insert(0, "(: Generated from {} by Arelle on {} :)".format(self.modelXbrl.modelDocument.basename, XmlUtil.dateunionValue(datetime.datetime.now())))

        with open(xfFile, "w", encoding="utf-8") as fh:
            fh.write("\n".join(self.xfLines))

        self.modelXbrl.info("info", "saved formula file %(file)s", file=xfFile)

    @property
    def xf(self):
        return xfLines[-1]

    @xf.setter
    def xf(self, line):
        self.xfLines.append(line)

    def objectId(self, fObj, elementType):
        eltNbr = self.eltTypeCount[elementType] = self.eltTypeCount.get(elementType, 0) + 1
        _id = fObj.id
        if _id:
            idDupNbr = self.nextIdDupNbr.get(_id,"")
            self.nextIdDupNbr[_id] = (idDupNbr or 1) + 1
            _id = "{}{}".format(_id, idDupNbr)
        else:
            _id = "{}{}".format(elementType, eltNbr)
        return _id

    def doObject(self, fObj, fromRel, pIndent, visited):
        if fObj is None:
            return
        cIndent = pIndent + "   "
        if isinstance(fObj, ModelAssertionSet):
            self.xf = "{}assertion-set {} {{".format(pIndent,  self.objectId(fObj, "assertionSet"))
            for modelRel in self.modelXbrl.relationshipSet(XbrlConst.assertionSet).fromModelObject(fObj):
                self.doObject(modelRel.toModelObject, modelRel, cIndent, visited)
            self.xf = "{}}};".format(pIndent)
        elif isinstance(fObj, (ModelValueAssertion, ModelExistenceAssertion, ModelFormula)):
            varSetType = "formula" if isinstance(fObj, ModelFormula) else "assertion"
            self.xf = "{}{} {} {{".format(pIndent, varSetType, self.objectId(fObj, varSetType))
            for arcrole in (XbrlConst.elementLabel,
                            XbrlConst.assertionSatisfiedMessage,
                            XbrlConst.assertionUnsatisfiedMessage,
                            XbrlConst.assertionUnsatisfiedSeverity
                            ):
                for modelRel in self.modelXbrl.relationshipSet(arcrole).fromModelObject(fObj):
                    self.doObject(modelRel.toModelObject, modelRel, cIndent, visited)
            if fObj.aspectModel == "non-dimensional":
                self.xf = "{}aspect-model-non-dimensional;".format(cIndent)
            if fObj.implicitFiltering == "false":
                self.xf = "{}no-implicit-filtering;".format(cIndent)
            if isinstance(fObj, ModelFormula):
                for attr in ("decimals", "precision", "value"):
                    if fObj.get(attr):
                        self.xf = "{}{} {{{}}};".format(cIndent, attr, fObj.get(attr))
                if fObj.get("source"):
                    self.xf = "{}source {};".format(cIndent, fObj.get("source"))
                for aspectsElt in XmlUtil.children(fObj, XbrlConst.formula, "aspects"):
                    self.xf = "{}aspect-rules{} {{".format(cIndent,
                                                           "source {}".format(aspectsElt.get("source")) if aspectsElt.get("source") else "")
                    for ruleElt in XmlUtil.children(aspectsElt, XbrlConst.formula, "*"):
                        self.doObject(ruleElt, None, cIndent + "   ", visited)
                    self.xf = "{}}};".format(cIndent)
            for arcrole in (XbrlConst.variableSetFilter,
                            XbrlConst.variableSet,
                            XbrlConst.variableSetPrecondition):
                for modelRel in self.modelXbrl.relationshipSet(arcrole).fromModelObject(fObj):
                    self.doObject(modelRel.toModelObject, modelRel, cIndent, visited)
            if isinstance(fObj, ModelValueAssertion):
                self.xf = "{}test {{{}}};".format(cIndent, fObj.viewExpression)
            elif isinstance(fObj, ModelExistenceAssertion):
                self.xf = "{}evaluation-count {{{}}};".format(cIndent, fObj.viewExpression or ". gt 0")
            self.xf = "{}}};".format(pIndent)
        elif isinstance(fObj, ModelConsistencyAssertion):
            self.xf = "{}consistency-assertion {} {{".format(pIndent, self.objectId(fObj, "consistencyAssertion"))
            for arcrole in (XbrlConst.elementLabel,
                            XbrlConst.assertionSatisfiedMessage,
                            XbrlConst.assertionUnsatisfiedMessage):
                for modelRel in self.modelXbrl.relationshipSet(arcrole).fromModelObject(fObj):
                    self.doObject(modelRel.toModelObject, modelRel, cIndent, visited)
            if fObj.isStrict:
                self.xf = "{}strict;".format(cIndent)
            if fObj.get("proportionalAcceptanceRadius"):
                self.xf = "{}proportional-acceptance-radius {{{}}};".format(cIndent, fObj.get("proportionalAcceptanceRadius"))
            if fObj.get("absoluteAcceptanceRadius"):
                self.xf = "{}absolute-acceptance-radius {{{}}};".format(cIndent, fObj.get("absoluteAcceptanceRadius"))
            for modelRel in self.modelXbrl.relationshipSet(XbrlConst.consistencyAssertionFormula).fromModelObject(fObj):
                self.doObject(modelRel.toModelObject, modelRel, cIndent, visited)
            self.xf = "{}}};".format(pIndent)
        elif isinstance(fObj, ModelFactVariable) and fromRel is not None:
            self.xf = "{}variable ${} {{".format(pIndent, fromRel.variableQname)
            if fromRel.variableQname.prefix:
                self.xmlns[fromRel.variableQname.prefix] = fromRel.variableQname.namespaceURI
            if fObj.bindAsSequence == "true":
                self.xf = "{}bind-as-sequence".format(cIndent)
            if fObj.nils == "true":
                self.xf = "{}nils".format(cIndent)
            if fObj.matches == "true":
                self.xf = "{}matches".format(cIndent)
            if fObj.fallbackValue:
                self.xf = "{}fallback {{{}}}".format(cIndent, fObj.fallbackValue)
            for modelRel in self.modelXbrl.relationshipSet(XbrlConst.variableFilter).fromModelObject(fObj):
                self.doObject(modelRel.toModelObject, modelRel, cIndent, visited)
            self.xf = "{}}};".format(pIndent)
        elif isinstance(fObj, ModelGeneralVariable) and fromRel is not None:
            self.xf = "{}variable ${} {{".format(pIndent, fromRel.variableQname)
            if fromRel.variableQname.prefix:
                self.xmlns[fromRel.variableQname.prefix] = fromRel.variableQname.namespaceURI
            if fObj.bindAsSequence:
                self.xf = "{}bind-as-sequence".format(cIndent)
            self.xf = "{}select {{{}}}".format(cIndent, fObj.select)
        elif isinstance(fObj, ModelParameter):
            if fromRel is not None:
                # parameter is referenced by a different QName on arc
                if fromRel.variableQname.prefix:
                    self.xmlns[fromRel.variableQname.prefix] = fromRel.variableQname.namespaceURI
                self.xf = "{}parameter ${} references ${};".format(pIndent, fromRel.variableQname, fObj.parameterQname)
            else: # root level parameter
                if fObj.parameterQname.prefix:
                    self.xmlns[fObj.parameterQname.prefix] = fObj.parameterQname.namespaceURI
                self.xf = "{}parameter {} {{".format(pIndent, fObj.parameterQname)
                if fObj.isRequired:
                    self.xf = "{}required".format(cIndent)
                self.xf = "{} select {{{}}}".format(cIndent, fObj.select)
                if fObj.asType:
                    self.xf = "{} as {{{}}}".format(cIndent, fObj.asType)
                    if fObj.asType.prefix:
                        self.xmlns[fObj.asType.prefix] = fObj.asType.namespaceURI
                self.xf = "{}}};".format(pIndent)
        elif isinstance(fObj, ModelFilter):
            if fromRel.isComplemented:
                self.xf = "{}complemented".format(pIndent)
            if not fromRel.isCovered and fromRel.localName == "variableFilterArc":
                self.xf = "{}non-covering".format(pIndent)
            if isinstance(fObj, ModelConceptName):
                if len(fObj.conceptQnames) == 1 and not fObj.qnameExpressions:
                    qn = next(iter(fObj.conceptQnames))
                    self.xmlns[qn.prefix] = qn.namespaceURI
                    self.xf = "{}concept-name {};".format(pIndent, qn)
                elif len(fObj.qnameExpressions) == 1 and not fObj.conceptQnames:
                    self.xf = "{}concept-name {{{}}};".format(pIndent, fObj.qnameExpressions[0])
                else:
                    self.xf = "{}concept-name".format(pIndent)
                    for qn in fObj.conceptQnames:
                        self.xmlns[qn.prefix] = qn.namespaceURI
                        self.xf = "{}   {}".format(pIndent, qn)
                    for qnExpr in fObj.qnameExpressions:
                        self.xf = "{}   {}".format(pIndent, qnExpr)
                    self.xf = "{}   ;".format(pIndent)
            elif isinstance(fObj, ModelConceptPeriodType):
                self.xf = "{}concept-period {};".format(pIndent, fObj.periodType)
            elif isinstance(fObj, ModelConceptBalance):
                self.xf = "{}concept-balance {};".format(pIndent, fObj.balance)
            elif isinstance(fObj, (ModelConceptDataType, ModelConceptSubstitutionGroup)):
                self.xf = "{}{} {} {};".format(pIndent, kebabCase(fObj.localName),
                                               "strict" if fObj.strict == "true" else "non-strict",
                                               fObj.filterQname if fObj.filterQname else "{{{}}}".format(fObj.qnameExpression))
            elif isinstance(fObj, ModelExplicitDimension):
                members = []
                for memberElt in XmlUtil.children(fObj, XbrlConst.df, "member"):
                    members.append("member")
                    member = XmlUtil.childText(memberElt, XbrlConst.df, "qname")
                    if member:
                        member = str(member) # qname, must coerce to string
                    else:
                        member = XmlUtil.childText(memberElt, XbrlConst.df, "qnameExpression")
                        if member:
                            member = "{{{}}}".format(member)
                        else:
                            member = "$" + XmlUtil.childText(memberElt, XbrlConst.df, "variable")
                    members.append(member)
                    linkrole = XmlUtil.childText(memberElt, XbrlConst.df, "linkrole")
                    if linkrole:
                        members.append("linkrole")
                        members.append("\"{}\"".format(linkrole))
                    arcrole = XmlUtil.childText(memberElt, XbrlConst.df, "arcrole")
                    if arcrole:
                        members.append("arcrole")
                        members.append("\"{}\"".format(arcrole))
                    axis = XmlUtil.childText(memberElt, XbrlConst.df, "axis")
                    if axis:
                        members.append("axis")
                        members.append(axis)
                self.xf = "{}explicit-dimension {} {};".format(pIndent,
                                                              fObj.dimQname or ("{{{}}}".format(fObj.dimQnameExpression) if fObj.dimQnameExpression else ""),
                                                              " ".join(members))
            elif isinstance(fObj, ModelTypedDimension): # this is a ModelTestFilter not same as genera/unit/period
                self.xf = "{}typed-dimension {} {};".format(pIndent,
                                                           fObj.dimQname or ("{{{}}}".format(fObj.dimQnameExpression) if fObj.dimQnameExpression else ""),
                                                           " {{{}}}".format(fObj.test) if fObj.test else "")
            elif isinstance(fObj, ModelTestFilter):
                self.xf = "{}{} {{{}}};".format(pIndent,
                                                "general" if isinstance(fObj, ModelGeneral) else
                                                "unit-general-measures" if isinstance(fObj, ModelGeneralMeasures) else
                                                "period" if isinstance(fObj, ModelPeriod) else
                                                "entity-identifier" if isinstance(fObj, ModelIdentifier) else None,
                                                fObj.test)
            elif isinstance(fObj, ModelDateTimeFilter):
                self.xf = "{}{} {{{}}}{};".format(pIndent, kebabCase(fObj.localName), fObj.date,
                                                  " {{{}}}".format(fObj.time) if fObj.time else "")
            elif isinstance(fObj, ModelInstantDuration):
                self.xf = "{}instant-duration {} {};".format(pIndent, fObj.boundary, fObj.variable)
            elif isinstance(fObj, ModelSingleMeasure):
                self.xf = "{}unit-single-measure {};".format(pIndent,
                                                             fObj.measureQname or ("{{{}}}".format(fObj.qnameExpression) if fObj.qnameExpression else ""))
            elif isinstance(fObj, ModelEntitySpecificIdentifier):
                self.xf = "{}entity scheme {{{}}} value {{{}}};".format(pIndent, fObj.scheme, fObj.value)
            elif isinstance(fObj, ModelEntityScheme):
                self.xf = "{}entity-scheme {{{}}};".format(pIndent, fObj.scheme)
            elif isinstance(fObj, ModelEntityRegexpScheme):
                self.xf = "{}entity-scheme-pattern \"{}\";".format(pIndent, fObj.pattern)
            elif isinstance(fObj, ModelEntityRegexpIdentifier):
                self.xf = "{}entity-identifier-pattern \"{}\";".format(pIndent, fObj.pattern)
            elif isinstance(fObj, ModelMatchFilter):
                self.xf = "{}{} ${} {}{};".format(pIndent, kebabCase(fObj.localName), fObj.variable,
                                                  " dimension {}".format(fObj.dimension) if fObj.get("dimension") else "",
                                                  " match-any" if fObj.matchAny else "")
            elif isinstance(fObj, ModelRelativeFilter):
                self.xf = "{}relative ${};".format(pIndent, fObj.variable)
            elif isinstance(fObj, ModelAncestorFilter):
                self.xf = "{}ancestor {};".format(pIndent,
                                                  fObj.ancestorQname or ("{{{}}}".format(fObj.qnameExpression) if fObj.qnameExpression else ""))
            elif isinstance(fObj, ModelParentFilter):
                self.xf = "{}parent {};".format(pIndent,
                                                  fObj.parentQname or ("{{{}}}".format(fObj.qnameExpression) if fObj.qnameExpression else ""))
            elif isinstance(fObj, ModelSiblingFilter):
                self.xf = "{}sibling ${};".format(pIndent, fObj.variable)
            elif isinstance(fObj, ModelNilFilter):
                self.xf = "{}nilled;".format(pIndent)
            elif isinstance(fObj, ModelAspectCover):
                aspects = []
                for aspectElt in XmlUtil.children(fObj, XbrlConst.acf, "aspect"):
                    aspects.append(XmlUtil.text(aspectElt))
                for dimElt in XmlUtil.descendants(fObj, XbrlConst.acf, ("qname", "qnameExpression")):
                    dimAspect = qname( dimElt, XmlUtil.text(dimElt) )
                    aspects.append("exclude-dimension" if dimElt.getparent().localName == "excludeDimension" else "dimension")
                    if dimElt.localName == "qname":
                        aspects.append(str(qname( dimElt, XmlUtil.text(dimElt) )))
                    else:
                        aspects.append("{{{}}}".format(XmlUtil.text(dimElt)))
                self.xf = "{}aspect-cover {};".format(pIndent, " ".join(aspects))
            elif isinstance(fObj, ModelConceptRelation):
                conceptRelationTerms = []
                if fObj.sourceQname:
                    conceptRelationTerms.append(fObj.sourceQname)
                elif fObj.variable:
                    conceptRelationTerms.append("$" + fObj.variable)
                else:
                    conceptRelationTerms.append("{{{}}}".format(fObj.sourceQnameExpression))
                if fObj.linkrole:
                    conceptRelationTerms.append("linkrole")
                    conceptRelationTerms.append(fObj.linkrole)
                elif fObj.linkroleExpression:
                    conceptRelationTerms.append("linkrole")
                    conceptRelationTerms.append("{{{}}}".format(fObj.linkroleExpression))
                if fObj.arcrole:
                    conceptRelationTerms.append("arcrole")
                    conceptRelationTerms.append(fObj.arcrole)
                elif fObj.arcroleExpression:
                    conceptRelationTerms.append("arcrole")
                    conceptRelationTerms.append("{{{}}}".format(fObj.arcroleExpression))
                if fObj.axis:
                    conceptRelationTerms.append("axis")
                    conceptRelationTerms.append(fObj.axis)
                if fObj.generations is not None:
                    conceptRelationTerms.append("generations {}".format(fObj.generations))
                if fObj.test:
                    conceptRelationTerms.append("test")
                    conceptRelationTerms.append("{{{}}}".format(fObj.test))
                self.xf = "{}concept-relation {};".format(pIndent, " ".join(conceptRelationTerms))
            elif isinstance(fObj, (ModelAndFilter, ModelOrFilter)):
                self.xf = "{}{} {{".format(pIndent, "and" if isinstance(fObj, ModelAndFilter)else "or")
                if fObj not in visited:
                    visited.add(fObj)
                    for modelRel in self.modelXbrl.relationshipSet(XbrlConst.booleanFilter).fromModelObject(fObj):
                        self.doObject(modelRel.toModelObject, modelRel, cIndent, visited)
                    visited.remove(fObj)
                self.xf = "{}}};".format(pIndent)
        elif isinstance(fObj, ModelMessage):
            self.xf = "{}{}{} \"{}\";".format(
                pIndent,
                "satisfied-message" if fromRel.arcrole == XbrlConst.assertionSatisfiedMessage else "unsatisfied-message",
                " ({})".format(fObj.xmlLang) if fObj.xmlLang else "",
                fObj.text.replace('"', '""'))
        elif isinstance(fObj, ModelAssertionSeverity):
            self.xf = "{}{} {};".format(
                pIndent,
                "unsatisfied-severity",
                fObj.level)
        elif isinstance(fObj, ModelCustomFunctionSignature):
            hasImplememntation = False
            if fObj not in visited:
                visited.add(fObj)
                for modelRel in self.modelXbrl.relationshipSet(XbrlConst.functionImplementation).fromModelObject(fObj):
                    self.doObject(modelRel.toModelObject, modelRel, pIndent, visited) # note: use pIndent as parent doesn't show
                    hasImplementation = True
                visited.remove(fObj)
            if not hasImplementation:
                self.xmlns[fObj.functionQname.prefix] = fObj.functionQname.namespaceURI
                self.xf = "{}abstract-function {}({}) as {};".format(pIndent, fObj.name,
                                                                      ", ".join(str(t) for t in fObj.inputTypes),
                                                                      fObj.outputType)
        elif isinstance(fObj, ModelCustomFunctionImplementation):
            sigObj = fromRel.fromModelObject
            self.xmlns[sigObj.functionQname.prefix] = sigObj.functionQname.namespaceURI
            self.xf = "{}function {}({}) as {} {{".format(pIndent,
                                                          sigObj.name,
                                                          ", ".join("{} as {}".format(inputName, sigObj.inputTypes[i])
                                                                    for i, inputName in enumerate(fObj.inputNames)),
                                                          sigObj.outputType)
            for name, stepExpr in fObj.stepExpressions:
                if "\n" not in stepExpr:
                    self.xf = "{}step ${} {{{}}};".format(cIndent, name, stepExpr)
                else:
                    self.xf = "{}step ${} {{".format(cIndent, name)
                    for exprLine in stepExpr.split("\n"):
                        self.xf = "{}   {}".format(cIndent, exprLine.lstrip())
                    self.xf = "{}}};".format(cIndent)
            self.xf = "{}return {{{}}};".format(cIndent, fObj.outputExpression)
            self.xf = "{}}};".format(pIndent)
        elif fObj.getparent().tag == "{http://xbrl.org/2008/formula}aspects":
            # aspect rules
            arg = ""
            if fObj.localName == "concept":
                if XmlUtil.hasChild(fObj, None, "qname"):
                    arg += " " + XmlUtil.childText(fObj, None, "qname")
                elif XmlUtil.hasChild(fObj, None, "qnameExpression"):
                    arg += " {" + XmlUtil.childText(fObj, None, "qnameExpression") + "}"
            elif fObj.localName == "entityIdentifier":
                if fObj.get("scheme"): arg += " scheme {" + fObj.get("scheme") + "}"
                if fObj.get("identifier"): arg += " identifier {" + fObj.get("identifier") + "}"
            elif fObj.localName == "period":
                if XmlUtil.hasChild(fObj, None, "forever"):
                    arg += " forever"
                if XmlUtil.hasChild(fObj, None, "instant"):
                    arg += " instant"
                    attr = XmlUtil.childAttr(fObj, None, "instant", "value")
                    if attr: arg += "{" + attr + "}"
                if XmlUtil.hasChild(fObj, None, "duration"):
                    arg += " duration"
                    attr = XmlUtil.childAttr(fObj, None, "duration", "start")
                    if attr: arg += " start {" + attr + "}"
                    attr = XmlUtil.childAttr(fObj, None, "duration", "end")
                    if attr: arg += " end {" + attr + "}"
            elif fObj.localName == "unit":
                if fObj.get("augment") == "true": arg += " augment"
            if fObj.localName in ("explicitDimension", "typedDimension"):
                arg += " dimension " + fObj.get("dimension")
            if fObj.localName in ("concept", "entityIdentifier", "period"):
                arg += ";"
            else:
                arg += " {"
            self.xf = "{}{}{}".format(pIndent, kebabCase(fObj.localName), arg)
            if fObj.localName == "unit":
                for elt in fObj.iterchildren():
                    arg = ""
                    if elt.get("source"): arg += " source " + elt.get("source")
                    if elt.get("measure"): arg += " measure {" + elt.get("measure") + "}"
                    self.xf = "{}{}{};".format(cIndent, kebabCase(elt.localName), arg)
            elif fObj.localName == "explicitDimension":
                for elt in fObj.iterchildren():
                    arg = ""
                    if XmlUtil.hasChild(elt, None, "qname"):
                        arg += " " + XmlUtil.childText(elt, None, "qname")
                    elif XmlUtil.hasChild(elt, None, "qnameExpression"):
                        arg += " {" + XmlUtil.childText(elt, None, "qnameExpression") + "}"
                    self.xf = "{}{}{};".format(cIndent, kebabCase(elt.localName), arg)
            elif fObj.localName == "typedDimension":
                for elt in fObj.iterchildren():
                    arg = ""
                    if XmlUtil.hasChild(elt, None, "xpath"):
                        arg += " xpath {" + ModelXbrl.childText(elt, None, "xpath") + "}"
                    elif XmlUtil.hasChild(elt, None, "value"):
                        arg += " value " + strQoute(XmlUtil.xmlstring(XmlUtil.child(elt, None, "value"),
                                                                      stripXmlns=True, contentsOnly=False))
                    self.xf = "{}{}{};".format(cIndent, kebabCase(elt.localName), arg)
            if fObj.localName not in ("concept", "entityIdentifier", "period"):
                self.xf = "{}}};".format(pIndent)
        # check for prefixes in AST of programs of fObj
        if hasattr(fObj, "compile") and type(fObj.compile).__name__ == "method":
            fObj.compile()
            for _prog, _ast in fObj.__dict__.items():
                if _prog.endswith("Prog") and isinstance(_ast, list):
                    XPathParser.prefixDeclarations(_ast, self.xmlns, fObj)


def saveXfMenuEntender(cntlr, menu, *args, **kwargs):
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Save Xbrl Formula file",
                     underline=0,
                     command=lambda: saveXfMenuCommand(cntlr) )

def saveXfMenuCommand(cntlr):
    # save DTS menu item has been invoked
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
        cntlr.addToLog("No taxonomy loaded.")
        return

        # get file name into which to save log file while in foreground thread
    xbrlFormulaFile = cntlr.uiFileDialog("save",
            title=_("arelle - Save XBRL Formula file"),
            initialdir=cntlr.config.setdefault("xbrlFormulaFileDir","."),
            filetypes=[(_("XBRL formula file .xf"), "*.xf")],
            defaultextension=".xf")
    if not xbrlFormulaFile:
        return False
    import os
    cntlr.config["xbrlFormulaFileDir"] = os.path.dirname(xbrlFormulaFile)
    cntlr.saveConfig()

    try:
        GenerateXbrlFormula(cntlr, xbrlFormulaFile)
    except Exception as ex:
        dts = cntlr.modelManager.modelXbrl
        dts.error("exception",
            _("Xbrl Formula file generation exception: %(error)s"), error=ex,
            modelXbrl=dts,
            exc_info=True)

def saveXfCommandLineOptionExtender(parser, *args, **kwargs):
    # extend command line options with a save DTS option
    parser.add_option("--save-xbrl-formula",
                      action="store",
                      dest="xbrlFormulaFile",
                      help=_("Save Formula File from formula linkbase."))

def saveXfCommandLineXbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    # extend XBRL-loaded run processing for this option
    if getattr(options, "xbrlFormulaFile", False):
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No taxonomy loaded.")
            return
        GenerateXbrlFormula(cntlr, options.xbrlFormulaFile)


__pluginInfo__ = {
    'name': 'Save Formula File',
    'version': '0.9',
    'description': "This plug-in adds a feature to output XBRL Formula file from formula linkbase model objects. ",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': saveXfMenuEntender,
    'CntlrCmdLine.Options': saveXfCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Run': saveXfCommandLineXbrlRun,
}
