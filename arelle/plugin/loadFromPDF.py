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
tags that allow giving an ID to each structural item).

At this time, if a structurally tagged element with text does not have an ID, if missingIDprefix
is specified, an id is generated (but not stored) for use in mapping.

Option showInfo will provide the pdf metadata and all tagged element values, including those
assigned an ID by feature missingIDprefix.

   by tools such as Acrobat using accessibility preparation
      Acrobat-DC seems to loose viewing glyphs on tables when autotagging
      Online Adobe seems to merge vertically adjacent table cells: https://acrobatservices.adobe.com/dc-accessibility-playground/main.html#
      Online PDFIX seems most successful with table cells: https://pdfix.io/add-tags-to-pdf/
   by libraries such as Python autotaggers for tables such as
      https://github.com/pdfix/pdfix-autotag-deepdoctection

Only StructTree nodes which have IDs, and form fields with IDs, are available to be loaded.

## Key Features

An xBRL-JSON template file is provided for each tagged PDF/A with inline XBRL.
   a) as an embedded file "ix.json" in the PDF or
   b) as a sibling file to the pdf named ix-template.json"

   The template file facts which are to receive contents from the pdf have @value missing and
   instead pdfIdRefs which is a list of space-separated IDs of structural node IDs and form field IDs
   which are space-contenated to form the value for the output xBRL-JSON file.
   
   Attributes pdfFormat, pdfScale and pdfSign correspond to like-named ix:nonFraction features.

   The output file is named with .pdf replaced by .json.

## Usage Instructions

### Command Line Usage

- **Stand alone convert pdf/a + template json into xBRL-JSON*:
  python loadFromPDF.py {pdfFilePath}
  argument --showInfo will list out, by pdf ID, all the structural nodes available for pdfIdRef'ing
                      and all the form fields by their field ID for pdfIdRef'ing
  argument --missingIDprefix provides a prefix to prepend to generated IDs for elements without ID



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
from pikepdf import Pdf, Dictionary, Array, Stream, Operator, parse_content_stream, unparse_content_stream, _core
from collections import defaultdict
from decimal import Decimal
import sys, os, json

DEFAULT_MISSING_ID_PREFIX="pdf_"  # None to block

try:
    from arelle.Version import authorLabel, copyrightLabel
    from arelle import CntlrWinMain
    from arelle.FunctionIxt import tr5Functions
except ImportError:
    # when run stand-alone as a main program this module expects to be in arelle's plugin directory
    # and sets module path as below to locate transformations module in arelle directory
    module_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0,module_path)
    from arelle import CntlrWinMain
    from arelle.FunctionIxt import tr5Functions
    authorLabel = 'Workiva, Inc.'
    copyrightLabel = '(c) Copyright 2011-present Workiva, Inc., All rights reserved.'

def decodePdfchar(s):
    if len(s) == 2:
        return chr(ord(s[0]) + (256 * ord(s[1])))
    return s

def bytesToNum(b):
    num = 0
    mult = 1
    for d in b[::-1]:
        num += d * mult
        mult *= 256
    return num

def numToBytes(n):
    b = []
    while n:
        b.append(n % 256)
        n = n // 256
    while len(b) % 2: # must be even number of bytes for UTF-16
        b.append(0)
    return bytes(bytearray(b[::-1]))
        
def fontChar(font, c):
    if c in font["bfchars"]:
        return font["bfchars"][c]
    for start, end, op in font["bfranges"]:
        if c >= start and c <= end:
            diff = bytesToNum(c) - bytesToNum(start)
            if isinstance(op, list):
                if diff < len(op):
                    return op[diff]
                return "?"
            else:
                return numToBytes(bytesToNum(op) + diff).decode("UTF-16BE")
                    

def loadFromPDF(cntlr, error, warning, modelXbrl, filepath, mappedUri, showInfo=False, missingIDprefix=DEFAULT_MISSING_ID_PREFIX, saveJson=False):

    if showInfo:
        print(f"loadFromPDF file: {os.path.basename(filepath)}")

    pdf = Pdf.open(filepath)
    
    if showInfo:
        metadata = pdf.open_metadata()
        print("Metadata:")
        for k, v in metadata.items():
            print(f"  {k}: {v}")
            
    markedContents = defaultdict(list)

    # load marked content (structured paragraph and section strings
    for p, page in enumerate(pdf.pages):
        fonts = {}
        fontRanges = {} # [start, end, toStart or [to values list]
        for name, font in page.get("/Resources",{}).get("/Font", {}).items():
            if "/ToUnicode" in font:
                fm = {}
                fr = []
                cr = []
                fonts[name] = {"bfchars": fm, "bfranges": fr, "csranges": cr}
                codespacerange = []
                beginCount = 0
                fbcharNum = 0
                for i in parse_content_stream(font["/ToUnicode"]):
                    if i.operator in (Operator("begincodespacerange"), Operator("beginbfrange"), Operator("beginbfchar")):
                        beginCount = i.operands[0]
                    elif i.operator == Operator("endcodespacerange"):
                        cr.append([c.__bytes__() for c in i.operands])
                    elif i.operator == Operator("endbfrange"):
                        for l in range(0, len(i.operands),3):
                            startChar = i.operands[l].__bytes__()
                            endChar = i.operands[l+1].__bytes__()
                            if isinstance(i.operands[l+2], _core._ObjectList):
                                fr.append( [startChar, endChar, 
                                            [l.__bytes__() for l in i.operands[l+2]]] )
                            else:
                                fr.append( [startChar, endChar, i.operands[l+2].__bytes__()] )
                    elif i.operator == Operator("endbfchar"):
                        #print(f"{name} fontInstr opr {str(i.operator)} ornd {[o.__bytes__() for o in i.operands]}")
                        c = None
                        for l in i.operands:
                            if c is None:
                                c = l.__bytes__()
                            else:
                                fm[c] = l.__bytes__().decode("UTF-16BE")
                                c = None

        ##or name, font in fonts.items():
        #    print(f"font {name} bytes {font}")
        mcid = None 
        txt = []
        fontName = fontSize = None
        font = None
        bbox = []
        instructions = parse_content_stream(page, "BDC Tf Tj TJ EMC Layout ")
        for i in instructions:
            if i.operator == Operator("BDC"):
                #if i.operands[0] == "/P" and "/MCID" in i.operands[1]:
                if "/MCID" in i.operands[1]:
                    mcid = i.operands[1]["/MCID"] # start of marked content
                elif i.operands[0] == "/Artifact" and "/BBox" in i.operands[1]:
                    rect = tuple(n for n in i.operands[1]["/BBox"])
                    bbox.append(rect)
            elif i.operator == Operator("Layout"):
                pass
            elif i.operator == Operator("EMC") and mcid is not None:
                #print(f"pg {p} mcid {mcid} font {fontName} tj {''.join(txt)}")
                markedContents[p,mcid] = ''.join(txt) # [''.join(txt), bbox]
                mcid = None # end of this marked content
                bbox = []
                txt = []
            elif i.operator == Operator("Tf"):
                fontName = str(i.operands[0])
                fontSize = i.operands[1]
                if fontName in fonts:
                    font = fonts[fontName]
                else:
                    font = None
            elif i.operator == Operator("Tj"):
                for s in i.operands:
                    t = s.__bytes__()
                    if font:
                        for l in range(0, len(str(s)), 2):
                            c = t[l:l+2]
                            txt.append(fontChar(font, c))
                    else:
                        txt.append(t)
            elif i.operator == Operator("TJ"):
                for a in i.operands:
                    for s in a:
                        if isinstance(s, (int, Decimal)):
                            pass # txt.append(" ") # not performing micro-spacing
                        else:
                            if font:
                                t = s.__bytes__()
                                for l in range(0, len(str(s)), 2):
                                    c = t[l:l+2]
                                    txt.append(fontChar(font, c))

    # load text blocks from structTree fields with IDs
    textBlocks = {}

    def loadTextBlocks(obj, pdfId="", key="", indent="", page=None, depth=0, trail=[]):
        if depth > 100:
            print(f"excessive recursion depth={depth} trail={trail}")
            return
        if isinstance(obj, (Array, list, tuple)):
            for v in obj:
                loadTextBlocks(v, pdfId, key, indent + "  ", page, depth+1, trail+[key])
        elif isinstance(obj, (Stream, Dictionary, dict)):
            if "/ID" in obj:
                pdfId = str(obj["/ID"])
            elif missingIDprefix:
                pdfId = f"{missingIDprefix}{len(textBlocks)}"
            if "/Pg" in obj:
                page = None
                c = obj["/Pg"]["/Contents"]
                for p, _page in enumerate(pdf.pages):
                    if c == _page["/Contents"]:
                        page = p
                        break
            for k, v in obj.items():
                if k not in ("/IDTree", "/P", "/Parent", "/Pg", "/Ff", "/Mk", "/Q", "/Rect", "/Font", "/Type", "/ColorSpace", "/MediaBox", "/Resources", "/Matrix", "/BBox", "/Border", "/DA", "/Length"):
                    loadTextBlocks(v, pdfId, k, indent + "  ", page, depth+1, trail+[k])
        elif key == "/K":
            if pdfId:
                if (page, obj) in markedContents:
                    # markedContent, bbox = markedContents[page,obj]
                    markedContent = markedContents[page,obj]
                    if pdfId in textBlocks:
                        textBlocks[pdfId] += "\n" + markedContent
                    else:
                        textBlocks[pdfId] = markedContent

    if "/StructTreeRoot" in pdf.Root:
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
    if "/AcroForm" in pdf.Root:
        loadFormFields(pdf.Root["/AcroForm"]["/Fields"])

    # at this point we have textBlocks and formFields by id
    if showInfo:
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
            idRefs = fact.pop("pdfIdRefs", None)
            format = fact.pop("pdfFormat", None)
            scale = fact.pop("pdfScale", None)
            sign = fact.pop("pdfSign", None)
            if idRefs:
                continTexts = []
                for pdfId in idRefs.split():
                    if pdfId in textBlocks:
                        continTexts.append(textBlocks[pdfId])
                    if pdfId in formFields:
                        continTexts.append(formFields[pdfId])
                value = " ".join(continTexts)
                if format:
                    tr5fn = format.rpartition(":")[2]
                    try:
                        value = tr5Functions[tr5fn](value)
                    except Exception as ex:
                        print(f"fact {oimFactId} format {format} invalid exception {ex}")
                if scale or sign:
                    try:
                        negate = -1 if sign else 1
                        num = Decimal(value)
                        if scale is not None:
                            num *= 10 ** Decimal(scale)
                        num *= negate
                        if num == num.to_integral() and (".0" not in v):
                            num = num.quantize(Decimal(1)) # drop any .0
                        value = "{:f}".format(num)
                    except:
                        print(f"fact {oimFactId} value to be scaled is not decimal {value}")
                fact["value"] = value
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

    showInfo = False
    missingIDprefix = None
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
                  "  --showInfo: show structural model and form fields available for mapping \n"
                  "  --missingIDprefix pdf_: add id to structural elements with text and no ID"
                  "  {file}: .pdf file to process and save as inline XBRL named {file}.xhtml")
        elif arg == "--showInfo":
            showInfo = True # shows StructTree
        elif arg == "--missingIDprefix":
            missingIDprefix = -1
        elif missingIDprefix == -1:
            missingIDprefix = arg
        else:
            if not arg.endswith(".pdf"):
                print("file {} must be a .pdf file".format(arg))
            elif os.path.exists(arg):
                pdfFile = arg
            else:
                print("file named {} not found".format(arg))

    if pdfFile:
        # load pdf and save json with values from pdf
        loadFromPDF(_cntlr, _logMessage, _logMessage, None, pdfFile, None, showInfo, missingIDprefix, True)
