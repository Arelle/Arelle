'''
Created on Oct 5, 2010
Refactored from ModelObject on Jun 11, 2011

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os
from arelle import XmlUtil, XbrlConst, ModelValue
from arelle.ModelObject import ModelObject

class ModelTestcaseVariation(ModelObject):
    def init(self, modelDocument):
        super(ModelTestcaseVariation, self).init(modelDocument)
        self.status = ""
        self.actual = []
        self.assertions = None
        
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
        nameElement = XmlUtil.descendant(self, None, "description")
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
            for anElement in self.iterdescendants():
                if isinstance(anElement,ModelObject) and anElement.get("readMeFirst") == "true":
                    if anElement.get("{http://www.w3.org/1999/xlink}href"):
                        uri = anElement.get("{http://www.w3.org/1999/xlink}href")
                    else:
                        uri = XmlUtil.innerText(anElement)
                    if anElement.get("name"):
                        self._readMeFirstUris.append( (ModelValue.qname(anElement, anElement.get("name")), uri) )
                    elif anElement.get("dts"):
                        self._readMeFirstUris.append( (anElement.get("dts"), uri) )
                    else:
                        self._readMeFirstUris.append(uri)
            if not self._readMeFirstUris:  # provide a dummy empty instance document
                self._readMeFirstUris.append(os.path.join(self.modelXbrl.modelManager.cntlr.configDir, "empty-instance.xml"))
            return self._readMeFirstUris
    
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
        resultInstance = XmlUtil.descendant(XmlUtil.descendant(self, None, "result"), None, "instance")
        if resultInstance is not None:
            return XmlUtil.text(resultInstance)
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
    def cfcnCall(self):
        # tuple of (expression, element holding the expression)
        try:
            return self._cfcnCall
        except AttributeError:
            self._cfcnCall = None
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
        if self.localName == "testcase":
            return self.document.basename[:4]   #starts with PASS or FAIL
        errorElement = XmlUtil.descendant(self, None, "error")
        if errorElement is not None:
            return ModelValue.qname(errorElement, XmlUtil.text(errorElement))
        resultElement = XmlUtil.descendant(self, None, "result")
        if resultElement is not None:
            expected = resultElement.get("expected")
            if expected:
                return expected
            for assertElement in XmlUtil.children(resultElement, None, "assert"):
                num = assertElement.get("num")
                if len(num) == 5:
                    return "EFM.{0}.{1}.{2}".format(num[0],num[1:3],num[3:6])
            asserTests = {}
            for atElt in XmlUtil.children(resultElement, None, "assertionTests"):
                try:
                    asserTests[atElt.get("assertionID")] = (_INT(atElt.get("countSatisfied")),_INT(atElt.get("countNotSatisfied")))
                except ValueError:
                    pass
            if asserTests:
                return asserTests
        elif self.get("result"):
            return self.get("result")
                
        return None

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
