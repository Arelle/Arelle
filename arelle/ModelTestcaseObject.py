'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

import fnmatch
import os, io, logging
from collections import defaultdict
from collections.abc import Generator
from typing import TYPE_CHECKING, Any

from arelle import XmlUtil, XbrlConst, ModelValue
from arelle.PrototypeDtsObject import PrototypeObject
from arelle.XbrlConst import DEFAULT_TARGET
from arelle.conformance.Constants import CONFORMANCE_SUITE_ID_OVERRIDES
from arelle.ModelObject import ModelObject

if TYPE_CHECKING:
    from arelle.FileSource import FileSource
    from arelle.ModelDocument import ModelDocument
    from arelle.ModelValue import QName

TXMY_PKG_SRC_ELTS = ("metadata", "catalog", "taxonomy")


def testcaseVariationsByTarget(testcaseVariations: list[ModelTestcaseVariation]) -> Generator[ModelTestcaseVariation, None, None]:
    for modelTestcaseVariation in testcaseVariations:
        modelTestcaseVariation.errors = None # Errors accumulate over multiple ixdsTargets for same variation
        # The Inline XBRL 1.1 conformance suite defines targets to validate using the `instance`
        # element with a `target` attribute to specify a target name. An absent attribute indicates
        # only the default target should be loaded.
        ixdsTargets = [instElt.get("target")
                      for resultElt in modelTestcaseVariation.iterdescendants("{*}result")
                      for instElt in resultElt.iterdescendants("{*}instance")]
        if ixdsTargets:
            # track status and actual (error codes, counts) across all targets
            allTargetsActual = []
            allTargetsStatus = ""
            for ixdsTarget in ixdsTargets:
                # A blank `target` value in the Inline XBRL 1.1 conformance suite
                # indicates we should only load the default target. Setting `None` results
                # in all targets being loaded, so we must pass DEFAULT_TARGET.
                modelTestcaseVariation.ixdsTarget = DEFAULT_TARGET if ixdsTarget is None else ixdsTarget
                yield modelTestcaseVariation
                allTargetsActual.extend(modelTestcaseVariation.actual)
                if allTargetsStatus not in ("fail", "fail (count)"):
                    # update status unless fail were noted by a prior target of this variation
                    allTargetsStatus = modelTestcaseVariation.status
            modelTestcaseVariation.status = allTargetsStatus
        else: # probably an expected error situation
            # To load all targets in the filing, we provide no value for `ixdsTarget`.
            modelTestcaseVariation.ixdsTarget = None
            yield modelTestcaseVariation

class ModelTestcaseVariation(ModelObject):
    errors: list[str] | None
    userExpectedErrors: list[dict[str, int]]
    _readMeFirstUris: list[str | tuple[QName | str, str]]
    _dataUris: defaultdict[str, list[str]]
    _parameters: dict[QName | None, tuple[QName | None, str | None]]
    _cfcnCall: tuple[str, ModelObject] | None
    _cfcnTest: tuple[str, ModelObject] | None
    _name: str | None
    readMeFirstElements: list[ModelObject | None]

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelTestcaseVariation, self).init(modelDocument)
        self.status: str = ""
        self.duration: float | None = None
        self.actual: list[str] = []
        self.assertions: dict[str, tuple[int, int]] | None = None
        self.ixdsTarget: str | None = None
        self.userExpectedErrors = []

    @property
    def id(self) -> str:
        # if there is a real ID, use it
        id = super(ModelTestcaseVariation, self).id
        if id is not None:
            for overrides in CONFORMANCE_SUITE_ID_OVERRIDES:
                if overrides.pathContainsString in self.modelDocument.filepath:
                    for override in overrides.overrides:
                        if self.modelDocument.filepath.endswith(override.pathSuffix) and id == override.oldId and self.readMeFirstUris == override.readMeFirstUris:
                            return override.newId
            return id
        # no ID, use the object ID so it isn't None
        return self.objectId()

    @property
    def name(self) -> str | None:
        try:
            return self._name
        except AttributeError:
            if self.get("name"):
                self._name = self.get("name")
            else:
                nameElement = XmlUtil.descendant(self, None, "name" if self.localName != "testcase" else "number")
                if nameElement is not None:
                    self._name = XmlUtil.innerText(nameElement)  # type: ignore[arg-type]
                else:
                    self._name = None
            return self._name

    @property
    def description(self) -> str | None:
        nameElement = XmlUtil.descendant(self, None, ("description", "documentation"))
        if nameElement is not None:
            return XmlUtil.innerText(nameElement)  # type: ignore[arg-type]
        return None

    @property
    def reference(self) -> str | None:
        efmNameElts = XmlUtil.children(self.getparent(), None, "name")  # type: ignore[arg-type]
        for efmNameElt in efmNameElts:
            if efmNameElt is not None and efmNameElt.text.startswith("EDGAR"):  # type: ignore[union-attr]
                return efmNameElt.text
        referenceElement = XmlUtil.descendant(self, None, "reference")
        if referenceElement is not None: # formula test suite
            return "{0}#{1}".format(referenceElement.get("specification"), referenceElement.get("id"))
        referenceElement = XmlUtil.descendant(self, None, "documentationReference")
        if referenceElement is not None: # w3c test suite
            return referenceElement.get("{http://www.w3.org/1999/xlink}href")
        descriptionElement = XmlUtil.descendant(self, None, "description")
        if descriptionElement is not None and descriptionElement.get("reference"):
            return descriptionElement.get("reference")  # xdt test suite
        if self.getparent().get("description"):  # type: ignore[union-attr]
            return self.getparent().get("description")  # type: ignore[union-attr] # base spec 2.1 test suite
        functRegistryRefElt = XmlUtil.descendant(self.getparent(), None, "reference")  # type: ignore[arg-type]
        if functRegistryRefElt is not None: # function registry
            return functRegistryRefElt.get("{http://www.w3.org/1999/xlink}href")
        return None

    @property
    def readMeFirstUris(self) -> list[str | tuple[QName | str, str]]:
        try:
            return self._readMeFirstUris
        except AttributeError:
            self._readMeFirstUris = []
            self.readMeFirstElements = []
            # first look if any plugin method to get readme first URIs
            if not any(pluginXbrlMethod(self)
                       for pluginXbrlMethod in self.modelXbrl.modelManager.cntlr.plugins.hooks("ModelTestcaseVariation.ReadMeFirstUris")):  # type: ignore[union-attr]
                if self.localName == "testGroup":  #w3c testcase
                    instanceTestElement = XmlUtil.descendant(self, None, "instanceTest")
                    if instanceTestElement is not None: # take instance first
                        self._readMeFirstUris.append(XmlUtil.descendantAttr(instanceTestElement, None,  # type: ignore[arg-type]
                                                                            "instanceDocument",
                                                                            "{http://www.w3.org/1999/xlink}href"))
                        self.readMeFirstElements.append(instanceTestElement)  # type: ignore[arg-type]
                    else:
                        schemaTestElement = XmlUtil.descendant(self, None, "schemaTest")
                        if schemaTestElement is not None:
                            self._readMeFirstUris.append(XmlUtil.descendantAttr(schemaTestElement, None,  # type: ignore[arg-type]
                                                                                "schemaDocument",
                                                                                "{http://www.w3.org/1999/xlink}href"))
                            self.readMeFirstElements.append(schemaTestElement)  # type: ignore[arg-type]
                elif self.localName == "test-case":  #xpath testcase
                    inputFileElement = XmlUtil.descendant(self, None, "input-file")
                    if inputFileElement is not None: # take instance first
                        self._readMeFirstUris.append(f"TestSources/{inputFileElement.text}.xml")  # type: ignore[union-attr]
                        self.readMeFirstElements.append(inputFileElement)  # type: ignore[arg-type]
                elif self.resultIsTaxonomyPackage:
                    self._readMeFirstUris.append(os.path.join(self.modelDocument.filepathdir, "tests", self.get("name") + ".zip"))  # type: ignore[operator]
                    self.readMeFirstElements.append(self)
                else:
                    # default built-in method for readme first uris
                    for anElement in self.iterdescendants():
                        if isinstance(anElement,ModelObject) and anElement.get("readMeFirst") == "true":
                            if anElement.get("{http://www.w3.org/1999/xlink}href"):
                                uri = anElement.get("{http://www.w3.org/1999/xlink}href")
                            else:
                                uri = XmlUtil.innerText(anElement)
                            if anElement.get("name"):
                                self._readMeFirstUris.append((ModelValue.qname(anElement, anElement.get("name")), uri))  # type: ignore[arg-type]
                                self.readMeFirstElements.append(anElement)
                            elif anElement.get("dts"):
                                self._readMeFirstUris.append((anElement.get("dts"), uri))  # type: ignore[arg-type]
                                self.readMeFirstElements.append(anElement)
                            else:
                                self._readMeFirstUris.append(uri)  # type: ignore[arg-type]
                                self.readMeFirstElements.append(anElement)
            if not self._readMeFirstUris:  # provide a dummy empty instance document
                self._readMeFirstUris.append(os.path.join(self.modelXbrl.modelManager.cntlr.configDir, "empty-instance.xml"))  # type: ignore[union-attr]
                self.readMeFirstElements.append(None)
            return self._readMeFirstUris

    @property
    def dataUris(self) -> defaultdict[str, list[str]]:
        try:
            return self._dataUris
        except AttributeError:
            self._dataUris = defaultdict(list) # may contain instances, schemas, linkbases
            for dataElement in XmlUtil.descendants(self, None, ("data", "input")):
                for elt in XmlUtil.descendants(dataElement, None, ("xsd", "schema", "linkbase", "instance", "taxonomyPackage")):
                    self._dataUris["schema" if elt.localName == "xsd" else elt.localName].append(elt.textValue.strip())  # type: ignore[union-attr]
            return self._dataUris

    @property
    def parameters(self) -> dict[QName | None, tuple[QName | None, str | None]]:
        try:
            return self._parameters
        except AttributeError:
            self._parameters = dict(
                [
                    (
                        ModelValue.qname(paramElt, paramElt.get("name")),
                        # prefix-less parameter names take default namespace of element
                        (
                            ModelValue.qname(paramElt, paramElt.get("datatype")),
                            paramElt.get("value")
                        )
                    )
                    for paramElt in XmlUtil.descendants(self, self.namespaceURI, "parameter")
                ]
            )
            return self._parameters

    @property
    def resultIsVersioningReport(self) -> bool:
        return XmlUtil.descendant(XmlUtil.descendant(self, None, "result"), None, "versioningReport") is not None  # type: ignore[arg-type]

    @property
    def versioningReportUri(self) -> str | None:
        return XmlUtil.text(XmlUtil.descendant(self, None, "versioningReport"))  # type: ignore[arg-type]

    @property
    def resultIsXbrlInstance(self) -> bool:
        return XmlUtil.descendant(XmlUtil.descendant(self, None, "result"), None, "instance") is not None  # type: ignore[arg-type]

    @property
    def resultXbrlInstanceUri(self) -> str | None:
        for pluginXbrlMethod in self.modelXbrl.modelManager.cntlr.plugins.hooks("ModelTestcaseVariation.ResultXbrlInstanceUri"):  # type: ignore[union-attr]
            resultInstanceUri = pluginXbrlMethod(self)
            if resultInstanceUri is not None:
                return resultInstanceUri or None # (empty string returns None)

        for resultElt in self.iterdescendants("{*}result"):
            for instElt in resultElt.iterdescendants("{*}instance"):
                if (instElt.get("target") or DEFAULT_TARGET) == (self.ixdsTarget or DEFAULT_TARGET): # match null and DEFAULT_TARGET
                    return XmlUtil.text(instElt)
        return None

    @property
    def resultIsInfoset(self) -> bool:
        if self.modelDocument.outpath:
            result = XmlUtil.descendant(self, None, "result")
            if result is not None:
                return XmlUtil.child(result, None, "file") is not None or XmlUtil.text(result).endswith(".xml")  # type: ignore[arg-type]
        return False

    @property
    def resultInfosetUri(self) -> str | None:
        result = XmlUtil.descendant(self, None, "result")
        if result is not None:
            child = XmlUtil.child(result, None, "file")  # type: ignore[arg-type]
            return os.path.join(self.modelDocument.outpath, XmlUtil.text(child if child is not None else result))
        return None

    @property
    def resultIsTable(self) -> bool:
        result = XmlUtil.descendant(self, None, "result")
        if result is not None :
            child = XmlUtil.child(result, None, "table")  # type: ignore[arg-type]
            if child is not None and XmlUtil.text(child).endswith(".xml"):
                return True
        return False

    @property
    def resultTableUri(self) -> str | None:
        result = XmlUtil.descendant(self, None, "result")
        if result is not None:
            child = XmlUtil.child(result, None, "table")  # type: ignore[arg-type]
            if child is not None:
                return os.path.join(self.modelDocument.outpath, XmlUtil.text(child))
        return None

    @property
    def resultIsTaxonomyPackage(self) -> bool:
        return any(e.localName for e in XmlUtil.descendants(self,None,TXMY_PKG_SRC_ELTS))  # type: ignore[union-attr]

    @property
    def variationDiscoversDTS(self) -> bool:
        return any(e.localName != "taxonomyPackage" # find any nonTP element (instance, schema, linkbase, etc)
                   for e in self.iterdescendants()
                   if isinstance(e,ModelObject) and e.get("readMeFirst") == "true")

    @property
    def cfcnCall(self) -> tuple[str, ModelObject] | None:
        # tuple of (expression, element holding the expression)
        try:
            return self._cfcnCall
        except AttributeError:
            self._cfcnCall = None
            if self.localName == "test-case":  #xpath testcase
                queryElement = XmlUtil.descendant(self, None, "query")
                if queryElement is not None:
                    filepath = (self.modelDocument.filepathdir + "/" + "Queries/XQuery/" +  # type: ignore[operator]
                                self.get("FilePath") + queryElement.get("name") + ".xq")
                    if os.sep != "/": filepath = filepath.replace("/", os.sep)
                    with io.open(filepath, "rt", encoding="utf-8") as f:
                        self._cfcnCall = (f.read(), self)
            else:
                for callElement in XmlUtil.descendants(self, XbrlConst.cfcn, "call"):
                    self._cfcnCall = (XmlUtil.innerText(callElement), callElement)  # type: ignore[assignment,arg-type]
                    break
            if self._cfcnCall is None and self.namespaceURI == "http://xbrl.org/2011/conformance-rendering/transforms":
                name = self.getparent().get("name")  # type: ignore[union-attr]
                input = self.get("input")
                if name and input:
                    self._cfcnCall =  ("{0}('{1}')".format(name, input.replace("'","''")), self)
            return self._cfcnCall

    @property
    def cfcnTest(self) -> tuple[str, ModelObject] | None:
        # tuple of (expression, element holding the expression)
        try:
            return self._cfcnTest
        except AttributeError:
            self._cfcnTest = None
            if self.localName == "test-case":  #xpath testcase
                outputFileElement = XmlUtil.descendant(self, None, "output-file")
                if outputFileElement is not None and outputFileElement.get("compare") == "Text":
                    filepath = (self.modelDocument.filepathdir + "/" + "ExpectedTestResults/" +  # type: ignore[operator]
                                self.get("FilePath") + outputFileElement.text)  # type: ignore[union-attr]
                    if os.sep != "/": filepath = filepath.replace("/", os.sep)
                    with io.open(filepath, 'rt', encoding='utf-8') as f:
                        self._cfcnTest = ("xs:string($result) eq '{0}'".format(f.read()), self)
            else:
                testElement = XmlUtil.descendant(self, XbrlConst.cfcn, "test")
                if testElement is not None:
                    self._cfcnTest = (XmlUtil.innerText(testElement), testElement)  # type: ignore[assignment,arg-type]
                elif self.namespaceURI == "http://xbrl.org/2011/conformance-rendering/transforms":
                    output = self.get("output")
                    if output:
                        self._cfcnTest =  ("$result eq '{0}'".format(output.replace("'","''")), self)
            return self._cfcnTest

    @property
    def expected(self) -> str | list[QName | str] | dict[str, tuple[int, int]] | None:
        for pluginXbrlMethod in self.modelXbrl.modelManager.cntlr.plugins.hooks("ModelTestcaseVariation.ExpectedResult"):  # type: ignore[union-attr]
            expected = pluginXbrlMethod(self)
            if expected:
                return expected  # type: ignore[no-any-return]
        # default behavior without plugins
        if self.localName == "testcase":
            return self.document.basename[:4]   #starts with PASS or FAIL
        elif self.localName == "testGroup":  #w3c testcase
            instanceTestElement = XmlUtil.descendant(self, None, "instanceTest")
            if instanceTestElement is not None: # take instance first
                return XmlUtil.descendantAttr(instanceTestElement, None, "expected", "validity")  # type: ignore[arg-type]
            else:
                schemaTestElement = XmlUtil.descendant(self, None, "schemaTest")
                if schemaTestElement is not None:
                    return XmlUtil.descendantAttr(schemaTestElement, None, "expected", "validity")  # type: ignore[arg-type]
        resultElement = XmlUtil.descendant(self, None, "result")
        if resultElement is not None:
            expected = resultElement.get("expected")
            if expected and resultElement.get("nonStandardErrorCodes") == "true":
                # if @expected and @nonStandardErrorCodes then use expected instead of error codes
                return expected
        errorElements = XmlUtil.descendants(self, None, "error")
        resultElement = XmlUtil.descendant(self, None, "result")
        if isinstance(errorElements,list) and len(errorElements) > 0:
            errorCodes = []
            for errorElement in errorElements:
                if errorElement.get("nonStandardErrorCodes"):
                    errorCode = errorElement.stringValue
                else:
                    errorCode = ModelValue.qname(errorElement, errorElement.stringValue)
                num = int(errorElement.attr("num") or 1)
                errorCodes.extend([errorCode] * num)
            return errorCodes
        if resultElement is not None:
            if expected:
                return expected  # type: ignore[no-any-return]
            for assertElement in XmlUtil.children(resultElement, None, "assert"):  # type: ignore[arg-type]
                num = assertElement.get("num")  # type: ignore[assignment]
                assert isinstance(num, str)
                if num.startswith("EXG."):
                    return num
                if num == "99999": # inline test, use name as expected
                    return assertElement.get("name")
                if len(num) == 5:
                    return "EFM.{0}.{1}.{2}".format(num[0], num[1:3], num[3:6])
            asserTests: dict[str, tuple[int, int]] = {}
            for atElt in XmlUtil.children(resultElement, None, "assertionTests"):  # type: ignore[arg-type]
                try:
                    asserTests[atElt.get("assertionID")] = (int(atElt.get("countSatisfied")), int(atElt.get("countNotSatisfied")))  # type: ignore[index,arg-type]
                except ValueError:
                    pass
            if asserTests:
                return asserTests
        elif self.get("result"):
            return self.get("result")

        return None

    @property
    def expectedWarnings(self) -> list[str] | None:
        warningElements = XmlUtil.descendants(self, None, "warning")
        if isinstance(warningElements, list) and len(warningElements) > 0:
            warningCodes = []
            for warningElement in warningElements:
                num = int(warningElement.attr("num") or 1)
                warningCodes.extend([warningElement.stringValue] * num)
            return warningCodes
        return None

    @property
    def match(self) -> str | None:
        resultElement = XmlUtil.descendant(self, None, "result")
        if resultElement is None:
            return None
        return resultElement.get('match')

    @property
    def expectedCount(self) -> Any:
        for pluginXbrlMethod in self.modelXbrl.modelManager.cntlr.plugins.hooks("ModelTestcaseVariation.ExpectedCount"):  # type: ignore[union-attr]
            _count = pluginXbrlMethod(self)
            if _count is not None: # ignore plug in if not a plug-in-recognized test case
                return _count
        return None

    @property
    def expectedReportCount(self) -> int | None:
        resultElement = XmlUtil.descendant(self, None, "result")
        if resultElement is None:
            return None
        report_count = resultElement.get('report_count')
        return int(report_count) if report_count is not None else None

    @property
    def severityLevel(self) -> int:
        for pluginXbrlMethod in self.modelXbrl.modelManager.cntlr.plugins.hooks("ModelTestcaseVariation.ExpectedSeverity"):  # type: ignore[union-attr]
            severityLevelName = pluginXbrlMethod(self)
            if severityLevelName: # ignore plug in if not a plug-in-recognized test case
                return logging._checkLevel(severityLevelName)  # type: ignore[no-any-return,attr-defined]
        # default behavior without plugins
        # SEC error cases have <assert severity={err|wrn}>...
        if (XmlUtil.descendant(self, None, "assert", attrName="severity", attrValue="wrn") is not None or
            XmlUtil.descendant(self, None, "result", attrName="severity", attrValue="warning") is not None):
            return logging._checkLevel("WARNING")  # type: ignore[no-any-return,attr-defined]
        return logging._checkLevel("INCONSISTENCY")  # type: ignore[no-any-return,attr-defined]

    @property
    def blockedMessageCodes(self) -> str | None:
        blockedCodesRegex = XmlUtil.descendantAttr(self, None, ("results","result"), "blockedMessageCodes")  # type: ignore[arg-type] # DQC 4/5 test suite
        if not blockedCodesRegex:
            ignoredCodes = XmlUtil.descendants(self, None, "ignore-error") # ESEF test suite
            if ignoredCodes:
                blockedCodesRegex = "|".join(".*" + c.stringValue for c in ignoredCodes)  # type: ignore[union-attr]
        return blockedCodesRegex

    @property
    def expectedVersioningReport(self) -> None:
        XmlUtil.text(XmlUtil.text(XmlUtil.descendant(XmlUtil.descendant(self, None, "result"), None, "versioningReport")))  # type: ignore[arg-type]

    @property
    def propertyView(self) -> list[tuple[str, str | None]]:  # type: ignore[override]
        assertions = []
        for assertionElement in XmlUtil.descendants(self, None, "assertionTests"):
            assertions.append(("assertion",assertionElement.get("assertionID")))
            assertions.append(("   satisfied", assertionElement.get("countSatisfied")))
            assertions.append(("   not sat.", assertionElement.get("countNotSatisfied")))
        '''
        for assertionElement in XmlUtil.descendants(self, None, "assert"):
            efmNum = assertionElement.get("num")
            assertions.append(("assertion",
                               "EFM.{0}.{1}.{2}".format(efmNum[0], efmNum[1:2], efmNum[3:4])))
            assertions.append(("   not sat.", "1"))
        '''
        readMeFirsts = [("readFirst", readMeFirstUri) for readMeFirstUri in self.readMeFirstUris]
        parameters = []
        if len(self.parameters) > 0: parameters.append(("parameters", None))
        for pName, pTypeValue in self.parameters.items():
            parameters.append((pName, pTypeValue[1]))  # type: ignore[arg-type]
        return [("id", self.id),  # type: ignore[return-value]
                ("name", self.name),
                ("description", self.description)] + \
                readMeFirsts + \
                parameters + \
               [("status", self.status),
                ("call", self.cfcnCall[0]) if self.cfcnCall else (),
                ("test", self.cfcnTest[0]) if self.cfcnTest else (),
                ("infoset", self.resultInfosetUri) if self.resultIsInfoset else (),
                ("expected", self.expected) if self.expected else (),
                ("actual", " ".join(str(i) for i in self.actual) if len(self.actual) > 0 else ())] + \
                assertions

    def __repr__(self) -> str:
        return "modelTestcaseVariation[{0}]{1})".format(self.objectId(), self.propertyView)

    def setUserExpectedErrors(self, testcaseExpectedErrors: dict[str, dict[str, int]], useFileSource: FileSource | None) -> list[dict[str, int]]:
        indexPath = self.document.filepath
        if useFileSource is not None and useFileSource.isZip:
            baseZipFile = useFileSource.basefile
            if indexPath.startswith(baseZipFile):  # type: ignore[arg-type]
                indexPath = indexPath[len(baseZipFile) + 1:]  # type: ignore[arg-type]
            indexPath = indexPath.replace("\\", "/")
        variationIdPath = f'{indexPath}:{self.id}'
        userExpectedErrors: list[dict[str, int]] = []
        for userPattern, userErrors in testcaseExpectedErrors.items():
            if fnmatch.fnmatch(variationIdPath, userPattern):
                userExpectedErrors.extend(userErrors)  # type: ignore[arg-type]
        self.userExpectedErrors = userExpectedErrors
        return userExpectedErrors
