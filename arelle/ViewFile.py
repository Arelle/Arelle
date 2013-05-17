'''
Created on Oct 9, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import csv, io, json, re, sys
from lxml import etree
from arelle.FileSource import FileNamedStringIO
if sys.version[0] >= '3':
    csvOpenMode = 'w'
    csvOpenNewline = ''
else:
    csvOpenMode = 'wb' # for 2.7
    csvOpenNewline = None

CSV = 0
HTML = 1
XML = 2
JSON = 3
TYPENAMES = ["CSV", "HTML", "XML", "JSON"]
nonNameCharPattern =  re.compile(r"[^\w\-\.:]")

class View:
    def __init__(self, modelXbrl, outfile, rootElementName, lang=None, style="table"):
        self.modelXbrl = modelXbrl
        self.lang = lang
        if isinstance(outfile, FileNamedStringIO):
            if outfile.fileName in ("html", "xhtml"):
                self.type = HTML
            elif outfile.fileName == "csv":
                self.type = CSV
            elif outfile.fileName == "json":
                self.type = JSON
            else:
                self.type = XML
        elif outfile.endswith(".html") or outfile.endswith(".htm") or outfile.endswith(".xhtml"):
            self.type = HTML
        elif outfile.endswith(".xml"):
            self.type = XML
        elif outfile.endswith(".json"):
            self.type = JSON
        else:
            self.type = CSV
        self.outfile = outfile
        if style == "rendering": # for rendering, preserve root element name
            self.rootElementName = rootElementName
        else: # root element is formed from words in title or description
            self.rootElementName = rootElementName[0].lower() + nonNameCharPattern.sub("", rootElementName.title())[1:]
        self.numHdrCols = 0
        self.treeCols = 0  # set to number of tree columns for auto-tree-columns
        if modelXbrl:
            if not lang: 
                self.lang = modelXbrl.modelManager.defaultLang
        if self.type == CSV:
            if isinstance(self.outfile, FileNamedStringIO):
                self.csvFile = self.outfile
            else:
                self.csvFile = open(outfile, csvOpenMode, newline=csvOpenNewline)
            self.csvWriter = csv.writer(self.csvFile, dialect="excel")
        elif self.type == HTML:
            if style == "rendering":
                html = io.StringIO(
'''
<html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <meta http-equiv="content-type" content="text/html;charset=utf-8" />
        <STYLE type="text/css"> 
            table {font-family:Arial,sans-serif;vertical-align:middle;white-space:normal;}
            th {background:#eee;}
            td {} 
            .tableHdr{border-top:.5pt solid windowtext;border-right:none;border-bottom:none;border-left:.5pt solid windowtext;}
            .zAxisHdr{border-top:.5pt solid windowtext;border-right:.5pt solid windowtext;border-bottom:none;border-left:.5pt solid windowtext;}
            .xAxisSpanLeg,.yAxisSpanLeg,.yAxisSpanArm{border-top:none;border-right:none;border-bottom:none;border-left:.5pt solid windowtext;}
            .xAxisHdrValue{border-top:.5pt solid windowtext;border-right:none;border-bottom:none;border-left:1.0pt solid windowtext;}
            .xAxisHdr{border-top:.5pt solid windowtext;border-right:none;border-bottom:none;border-left:.5pt solid windowtext;} 
            .yAxisHdrWithLeg{vertical-align:middle;border-top:.5pt solid windowtext;border-right:none;border-bottom:none;border-left:.5pt solid windowtext;}
            .yAxisHdrWithChildrenFirst{border-top:none;border-right:none;border-bottom:.5pt solid windowtext;border-left:.5pt solid windowtext;}
            .yAxisHdrAbstract{border-top:.5pt solid windowtext;border-right:none;border-bottom:none;border-left:.5pt solid windowtext;}
            .yAxisHdrAbstractChildrenFirst{border-top:none;border-right:none;border-bottom:.5pt solid windowtext;border-left:.5pt solid windowtext;}
            .yAxisHdr{border-top:.5pt solid windowtext;border-right:none;border-bottom:none;border-left:.5pt solid windowtext;}
            .cell{border-top:1.0pt solid windowtext;border-right:.5pt solid windowtext;border-bottom:.5pt solid windowtext;border-left:.5pt solid windowtext;}
            .abstractCell{border-top:1.0pt solid windowtext;border-right:.5pt solid windowtext;border-bottom:.5pt solid windowtext;border-left:.5pt solid windowtext;background:#e8e8e8;}
            .blockedCell{border-top:1.0pt solid windowtext;border-right:.5pt solid windowtext;border-bottom:.5pt solid windowtext;border-left:.5pt solid windowtext;background:#eee;}
            .tblCell{border-top:.5pt solid windowtext;border-right:.5pt solid windowtext;border-bottom:.5pt solid windowtext;border-left:.5pt solid windowtext;}
        </STYLE>
    </head>
    <body>
        <table border="1" cellspacing="0" cellpadding="4" style="font-size:8pt;">
        </table>
    </body>
</html>
'''
                )
            else:
                html = io.StringIO(
'''
<html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <meta http-equiv="content-type" content="text/html;charset=utf-8" />
        <STYLE type="text/css"> 
            table {font-family:Arial,sans-serif;vertical-align:middle;white-space:normal;
                    border-top:.5pt solid windowtext;border-right:1.5pt solid windowtext;border-bottom:1.5pt solid windowtext;border-left:.5pt solid windowtext;}
            th {background:#eee;}
            td {} 
            .tableHdr{border-top:.5pt solid windowtext;border-right:none;border-bottom:.5pt solid windowtext;border-left:.5pt solid windowtext;}
            .rowSpanLeg{width:1.0em;border-top:none;border-right:none;border-bottom:none;border-left:.5pt solid windowtext;}
            .tableCell{border-top:.5pt solid windowtext;border-right:none;border-bottom:none;border-left:.5pt solid windowtext;}
            .tblCell{border-top:.5pt solid windowtext;border-right:none;border-bottom:.5pt solid windowtext;border-left:.5pt solid windowtext;}
        </STYLE>
    </head>
    <body>
        <table cellspacing="0" cellpadding="4" style="font-size:8pt;">
        </table>
    </body>
</html>
'''
                )
            self.xmlDoc = etree.parse(html)
            html.close()
            self.tblElt = None
            for self.tblElt in self.xmlDoc.iter(tag="{http://www.w3.org/1999/xhtml}table"):
                break
        elif self.type == XML:
            html = io.StringIO("<{0}/>".format(self.rootElementName))
            self.xmlDoc = etree.parse(html)
            html.close()
            self.docEltLevels = [self.xmlDoc.getroot()]
            self.tblElt = self.docEltLevels[0]
        elif self.type == JSON:
            self.entries = []
            self.entryLevels = [self.entries]
            self.jsonObject = {self.rootElementName: self.entries}
        
    def addRow(self, cols, asHeader=False, treeIndent=0, colSpan=1, xmlRowElementName=None, xmlRowEltAttr=None, xmlRowText=None, xmlCol0skipElt=False, xmlColElementNames=None, lastColSpan=None):
        if asHeader and len(cols) > self.numHdrCols:
            self.numHdrCols = len(cols)
        if self.type == CSV:
            self.csvWriter.writerow(cols if not self.treeCols else
                                    ([None for i in range(treeIndent)] +
                                     cols[0:1] + 
                                     [None for i in range(treeIndent, self.treeCols - 1)] +
                                     cols[1:]))
        elif self.type == HTML:
            tr = etree.SubElement(self.tblElt, "{http://www.w3.org/1999/xhtml}tr")
            td = None
            for i, col in enumerate(cols + [None for emptyCol in range(self.numHdrCols - colSpan + 1 - len(cols))]):
                attrib = {}
                if asHeader:
                    attrib["class"] = "tableHdr"
                    colEltTag = "{http://www.w3.org/1999/xhtml}th"
                else:
                    colEltTag = "{http://www.w3.org/1999/xhtml}td"
                    attrib["class"] = "tableCell"
                if i == 0:
                    if self.treeCols - 1 > treeIndent:
                        attrib["colspan"] = str(self.treeCols - treeIndent + colSpan - 1)
                    elif colSpan > 1:
                        attrib["colspan"] = str(colSpan)
                if i == 0 and self.treeCols:
                    for indent in range(treeIndent):
                        etree.SubElement(tr, colEltTag,
                                         attrib={"class":"rowSpanLeg"},
                                         ).text = '\u00A0'  # produces &nbsp;
                td = etree.SubElement(tr, colEltTag, attrib=attrib)
                td.text = str(col) if col else '\u00A0'  # produces &nbsp;
            if lastColSpan and td is not None:
                td.set("colspan", str(lastColSpan))
        elif self.type == XML:
            if asHeader:
                # save column element names
                self.xmlRowElementName = xmlRowElementName or "row"
                self.columnEltNames = [col[0].lower() + nonNameCharPattern.sub('', col[1:])
                                       for col in cols]
            else:
                if treeIndent < len(self.docEltLevels) and self.docEltLevels[treeIndent] is not None:
                    parentElt = self.docEltLevels[treeIndent]
                else:
                    # problem, error message? unexpected indent
                    parentElt = self.docEltLevels[0] 
                # escape attributes content
                escapedRowEltAttr = dict(((k, v.replace("&","&amp;").replace("<","&lt;"))
                                          for k,v in xmlRowEltAttr.items())
                                         if xmlRowEltAttr else ())
                rowElt = etree.SubElement(parentElt, xmlRowElementName or self.xmlRowElementName, attrib=escapedRowEltAttr)
                if treeIndent + 1 >= len(self.docEltLevels): # extend levels as needed
                    for extraColIndex in range(len(self.docEltLevels) - 1, treeIndent + 1):
                        self.docEltLevels.append(None)
                self.docEltLevels[treeIndent + 1] = rowElt
                if not xmlColElementNames: xmlColElementNames = self.columnEltNames
                if len(cols) == 1 and not xmlCol0skipElt:
                    rowElt.text = xmlRowText if xmlRowText else cols[0]
                else:
                    isDimensionName = isDimensionValue = False
                    for i, col in enumerate(cols):
                        if (i != 0 or not xmlCol0skipElt) and col:
                            if i < len(xmlColElementNames):
                                elementName = xmlColElementNames[i]
                                if elementName == "dimensions":
                                    elementName = "dimension" # one element per dimension
                                    isDimensionName = True
                            if isDimensionName:
                                isDimensionValue = True
                                isDimensionName = False
                                dimensionName = str(col)
                            else:
                                elt = etree.SubElement(rowElt, elementName)
                                elt.text = str(col).replace("&","&amp;").replace("<","&lt;")
                                if isDimensionValue:
                                    elt.set("name", dimensionName)
                                    isDimensionName = True
                                    isDimensionValue = False
        elif self.type == JSON:
            if asHeader:
                # save column element names
                self.xmlRowElementName = xmlRowElementName
                self.columnEltNames = [col[0].lower() + nonNameCharPattern.sub('', col[1:])
                                       for col in cols]
            else:
                if treeIndent < len(self.entryLevels) and self.entryLevels[treeIndent] is not None:
                    entries = self.entryLevels[treeIndent]
                else:
                    # problem, error message? unexpected indent
                    entries = self.entryLevels[0] 
                entry = []
                if xmlRowElementName:
                    entry.append(xmlRowElementName)
                elif self.xmlRowElementName:
                    entry.append(self.xmlRowElementName)
                if xmlRowEltAttr:
                    entry.append(xmlRowEltAttr)
                else:
                    entry.append({})
                entries.append(entry)
                if treeIndent + 1 >= len(self.entryLevels): # extend levels as needed
                    for extraColIndex in range(len(self.entryLevels) - 1, treeIndent + 1):
                        self.entryLevels.append(None)
                self.entryLevels[treeIndent + 1] = entry
                if not xmlColElementNames: xmlColElementNames = self.columnEltNames
                if len(cols) == 1 and not xmlCol0skipElt:
                    entry.append(xmlRowText if xmlRowText else cols[0])
                else:
                    content = {}
                    entry.append(content)
                    for i, col in enumerate(cols):
                        if (i != 0 or not xmlCol0skipElt) and col and i < len(xmlColElementNames):
                                elementName = xmlColElementNames[i]
                                if elementName == "dimensions":
                                    value = dict((str(cols[i]),str(cols[i+1])) for i in range(i, len(cols), 2))
                                else:
                                    value = str(col)
                                content[elementName] = value
        if asHeader and lastColSpan: 
            self.numHdrCols += lastColSpan - 1
                                
    def close(self, noWrite=False):
        if self.type == CSV:
            if not isinstance(self.outfile, FileNamedStringIO):
                self.csvFile.close()
        elif not noWrite:
            fileType = TYPENAMES[self.type]
            try:
                from arelle import XmlUtil
                if isinstance(self.outfile, FileNamedStringIO):
                    fh = self.outfile
                else:
                    fh = open(self.outfile, "w", encoding="utf-8")
                if self.type == JSON:
                    fh.write(json.dumps(self.jsonObject, ensure_ascii=False))
                else:
                    XmlUtil.writexml(fh, self.xmlDoc, encoding="utf-8",
                                     xmlcharrefreplace= (self.type == HTML) )
                if not isinstance(self.outfile, FileNamedStringIO):
                    fh.close()
                self.modelXbrl.info("info", _("Saved output %(type)s to %(file)s"), file=self.outfile, type=fileType)
            except (IOError, EnvironmentError) as err:
                self.modelXbrl.exception("arelle:htmlIOError", _("Failed to save output %(type)s to %(file)s: \s%(error)s"), file=self.outfile, type=fileType, error=err)
        self.modelXbrl = None
        if self.type == HTML:
            self.tblElt = None
        elif self.type == XML:
            self.docEltLevels = None
        self.__dict__.clear() # dereference everything after closing document

