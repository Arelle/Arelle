'''
See COPYRIGHT.md for copyright information.
'''
import os, io, logging
from collections import defaultdict
from arelle import XmlUtil, XbrlConst, ModelValue
from arelle.ModelObject import ModelObject
from arelle.PluginManager import pluginClassMethods

TXMY_PKG_SRC_ELTS = ("metadata", "catalog", "taxonomy")


def testcaseVariationsByTarget(testcaseVariations):
    for modelTestcaseVariation in testcaseVariations:
        modelTestcaseVariation.errors = None # Errors accumulate over multiple ixdsTargets for same variation
        ixdsTargets = [instElt.get("target")
                      for resultElt in modelTestcaseVariation.iterdescendants("{*}result")
                      for instElt in resultElt.iterdescendants("{*}instance")]
        if ixdsTargets:
            # track status and actual (error codes, counts) across all targets
            allTargetsActual = []
            allTargetsStatus = ""
            for ixdsTarget in ixdsTargets:
                modelTestcaseVariation.ixdsTarget = ixdsTarget
                yield modelTestcaseVariation
                allTargetsActual.extend(modelTestcaseVariation.actual)
                if allTargetsStatus not in ("fail", "fail (count)"):
                    # update status unless fail were noted by a prior target of this variation
                    allTargetsStatus = modelTestcaseVariation.status
            modelTestcaseVariation.status = allTargetsStatus
        else: # probably an expected error situation
            modelTestcaseVariation.ixdsTarget = None
            yield modelTestcaseVariation

class ModelTestcaseVariation(ModelObject):
    def init(self, modelDocument):
        super(ModelTestcaseVariation, self).init(modelDocument)
        self.status = ""
        self.duration: float | None = None
        self.actual = []
        self.assertions = None
        self.ixdsTarget = None

    @property
    def id(self):
        # if there is a real ID, use it
        id = super(ModelTestcaseVariation, self).id
        if id is not None:
            return id
        # no ID, use the object ID so it isn't None
        return self.objectId()

    @property
    def name(self):
        try:
            return self._name
        except AttributeError:
            if self.get("name"):
                self._name = self.get("name")
            else:
                nameElement = XmlUtil.descendant(self, None, "name" if self.localName != "testcase" else "number")
                if nameElement is not None:
                    self._name = XmlUtil.innerText(nameElement)
                else:
                    self._name = None
            return self._name

    @property
    def description(self):
        nameElement = XmlUtil.descendant(self, None, ("description", "documentation"))
        if nameElement is not None:
            return XmlUtil.innerText(nameElement)
        return None

    @property
    def reference(self):
        efmNameElts = XmlUtil.children(self.getparent(), None, "name")
        for efmNameElt in efmNameElts:
            if efmNameElt is not None and efmNameElt.text.startswith("EDGAR"):
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
        if self.getparent().get("description"):
            return self.getparent().get("description")  # base spec 2.1 test suite
        functRegistryRefElt = XmlUtil.descendant(self.getparent(), None, "reference")
        if functRegistryRefElt is not None: # function registry
            return functRegistryRefElt.get("{http://www.w3.org/1999/xlink}href")
        return None

    @property
    def readMeFirstUris(self):
        try:
            return self._readMeFirstUris
        except AttributeError:
            self._readMeFirstUris = []
            self.readMeFirstElements = []
            # first look if any plugin method to get readme first URIs
            if not any(pluginXbrlMethod(self)
                       for pluginXbrlMethod in pluginClassMethods("ModelTestcaseVariation.ReadMeFirstUris")):
                if self.localName == "testGroup":  #w3c testcase
                    instanceTestElement = XmlUtil.descendant(self, None, "instanceTest")
                    if instanceTestElement is not None: # take instance first
                        self._readMeFirstUris.append(XmlUtil.descendantAttr(instanceTestElement, None,
                                                                            "instanceDocument",
                                                                            "{http://www.w3.org/1999/xlink}href"))
                        self.readMeFirstElements.append(instanceTestElement)
                    else:
                        schemaTestElement = XmlUtil.descendant(self, None, "schemaTest")
                        if schemaTestElement is not None:
                            self._readMeFirstUris.append(XmlUtil.descendantAttr(schemaTestElement, None,
                                                                                "schemaDocument",
                                                                                "{http://www.w3.org/1999/xlink}href"))
                            self.readMeFirstElements.append(schemaTestElement)
                elif self.localName == "test-case":  #xpath testcase
                    inputFileElement = XmlUtil.descendant(self, None, "input-file")
                    if inputFileElement is not None: # take instance first
                        self._readMeFirstUris.append("TestSources/" + inputFileElement.text + ".xml")
                        self.readMeFirstElements.append(inputFileElement)
                elif self.resultIsTaxonomyPackage:
                    self._readMeFirstUris.append( os.path.join(self.modelDocument.filepathdir, "tests", self.get("name") + ".zip") )
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
                                self._readMeFirstUris.append( (ModelValue.qname(anElement, anElement.get("name")), uri) )
                                self.readMeFirstElements.append(anElement)
                            elif anElement.get("dts"):
                                self._readMeFirstUris.append( (anElement.get("dts"), uri) )
                                self.readMeFirstElements.append(anElement)
                            else:
                                self._readMeFirstUris.append(uri)
                                self.readMeFirstElements.append(anElement)
            if not self._readMeFirstUris:  # provide a dummy empty instance document
                self._readMeFirstUris.append(os.path.join(self.modelXbrl.modelManager.cntlr.configDir, "empty-instance.xml"))
                self.readMeFirstElements.append(None)
            return self._readMeFirstUris

    @property
    def dataUris(self):
        try:
            return self._dataUris
        except AttributeError:
            self._dataUris = defaultdict(list) # may contain instances, schemas, linkbases
            for dataElement in XmlUtil.descendants(self, None, ("data", "input")):
                for elt in XmlUtil.descendants(dataElement, None, ("xsd", "schema", "linkbase", "instance")):
                    self._dataUris["schema" if elt.localName == "xsd" else elt.localName].append(elt.textValue.strip())
            return self._dataUris

    @property
    def parameters(self):
        try:
            return self._parameters
        except AttributeError:
            self._parameters = dict([
                (ModelValue.qname(paramElt, paramElt.get("name")), # prefix-less parameter names take default namespace of element
                 (ModelValue.qname(paramElt, paramElt.get("datatype")),paramElt.get("value")))
                for paramElt in XmlUtil.descendants(self, self.namespaceURI, "parameter")])
            return self._parameters

    @property
    def resultIsVersioningReport(self):
        return XmlUtil.descendant(XmlUtil.descendant(self, None, "result"), None, "versioningReport") is not None

    @property
    def versioningReportUri(self):
        return XmlUtil.text(XmlUtil.descendant(self, None, "versioningReport"))

    @property
    def resultIsXbrlInstance(self):
        return XmlUtil.descendant(XmlUtil.descendant(self, None, "result"), None, "instance") is not None

    @property
    def resultXbrlInstanceUri(self):
        for pluginXbrlMethod in pluginClassMethods("ModelTestcaseVariation.ResultXbrlInstanceUri"):
            resultInstanceUri = pluginXbrlMethod(self)
            if resultInstanceUri is not None:
                return resultInstanceUri or None # (empty string returns None)

        for resultElt in self.iterdescendants("{*}result"):
            for instElt in resultElt.iterdescendants("{*}instance"):
                if (instElt.get("target") or "") == (self.ixdsTarget or ""): # match null and emptyString
                    return XmlUtil.text(instElt)
        return None

    @property
    def resultIsInfoset(self):
        if self.modelDocument.outpath:
            result = XmlUtil.descendant(self, None, "result")
            if result is not None:
                return XmlUtil.child(result, None, "file") is not None or XmlUtil.text(result).endswith(".xml")
        return False

    @property
    def resultInfosetUri(self):
        result = XmlUtil.descendant(self, None, "result")
        if result is not None:
            child = XmlUtil.child(result, None, "file")
            return os.path.join(self.modelDocument.outpath, XmlUtil.text(child if child is not None else result))
        return None

    @property
    def resultIsTable(self):
        result = XmlUtil.descendant(self, None, "result")
        if result is not None :
            child = XmlUtil.child(result, None, "table")
            if child is not None and XmlUtil.text(child).endswith(".xml"):
                return True
        return False

    @property
    def resultTableUri(self):
        result = XmlUtil.descendant(self, None, "result")
        if result is not None:
            child = XmlUtil.child(result, None, "table")
            if child is not None:
                return os.path.join(self.modelDocument.outpath, XmlUtil.text(child))
        return None

    @property
    def resultIsTaxonomyPackage(self):
        return any(e.localName for e in XmlUtil.descendants(self,None,TXMY_PKG_SRC_ELTS))

    @property
    def variationDiscoversDTS(self):
        return any(e.localName != "taxonomyPackage" # find any nonTP element (instance, schema, linkbase, etc)
                   for e in self.iterdescendants()
                   if isinstance(e,ModelObject) and e.get("readMeFirst") == "true")

    @property
    def cfcnCall(self):
        # tuple of (expression, element holding the expression)
        try:
            return self._cfcnCall
        except AttributeError:
            self._cfcnCall = None
            if self.localName == "test-case":  #xpath testcase
                queryElement = XmlUtil.descendant(self, None, "query")
                if queryElement is not None:
                    filepath = (self.modelDocument.filepathdir + "/" + "Queries/XQuery/" +
                                self.get("FilePath") + queryElement.get("name") + '.xq')
                    if os.sep != "/": filepath = filepath.replace("/", os.sep)
                    with io.open(filepath, 'rt', encoding='utf-8') as f:
                        self._cfcnCall = (f.read(), self)
            else:
                for callElement in XmlUtil.descendants(self, XbrlConst.cfcn, "call"):
                    self._cfcnCall = (XmlUtil.innerText(callElement), callElement)
                    break
            if self._cfcnCall is None and self.namespaceURI == "http://xbrl.org/2011/conformance-rendering/transforms":
                name = self.getparent().get("name")
                input = self.get("input")
                if name and input:
                    self._cfcnCall =  ("{0}('{1}')".format(name, input.replace("'","''")), self)
            return self._cfcnCall

    @property
    def cfcnTest(self):
        # tuple of (expression, element holding the expression)
        try:
            return self._cfcnTest
        except AttributeError:
            self._cfcnTest = None
            if self.localName == "test-case":  #xpath testcase
                outputFileElement = XmlUtil.descendant(self, None, "output-file")
                if outputFileElement is not None and outputFileElement.get("compare") == "Text":
                    filepath = (self.modelDocument.filepathdir + "/" + "ExpectedTestResults/" +
                                self.get("FilePath") + outputFileElement.text)
                    if os.sep != "/": filepath = filepath.replace("/", os.sep)
                    with io.open(filepath, 'rt', encoding='utf-8') as f:
                        self._cfcnTest = ("xs:string($result) eq '{0}'".format(f.read()), self)
            else:
                testElement = XmlUtil.descendant(self, XbrlConst.cfcn, "test")
                if testElement is not None:
                    self._cfcnTest = (XmlUtil.innerText(testElement), testElement)
                elif self.namespaceURI == "http://xbrl.org/2011/conformance-rendering/transforms":
                    output = self.get("output")
                    if output:
                        self._cfcnTest =  ("$result eq '{0}'".format(output.replace("'","''")), self)
            return self._cfcnTest

    @property
    def expected(self):
        for pluginXbrlMethod in pluginClassMethods("ModelTestcaseVariation.ExpectedResult"):
            expected = pluginXbrlMethod(self)
            if expected:
                return expected
        # default behavior without plugins
        if self.localName == "testcase":
            return self.document.basename[:4]   #starts with PASS or FAIL
        elif self.localName == "testGroup":  #w3c testcase
            instanceTestElement = XmlUtil.descendant(self, None, "instanceTest")
            if instanceTestElement is not None: # take instance first
                return XmlUtil.descendantAttr(instanceTestElement, None, "expected", "validity")
            else:
                schemaTestElement = XmlUtil.descendant(self, None, "schemaTest")
                if schemaTestElement is not None:
                    return XmlUtil.descendantAttr(schemaTestElement, None, "expected", "validity")
        resultElement = XmlUtil.descendant(self, None, "result")
        if resultElement is not None:
            expected = resultElement.get("expected")
            if expected and resultElement.get("nonStandardErrorCodes") == "true":
                # if @expected and @nonStandardErrorCodes then use expected instead of error codes
                return expected
        errorElements = XmlUtil.descendants(self, None, "error")
        resultElement = XmlUtil.descendant(self, None, "result")
        if isinstance(errorElements,list) and len(errorElements) > 0:
            return [ModelValue.qname(e, e.stringValue) if not e.get("nonStandardErrorCodes")
                    else e.stringValue
                    for e in errorElements]
        #else:
        #    errorElement = errorElements[1]
        #    if errorElement is not None and not errorElement.get("nonStandardErrorCodes"):
        #        _errorText = XmlUtil.text(errorElement)
        #        if ' ' in _errorText: # list of tokens
        #            return _errorText
        #        return ModelValue.qname(errorElement, _errorText)  # turn into a QName
        if resultElement is not None:
            if expected:
                return expected
            for assertElement in XmlUtil.children(resultElement, None, "assert"):
                num = assertElement.get("num")
                if num == "99999": # inline test, use name as expected
                    return assertElement.get("name")
                if len(num) == 5:
                    return "EFM.{0}.{1}.{2}".format(num[0],num[1:3],num[3:6])
            asserTests = {}
            for atElt in XmlUtil.children(resultElement, None, "assertionTests"):
                try:
                    asserTests[atElt.get("assertionID")] = (int(atElt.get("countSatisfied")),int(atElt.get("countNotSatisfied")))
                except ValueError:
                    pass
            if asserTests:
                return asserTests
        elif self.get("result"):
            return self.get("result")

        return None

    @property
    def expectedCount(self):
        for pluginXbrlMethod in pluginClassMethods("ModelTestcaseVariation.ExpectedCount"):
            _count = pluginXbrlMethod(self)
            if _count is not None: # ignore plug in if not a plug-in-recognized test case
                return _count
        return None


    @property
    def severityLevel(self):
        for pluginXbrlMethod in pluginClassMethods("ModelTestcaseVariation.ExpectedSeverity"):
            severityLevelName = pluginXbrlMethod(self)
            if severityLevelName: # ignore plug in if not a plug-in-recognized test case
                return logging._checkLevel(severityLevelName)
        # default behavior without plugins
        # SEC error cases have <assert severity={err|wrn}>...
        if (XmlUtil.descendant(self, None, "assert", attrName="severity", attrValue="wrn") is not None or
            XmlUtil.descendant(self, None, "result", attrName="severity", attrValue="warning") is not None):
            return logging._checkLevel("WARNING")
        return logging._checkLevel("INCONSISTENCY")

    @property
    def blockedMessageCodes(self):
        blockedCodesRegex = XmlUtil.descendantAttr(self, None, ("results","result"), "blockedMessageCodes") # DQC 4/5 test suite
        if not blockedCodesRegex:
            ignoredCodes = XmlUtil.descendants(self, None, "ignore-error") # ESEF test suite
            if ignoredCodes:
                blockedCodesRegex = "|".join(".*" + c.stringValue for c in ignoredCodes)
        return blockedCodesRegex

    @property
    def expectedVersioningReport(self):
        XmlUtil.text(XmlUtil.text(XmlUtil.descendant(XmlUtil.descendant(self, None, "result"), None, "versioningReport")))

    @property
    def propertyView(self):
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
            parameters.append((pName,pTypeValue[1]))
        return [("id", self.id),
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

    def __repr__(self):
        return ("modelTestcaseVariation[{0}]{1})".format(self.objectId(),self.propertyView))
