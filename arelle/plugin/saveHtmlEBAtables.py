"""
Save HTML EBA Tables is an example of a plug-in to both GUI menu and command line/web service
that will save a directory containing HTML Tablesets with an EBA index page.

See COPYRIGHT.md for copyright information.
"""

import os
import threading
from operator import itemgetter
from optparse import OptionParser
from tkinter import Menu
from typing import Any

from lxml import etree

from arelle import Version, XbrlConst, XmlUtil
from arelle.CntlrCmdLine import CntlrCmdLine
from arelle.CntlrWinMain import CntlrWinMain
from arelle.ModelDocument import Type
from arelle.ModelObjectFactory import parser
from arelle.ModelRenderingObject import DefnMdlTable
from arelle.ModelXbrl import ModelXbrl
from arelle.rendering import RenderingEvaluator
from arelle.RuntimeOptions import RuntimeOptions
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import PluginHooks
from arelle.ViewFileRenderedGrid import viewRenderedGrid

_: TypeGetText

MENU_HTML = """<!DOCTYPE html>
<html>
<head>
  <style>
    body {
      margin: 0;
      padding: 10px;
      font-family: Arial, sans-serif;
      color: #243e5e;
    }
    .nav-list-menu-ul {
      list-style-type: none;
      padding: 0;
      margin: 0;
    }
    .nav-list-menu-li {
      margin: 5px 0;
      padding: 5px;
      border-bottom: 1px solid #eee;
    }
    .nav-list-menu-link {
      text-decoration: none;
      cursor: pointer;
      display: block;
      background: none;
      border: none;
      padding: 0;
    }
    .nav-list-menu-link:hover {
      text-decoration: underline;
    }
  </style>
</head>
<body>
    <ul class="nav-list-menu-ul"/>
</body>
</html>
"""

CENTER_LANDING_HTML = """<!DOCTYPE html>
<html>
<head>
  <style>
    body {
      margin: 0;
      padding: 20px;
      font-family: Arial, sans-serif;
    }
    #page-title {
      margin-bottom: 20px;
    }
    #page-title h1 {
      color: #243e5e;
      margin-top: 0;
    }
    #content-center {
      margin-top: 20px;
      line-height: 1.5;
    }
  </style>
</head>
<body>
  <div id="page-title">
    <h1>Taxonomy Tables Viewer</h1>
  </div>
  <div id="content-center">
    <p>Please select tables to view by clicking in the left column.</p>
  </div>
</body>
</html>
"""

TABLE_CSS_EXTRAS = """
table {background:#fff}
"""


def indexFileHTML(indexBaseName: str) -> str:
    return f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EBA - Tablesets</title>
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      height: 100%;
      width: 100%;
      font-family: Arial, sans-serif;
      display: flex;
      flex-direction: column;
    }}
    #header {{
      background: rgb(36, 62, 94);
      color: rgb(255, 255, 255);
      height: 40px;
    }}
    #header h1 {{
      font-size: 1.5em;
      margin: 0.25em;
    }}
    #main-container {{
      display: flex;
      flex: 1;
      height: calc(100vh - 40px);
    }}
    #menu-container {{
      width: 360px;
      border-right: 2px solid #243e5e;
      overflow-y: auto;
      box-sizing: border-box;
    }}
    #content-container {{
      flex: 1;
      overflow: auto;
      box-sizing: border-box;
    }}
    iframe {{
      border: none;
      width: 100%;
      height: 100%;
    }}
  </style>
  <script>
    function loadContent(url) {{
      document.getElementById('content-frame').src = url;
    }}
  </script>
</head>
<body>
  <div id="header"><h1>EBA - Tablesets</h1></div>
  <div id="main-container">
    <div id="menu-container">
      <iframe src="{indexBaseName}FormsFrame.html" width="100%" height="100%" frameborder="0" id="menu-frame"></iframe>
    </div>
    <div id="content-container">
      <iframe src="{indexBaseName}CenterLanding.html" width="100%" height="100%" frameborder="0" id="content-frame"></iframe>
    </div>
  </div>
</body>
</html>
'''


def generateHtmlEbaTablesetFiles(dts: ModelXbrl, indexFile: str, lang: str = "en") -> None:
    try:
        numTableFiles = 0
        _parser = parser(dts, None)[0]
        menuFrameDocument = etree.fromstring(MENU_HTML, parser=_parser, base_url=indexFile)
        listElt = menuFrameDocument.find(".//ul")
        assert listElt is not None, "No list element in index document"

        indexBase = indexFile.rpartition(".")[0]
        groupTableRels = dts.modelXbrl.relationshipSet(XbrlConst.euGroupTable)
        modelTables = []

        def viewTable(modelTable: DefnMdlTable) -> None:
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
                viewRenderedGrid(dts, tblFile, lang=lang, cssExtras=TABLE_CSS_EXTRAS, table=tableName)  # type: ignore[no-untyped-call]

                elt = etree.SubElement(listElt, "li")
                elt.set("class", "nav-list-menu-li")
                elt.set("id", tableId)
                elt = etree.SubElement(elt, "button")
                elt.text = modelTable.genLabel(lang=lang, strip=True)
                elt.set("class", "nav-list-menu-link")
                elt.set("onClick", f"javascript:parent.loadContent('{tableId}.html');")
                elt.text = modelTable.genLabel(lang=lang, strip=True)
            else:
                elt = etree.SubElement(listElt, "li")
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
            XmlUtil.writexml(fh, menuFrameDocument, encoding="utf-8")

        with open(indexFile, "w", encoding="utf-8") as fh:
            fh.write(indexFileHTML(os.path.basename(indexBase)))

        with open(indexBase + "CenterLanding.html", "w", encoding="utf-8") as fh:
            fh.write(CENTER_LANDING_HTML)

        dts.info(
            "info:saveEBAtables",
            _("Tables index file of %(entryFile)s has %(numberTableFiles)s table files with index file %(indexFile)s."),
            modelObject=dts,
            entryFile=dts.uri,
            numberTableFiles=numTableFiles,
            indexFile=indexFile,
        )

        dts.modelManager.showStatus(_("Saved EBA HTML Table Files"), 5000)
    except Exception as ex:
        dts.error(
            "exception",
            _("HTML EBA Tableset files generation exception: %(error)s"),
            error=ex,
            modelXbrl=dts,
            exc_info=True,
        )


def saveHtmlEbaTablesMenuCommand(cntlr: CntlrWinMain) -> None:
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
        cntlr.addToLog("No DTS loaded.")  # type: ignore[no-untyped-call]
        return

    assert cntlr.config is not None
    indexFile = cntlr.uiFileDialog(  # type: ignore[no-untyped-call]
        "save",
        title=_("arelle - Save HTML EBA Tables Index file"),
        initialdir=cntlr.config.setdefault("htmlEbaTablesFileDir", "."),
        filetypes=[(_("HTML index file .html"), "*.html")],
        defaultextension=".html",
    )
    if not isinstance(indexFile, str):
        return
    cntlr.config["htmlEbaTablesFileDir"] = os.path.dirname(indexFile)
    cntlr.saveConfig()

    thread = threading.Thread(
        target=lambda _dts=cntlr.modelManager.modelXbrl, _indexFile=indexFile: generateHtmlEbaTablesetFiles(
            _dts, _indexFile
        )
    )
    thread.daemon = True
    thread.start()


class SaveHtmlEbaTablesPlugin(PluginHooks):
    @staticmethod
    def cntlrWinMainMenuTools(
        cntlr: CntlrWinMain,
        menu: Menu,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        menu.add_command(label="Save HTML EBA Tables", underline=0, command=lambda: saveHtmlEbaTablesMenuCommand(cntlr))

    @staticmethod
    def cntlrCmdLineOptions(
        parser: OptionParser,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        parser.add_option(
            "--save-EBA-tablesets",
            action="store",
            dest="ebaTablesetIndexFile",
            help=_("Save HTML EBA Tablesets index file with provided filename."),
        )

    @staticmethod
    def cntlrCmdLineXbrlLoaded(
        cntlr: CntlrCmdLine,
        options: RuntimeOptions,
        modelXbrl: ModelXbrl,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        ebaTablesetIndexFile = getattr(options, "ebaTablesetIndexFile", None)
        modelDocType = getattr(modelXbrl.modelDocument, "type", None)
        if ebaTablesetIndexFile == "generateEBAFiles" and modelDocType in (Type.TESTCASESINDEX, Type.TESTCASE):
            cntlr.modelManager.generateEBAFiles = True  # type: ignore[attr-defined]

    @staticmethod
    def cntlrCmdLineXbrlRun(
        cntlr: CntlrCmdLine,
        options: RuntimeOptions,
        modelXbrl: ModelXbrl,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        ebaTablesetIndexFile = getattr(options, "ebaTablesetIndexFile", None)
        if ebaTablesetIndexFile is None or ebaTablesetIndexFile == "generateEBAFiles":
            return
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No taxonomy loaded.")
            return
        RenderingEvaluator.init(modelXbrl)  # type: ignore[no-untyped-call]
        generateHtmlEbaTablesetFiles(cntlr.modelManager.modelXbrl, ebaTablesetIndexFile)


__pluginInfo__ = {
    "name": "Save HTML EBA Tables",
    "version": "0.10",
    "description": "This plug-in adds a feature to a directory containing HTML Tablesets with an EBA index page.",
    "license": "Apache-2",
    "author": Version.authorLabel,
    "copyright": Version.copyrightLabel,
    # classes of mount points (required)
    "CntlrWinMain.Menu.Tools": SaveHtmlEbaTablesPlugin.cntlrWinMainMenuTools,
    "CntlrCmdLine.Options": SaveHtmlEbaTablesPlugin.cntlrCmdLineOptions,
    "CntlrCmdLine.Xbrl.Loaded": SaveHtmlEbaTablesPlugin.cntlrCmdLineXbrlLoaded,
    "CntlrCmdLine.Xbrl.Run": SaveHtmlEbaTablesPlugin.cntlrCmdLineXbrlRun,
}
