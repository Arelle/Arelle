'''
See COPYRIGHT.md for copyright information.
'''
from arelle import ModelDocument, ViewFile
from arelle.ViewUtil import sortCountExpected
import os

def viewTests(modelXbrl, outfile, cols=None):
    modelXbrl.modelManager.showStatus(_("viewing Tests"))
    view = ViewTests(modelXbrl, outfile, cols)
    view.viewTestcaseIndexElement(modelXbrl.modelDocument)
    view.close()

COL_WIDTHS = {
    "Index": 12,
    "Index.1": 12,
    "Index.2": 12,
    "Index.3": 12,
    "Index.4": 12,
    "Testcase": 20,
    "Id": 10,
    "Name": 50,
    "Reference": 20,
    "ReadMeFirst": 20,
    "Status": 8,
    "Expected": 20,
    "Actual": 100}

class ViewTests(ViewFile.View):
    def __init__(self, modelXbrl, outfile, cols):
        super(ViewTests, self).__init__(modelXbrl, outfile, "Tests")
        self.cols = cols

    def viewTestcaseIndexElement(self, modelDocument, parentDocument=None, nestedDepth=0):
        if parentDocument is None: # not a nested testacases index
            self.nestedIndexDepth = 0
            self.xlsxDocNames = []
            self.xlsxTestcase = ""
            if self.cols:
                if isinstance(self.cols,str): self.cols = self.cols.replace(',',' ').split()
                unrecognizedCols = []
                for col in self.cols:
                    if col not in COL_WIDTHS:
                        unrecognizedCols.append(col)
                if unrecognizedCols:
                    self.modelXbrl.error("arelle:unrecognizedTestReportColumn",
                                         _("Unrecognized columns: %(cols)s"),
                                         modelXbrl=self.modelXbrl, cols=','.join(unrecognizedCols))
                if "Period" in self.cols:
                    i = self.cols.index("Period")
                    self.cols[i:i+1] = ["Start", "End/Instant"]
            else:
                self.cols = ["Index"]
                def determineNestedIndexDepth(doc, nestedDepth):
                    if nestedDepth > self.nestedIndexDepth:
                        self.nestedIndexDepth = nestedDepth
                        self.cols.append("Index.{}".format(nestedDepth))
                        self.xlsxDocNames.append("")
                    for referencedDocument in doc.referencesDocument.keys():
                        if referencedDocument.type == ModelDocument.Type.TESTCASESINDEX:
                            determineNestedIndexDepth(referencedDocument, nestedDepth + 1)
                determineNestedIndexDepth(modelDocument, 0)
                self.cols += ["Testcase", "Id"]
                if self.type != ViewFile.XML:
                    self.cols.append("Name")
                    self.xlsxDocNames.append("")
                self.cols += ["ReadMeFirst", "Status", "Expected", "Actual"]

            self.setColWidths([COL_WIDTHS.get(col, 8) for col in self.cols])
            self.addRow(self.cols, asHeader=True)

        if modelDocument.type in (ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.REGISTRY):
            cols = []
            attr = {}
            if self.type in (ViewFile.XLSX, ViewFile.CSV):
                self.xlsxDocName = None
            indexColName = "Index.{}".format(nestedDepth) if nestedDepth else "Index"
            for col in self.cols:
                if col == indexColName:
                    docName = os.path.basename(modelDocument.uri)
                    if parentDocument and os.path.basename(parentDocument.uri) == docName:
                        docName = os.path.basename(os.path.dirname(modelDocument.uri))
                    if self.type in (ViewFile.XLSX, ViewFile.CSV):
                        self.xlsxDocNames[nestedDepth] = docName
                    else:
                        attr["name"] = docName
                    break
                else:
                    cols.append("")
            if self.type not in (ViewFile.XLSX, ViewFile.CSV):
                self.addRow(cols, treeIndent=0, xmlRowElementName="testcaseIndex", xmlRowEltAttr=attr, xmlCol0skipElt=True)
            # sort test cases by uri
            testcases = []
            for referencedDocument, _ref in sorted(modelDocument.referencesDocument.items(),
                                             key=lambda i:i[1].referringModelObject.objectIndex if i[1] else 0):
                if referencedDocument.type in (ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.REGISTRY):
                    self.viewTestcaseIndexElement(referencedDocument, modelDocument, nestedDepth+1)
                else:
                    testcases.append((referencedDocument.uri, referencedDocument.objectId()))
            testcases.sort()
            for testcaseTuple in testcases:
                self.viewTestcase(self.modelXbrl.modelObject(testcaseTuple[1]), 1)
        elif modelDocument.type in (ModelDocument.Type.TESTCASE, ModelDocument.Type.REGISTRYTESTCASE):
            self.viewTestcase(modelDocument, 0)
        else:
            pass

    def viewTestcase(self, modelDocument, indent):
        cols = []
        attr = {}
        docName = os.path.basename(modelDocument.uri)
        if docName == "index.xml":
            docName = os.path.basename(os.path.dirname(modelDocument.uri))
        if self.type in (ViewFile.XLSX, ViewFile.CSV):
            self.xlsxTestcase = os.path.basename(docName)
        for col in self.cols:
            if col == "Testcase":
                if self.type != ViewFile.XML:
                    cols.append(docName)
                else:
                    attr["name"] = os.path.basename(modelDocument.uri)
                break
            else:
                cols.append("")
        if self.type not in (ViewFile.XLSX, ViewFile.CSV):
            self.addRow(cols, treeIndent=indent, xmlRowElementName="testcase", xmlRowEltAttr=attr, xmlCol0skipElt=True)
        for modelTestcaseVariation in getattr(modelDocument, "testcaseVariations", ()):
            self.viewTestcaseVariation(modelTestcaseVariation, indent+1)

    def viewTestcaseVariation(self, modelTestcaseVariation, indent):
        id = modelTestcaseVariation.id
        if id is None:
            id = ""
        cols = []
        attr = {}
        if self.type in (ViewFile.XLSX, ViewFile.CSV):
            cols.extend(self.xlsxDocNames)
            cols.append(self.xlsxTestcase)
            indent = 0 # excel & CSV show all columns to allow filtering
        for col in self.cols:
            if self.type in (ViewFile.XLSX, ViewFile.CSV) and (col.startswith("Index") or col == "Testcase"):
                pass # these columns added above
            elif col == "Id":
                cols.append(id or modelTestcaseVariation.name)
            elif col == "Name":
                if self.type != ViewFile.XML:
                    cols.append(modelTestcaseVariation.description or modelTestcaseVariation.name)
                else:
                    attr["name"] = modelTestcaseVariation.description or modelTestcaseVariation.name
            elif col == "Reference":
                cols.append(modelTestcaseVariation.reference)
            elif col == "ReadMeFirst":
                cols.append(" ".join(str(uri) for uri in modelTestcaseVariation.readMeFirstUris))
            elif col == "Status":
                cols.append(modelTestcaseVariation.status)
            elif col == "Expected":
                _exp = sortCountExpected(modelTestcaseVariation.expected)
                cols.append(", ".join(str(e) for e in _exp) if isinstance(_exp, list) else _exp)
            elif col == "Actual":
                cols.append(", ".join(str(code) for code in modelTestcaseVariation.actual))
            else:
                cols.append("")
        self.addRow(cols, treeIndent=indent, xmlRowElementName="variation", xmlRowEltAttr=attr, xmlCol0skipElt=False)
