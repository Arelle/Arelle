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
  
### Local Viewer Operation

Use arelle/examples/viewer/inlinePdfViewer.html with ?doc= name of output json from this plugin

### GUI Usage

* **Load PDF Report**: <<FEATURE NOT READY>>
  1. Using the normal `File` menu `Open File...` dialog, select the PDF/A file, or
  2. Using this module as a main program, save the value-enhanced inline source.
  

"""
from pikepdf import Pdf, Dictionary, Array, Stream, Operator, parse_content_stream, unparse_content_stream, _core
from collections import defaultdict, OrderedDict
from decimal import Decimal
import sys, os, json

DEFAULT_MISSING_ID_PREFIX="pdf_"  # None to block

# from https://github.com/maxwell-bland/pdf-latin-text-encodings
mac_encoding = {65: 'A', 174: 'Æ', 231: 'Á', 229: 'Â', 128: 'Ä', 203: 'À', 129: 'Å', 204: 'Ã', 66: 'B', 67: 'C', 130: 'Ç', 68: 'D', 69: 'E', 131: 'É', 230: 'j', 232: 'Ë', 233: 'È', 70: 'F', 71: 'G', 72: 'H', 73: 'I', 234: 'Í', 235: 'Î', 236: 'Ï', 237: 'Ì', 74: 'J', 75: 'K', 76: 'L', 77: 'M', 78: 'N', 132: 'Ñ', 79: 'O', 206: 'Œ', 238: 'Ó', 239: 'Ô', 133: 'Ö', 241: 'Ò', 175: 'Ø', 205: 'Õ', 80: 'P', 81: 'Q', 82: 'R', 83: 'S', 84: 'T', 85: 'U', 242: 'Ú', 243: 'Û', 134: 'Ü', 244: 'Ù', 86: 'V', 87: 'W', 88: 'X', 89: 'Y', 217: 'Ÿ', 90: 'Z', 97: 'a', 135: 'á', 137: 'â', 171: 'a', 138: 'ä', 190: 'æ', 136: 'à', 38: '&', 140: 'å', 94: '^', 126: '~', 42: '*', 64: '@', 139: 'ã', 98: 'b', 92: '\\', 124: '|', 123: '{', 125: '}', 91: '[', 93: ']', 249: '̆', 165: '•', 99: 'c', 255: 'ˇ', 141: 'ç', 252: '̧', 162: '¢', 246: 'ˆ', 58: ':', 44: ',', 169: '©', 219: '¤', 100: 'd', 160: '†', 224: '‡', 161: '°', 172: '̈', 214: '÷', 36: '$', 250: '̇', 245: 'ı', 101: 'e', 142: 'é', 144: 'ê', 145: 'ë', 143: 'è', 56: '8', 201: '.', 209: '-', 208: '–', 61: '=', 33: '!', 193: '¡', 102: 'f', 222: 'f', 53: '5', 223: 'f', 196: 'ƒ', 52: '4', 218: '⁄', 103: 'g', 167: 'ß', 96: '`', 62: '>', 199: '«', 200: '»', 220: '‹', 221: '›', 104: 'h', 253: '̋', 45: '-', 105: 'i', 146: 'í', 148: 'î', 149: 'ï', 147: 'ì', 106: 'j', 107: 'k', 108: 'l', 60: '<', 194: '¬', 109: 'm', 248: '̄', 181: 'μ', 110: 'n', 57: '9', 150: 'ñ', 35: '#', 111: 'o', 151: 'ó', 153: 'ô', 154: 'ö', 207: 'œ', 254: '̨', 152: 'ò', 49: '1', 187: 'ª', 188: 'º', 191: 'ø', 155: 'õ', 112: 'p', 166: '¶', 40: '(', 41: ')', 37: '%', 46: '.', 225: '·', 228: '‰', 43: '+', 177: '±', 113: 'q', 63: '?', 192: '¿', 34: '"', 227: '„', 210: '“', 211: '”', 212: '‘', 213: '’', 226: '‚', 39: "'", 114: 'r', 168: '®', 251: '̊', 115: 's', 164: '§', 59: ';', 55: '7', 54: '6', 47: '/', 32: ' ', 163: '£', 116: 't', 51: '3', 247: '̃', 170: '™', 50: '2', 117: 'u', 156: 'ú', 158: 'û', 159: 'ü', 157: 'ù', 95: '_', 118: 'v', 119: 'w', 120: 'x', 121: 'y', 216: 'ÿ', 180: '¥', 122: 'z', 48: '0'}
pdf_encoding = {65: 'A', 198: 'Æ', 193: 'Á', 194: 'Â', 196: 'Ä', 192: 'À', 197: 'Å', 195: 'Ã', 66: 'B', 67: 'C', 199: 'Ç', 68: 'D', 69: 'E', 201: 'É', 202: 'j', 203: 'Ë', 200: 'È', 208: 'Ð', 160: '€', 70: 'F', 71: 'G', 72: 'H', 73: 'I', 205: 'Í', 206: 'Î', 207: 'Ï', 204: 'Ì', 74: 'J', 75: 'K', 76: 'L', 149: 'Ł', 77: 'M', 78: 'N', 209: 'Ñ', 79: 'O', 150: 'Œ', 211: 'Ó', 212: 'Ô', 214: 'Ö', 210: 'Ò', 216: 'Ø', 213: 'Õ', 80: 'P', 81: 'Q', 82: 'R', 83: 'S', 151: 'Š', 84: 'T', 222: 'Þ', 85: 'U', 218: 'Ú', 219: 'Û', 220: 'Ü', 217: 'Ù', 86: 'V', 87: 'W', 88: 'X', 89: 'Y', 221: 'Ý', 152: 'Ÿ', 90: 'Z', 153: 'Ž', 97: 'a', 225: 'á', 226: 'â', 180: 'a', 228: 'ä', 230: 'æ', 224: 'à', 38: '&', 229: 'å', 94: '^', 126: '~', 42: '*', 64: '@', 227: 'ã', 98: 'b', 92: '\\', 124: '|', 123: '{', 125: '}', 91: '[', 93: ']', 24: '̆', 166: '¦', 128: '•', 99: 'c', 25: 'ˇ', 231: 'ç', 184: '̧', 162: '¢', 26: 'ˆ', 58: ':', 44: ',', 169: '©', 164: '¤', 100: 'd', 129: '†', 130: '‡', 176: '°', 168: '̈', 247: '÷', 36: '$', 27: '̇', 154: 'ı', 101: 'e', 233: 'é', 234: 'ê', 235: 'ë', 232: 'è', 56: '8', 131: '.', 132: '-', 133: '–', 61: '=', 240: 'ð', 33: '!', 161: '¡', 102: 'f', 147: 'f', 53: '5', 148: 'f', 134: 'ƒ', 52: '4', 135: '⁄', 103: 'g', 223: 'ß', 96: '`', 62: '>', 171: '«', 187: '»', 136: '‹', 137: '›', 104: 'h', 28: '̋', 45: '-', 105: 'i', 237: 'í', 238: 'î', 239: 'ï', 236: 'ì', 106: 'j', 107: 'k', 108: 'l', 60: '<', 172: '¬', 155: 'ł', 109: 'm', 175: '̄', 138: '−', 181: 'μ', 215: '×', 110: 'n', 57: '9', 241: 'ñ', 35: '#', 111: 'o', 243: 'ó', 244: 'ô', 246: 'ö', 156: 'œ', 29: '̨', 242: 'ò', 49: '1', 189: '½', 188: '¼', 185: '¹', 170: 'ª', 186: 'º', 248: 'ø', 245: 'õ', 112: 'p', 182: '¶', 40: '(', 41: ')', 37: '%', 46: '.', 183: '·', 139: '‰', 43: '+', 177: '±', 113: 'q', 63: '?', 191: '¿', 34: '"', 140: '„', 141: '“', 142: '”', 143: '‘', 144: '’', 145: '‚', 39: "'", 114: 'r', 174: '®', 30: '̊', 115: 's', 157: 'š', 167: '§', 59: ';', 55: '7', 54: '6', 47: '/', 32: ' ', 163: '£', 116: 't', 254: 'þ', 51: '3', 190: '¾', 179: '³', 31: '̃', 146: '™', 50: '2', 178: '²', 117: 'u', 250: 'ú', 251: 'û', 252: 'ü', 249: 'ù', 95: '_', 118: 'v', 119: 'w', 120: 'x', 121: 'y', 253: 'ý', 255: 'ÿ', 165: '¥', 122: 'z', 158: 'ž', 48: '0'}
std_encoding = {65: 'A', 225: 'Æ', 66: 'B', 67: 'C', 68: 'D', 69: 'E', 70: 'F', 71: 'G', 72: 'H', 73: 'I', 74: 'J', 75: 'K', 76: 'L', 232: 'Ł', 77: 'M', 78: 'N', 79: 'O', 234: 'Œ', 233: 'Ø', 80: 'P', 81: 'Q', 82: 'R', 83: 'S', 84: 'T', 85: 'U', 86: 'V', 87: 'W', 88: 'X', 89: 'Y', 90: 'Z', 97: 'a', 194: 'a', 241: 'æ', 38: '&', 94: '^', 126: '~', 42: '*', 64: '@', 98: 'b', 92: '\\', 124: '|', 123: '{', 125: '}', 91: '[', 93: ']', 198: '̆', 183: '•', 99: 'c', 207: 'ˇ', 203: '̧', 162: '¢', 195: 'ˆ', 58: ':', 44: ',', 168: '¤', 100: 'd', 178: '†', 179: '‡', 200: '̈', 36: '$', 199: '̇', 245: 'ı', 101: 'e', 56: '8', 188: '.', 208: '-', 177: '–', 61: '=', 33: '!', 161: '¡', 102: 'f', 174: 'f', 53: '5', 175: 'f', 166: 'ƒ', 52: '4', 164: '⁄', 103: 'g', 251: 'ß', 193: '`', 62: '>', 2219: '«', 2235: '»', 172: '‹', 173: '›', 104: 'h', 205: '̋', 45: '-', 105: 'i', 106: 'j', 107: 'k', 108: 'l', 60: '<', 248: 'ł', 109: 'm', 197: '̄', 110: 'n', 57: '9', 35: '#', 111: 'o', 250: 'œ', 206: '̨', 49: '1', 227: 'ª', 235: 'º', 249: 'ø', 112: 'p', 182: '¶', 40: '(', 41: ')', 37: '%', 46: '.', 180: '·', 189: '‰', 43: '+', 113: 'q', 63: '?', 191: '¿', 34: '"', 185: '„', 170: '“', 186: '”', 96: '‘', 39: '’', 184: '‚', 169: "'", 114: 'r', 202: '̊', 115: 's', 167: '§', 59: ';', 55: '7', 54: '6', 47: '/', 3104: 's', 163: '£', 116: 't', 51: '3', 196: '̃', 50: '2', 117: 'u', 95: '_', 118: 'v', 119: 'w', 120: 'x', 121: 'y', 165: '¥', 122: 'z', 48: '0'}
win_encoding = {65: 'A', 198: 'Æ', 193: 'Á', 194: 'Â', 196: 'Ä', 192: 'À', 197: 'Å', 195: 'Ã', 66: 'B', 67: 'C', 199: 'Ç', 68: 'D', 69: 'E', 201: 'É', 202: 'j', 203: 'Ë', 200: 'È', 208: 'Ð', 128: '€', 70: 'F', 71: 'G', 72: 'H', 73: 'I', 205: 'Í', 206: 'Î', 207: 'Ï', 204: 'Ì', 74: 'J', 75: 'K', 76: 'L', 77: 'M', 78: 'N', 209: 'Ñ', 79: 'O', 140: 'Œ', 211: 'Ó', 212: 'Ô', 214: 'Ö', 210: 'Ò', 216: 'Ø', 213: 'Õ', 80: 'P', 81: 'Q', 82: 'R', 83: 'S', 138: 'Š', 84: 'T', 222: 'Þ', 85: 'U', 218: 'Ú', 219: 'Û', 220: 'Ü', 217: 'Ù', 86: 'V', 87: 'W', 88: 'X', 89: 'Y', 221: 'Ý', 159: 'Ÿ', 90: 'Z', 142: 'Ž', 97: 'a', 225: 'á', 226: 'â', 180: 'a', 228: 'ä', 230: 'æ', 224: 'à', 38: '&', 229: 'å', 94: '^', 126: '~', 42: '*', 64: '@', 227: 'ã', 98: 'b', 92: '\\', 124: '|', 123: '{', 125: '}', 91: '[', 93: ']', 166: '¦', 149: '•', 99: 'c', 231: 'ç', 184: '̧', 162: '¢', 136: 'ˆ', 58: ':', 44: ',', 169: '©', 164: '¤', 100: 'd', 134: '†', 135: '‡', 176: '°', 168: '̈', 247: '÷', 36: '$', 101: 'e', 233: 'é', 234: 'ê', 235: 'ë', 232: 'è', 56: '8', 133: '.', 151: '-', 150: '–', 61: '=', 240: 'ð', 33: '!', 161: '¡', 102: 'f', 53: '5', 131: 'ƒ', 52: '4', 103: 'g', 223: 'ß', 96: '`', 62: '>', 171: '«', 187: '»', 139: '‹', 155: '›', 104: 'h', 45: '-', 105: 'i', 237: 'í', 238: 'î', 239: 'ï', 236: 'ì', 106: 'j', 107: 'k', 108: 'l', 60: '<', 172: '¬', 109: 'm', 175: '̄', 181: 'μ', 215: '×', 110: 'n', 57: '9', 241: 'ñ', 35: '#', 111: 'o', 243: 'ó', 244: 'ô', 246: 'ö', 156: 'œ', 242: 'ò', 49: '1', 189: '½', 188: '¼', 185: '¹', 170: 'ª', 186: 'º', 248: 'ø', 245: 'õ', 112: 'p', 182: '¶', 40: '(', 41: ')', 37: '%', 46: '.', 183: '·', 137: '‰', 43: '+', 177: '±', 113: 'q', 63: '?', 191: '¿', 34: '"', 132: '„', 147: '“', 148: '”', 145: '‘', 146: '’', 130: '‚', 39: "'", 114: 'r', 174: '®', 115: 's', 154: 'š', 167: '§', 59: ';', 55: '7', 54: '6', 47: '/', 32: ' ', 163: '£', 116: 't', 254: 'þ', 51: '3', 190: '¾', 179: '³', 152: '̃', 153: '™', 50: '2', 178: '²', 117: 'u', 250: 'ú', 251: 'û', 252: 'ü', 249: 'ù', 95: '_', 118: 'v', 119: 'w', 120: 'x', 121: 'y', 253: 'ý', 255: 'ÿ', 165: '¥', 122: 'z', 158: 'ž', 48: '0'}
encoding = {"/MacRomanEncoding": mac_encoding,
            "/PDFDocEncoding": pdf_encoding,
            "/StandardEncoding": std_encoding,
            "/WinAnsiEncoding": win_encoding}

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
    if "encoding" in font:
        return encoding[font["encoding"]][c] # c is a byte, not char
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
        if pdf.attachments:
            print("Attachments:")
            for k, v in pdf.attachments.items():
                print(f"  {k} Description: {v.description}, Filename: {v.filename},  Size: {v.obj.EF.F.Params.Size}")
    
    markedContents = {}
    ixTextFields = defaultdict(list)
    ixFormFields = []

    # load marked content (structured paragraph and section strings
    for pIndex, page in enumerate(pdf.pages):
        p = page.objgen[0] # for matching to pdf.js page number
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
            elif "/Encoding" in font:
                fonts[name] = {"encoding": str(font["/Encoding"])}

        ##or name, font in fonts.items():
        #    print(f"font {name} bytes {font}")
        mcid = None
        txt = []
        pos = None
        fontName = fontSize = None
        font = None
        instructions = parse_content_stream(page, "BDC Tf Tj TJ EMC Td TD Tm T* ")
        for i in instructions:
            if i.operator == Operator("BDC"):
                #if i.operands[0] == "/P" and "/MCID" in i.operands[1]:
                if "/MCID" in i.operands[1]:
                    mcid = i.operands[1]["/MCID"] # start of marked content
            elif i.operator == Operator("Td"): #Move to the start of the next line
                if txt and i.operands[1] < 0:
                    txt.append("\n")
            elif i.operator == Operator("TD"): #move to next line
                if txt and i.operands[1] < 0:
                    txt.append("\n")
            elif i.operator == Operator("Tm"): #Set the text matrix, Tm
                m = list(i.operands)
                if pos is None:
                    pos = m
                else:
                    pos[0] = min(m[0], pos[0])
                    pos[1] = max(m[1], pos[1])
                    pos[2] = min(m[2], pos[2])
                    pos[3] = min(m[3], pos[3])
                    pos[4] = max(m[4], pos[4])
                    pos[5] = min(m[5], pos[5])
            elif i.operator == Operator("T*"):
                if txt:
                    txt.append("\n")
            elif i.operator == Operator("EMC") and mcid is not None:
                #print(f"pg {p} mcid {mcid} font {fontName} tj {''.join(txt)}")
                markedContents[p,mcid] = {
                    "txt": ''.join(txt), # [''.join(txt), bbox]
                    "pos": pos}
                mcid = None # end of this marked content
                pos = None
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
                        if "encoding" in font:
                            for b in t:
                                txt.append(fontChar(font, b))
                        else:
                            for l in range(0, len(str(s)), 2):
                                c = t[l:l+2]
                                txt.append(fontChar(font, c))
                    else:
                        txt.append(str(s))
            elif i.operator == Operator("TJ"):
                for a in i.operands:
                    for s in a:
                        if isinstance(s, (int, Decimal)):
                            pass # txt.append(" ") # not performing micro-spacing
                        else:
                            if font:
                                t = s.__bytes__()
                                if "encoding" in font:
                                    for b in t:
                                        txt.append(fontChar(font, b))
                                else:
                                    for l in range(0, len(str(s)), 2):
                                        c = t[l:l+2]
                                        txt.append(fontChar(font, c))

    # load text blocks from structTree fields with IDs
    textBlocks = {}
    structMcid = defaultdict(list)

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
                page = obj["/Pg"].objgen[0]
            for k, v in obj.items():
                if k not in ("/IDTree", "/P", "/Parent", "/Pg", "/Ff", "/Mk", "/Q", "/Rect", "/Font", "/Type", "/ColorSpace", "/MediaBox", "/Resources", "/Matrix", "/BBox", "/Border", "/DA", "/Length"):
                    loadTextBlocks(v, pdfId, k, indent + "  ", page, depth+1, trail+[k])
        elif key == "/K":
            if pdfId:
                if (page, obj) in markedContents:
                    # markedContent, bbox = markedContents[page,obj]
                    markedContent = markedContents[page,obj]
                    mcid = f"p{page}R_mc{obj}"
                    if pdfId in textBlocks:
                        if mcid not in structMcid[pdfId]:
                            textBlocks[pdfId] += "\n" + markedContent["txt"]
                            structMcid[pdfId].append(mcid)
                    else:
                        textBlocks[pdfId] = markedContent["txt"]
                        structMcid[pdfId].append(mcid)

    if "/StructTreeRoot" in pdf.Root:
        loadTextBlocks(pdf.Root["/StructTreeRoot"])

    # load form fields by IDs
    formFields = defaultdict(dict)

    def loadFormFields(obj, pdfId="", altId="", key="", indent=""):
        if isinstance(obj, (Array, list, tuple)):
            if key == "/Rect":
                if pdfId or Tu:
                    formFields[str(altId) or str(pdfId)]["Rect"] = [float(x) if isinstance(x, Decimal) else x for x in obj]
            else:
                for v in obj:
                    loadFormFields(v, pdfId, altId, key, indent + "  ")
        elif isinstance(obj, (Stream, Dictionary, dict)):
            if "/T" in obj:
                pdfId = obj["/T"]
            elif "/TU" in obj: # alternative id for accessibility or extraction
                altId = obj["/TU"]
            for k, v in obj.items():
                if k not in ("/IDTree", "/P", "/Parent", "/Pg", "/Ff", "/Mk", "/Q", "/Font", "/Type", "/ColorSpace", "/MediaBox", "/Resources", "/Matrix", "/BBox", "/Border", "/DA", "/Length"):
                    loadFormFields(v, pdfId, altId, k, indent + "  ")
            if "/P" in obj and str(obj["/P"].Type) == "/Page":
                formFields[str(altId) or str(pdfId)]["Page"] = obj["/P"].objgen[0]
        elif key == "/V":
            if pdfId:
                formFields[str(altId) or str(pdfId)]["V"] = str(obj)
    if "/AcroForm" in pdf.Root:
        loadFormFields(pdf.Root["/AcroForm"]["/Fields"])

    # at this point we have textBlocks and formFields by id
    if showInfo:
        print(f"marked contents:")
        for k,v in markedContents.items():
            print(f"p{k[0]}R_mc{k[1]}: {v}")
        print(f"str mcid:")
        for k,v in structMcid.items():
            print(f"{k}: {', '.join(v)}")
        print(f"text blocks:\n{os.linesep.join(k + ': ' + v for k,v in textBlocks.items())}")
        print(f"form fields:\n{os.linesep.join(k + ': ' + str(v) for k,v in formFields.items())}")

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
        ixTextFields = defaultdict(list)
        ixFormFields = []
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
                        ixTextFields[oimFactId].extend(structMcid[pdfId])
                    if pdfId in formFields:
                        continTexts.append(formFields[pdfId]["V"])
                        ixFormFields.append([oimFactId, 
                                             f"p{formFields[pdfId]['Page']}R",
                                             *formFields[pdfId]["Rect"]])
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
            oimObject["pdfMapping"] = OrderedDict((
                ("file", os.path.basename(filepath)),
                ("target", None),
                ("ixTextFields", ixTextFields),
                ("ixFormFields", ixFormFields)
                ))
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
    import builtins
    builtins.__dict__['_'] = gettext.gettext

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
