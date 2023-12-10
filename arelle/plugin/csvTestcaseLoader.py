"""
See COPYRIGHT.md for copyright information.

## Overview

This plugin determines whether the subject file is a CSV testcase file,
and if so returns a ModelDocument with ModelTestcaseObjects as if loaded from xml

Note: please add expected testcase error xmlns elements to testcaseElementXml below

"""

import csv, io, os
from lxml import etree
from arelle.ModelDocument import Type, create as createModelDocument
from arelle.ModelTestcaseObject import ModelTestcaseVariation
from arelle.ModelValue import qname
from arelle.Version import authorLabel, copyrightLabel
from arelle import XmlUtil

testNS = "http://xbrl.org/2005/conformance"
testcaseElementXml = '''<testcase
  xmlns="http://xbrl.org/2005/conformance"
  xmlns:calc11e="https://xbrl.org/2023/calculation-1.1/error"
  xmlns:enumie="http://xbrl.org/2014/extensible-enumerations/instance-errors"
  xmlns:enumte="http://xbrl.org/2014/extensible-enumerations/taxonomy-errors"
  xmlns:enum2ie="http://xbrl.org/2020/extensible-enumerations-2.0/instance-errors"
  xmlns:enum2te="http://xbrl.org/2020/extensible-enumerations-2.0/taxonomy-errors"
  xmlns:err="http://www.w3.org/2005/xqt-errors"
  xmlns:oime="http://www.xbrl.org/2021/oim/error"
  xmlns:oimce="https://xbrl.org/2021/oim-common/error"
  xmlns:rpe="https://xbrl.org/2023/report-package/error"
  xmlns:tpe="http://xbrl.org/2016/taxonomy-package/errors"
  xmlns:xbrlce="https://xbrl.org/2021/xbrl-csv/error"
  xmlns:xbrlje="https://xbrl.org/2021/xbrl-json/error"
  xmlns:xbrlxe="https://xbrl.org/2021/xbrl-xml/error"
  xmlns:xbrldie="http://xbrl.org/2005/xbrldi/errors"
  xmlns:xbrldte="http://xbrl.org/2005/xbrldt/errors"
  xmlns:xmlSchema="http://www.xbrl.org/2005/genericXmlSchemaError"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-taxonomyPackage"
  xmlns:utre=http://www.xbrl.org/2009/utr/errors"
  xsi:schemaLocation="http://xbrl.org/2005/conformance https://www.xbrl.org/2005/conformance.xsd"
/>'''

def csvTestcaseLoader(modelXbrl, mappedUri, filepath, *args, **kwargs):
    doc = None
    testcase = None
    try:
        _file = modelXbrl.fileSource.file(filepath, encoding='utf-8-sig')[0]
        for rowIndex, row in enumerate(csv.reader(_file, "excel")):
            if rowIndex == 0:
                if row != ["input", "errors" , "report_count", "description"]:
                    break # not a CSV testcase file
                modelXbrl.modelDocument = doc = createModelDocument(
                  modelXbrl,
                  Type.TESTCASE,
                  filepath,
                  isEntry=True,
                  initialComment="extracted from CSV Testcase {}".format(mappedUri),
                  documentEncoding="utf-8",
                  base=modelXbrl.entryLoadingUrl,
                  initialXml=testcaseElementXml
                )
                testcase = doc.xmlRootElement    
            else:
                input, errors, report_count, description = row
                id = os.path.splitext(input)[0]
                var = XmlUtil.addChild(testcase, qname(testNS, "variation"), attributes={"id": id, "name":id})
                XmlUtil.addChild(var, qname(testNS, "description"), text=description)
                # guess at data element type
                if input.endswith(".xs") or input.endswith(".xsd"):
                    dataElt = "schema" 
                elif input.endswith(".xbrl"):
                    dataElt = "instance"
                elif input.endswith(".zip"):
                    dataElt = "taxonomyPackage"
                else: # doesn't matter between instance and linkbase
                    dataElt = "instance"
                XmlUtil.addChild(XmlUtil.addChild(var, qname(testNS, "data")),
                                 qname(testNS, dataElt), text=input, attributes={"readMeFirst": "true"})
                result = XmlUtil.addChild(var, qname(testNS, "result"))
                for error in errors.split():
                    XmlUtil.addChild(result, qname(testNS, "error"), text=error)
        if testcase is not None:
            doc.testcaseDiscover(testcase, modelXbrl.modelManager.validateTestcaseSchema)

    except csv.Error as ex:
        error("arelle:testcaseCsvError", str(ex), href=filepath, **kwargs)
    except Exception as ex:
        error("arelle:testcaseException", str(ex), href=filepath, **kwargs)
        
    return doc

def isCsvTestcase(modelXbrl, mappedUri, normalizedUri, filepath, **kwargs):
    if filepath.endswith(".csv"):
        with io.open(filepath, 'rt', encoding='utf-8') as f:
            _fileStart = f.read(256)
            if _fileStart.startswith("input,errors,report_count,description"):
                return True
    return False

__pluginInfo__ = {
    'name': 'Load CSV Testcase',
    'version': '1.0',
    'description': "This plug-in loads XBRL instance data from a CSV testcase.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'ModelDocument.IsPullLoadable': isCsvTestcase,
    'ModelDocument.PullLoader': csvTestcaseLoader
}
