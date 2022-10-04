'''
Save formula linkbase into XBRL Formula (syntax) files.

See COPYRIGHT.md for copyright information.

Checks for restricted XPath in compiled formula XPath expressions.

When running in GUI mode, if this plugin is loaded, it always checks formulas for restricted XPath.
You can block formula execution by tools->formula->parameters under IDs put "nothing" (anything not matching a formula id)

When running in Command Line mode, specify --plugin formulaXPathChecker --check-formula-restricted-XPath to activate
these checks (even if plugin is loaded without --check-formula-restricted-XPath the checks don't occur in command line mode).
In command line mode, one can block formula execution by --formula validate (e.g., they are compiled/validated and checked but
not executed).

When running a test suite in command line mode (such as formula suite), to run these checks add the parameters
         --plugin formulaXPathChecker --check-formula-restricted-XPath

When loading a taxonomy package, to check all entries in the package, do not specify --file parameter, instead --check-package-entries
         --package myTaxonomyPackage.zip --plugin formulaXPathChecker --check-formula-restricted-XPath --check-package-entries
'''
from arelle.ViewUtilFormulae import rootFormulaObjects, formulaObjSortKey
from arelle.ModelFormulaObject import (aspectStr, ModelValueAssertion, ModelExistenceAssertion, ModelConsistencyAssertion,
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
from arelle.XPathParser import (VariableRef, QNameDef, OperationDef, RangeDecl, Expr, ProgHeader,
                                exceptionErrorIndication)
from arelle.XPathContext import (XPathException, VALUE_OPS, GENERALCOMPARISON_OPS, NODECOMPARISON_OPS,
                                 COMBINING_OPS, LOGICAL_OPS, UNARY_OPS, FORSOMEEVERY_OPS, PATH_OPS,
                                 SEQUENCE_TYPES, GREGORIAN_TYPES)
from arelle import FileSource, PackageManager, XbrlConst, XmlUtil, XPathParser, ValidateXbrlDimensions, ValidateFormula
from arelle.Version import authorLabel, copyrightLabel
import os, datetime, logging

FNs_BLOCKED = ("doc", "doc-available", "collection", "element-with-id")

class NotExportable(Exception):
    def __init__(self, message):
        self.message = message

def kebabCase(name):
    return "".join("-" + c.lower() if c.isupper() else c for c in name)

def strQuote(s):
    return '"' + s.replace('"', '""') + '"'

class FormulaXPathChecker:
    def __init__(self, modelXbrl):
        self.modelXbrl = modelXbrl

        for cfQnameArity in sorted(qnameArity
                                   for qnameArity in self.modelXbrl.modelCustomFunctionSignatures.keys()
                                   if isinstance(qnameArity, (tuple,list))):
            cfObject = self.modelXbrl.modelCustomFunctionSignatures[cfQnameArity]
            self.doObject(cfObject, None, set())

        rootObjects = rootFormulaObjects(self) # sets var sets up

        # put parameters at root regardless of whether linked to
        for qn, param in sorted(self.modelXbrl.qnameParameters.items(), key=lambda i:i[0]):
            self.doObject(param, None, set())

        for rootObject in sorted(rootObjects, key=formulaObjSortKey):
            self.doObject(rootObject, None, set())

    def checkProg(self, fObj, sourceAttr, progAttr):
        try:
            if isinstance(progAttr, str):
                prog = getattr(fObj, progAttr, None)
            else:
                prog = progAttr
            if prog:
                self.evalProg(prog)
        except XPathException as err:
            self.modelXbrl.warning("arelle:formulaRestrictedXPath",
                _("%(object)s id %(id)s label %(label)s %(attrName)s \nWarning: %(error)s \nExpression: %(expression)s"),
                modelObject=fObj, object=fObj.qname, id=fObj.id, label=fObj.xlinkLabel, attrName=sourceAttr, error=err.message, expression=err.line)

    def stepAxis(self, op, p):
            if isinstance(p,QNameDef):
                axis = p.axis
                if p.isAttribute:
                    if p.localName != "id":
                        raise XPathException(self.progHeader, 'navigateAttr', 'Axis step {} to {}'.format(op, p.localName))
                elif op in ('/', '//', '..') or op is None:
                    raise XPathException(self.progHeader, 'navigateStep', 'Operation {} Axis step {} to {}'.format(op or "", axis or "", p.localName))
            elif isinstance(p, OperationDef) and isinstance(p.name,QNameDef):
                raise XPathException(p, 'navigate', 'Operation {} Axis step {} to {}'.format(op, p, p.name.localName))
            else:
                raise XPathException(p, 'navigate', 'Operation {} Axis step to {}'.format(op, p))

    def evaluateRangeVars(self, op, p, args):
        if isinstance(p, RangeDecl):
            self.evalProg(p.bindingSeq)
            if args and len(args) >= 1:
                self.evaluateRangeVars(op, args[0], args[1:])
        elif isinstance(p, Expr):
            if p.name == 'return':
                self.evalProg(p.expr)
            elif p.name == 'satisfies':
                self.evalProg(p.expr)


    def evalProg(self, exprStack, parentOp=None):
        setProgHeader = False
        for p in exprStack:
            if isinstance(p,QNameDef) or (p == '*' and parentOp in ('/', '//')): # path step QName or wildcard
                # step axis operation
                self.stepAxis(parentOp, p)
            elif isinstance(p,OperationDef):
                op = p.name
                if isinstance(op, QNameDef): # function call
                    args = self.evalProg(p.args)
                    ns = op.namespaceURI; localname = op.localName
                    if op.unprefixed and localname in {'attribute', 'comment', 'document-node', 'element',
                       'item', 'node', 'processing-instruction', 'schema-attribute', 'schema-element', 'text'}:
                        # step axis operation
                        self.stepAxis(parentOp, p)
                    elif (op.unprefixed or ns == XbrlConst.fn) and localname in FNs_BLOCKED:
                        raise XPathException(p, 'function is restricted', 'Function is restricted {}'.format(p))
                elif op in VALUE_OPS:
                    self.evalProg(p.args)
                elif op in GENERALCOMPARISON_OPS:
                    # general comparisons
                    self.evalProg(p.args)
                elif op in NODECOMPARISON_OPS:
                    # node comparisons
                    s2 = self.evalProg(p.args)
                elif op in COMBINING_OPS:
                    # node comparisons
                    self.evalProg(p.args)
                elif op in LOGICAL_OPS:
                    # general comparisons
                    self.evalProg(p.args)
                elif op in UNARY_OPS:
                    self.evalProg(p.args)
                elif op == 'sequence':
                    result = self.evalProg(p.args)
                elif op in FORSOMEEVERY_OPS: # for, some, every
                    result = []
                    self.evaluateRangeVars(op, p.args[0], p.args[1:])
                elif op == 'if':
                    self.evalProg(p.args[0].expr[0])
                    self.evalProg(p.args[1].args) # evaluate both arguments
                    self.evalProg(p.args[2].args)
                elif op in PATH_OPS:
                    self.evalProg(p.args, parentOp=op)
            elif isinstance(p,ProgHeader):
                self.progHeader = p
                setProgHeader = True
        if setProgHeader:
            self.progHeader = None

    def doObject(self, fObj, fromRel, visited):
        if fObj is None:
            return
        if isinstance(fObj, ModelAssertionSet):
            for modelRel in self.modelXbrl.relationshipSet(XbrlConst.assertionSet).fromModelObject(fObj):
                self.doObject(modelRel.toModelObject, modelRel, visited)
        elif isinstance(fObj, (ModelValueAssertion, ModelExistenceAssertion, ModelFormula)):
            for arcrole in (XbrlConst.elementLabel,
                            XbrlConst.assertionSatisfiedMessage,
                            XbrlConst.assertionUnsatisfiedMessage,
                            XbrlConst.assertionUnsatisfiedSeverity
                            ):
                for modelRel in self.modelXbrl.relationshipSet(arcrole).fromModelObject(fObj):
                    self.doObject(modelRel.toModelObject, modelRel, visited)
            if isinstance(fObj, ModelFormula):
                self.checkProg(fObj, "value", "valueProg")
                aspectProgs = getattr(fObj, "aspectProgs", {})
                for aspect, prog in aspectProgs.items():
                    self.checkProg(fObj, aspectStr(aspect), prog)
            for arcrole in (XbrlConst.variableSetFilter,
                            XbrlConst.variableSet,
                            XbrlConst.variableSetPrecondition):
                for modelRel in self.modelXbrl.relationshipSet(arcrole).fromModelObject(fObj):
                    self.doObject(modelRel.toModelObject, modelRel, visited)
            if isinstance(fObj, (ModelValueAssertion, ModelExistenceAssertion)):
                self.checkProg(fObj, "test", "testProg")
        elif isinstance(fObj, ModelConsistencyAssertion):
            if fObj.hasProportionalAcceptanceRadius:
                self.checkProg(fObj, "proportionalAcceptanceRadius", "radiusProg")
            elif fObj.hasProportionalAcceptanceRadius:
                self.checkProg(fObj, "absoluteAcceptanceRadius", "radiusProg")
            for arcrole in (XbrlConst.elementLabel,
                            XbrlConst.assertionSatisfiedMessage,
                            XbrlConst.assertionUnsatisfiedMessage):
                for modelRel in self.modelXbrl.relationshipSet(arcrole).fromModelObject(fObj):
                    self.doObject(modelRel.toModelObject, modelRel, visited)
            for modelRel in self.modelXbrl.relationshipSet(XbrlConst.consistencyAssertionFormula).fromModelObject(fObj):
                self.doObject(modelRel.toModelObject, modelRel, visited)
        elif isinstance(fObj, ModelFactVariable) and fromRel is not None:
            self.checkProg(fObj, "fallbackValue", "fallbackValueProg")
            for modelRel in self.modelXbrl.relationshipSet(XbrlConst.variableFilter).fromModelObject(fObj):
                self.doObject(modelRel.toModelObject, modelRel, visited)
        elif isinstance(fObj, ModelGeneralVariable) and fromRel is not None:
            self.checkProg(fObj, "select", "selectProg")
        elif isinstance(fObj, ModelParameter):
            self.checkProg(fObj, "select", "selectProg")
        elif isinstance(fObj, ModelFilter):
            if isinstance(fObj, ModelConceptName):
                for i, prog in enumerate(getattr(fObj, "qnameExpressionProgs", ())):
                    self.checkProg(fObj, "qnameExpression"+str(i+1), prog)
            elif isinstance(fObj, ModelExplicitDimension):
                for i, memberProg in enumerate(getattr(fObj, "memberProgs", ())):
                    if memberProg.qnameExprProg:
                        self.checkProg(fObj, "member{}qnameExpression".format(i+1), memberProg.qnameExprProg)
            elif isinstance(fObj, ModelTypedDimension): # this is a ModelTestFilter not same as genera/unit/period
                self.checkProg(fObj, "qnameExpression", "dimQnameExpressionProg")
            elif isinstance(fObj, ModelTestFilter):
                self.checkProg(fObj, "test", "testProg")
            elif isinstance(fObj, ModelSingleMeasure):
                self.checkProg(fObj, "qnameExpression", "qnameExpressionProg")
            elif isinstance(fObj, ModelEntitySpecificIdentifier):
                self.checkProg(fObj, "scheme", "schemeProg")
                self.checkProg(fObj, "value", "valueProg")
            elif isinstance(fObj, ModelEntityScheme):
                self.checkProg(fObj, "scheme", "schemeProg")
            elif isinstance(fObj, (ModelAncestorFilter,ModelParentFilter)):
                self.checkProg(fObj, "qnameExpression", "qnameExpressionProg")
            elif isinstance(fObj, ModelAspectCover):
                for mode in ("include", "exclude"):
                    for i, dimProg in enumerate(getattr(fObj, "{}dDimQnameProgs", ())):
                        self.checkProg(fObj, "{}Dimension{}QnameExpression".format(mode,i+1), dimProg)
            elif isinstance(fObj, ModelConceptRelation):
                self.checkProg(fObj, "qnameExpression", "sourceQnameExpressionProg")
                self.checkProg(fObj, "linkroleExpression", "linkroleQnameExpressionProg")
                self.checkProg(fObj, "linknameExpression", "linknameQnameExpressionProg")
                self.checkProg(fObj, "arcroleExpression", "arcroleQnameExpressionProg")
                self.checkProg(fObj, "arcnameExpression", "arcnameQnameExpressionProg")
                self.checkProg(fObj, "test", "testExpressionProg")
        elif isinstance(fObj, ModelMessage):
            if isinstance(fObj, ModelConceptName):
                for i, prog in enumerate(getattr(fObj, "expressionProgs", ())):
                    self.checkProg(fObj, "expression"+str(i+1), prog)
        elif isinstance(fObj, ModelCustomFunctionImplementation):
            self.checkProg(fObj, "output", "outputProg")
            for i, prog in enumerate(getattr(fObj, "stepProgs", ())):
                self.checkProg(fObj, "step"+str(i+1), prog)

def checkFormulaXPathCommandLineOptionExtender(parser, *args, **kwargs):
    # extend command line options with a save DTS option
    parser.add_option("--check-formula-restricted-XPath",
                      action="store_true",
                      dest="checkFormulaRestrictedXPath",
                      help=_("Check formula for restricted XPath features."))
    parser.add_option("--check-package-entries",
                      action="store_true",
                      dest="checkPackageEntries",
                      help=_("Check all package entries."))

def checkFormulaXPathCommandLineXbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    # extend XBRL-loaded run processing for this option
    if getattr(options, "checkFormulaRestrictedXPath", False):
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No taxonomy loaded.")
            return
        cntlr.modelManager.modelXbrl.checkFormulaRestrictedXPath = True



def validateFormulaCompiled(modelXbrl, xpathContext):
    if getattr(modelXbrl, "checkFormulaRestrictedXPath", True): # true allows it to always work for GUI
        try:
            FormulaXPathChecker(modelXbrl)
        except Exception as ex:
            modelXbrl.error("exception",
                _("Xbrl Formula file generation exception: %(error)s"), error=ex,
                modelXbrl=modelXbrl,
                exc_info=True)

def validateUtilityRun(cntlr, options, *args, **kwargs):
    if getattr(options, "checkPackageEntries", False) and not options.entrypointFile:
        setattr(options, 'entrypointFile', '[]') # set empty entrypoints list so CntlrCmdLine continues to CntlrCmdLine.Filing.Start pugin
        setattr(options, 'formulaAction', 'validate')
        setattr(options, 'validate', True)

def setupPackageEntrypoints(cntlr, options, filesource, entrypointFiles, *args, **kwargs):
    # check package entries formula code
    if getattr(options, "checkPackageEntries", False) and not entrypointFiles:
        for packageInfo in sorted(PackageManager.packagesConfig.get("packages", []),
                                  key=lambda packageInfo: (packageInfo.get("name",""),packageInfo.get("version",""))):
            cntlr.addToLog(_("Package %(package)s Version %(version)s"),
                           messageArgs={"package": packageInfo["name"], "version": packageInfo["version"]},
                           messageCode="info",
                           level=logging.INFO)
            filesource = FileSource.openFileSource(packageInfo["URL"], cntlr)
            if filesource.isTaxonomyPackage:  # if archive is also a taxonomy package, activate mappings
                filesource.loadTaxonomyPackageMappings()
            for name, urls in packageInfo.get("entryPoints",{}).items():
                for url in urls:
                    if filesource and filesource.isArchive:
                        cntlr.addToLog(_("   EntryPont %(entryPoint)s: %(url)s"),
                                       messageArgs={"entryPoint": name or urls[0][2],
                                                    "url": url[1]},
                                       messageCode="info",
                                       level=logging.INFO)
                        entrypointFiles.append({"file":url[1]})

__pluginInfo__ = {
    'name': 'Formula XPath Checker',
    'version': '0.9',
    'description': "This plug-in checks for restricted XPath in formula expressions. ",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrCmdLine.Options': checkFormulaXPathCommandLineOptionExtender,
    'CntlrCmdLine.Utility.Run': validateUtilityRun,
    'CntlrCmdLine.Filing.Start': setupPackageEntrypoints,
    'CntlrCmdLine.Xbrl.Run': checkFormulaXPathCommandLineXbrlRun,
    'ValidateFormula.Compiled': validateFormulaCompiled
}
