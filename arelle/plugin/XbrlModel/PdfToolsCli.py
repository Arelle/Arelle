"""
See COPYRIGHT.md for copyright information.

Command-line wiring for the XbrlModel PDF tools, exposed through the XBRL Model
plugin (``--plugins XbrlModel``):

  * ``inlineXbrlToPdf``  — GENERATE a structurally tagged PDF from an inline
    XBRL document, with fact ``valueSources`` traceable to page + MCID.
  * ``alignFactsToSurface``  — LOCATE inline-XBRL facts inside an EXISTING second
    rendering of the same report (no rendering of its own):

      - ``--align-to-pdf``: a filer / Acrobat tagged PDF, emitting page+mcid, image
        page+bbox and form-field ``valueSources``;
      - ``--align-to-html5``: a published HTML5 report carrying no XBRL at all,
        emitting ``xbrlx:htmlElementPointer`` + text offset + quote.

Both operate on file inputs (no loaded model), so they run from the
``CntlrCmdLine.Utility.Run`` hook. Heavy dependencies (Chrome, WeasyPrint, PIL)
are imported lazily inside the tools, so wiring these options does not pull them
in until a tool is actually invoked.

Examples
--------
    arelleCmdLine --plugins XbrlModel --align-to-pdf \
        --al-html report.xhtml --al-facts report-html-facts.json \
        --al-pdf filer.pdf --al-out-facts report-pdf-facts.json

    arelleCmdLine --plugins XbrlModel --inline-to-pdf \
        --ix-html report.xhtml --ix-facts report-html-facts.json \
        --ix-pdf report.pdf

    arelleCmdLine --plugins XbrlModel --align-to-html5 \
        --al-html report.xhtml --al-facts report-html-facts.json \
        --al-html5 annual-report.html --al-out-facts report-html5-facts.json
"""
import importlib.util
import os
import sys

_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "tools")


def _loadTool(name):
    """Load a tools/*.py module by file path (the tools are standalone scripts,
    not a package, and self-configure sys.path for their own imports)."""
    path = os.path.join(_TOOLS_DIR, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def addPdfToolOptions(parser):
    """Register the PDF-tool command-line options (called from the plugin's
    ``CntlrCmdLine.Options`` hook)."""
    parser.add_option("--inline-to-pdf", action="store_true", dest="inlineToPdf",
                      help=_("XbrlModel: generate a traceable tagged PDF from inline XBRL "
                             "(requires --ix-html, --ix-facts, --ix-pdf)."))
    parser.add_option("--ix-html", dest="ixHtml", help=_("inline XBRL .xhtml/.html source"))
    parser.add_option("--ix-facts", dest="ixFacts", help=_("OIM-Taxonomy html-locator facts JSON (saveOIMFacts)"))
    parser.add_option("--ix-pdf", dest="ixPdf", help=_("output tagged PDF path"))
    parser.add_option("--ix-out-facts", dest="ixOutFacts", help=_("output rewritten facts JSON path"))
    parser.add_option("--ix-engine", dest="ixEngine", default="chrome",
                      help=_("render engine: chrome (default) or weasyprint"))
    parser.add_option("--ix-no-reflow", action="store_true", dest="ixNoReflow",
                      help=_("chrome engine: keep fixed (absolute) layout instead of reflowing"))

    parser.add_option("--align-to-pdf", action="store_true", dest="alignToPdf",
                      help=_("XbrlModel: locate inline-XBRL facts in an existing tagged PDF "
                             "(requires --al-html, --al-facts, --al-pdf)."))
    parser.add_option("--align-to-html5", action="store_true", dest="alignToHtml5",
                      help=_("XbrlModel: locate inline-XBRL facts in an existing HTML5 "
                             "rendering of the same report, emitting element pointers "
                             "(requires --al-html, --al-facts, --al-html5)."))
    parser.add_option("--al-html", dest="alHtml", help=_("inline XBRL .xhtml/.html source"))
    parser.add_option("--al-facts", dest="alFacts", help=_("OIM-Taxonomy html-locator facts JSON (saveOIMFacts)"))
    parser.add_option("--al-pdf", dest="alPdf", help=_("existing tagged PDF to locate facts within"))
    parser.add_option("--al-html5", dest="alHtml5", help=_("existing HTML5 rendering to locate facts within"))
    parser.add_option("--al-out-facts", dest="alOutFacts", help=_("output rewritten facts JSON path"))
    # Which party is running the aligner decides what its output claims, so it is stated
    # rather than inferred -- the same distinction, values and default as
    # --taggingJournalInto. See alignFactsToSurface's INTO_MODEL / INTO_DERIVED.
    parser.add_option("--alignInto", action="store", dest="alignInto",
                      choices=("model", "derivedContent"),
                      help=_("Where the located sources go: 'model' when a preparer aligns "
                             "onto a surface of their own, so the locators are the filing's "
                             "own content; 'derivedContent' (default for --align-to-html5) "
                             "when anyone else aligns onto somebody else's report, so they "
                             "are recorded as bound derived fact values beside a model left "
                             "as filed. --align-to-pdf supports 'model' only."))


def _require(cntlr, options, names):
    missing = [n for n in names if not getattr(options, n, None)]
    if missing:
        cntlr.addToLog(_("XbrlModel PDF tools: missing required options: %(m)s")
                       % {"m": ", ".join(missing)}, level="ERROR")
        return False
    return True


def runPdfTools(cntlr, options, *args, **kwargs):
    """Invoke a PDF tool if its trigger option was given (called from the
    plugin's ``CntlrCmdLine.Utility.Run`` hook)."""
    if getattr(options, "inlineToPdf", None):
        if _require(cntlr, options, ("ixHtml", "ixFacts", "ixPdf")):
            cntlr.showStatus(_("inlineXbrlToPdf: generating {0}").format(os.path.basename(options.ixPdf)))
            _loadTool("inlineXbrlToPdf").convert(
                options.ixHtml, options.ixFacts, options.ixPdf, options.ixOutFacts,
                engine=(options.ixEngine or "chrome"), reflow=not options.ixNoReflow)
    if getattr(options, "alignToPdf", None):
        if _require(cntlr, options, ("alHtml", "alFacts", "alPdf")):
            tool = _loadTool("alignFactsToSurface")
            into = getattr(options, "alignInto", None) or tool.INTO_MODEL
            if into != tool.INTO_MODEL:
                cntlr.addToLog(_("XbrlModel --align-to-pdf: --alignInto %(into)s is not "
                                 "supported for the PDF surface (it emits two fact locator "
                                 "types, and a derived content object names one source); "
                                 "use --alignInto model.") % {"into": into}, level="ERROR")
            else:
                cntlr.showStatus(_("alignFactsToSurface: locating facts in {0}").format(os.path.basename(options.alPdf)))
                tool.align(options.alHtml, options.alFacts, options.alPdf, options.alOutFacts,
                           into=into)
    if getattr(options, "alignToHtml5", None):
        if _require(cntlr, options, ("alHtml", "alFacts", "alHtml5")):
            tool = _loadTool("alignFactsToSurface")
            cntlr.showStatus(_("alignFactsToSurface: locating facts in {0}").format(os.path.basename(options.alHtml5)))
            tool.alignToHtml5(options.alHtml, options.alFacts, options.alHtml5,
                              options.alOutFacts,
                              into=getattr(options, "alignInto", None) or tool.INTO_DERIVED)


# --------------------------------------------------------------------------
# GUI (Tools menu). The tools operate on file inputs and need no loaded model,
# so the menu items just prompt for files and run the tool in a background
# thread (large filings take minutes). Advanced options (engine, --no-reflow)
# are command-line only; the GUI uses the defaults (chrome engine, reflow on).
# --------------------------------------------------------------------------
def _askOpen(cntlr, key, title, filetypes):
    path = cntlr.uiFileDialog("open", title=title,
                              initialdir=cntlr.config.setdefault(key, "."),
                              filetypes=filetypes)
    if path:
        cntlr.config[key] = os.path.dirname(path)
        cntlr.saveConfig()
    return path


def _askSave(cntlr, key, title, filetypes, defaultextension):
    path = cntlr.uiFileDialog("save", title=title,
                              initialdir=cntlr.config.setdefault(key, "."),
                              filetypes=filetypes, defaultextension=defaultextension)
    if path:
        cntlr.config[key] = os.path.dirname(path)
        cntlr.saveConfig()
    return path


def _runInThread(cntlr, label, fn):
    import threading

    def _work():
        try:
            cntlr.showStatus(_("{0}: running …").format(label))
            fn()
            cntlr.showStatus(_("{0}: done").format(label), clearAfter=5000)
            cntlr.addToLog(_("%(label)s completed.") % {"label": label})
        except Exception as ex:  # keep the GUI responsive on failure
            cntlr.addToLog(_("%(label)s exception: %(err)s")
                           % {"label": label, "err": ex}, level="ERROR")
    threading.Thread(target=_work, daemon=True).start()


def guiGenerate(cntlr):
    htmlFt = [(_("Inline XBRL (.xhtml .htm .html)"), "*.xhtml *.htm *.html")]
    jsonFt = [(_("OIM facts JSON (.json)"), "*.json")]
    pdfFt = [(_("PDF (.pdf)"), "*.pdf")]
    html = _askOpen(cntlr, "xbrlModelPdfHtmlDir", _("Select inline XBRL document"), htmlFt)
    if not html:
        return
    facts = _askOpen(cntlr, "xbrlModelPdfFactsDir",
                     _("Select html-locator facts JSON (from saveOIMFacts)"), jsonFt)
    if not facts:
        return
    pdf = _askSave(cntlr, "xbrlModelPdfOutDir", _("Save generated tagged PDF as"), pdfFt, ".pdf")
    if not pdf:
        return
    outFacts = os.path.splitext(pdf)[0] + "-pdf-facts.json"
    _runInThread(cntlr, _("Inline XBRL → tagged PDF"),
                 lambda: _loadTool("inlineXbrlToPdf").convert(
                     html, facts, pdf, outFacts, engine="chrome", reflow=True))


def guiAlign(cntlr):
    htmlFt = [(_("Inline XBRL (.xhtml .htm .html)"), "*.xhtml *.htm *.html")]
    jsonFt = [(_("OIM facts JSON (.json)"), "*.json")]
    pdfFt = [(_("PDF (.pdf)"), "*.pdf")]
    html = _askOpen(cntlr, "xbrlModelPdfHtmlDir", _("Select inline XBRL document"), htmlFt)
    if not html:
        return
    facts = _askOpen(cntlr, "xbrlModelPdfFactsDir",
                     _("Select html-locator facts JSON (from saveOIMFacts)"), jsonFt)
    if not facts:
        return
    pdf = _askOpen(cntlr, "xbrlModelPdfInDir", _("Select existing tagged PDF"), pdfFt)
    if not pdf:
        return
    outFacts = _askSave(cntlr, "xbrlModelPdfOutDir", _("Save located facts JSON as"), jsonFt, ".json")
    if not outFacts:
        return
    _runInThread(cntlr, _("Locate facts in PDF"),
                 lambda: _loadTool("alignFactsToSurface").align(html, facts, pdf, outFacts))


def guiAlignHtml5(cntlr):
    htmlFt = [(_("Inline XBRL (.xhtml .htm .html)"), "*.xhtml *.htm *.html")]
    jsonFt = [(_("OIM facts JSON (.json)"), "*.json")]
    html5Ft = [(_("HTML5 document (.html .htm)"), "*.html *.htm")]
    html = _askOpen(cntlr, "xbrlModelPdfHtmlDir", _("Select inline XBRL document"), htmlFt)
    if not html:
        return
    facts = _askOpen(cntlr, "xbrlModelPdfFactsDir",
                     _("Select html-locator facts JSON (from saveOIMFacts)"), jsonFt)
    if not facts:
        return
    target = _askOpen(cntlr, "xbrlModelHtml5InDir",
                      _("Select the HTML5 rendering to locate facts within"), html5Ft)
    if not target:
        return
    outFacts = _askSave(cntlr, "xbrlModelPdfOutDir", _("Save located facts JSON as"), jsonFt, ".json")
    if not outFacts:
        return
    # The GUI takes the default party -- derived content, which claims nothing on the filer's
    # behalf. A preparer aligning onto their own website uses --alignInto model on the command
    # line, as with the engine and reflow options above.
    _runInThread(cntlr, _("Locate facts in HTML5 rendering"),
                 lambda: _loadTool("alignFactsToSurface").alignToHtml5(html, facts, target, outFacts))


def addPdfToolsMenu(cntlr, menu):
    """Add the fact-locator tools to the GUI Tools menu (called from the
    plugin's ``CntlrWinMain.Menu.Tools`` hook)."""
    menu.add_command(label=_("Inline XBRL → tagged PDF (generate)…"),
                     underline=0, command=lambda: guiGenerate(cntlr))
    menu.add_command(label=_("Locate facts in existing tagged PDF…"),
                     underline=0, command=lambda: guiAlign(cntlr))
    menu.add_command(label=_("Locate facts in an HTML5 rendering…"),
                     underline=0, command=lambda: guiAlignHtml5(cntlr))
