"""
See COPYRIGHT.md for copyright information.

## Overview

THIS IS A PROOF OF CONCEPT DEMO AND NOT INTENDED FOR PRODUCTION OR FUTURE USE

THE TEMPLATE FILE IMPLEMENTATION HERE IS JUST FOR AMUSEMENT

Reference ISO 32000-2, section 14.7.5 Structure content, or PDF/A accessibility tagging tools

The Load From PDF plugin is designed for PDF/A reports with structural tagged PDF content to:
  a) stand alone convert reports with PDF/A with a OIM-json template into OIM JSON syntax
  b) load reports intp Arelle from PDF/A that contain structural tagged PDF content

An unstructured PDF file can be converted to a PDF/A structurally tagged file (with accessiblity
tags that allow giving an ID to each structural item):

   by tools such as Acrobat using accessibility preparation
   by libraries such as Python autotaggers for tables such as
      https://github.com/pdfix/pdfix-autotag-deepdoctection

Only StructTree nodes which have IDs, and form fields with IDs, are available to be loaded.

## Key Features

An xBRL-JSON template file is provided for each tagged PDF/A with inline XBRL.
   a) as an embedded file "ix.json" in the PDF or
   b) as a sibling file to the pdf named ix-template.json"

   The template file facts which are to receive contents from the pdf have @value missing and
   instead pdfIdRefs which is a list of space-separated IDs of structural node IDs and form field IDs
   which are space-contenated to form the value for the output xBRL-JSON file.  (Suggested
   enhancement for numeric facts includes adding transform, scale and sign.)

   The output file is named with .pdf replaced by .json.

## Usage Instructions

### Command Line Usage

- **Stand alone convert pdf/a + template json into xBRL-JSON*:
  python loadFromPDF.py {pdfFilePath}
  argument --debug will list out, by pdf ID, all the structural nodes available for pdfIdRef'ing
                    and all the form fields by their field ID for pdfIdRef'ing



- **Load OIM Report**:
  To load an OIM report, specify the file path to the JSON, CSV, or XLSX file:
  ```bash
  python arelleCmdLine.py --plugins loadFromPDF --file filing-document.json
  ```

- **Save xBRL-XML Instance**:  <<FEATURE NOT READY>>
  Use the `--saveOIMinstance` argument to save an xBRL-XML instance from an OIM report:
  ```bash
  python arelleCmdLine.py --plugins loadFromPDF --file filing-document.json
  ```

### GUI Usage

* **Load PDF Report**: <<FEATURE NOT READY>>
  1. Using the normal `File` menu `Open File...` dialog, select the PDF/A file, or
  2. Using this module as a main program, save the value-enhanced inline source.
"""
from pikepdf import Pdf, Dictionary, Array, Stream, Operator, parse_content_stream, unparse_content_stream
from collections import defaultdict
import sys, os, json

try:
    from arelle.Version import authorLabel, copyrightLabel
except ImportError:
    authorLabel = 'Workiva, Inc.'
    copyrightLabel = '(c) Copyright 2011-present Workiva, Inc., All rights reserved.'


def loadFromPDF(cntlr, error, warning, modelXbrl, filepath, mappedUri, debug, saveJson):

    pdf = Pdf.open(filepath)

    markedContents = defaultdict(list)

    # load marked content (structured paragraph and section strings
    for p, page in enumerate(pdf.pages):
        mcid = None
        txt = []
        instructions = parse_content_stream(page, "BDC Tj TJ EMC ")
        for i in instructions:
            if i.operator == Operator("BDC") and i.operands[0] == "/P" and "/MCID" in i.operands[1]:
                mcid = i.operands[1]["/MCID"] # start of marked content
            elif i.operator == Operator("EMC") and mcid is not None:
                #print(f"pg {p} mcid {mcid} tj {''.join(txt)}")
                markedContents[p,mcid] = ''.join(txt)
                mcid = None # end of this marked content
                txt = []
            elif i.operator == Operator("Tj"):
                for s in i.operands:
                    txt.append(str(s))
            elif i.operator == Operator("TJ"):
                for a in i.operands:
                    for s in a:
                        if isinstance(s, int):
                            txt.append(" ") # not performing micro-spacing
                        else:
                            txt.append(str(s))

    # load text blocks from structTree fields with IDs
    textBlocks = {}

    def loadTextBlocks(obj, pdfId="", key="", indent="", page=None):
        if isinstance(obj, (Array, list, tuple)):
            for v in obj:
                loadTextBlocks(v, pdfId, key, indent + "  ")
        elif isinstance(obj, (Stream, Dictionary, dict)):
            if "/ID" in obj:
                pdfId = str(obj["/ID"])
            if "/Pg" in obj:
                page = None
                c = obj["/Pg"]["/Contents"]
                for p, _page in enumerate(pdf.pages):
                    if c == _page["/Contents"]:
                        page = p
                        break
            for k, v in obj.items():
                if k not in ("/IDTree", "/P", "/Parent", "/Pg", "/Ff", "/Mk", "/Q", "/Rect", "/Font", "/Type", "/ColorSpace", "/MediaBox", "/Resources", "/Matrix", "/BBox", "/Border", "/DA", "/Length"):
                    loadTextBlocks(v, pdfId, k, indent + "  ", page)
        elif key == "/K":
            if pdfId:
                if (page, obj) in markedContents:
                    markedContent = markedContents[page,obj]
                    if pdfId in textBlocks:
                        textBlocks[pdfId] += "\n" + markedContent
                    else:
                        textBlocks[pdfId] = markedContent

    loadTextBlocks(pdf.Root["/StructTreeRoot"])

    # load form fields by IDs
    formFields = {}

    def loadFormFields(obj, pdfId="", key="", indent=""):
        if isinstance(obj, (Array, list, tuple)):
            for v in obj:
                loadFormFields(v, pdfId, key, indent + "  ")
        elif isinstance(obj, (Stream, Dictionary, dict)):
            if "/T" in obj:
                pdfId = obj["/T"]
            for k, v in obj.items():
                if k not in ("/IDTree", "/P", "/Parent", "/Pg", "/Ff", "/Mk", "/Q", "/Rect", "/Font", "/Type", "/ColorSpace", "/MediaBox", "/Resources", "/Matrix", "/BBox", "/Border", "/DA", "/Length"):
                    loadFormFields(v, pdfId, k, indent + "  ")
        elif key == "/V":
            if pdfId:
                formFields[str(pdfId)] = str(obj)

    loadFormFields(pdf.Root["/AcroForm"]["/Fields"])

    # at this point we have textBlocks and formFields by id
    if debug:
        print(f"text blocks:\n{os.linesep.join(k + ': ' + v for k,v in textBlocks.items())}")
        print(f"form fields:\n{os.linesep.join(k + ': ' + v for k,v in formFields.items())}")

    # read attached ix.jsonl for inline specifications
    oimFile = None
    if "ix.json" in pdf.attachments:
        oimFile = pdf.attachments['ix.json'].get_file()
    else:
        jsonTemplateFile = os.path.join(os.path.dirname(filepath), "ix-template.json")
        if os.path.exists(jsonTemplateFile):
            oimFile = open(jsonTemplateFile, mode="r")
    if oimFile:
        oimObject = json.load(oimFile)
        # replace fact pdfIdRefs with strings
        for oimFactId, fact in oimObject.get("facts", {}).items():
            if "pdfIdRefs" in fact:
                continTexts = []
                for pdfId in fact["pdfIdRefs"].split():
                    if pdfId in textBlocks:
                        continTexts.append(textBlocks[pdfId])
                    if pdfId in formFields:
                        continTexts.append(formFields[pdfId])
                fact["value"] = " ".join(continTexts)
                fact.pop("pdfIdRefs")
        if saveJson:
            json.dump(oimObject, open(filepath.replace(".pdf", ".json"),"w"), indent=2)


# arelle integration methods TBD


lastFilePath = lastFilePathIsPDF = None

def isPdfLoadable(modelXbrl, mappedUri, normalizedUri, filepath, **kwargs):
    global lastFilePath, lastFilePathIsPDF
    lastFilePath = filepath
    lastFilePathIsPDF = False
    _ext = os.path.splitext(filepath)[1]
    if _ext in (".pdf",):
        lastFilePathIsOIM = True
    elif isHttpUrl(normalizedUri) and '?' in _ext: # query parameters and not .pdf, may be PDF anyway
        with io.open(filepath, 'rt', encoding='utf-8') as f:
            _fileStart = f.read(256)
        if _fileStart and re_match(r"%PDF-(1\.[67]|2.[0])", _fileStart):
            lastFilePathIsPDF = True
    return lastFilePathIsPDF

def pdfLoader(modelXbrl, mappedUri, filepath, *args, **kwargs):
    if filepath != lastFilePath or not lastFilePathIsOIM:
        return None # not an OIM file

    cntlr = modelXbrl.modelManager.cntlr
    cntlr.showStatus(_("Loading OIM file: {0}").format(os.path.basename(filepath)))
    doc = loadFromOIM(cntlr, modelXbrl.error, modelXbrl.warning, modelXbrl, filepath, mappedUri)
    if doc is None:
        return None # not a PDF file
    modelXbrl.loadedFromPDF = True
    modelXbrl.loadedFromPDfErrorCount = len(modelXbrl.errors)
    return doc

def fileSourceFile(cntlr, filepath, binary, stripDeclaration):
    modelManager = cntlr.modelManager
    if filepath == 'ix.json':
        return # open handle to file
    return None

def fileSourceExists(cntlr, filepath):
    modelManager = cntlr.modelManager
    if filepath == 'ix.json':
        return True
    return None

__pluginInfo__ = {
    'name': 'Load From PDF',
    'version': '1.0',
    'description': "This plug-in loads XBRL instance data from PDF/A with a tagged (accessibility) StructTree and form fields, and saves the resulting XBRL Instance.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'ModelDocument.IsPullLoadable': isPdfLoadable,
    'ModelDocument.PullLoader': pdfLoader,
    'FileSource.File': fileSourceFile,
    'FileSource.Exists': fileSourceExists,
}


# stand alone main program methods
if __name__ == "__main__":
    global _
    import gettext
    _ = gettext.gettext

    class _cntlr:
        def showStatus(self, msg, clearAfter=0):
            print(msg)

    def _logMessage(severity, code, message, **kwargs):
        print("[{}] {}".format(code, message % kwargs))

    debug = False
    pdfFile = None

    for arg in sys.argv[1:]:
        if arg in ("-a", "--about"):
            print("\narelle(r) PDF/A inline converter"
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
                  "  {file}: .pdf file to process and save as inline XBRL named {file}.xhtml")
        elif arg == "--debug":
            debug = True # shows StructTree
        else:
            if not arg.endswith(".pdf"):
                print("file {} must be a .pdf file".format(arg))
            elif os.path.exists(arg):
                pdfFile = arg
            else:
                print("file named {} not found".format(arg))

    if pdfFile:
        # load pdf and save json with values from pdf
        loadFromPDF(_cntlr, _logMessage, _logMessage, None, pdfFile, None, debug, True)
