'''
Save HTML EBA Tables is an example of a plug-in to both GUI menu and command line/web service
that will save a directory containing HTML Tablesets with an EBA index page.

See COPYRIGHT.md for copyright information.
'''
import os
import threading
from operator import itemgetter

from lxml import etree

from arelle import Version, XbrlConst, XmlUtil
from arelle.ModelDocument import Type
from arelle.ModelObjectFactory import parser
from arelle.ModelRenderingObject import DefnMdlTable
from arelle.rendering import RenderingEvaluator
from arelle.ViewFileRenderedGrid import viewRenderedGrid

INDEX_DOCUMENT_HTML = '''
<html xmlns="http://www.w3.org/1999/xhtml">
<head id="Left">
</head>
<body class="LTR IE7 ENGB">
    <ul class="CMSListMenuUL" id="Vertical2"/>
</body>
</html>
'''

TOP_FRAME_HTML = '''
<html xmlns="http://www.w3.org/1999/xhtml">
<head id="Top">
</head>
  <body class="LTR IE7 ENGB">
    <div id="topsection">
      <div id="topsectionLeft" style="cursor:pointer;" onclick="location.href='https://www.eba.europa.eu/';"></div>
      <div id="topsectionRight"></div>
      <div id="topnavigation"></div>
    </div>
  </body>
</html>
'''

CENTER_LANDING_HTML = '''
<html xmlns="http://www.w3.org/1999/xhtml">
<head id="Center">
</head>
<body class="LTR IE7 ENGB">
  <div id="plc_lt_zoneContent_usercontrol_userControlElem_ContentPanel">
    <div id="plc_lt_zoneContent_usercontrol_userControlElem_PanelTitle">
      <div id="pagetitle" style="float:left;width:500px;">
        <h1>Taxonomy Tables Viewer</h1>
      </div>
    </div>
  </div>
  <div style="clear:both;"></div>
  <div id="contentcenter">
    <p style="text-align: justify; margin-top: 0pt; margin-bottom: 0pt">Please select tables to view by clicking in the left column.</p>
  </div>
</body>
</html>
'''

TABLE_CSS_EXTRAS = '''
table {background:#fff}
'''

def indexFileHTML(indexBaseName: str) -> str:
    return f'''
<html xmlns="http://www.w3.org/1999/xhtml">
<head id="Head1">
  <title>European Banking Authority - EBA  - FINREP Taxonomy</title>
  <meta name="generator" content="Arelle(r) {Version.version}" />
  <meta name="provider" content="Aguilonius(r)" />
  <meta http-equiv="content-type" content="text/html; charset=UTF-8" />
  <meta http-equiv="pragma" content="no-cache" />
  <meta http-equiv="content-style-type" content="text/css" />
  <meta http-equiv="content-script-type" content="text/javascript" />
</head>
<frameset border="0" frameborder="0" rows="90,*">
   <frame name="head" src="{indexBaseName}TopFrame.html" scrolling="no" marginwidth="0" marginheight="10"/>
   <frameset  bordercolor="#0000cc" border="10" frameborder="no" framespacing="0" cols="360, *">
      <frame src="{indexBaseName}FormsFrame.html" name="menu" bordercolor="#0000cc"/>
      <frame src="{indexBaseName}CenterLanding.html" name="body" bordercolor="#0000cc"/>
   </frameset>
</frameset>
'''


def generateHtmlEbaTablesetFiles(dts, indexFile, lang="en"):
    try:
        numTableFiles = 0
        _parser = parser(dts, None)[0]
        indexDocument = etree.fromstring(INDEX_DOCUMENT_HTML, parser=_parser, base_url=indexFile)
        listElt = indexDocument.find(".//{http://www.w3.org/1999/xhtml}ul")
        assert listElt is not None, "No list element in index document"

        indexBase = indexFile.rpartition(".")[0]
        groupTableRels = dts.modelXbrl.relationshipSet(XbrlConst.euGroupTable)
        modelTables = []
        def viewTable(modelTable):
            if modelTable is None:
                return
            tableId = modelTable.id or ""
            if isinstance(modelTable, DefnMdlTable):
                dts.modelManager.cntlr.addToLog("viewing: " + tableId)
                tblFile = os.path.join(os.path.dirname(indexFile), tableId + ".html")
                tableName = tableId
                if tableName.startswith("eba_t"):
                    tableName = tableName.removeprefix("eba_t")
                elif tableName.startswith("srb_t"):
                    tableName = tableName.removeprefix("srb_t")
                viewRenderedGrid(dts,
                                 tblFile,
                                 lang=lang,
                                 cssExtras=TABLE_CSS_EXTRAS,
                                 table=tableName)

                elt = etree.SubElement(listElt, "{http://www.w3.org/1999/xhtml}li")
                elt.set("class", "CMSListMenuLI")
                elt.set("id", tableId)
                elt = etree.SubElement(elt, "{http://www.w3.org/1999/xhtml}a")
                elt.text = modelTable.genLabel(lang=lang, strip=True)
                elt.set("class", "CMSListMenuLink")
                elt.set("href", "javascript:void(0)")
                elt.set("onClick", f"javascript:parent.body.location.href='{tableId}.html';")
                elt.text = modelTable.genLabel(lang=lang, strip=True)
            else:
                elt = etree.SubElement(listElt, "{http://www.w3.org/1999/xhtml}li")
                elt.set("class", "CMSListMenuLink")
                elt.set("id", tableId)
                elt.text = modelTable.label(lang=lang, strip=True)

            for rel in groupTableRels.fromModelObject(modelTable):
                viewTable(rel.toModelObject)

        for rootConcept in groupTableRels.rootConcepts:
            sourceline = 0
            for rel in dts.modelXbrl.relationshipSet(XbrlConst.euGroupTable).fromModelObject(rootConcept):
                sourceline = rel.sourceline
                break
            modelTables.append((rootConcept, sourceline))

        for modelTable, _order in sorted(modelTables, key=itemgetter(1)):
            viewTable(modelTable)

        with open(indexBase + "FormsFrame.html", "w", encoding="utf-8") as fh:
            XmlUtil.writexml(fh, indexDocument, encoding="utf-8")

        with open(indexFile, "w", encoding="utf-8") as fh:
            fh.write(indexFileHTML(os.path.basename(indexBase)))

        with open(indexBase + "TopFrame.html", "w", encoding="utf-8") as fh:
            fh.write(TOP_FRAME_HTML)

        with open(indexBase + "CenterLanding.html", "w", encoding="utf-8") as fh:
            fh.write(CENTER_LANDING_HTML)

        dts.info("info:saveEBAtables",
                 _("Tables index file of %(entryFile)s has %(numberTableFiles)s table files with index file %(indexFile)s."),
                 modelObject=dts,
                 entryFile=dts.uri, numberTableFiles=numTableFiles, indexFile=indexFile)

        dts.modelManager.showStatus(_("Saved EBA HTML Table Files"), 5000)
    except Exception as ex:
        dts.error("exception",
            _("HTML EBA Tableset files generation exception: %(error)s"), error=ex,
            modelXbrl=dts,
            exc_info=True)

def saveHtmlEbaTablesMenuEntender(cntlr, menu, *args, **kwargs):
    menu.add_command(label="Save HTML EBA Tables",
                     underline=0,
                     command=lambda: saveHtmlEbaTablesMenuCommand(cntlr) )

def saveHtmlEbaTablesMenuCommand(cntlr):
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
        cntlr.addToLog("No DTS loaded.")
        return

    indexFile = cntlr.uiFileDialog("save",
            title=_("arelle - Save HTML EBA Tables Index file"),
            initialdir=cntlr.config.setdefault("htmlEbaTablesFileDir","."),
            filetypes=[(_("HTML index file .html"), "*.html")],
            defaultextension=".html")
    if not indexFile:
        return False
    cntlr.config["htmlEbaTablesFileDir"] = os.path.dirname(indexFile)
    cntlr.saveConfig()

    thread = threading.Thread(target=lambda
                                  _dts=cntlr.modelManager.modelXbrl,
                                  _indexFile=indexFile:
                                        generateHtmlEbaTablesetFiles(_dts, _indexFile))
    thread.daemon = True
    thread.start()

def saveHtmlEbaTablesCommandLineOptionExtender(parser, *args, **kwargs):
    parser.add_option("--save-EBA-tablesets",
                      action="store",
                      dest="ebaTablesetIndexFile",
                      help=_("Save HTML EBA Tablesets index file, with tablest HTML files to out directory specify 'generateOutFiles'."))

def saveHtmlEbaTablesCommandLineXbrlLoaded(cntlr, options, modelXbrl, *args, **kwargs):
    if getattr(options, "ebaTablesetIndexFile", None) and options.ebaTablesetIndexFile == "generateEBAFiles" and modelXbrl.modelDocument.type in (Type.TESTCASESINDEX, Type.TESTCASE):
        cntlr.modelManager.generateEBAFiles = True

def saveHtmlEbaTablesCommandLineXbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    if getattr(options, "ebaTablesetIndexFile", None) and options.ebaTablesetIndexFile != "generateEBAFiles":
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No taxonomy loaded.")
            return
        RenderingEvaluator.init(modelXbrl)
        generateHtmlEbaTablesetFiles(cntlr.modelManager.modelXbrl, options.ebaTablesetIndexFile)


__pluginInfo__ = {
    'name': 'Save HTML EBA Tables',
    'version': '0.9',
    'description': "This plug-in adds a feature to a directory containing HTML Tablesets with an EBA index page.",
    'license': 'Apache-2',
    'author': Version.authorLabel,
    'copyright': Version.copyrightLabel,
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': saveHtmlEbaTablesMenuEntender,
    'CntlrCmdLine.Options': saveHtmlEbaTablesCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Loaded': saveHtmlEbaTablesCommandLineXbrlLoaded,
    'CntlrCmdLine.Xbrl.Run': saveHtmlEbaTablesCommandLineXbrlRun,
}
