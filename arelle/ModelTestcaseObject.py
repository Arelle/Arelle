'''
Created on Oct 5, 2010
Refactored from ModelObject on Jun 11, 2011

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle import XmlUtil, XbrlConst, ModelValue
from arelle.ModelObject import ModelObject

class ModelTestcaseVariation(ModelObject):
    def init(self, modelDocument):
        super().init(modelDocument)
        self.status = ""
        self.actual = []
        self.assertions = None

    @property
    def name(self):
        if self.get("name"):
            return self.get("name")
        nameElement = XmlUtil.descendant(self, None, "name" if self.localName != "testcase" else "number")
        if nameElement is not None:
            return XmlUtil.innerText(nameElement)
        return None

    @property
    def description(self):
        nameElement = XmlUtil.descendant(self, None, "description")
        if nameElement is not None:
            return XmlUtil.innerText(nameElement)
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
            return self._readMeFirstUris
    
    @property
    def parameters(self):
        try:
            return self._parameters
        except AttributeError:
            self._parameters = dict([
                (ModelValue.qname(paramElt, paramElt.get("name")),
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
    def cfcnCall(self):
        # tuple of (expression, element holding the expression)
        try:
            return self._cfcnCall
        except AttributeError:
            self._cfcnCall = None
            for callElement in XmlUtil.descendants(self, XbrlConst.cfcn, "call"):
                self._cfcnCall = (XmlUtil.innerText(callElement), callElement)
                break
            return self._cfcnCall
    
    @property
    def cfcnTest(self):
        # tuple of (expression, element holding the expression)
        try:
            return self._cfcnTest
        except AttributeError:
            self._cfcnTest = None
            testElement = XmlUtil.descendant(self, XbrlConst.cfcn, "test")
            if testElement:
                self._cfcnTest = (testElement.innerText, testElement)
            return self._cfcnTest
    
    @property
    def expected(self):
        if self.localName == "testcase":
            return self.document.basename[:4]   #starts with PASS or FAIL
        errorElement = XmlUtil.descendant(self, None, "error")
        if errorElement is not None:
            return ModelValue.qname(errorElement, XmlUtil.text(errorElement))
        versioningReport = XmlUtil.descendant(self, None, "versioningReport")
        if versioningReport is not None:
            return XmlUtil.text(versioningReport)
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
                    asserTests[atElt.get("assertionID")] = (int(atElt.get("countSatisfied")),int(atElt.get("countNotSatisfied")))
                except ValueError:
                    pass
            if asserTests:
                return asserTests
                
        return None

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
                ("expected", self.expected) if self.expected else (),
                ("actual", " ".join(str(i) for i in self.actual) if len(self.actual) > 0 else ())] + \
                assertions
        
    def __repr__(self):
        return ("modelTestcaseVariation[{0}]{1})".format(self.objectId(),self.propertyView))
