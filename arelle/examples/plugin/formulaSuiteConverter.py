'''
XBRL formula conf suite converter
   from Formula 1.0 to XF

   arelleCmdline
     --plugin formulaSuiteConverter
     --source-test-suite-dir {directory containing index.xml file for suite)
     --converted-test-suite-dir {directory receiving converted suite)


See COPYRIGHT.md for copyright information.
'''
from arelle import ModelXbrl, XmlUtil
from arelle.ModelDocument import Type
from arelle.ModelValue import qname
from arelle.ViewUtilFormulae import rootFormulaObjects, formulaObjSortKey
from arelle.PluginManager import pluginClassMethods
from arelle.PrototypeDtsObject import PrototypeObject
from arelle.PythonUtil import attrdict
from arelle.Version import authorLabel, copyrightLabel
import os, shutil
from lxml import etree
import regex as re

oimErrPattern = re.compile("(oime|xbrlxe):")
QN_SCHEMA_REF = qname("{http://www.xbrl.org/2003/linkbase}schemaRef")

def convertVariation(cntlr, variationFile, variationElt, inPath, outPath, entryPoint, resultInstFile):
    entryFile = os.path.join(inPath, entryPoint)
    modelXbrl = ModelXbrl.load(cntlr.modelManager, entryFile)
    doc = modelXbrl.modelDocument
    formulaRootObjects = rootFormulaObjects(modelXbrl) # sets var sets up
    formulaFile = None
    for formulaRootObject in sorted(formulaRootObjects, key=formulaObjSortKey):
        formulaFile = formulaRootObject.modelDocument.basename # first formula file
        break
    # convert formula linkbaseRefs into shim schema refs
    if doc.type in (Type.INSTANCE, Type.INLINEXBRL, Type.INLINEXBRLDOCUMENTSET):
        for lbDoc, ref in doc.referencesDocument.items():
            if lbDoc.type == Type.LINKBASE:
                lbRef = lbDoc.basename
                if lbRef == formulaFile:
                    lbRef = os.path.splitext(lbRef)[0] + ".xf"
                    lbDoc.uri = os.path.splitext(lbDoc.uri)[0] + ".xsd"
                lbXsdFile = os.path.splitext(lbRef)[0] + ".xsd"
                with open(os.path.join(outPath, lbXsdFile), "w", encoding="utf-8") as fh:
                    fh.write("""
<?xml version="1.0" encoding="utf-8"?>
<schema
    xmlns="http://www.w3.org/2001/XMLSchema"
    xmlns:link="http://www.xbrl.org/2003/linkbase"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    elementFormDefault="qualified">
  <annotation>
    <appinfo>
      <link:linkbaseRef
        xlink:href="{}"
        xlink:type="simple"
        xlink:arcrole="http://www.w3.org/1999/xlink/properties/linkbase"/>
    </appinfo>
  </annotation>
</schema>
""".format(lbRef))
                lbDoc.type = Type.SCHEMA
                ref.referringModelObject = PrototypeObject(ref.referringModelObject.modelDocument, ref.referringModelObject)
                ref.referringModelObject.qname = QN_SCHEMA_REF

    # perform OIM validation on xBRL-XML source instance
    for pluginXbrlMethod in pluginClassMethods("Validate.XBRL.Finally"):
        pluginXbrlMethod(doc)
    if any(oimErrPattern.match(err) for err in modelXbrl.errors):
        modelXbrl.error("testSuiteConverter:unconvertableTestcase",
                        f"Variation {variationFile} {variationElt.get('id')} has OIM errors",
                        modelObject=modelXbrl)
        variationElt.getparent().remove(variationElt)
        return {}
    transformedFiles = {}
    convertedFiles = {}
    if formulaFile:
        formulaOutFile = os.path.splitext(formulaFile)[0] + ".xf"
        transformedFiles["xbrlFormulaFile"] = os.path.join(outPath, formulaOutFile)
        convertedFiles[formulaFile] = formulaOutFile
    if doc.type in (Type.INSTANCE, Type.INLINEXBRL, Type.INLINEXBRLDOCUMENTSET):
        instOutFile = os.path.splitext(doc.basename)[0] + ".json"
        transformedFiles["saveLoadableOIM"] = os.path.join(outPath, instOutFile)
        convertedFiles[doc.basename] = instOutFile
    # CntlrCmdLine.Xbrl.Run invokes both saveLoadableOIM for instance and formulaSaver for xf
    options = attrdict(**transformedFiles)
    try:
        for pluginXbrlMethod in pluginClassMethods("CntlrCmdLine.Xbrl.Run"):
            pluginXbrlMethod(cntlr, options, modelXbrl)
    except Exception as ex:
        modelXbrl.error("testSuiteConverter:unconvertableTestcase",
                        f"Variation {variationFile} {variationElt.get('id')} is not transformable to XF or OIM: {ex}",
                        modelObject=modelXbrl)
        variationElt.getparent().remove(variationElt)
        return {}
    if resultInstFile:
        resultOutFile = os.path.splitext(resultInstFile)[0] + ".json"
        options = attrdict(saveLoadableOIM=os.path.join(outPath, resultOutFile))
        convertedFiles[resultInstFile] = resultOutFile
        try:
            for pluginXbrlMethod in pluginClassMethods("CntlrCmdLine.Xbrl.Run"):
                pluginXbrlMethod(cntlr, options, modelXbrl)
        except Exception as ex:
            modelXbrl.error("testSuiteConverter:unconvertableTestcase",
                            f"Variation {variationFile} {variationElt.get('id')} is not transformable to XF or OIM: {ex}",
                            modelObject=modelXbrl)
            variationElt.getparent().remove(variationElt)
            return {}
    return convertedFiles

def convertTestcase(cntlr, inPath, outPath, testcaseFile):
    testcaseDir = os.path.dirname(testcaseFile)
    indexTree = etree.parse(os.path.join(inPath, testcaseFile))
    # check if an index to testcases
    if indexTree.find("testcases") is not None:
        for testcasesElt in indexTree.iter("testcases"):
            # index to testcases
            testcaseRoot = testcasesElt.get("root")
            if testcaseRoot:
                tcInPath = os.path.join(inPath, testcaseRoot)
                tcOutPath = os.path.join(outPath, testcaseRoot)
            else:
                tcInPath = inPath
                tcOutPath = outPath
            if not os.path.exists(tcOutPath):
                os.mkdir(tcOutPath)
            for testcaseElt in testcasesElt.iter("testcase"):
                convertTestcase(cntlr, tcInPath, tcOutPath, testcaseElt.get("uri"))
    else:
        # testcase file
        convertedFiles = {}
        for variationElt in indexTree.iter("{*}variation"):
            readMeFirstElt = variationElt.find("*/*[@readMeFirst='true']")
            readMeFirstFile = readMeFirstElt.text
            resultInstElt = variationElt.find("{*}result/{*}instance")
            if resultInstElt is not None:
                resultInstFile = resultInstElt.text
            else:
                resultInstFile = None
            if testcaseDir:
                tcInPath = os.path.join(inPath, testcaseDir)
                tcOutPath = os.path.join(outPath, testcaseDir)
            else:
                tcInPath = inPath
                tcOutPath = outPath
            if not os.path.exists(tcOutPath):
                os.mkdir(tcOutPath)
            if os.path.exists(os.path.join(tcInPath, readMeFirstFile)):
                convertedFiles |= convertVariation(cntlr, os.path.basename(testcaseFile), variationElt, tcInPath, tcOutPath, readMeFirstFile, resultInstFile)
        if convertedFiles:
            # update testcase and copy over un-converted files
            if testcaseDir:
                tcInPath = os.path.join(inPath, testcaseDir)
                tcOutPath = os.path.join(outPath, testcaseDir)
            else:
                tcInPath = inPath
                tcOutPath = outPath
            if not os.path.exists(tcOutPath):
                os.mkdir(tcOutPath)
            for elt in indexTree.iter():
                if isinstance(elt.tag, str) and (elt.tag.endswith("schema") or elt.tag.endswith("linkbase") or elt.tag.endswith("instance")):
                    if elt.text in convertedFiles:
                        elt.text = convertedFiles[elt.text]
                    else:
                        srcFile = os.path.join(tcInPath, elt.text)
                        if os.path.exists(srcFile):
                            dstFile = os.path.join(tcOutPath, elt.text)
                            dstdir = os.path.dirname(dstFile)
                            if not os.path.exists(dstdir):
                                os.mkdir(dstdir)
                            shutil.copyfile(srcFile, dstFile)
        tcOutFile = os.path.join(outPath, testcaseFile)
        tcOutDir = os.path.dirname(tcOutFile)
        if not os.path.exists(tcOutDir):
            os.mkdir(tcOutDir)
        with open(tcOutFile, "w", encoding="utf-8") as fh:
            XmlUtil.writexml(fh, indexTree, indent="  ", encoding="utf-8")

def convertSuite(cntlr, options, *args, **kwargs):
    sourceSuiteDir = getattr(options, "sourceTestSuiteDir", None)
    convertedSuiteDir = getattr(options, "convertedTestSuiteDir", None)
    if not os.path.exists(sourceSuiteDir):
        os.mkdir(sourceSuiteDir)
    for testcaseFile in ("index.xml",):
        convertTestcase(cntlr, sourceSuiteDir, convertedSuiteDir, testcaseFile)
        shutil.copyfile(os.path.join(sourceSuiteDir, testcaseFile), os.path.join(convertedSuiteDir, testcaseFile))

def commandLineOptionExtender(parser, *args, **kwargs):
    parser.add_option("--source-test-suite-dir",
                      action="store",
                      dest="sourceTestSuiteDir",
                      help=_("The source directory containing formula linkbase files to convert to XF."))
    parser.add_option("--converted-test-suite-dir",
                      action="store",
                      dest="convertedTestSuiteDir",
                      help=_("The destination directory to save the converted XF files."))

__pluginInfo__ = {
    'name': 'Formula Suite Converter',
    'version': '0.9',
    'description': "Convert XBRL Formula conformance suite to XF.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # use formulaSaver tt output XF and saveLoadableOIM to output json instance
    'import': ('formulaSaver', 'saveLoadableOIM', 'loadFromOIM'),
    # classes of mount points (required)
    'CntlrCmdLine.Options': commandLineOptionExtender,
    'CntlrCmdLine.Utility.Run': convertSuite
}
