'''
See COPYRIGHT.md for copyright information.

This plugin allows GUI and command line users to test transforms.

Custom extensions are also made available when their plugin has been loaded
(e.g., for SEC custom transforms use plugin transforms/SEC, validate/EFM or EdgarRenderer)

Errors are shown both in results field as well as reported in the message pane (GUI) and reported in log (command line).

For GUI operation tools -> transformation tester:

    Select registry (ixt v1-4, ixt-sec)
    Select or enter transform
    Enter source text
    Press "transform"
    Result (or error code)

For command line operation:

    arelleCmdLine --plugins transforms/tester --testTransform 'registry name transformation name pattern' (space separated)
    note: the transform name may be optionally prefixed
    results or errors are in the log

    arelleCmdLine --plugins transforms/tester --testTransform 'ixt v3 datedaymonthen 29th February' or
    arelleCmdLine --plugins transforms/tester --testTransform 'ixt v3 ixt:datedaymonthen 29th February'

    SEC transform example:

    arelleCmdLine --plugins 'transforms/tester|transforms/SEC' --testTransform "ixt-sec durwordsen 23 days"

    Help instructions and list of available transforms:

    arelleCmdLine --plugins transforms/tester --testTransform 'help'  (or '?') or
    arelleCmdLine --plugins 'transforms/tester|transforms/SEC' --testTransform 'help'

For REST API operation:
    web browser: http://localhost:8080/rest/xbrl/validation?plugins=transforms/tester&testTransform=ixt v3 datedaymonthen 29th February
    cmd line: curl 'http://localhost:8080/rest/xbrl/validation?plugins=transforms/tester&testTransform=ixt%20v3%20datedaymonthen%2029th%20February'

'''
import os, re, logging
from optparse import SUPPRESS_HELP
from arelle.FunctionIxt import ixtNamespaces, ixtNamespaceFunctions
from arelle.ModelFormulaObject import Trace
from arelle.Version import authorLabel, copyrightLabel
from arelle.XmlUtil import setXmlns
from arelle import ModelDocument, ModelXbrl, ValidateXbrl, XbrlConst, XPathParser, XPathContext

class TransformTester:
    def __init__(self, cntlr, isCmdLine=False):
        self.cntlr = cntlr

        # setup tester
        xml = "<rootElement/>"
        self.modelXbrl = ModelXbrl.create(cntlr.modelManager, ModelDocument.Type.UnknownNonXML, initialXml=xml, isEntry=True)
        self.validator = ValidateXbrl.ValidateXbrl(self.modelXbrl)
        self.validator.validate(self.modelXbrl)  # required to set up
        cntlr.showStatus(_("Initializing Formula Grammar"))
        XPathParser.initializeParser(cntlr.modelManager)
        cntlr.showStatus(None)

        self.trRegs = sorted(ixtNamespaces.keys())
        self.trPrefixNSs = dict((qn.prefix, qn.namespaceURI)
                                  for qn in self.modelXbrl.modelManager.customTransforms.keys())
        self.trRegs.extend(sorted(self.trPrefixNSs.keys()))
        self.trPrefixNSs.update(ixtNamespaces)

    def getTrNames(self, trReg):
        trNS = self.trPrefixNSs[trReg]
        trPrefix = trReg.split()[0] # for ixt remove TRn part
        setXmlns(self.modelXbrl.modelDocument, trPrefix, trNS)
        if trNS in ixtNamespaceFunctions:
            return sorted("{}:{}".format(trPrefix, key)
                          for key in ixtNamespaceFunctions[trNS].keys())
        # custom transforms
        return sorted(str(trQn)
                      for trQn in self.modelXbrl.modelManager.customTransforms.keys()
                      if trQn.prefix == trPrefix)

    def transform(self, trReg, trName, sourceValue):
        try:
            trNS = self.trPrefixNSs[trReg]
            trPrefix = trReg.split()[0] # for ixt remove TRn part
            setXmlns(self.modelXbrl.modelDocument, trPrefix, trNS)
            self.modelXbrl.modelManager.showStatus(_("Executing call"))
            elt = self.modelXbrl.modelDocument.xmlRootElement
            if ':' in trName:
                prefixedFnName = trName
            else:
                prefixedFnName = "{}:{}".format(trPrefix, trName)
            callExprStack = XPathParser.parse(self.validator,
                                              '{}("{}")'.format(prefixedFnName, sourceValue),
                                              elt, trName + " call", Trace.CALL)
            xpathContext = XPathContext.create(self.modelXbrl, sourceElement=elt)
            result = xpathContext.evaluate(callExprStack)
            while result and isinstance(result, (tuple,list,set)):
                result = next(iter(result)) # de-sequence result
            return result
        except XPathContext.XPathException as err:
            self.modelXbrl.error(err.code, err.message)
            return err



def cmdLineOptionExtender(parser, *args, **kwargs):
    parser.add_option("--testTransform",
                      action="store",
                      dest="testTransform",
                      help=_("Test a transformation registry transform. "
                             "Enter 'help' or '?' for a list of transformation registries available.  "
                             "Enter registry name, space, transformation name, space and pattern.  "
                             "E.g., 'ixt v3 datedaymonthen 29th February' or ixt v3 ixt:datedaymonthen 29th February'. "))


def cmdLineRun(cntlr, options, *args, **kwargs):
    if options.testTransform:
        tester = TransformTester(cntlr)
        arg = options.testTransform
        argWord, _sep, rest = arg.partition(" ")
        trReg = None
        for _regName in tester.trPrefixNSs.keys():
            if arg.startswith(_regName):
                trReg = _regName
                rest = arg[len(trReg)+1:]
        if trReg is None or argWord in ("help", "?"):
            cntlr.addToLog("Registries available: {}".format(", ".join(tester.trRegs)),
                           messageCode="tester:registries", level=logging.INFO)
        else:
            trName, _sep, sourceValue = rest.partition(" ")
            print("reg {} name {} source {}".format(trReg, trName, sourceValue))
            result = tester.transform(trReg, trName, sourceValue)
            tester.modelXbrl.info("tester:transformation",
                                  "%(registry)s %(transformName)s source '%(sourceValue)s' result '%(resultValue)s'",
                                  registry=trReg, transformName=trName, sourceValue=sourceValue, resultValue=str(result))
        tester.modelXbrl.close()

def transformationTesterMenuExtender(cntlr, menu, *args, **kwargs):
    # define tkinger only when running in GUI mode, not available in cmd line or web server modes
    from tkinter import Toplevel, StringVar, N, S, E, EW, W
    try:
        from tkinter.ttk import Frame, Button, Entry
    except ImportError:
        from ttk import Frame, Button
    from arelle.UiUtil import gridHdr, gridCell, gridCombobox, label, checkbox
    from arelle.CntlrWinTooltip import ToolTip
    class DialogTransformTester(Toplevel):
        def __init__(self, tester):
            self.tester = tester
            self.mainWin = tester.cntlr

            parent = self.mainWin.parent
            super(DialogTransformTester, self).__init__(parent)
            self.parent = parent
            parentGeometry = re.match("(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", parent.geometry())
            dialogX = int(parentGeometry.group(3))
            dialogY = int(parentGeometry.group(4))
            self.selectedGroup = None

            self.transient(self.parent)
            self.title(_("Transformation Tester"))

            frame = Frame(self)

            # load grid
            trRegLabel = label(frame, 0, 0, _("Registry:"))
            trReg = self.tester.trRegs[-1] # default is latest
            self.trRegName = gridCombobox(frame, 1, 0,
                                          value=trReg,
                                          values=self.tester.trRegs,
                                          comboboxselected=self.dialogTrRegComboBoxSelected)
            trRegToolTipMessage = _("Select Transformation Registry")
            ToolTip(self.trRegName, text=trRegToolTipMessage, wraplength=360)
            ToolTip(trRegLabel, text=trRegToolTipMessage, wraplength=360)

            trNameLabel = label(frame, 0, 1, _("Transform:"))
            self.trNameName = gridCombobox(frame, 1, 1,
                                          value="",
                                          values=self.tester.getTrNames(trReg),
                                          comboboxselected=self.dialogTrNameComboBoxSelected)
            trRegToolTipMessage = _("Select or enter transform")
            ToolTip(self.trRegName, text=trRegToolTipMessage, wraplength=360)
            ToolTip(trRegLabel, text=trRegToolTipMessage, wraplength=360)

            sourceLabel = label(frame, 0, 2, _("Source text:"))
            ToolTip(sourceLabel, text=_("Enter the source text which is to be transformed. "), wraplength=240)
            self.sourceVar = StringVar()
            self.sourceVar.set("")
            sourceEntry = Entry(frame, textvariable=self.sourceVar, width=50)
            sourceLabel.grid(row=2, column=0, sticky=W)
            sourceEntry.grid(row=2, column=1, sticky=EW, pady=3, padx=3)

            resultLabel = label(frame, 1, 3, _("Result:"))
            ToolTip(sourceLabel, text=_("Transformation result. "), wraplength=240)
            self.resultVar = StringVar()
            self.resultVar.set("")
            resultEntry = Entry(frame, textvariable=self.resultVar, width=50)
            resultLabel.grid(row=3, column=0, sticky=W)
            resultEntry.grid(row=3, column=1, sticky=EW, pady=3, padx=3)


            self.mainWin.showStatus(None)

            btnPad = 2 if self.mainWin.isMSW else 0 # buttons too narrow on windows
            okButton = Button(frame, text=_("Transform"), width=8 + btnPad, command=self.dialogOk)
            cancelButton = Button(frame, text=_("Done"), width=4 + btnPad, command=self.dialogClose)
            cancelButton.grid(row=4, column=0, sticky=E, columnspan=2, pady=3, padx=3)
            okButton.grid(row=4, column=0, sticky=E, columnspan=2, pady=3, padx=64)
            ToolTip(okButton, text=_("Transform the source entered. "), wraplength=240)
            ToolTip(cancelButton, text=_("Close this dialog. "), wraplength=240)

            frame.grid(row=0, column=0, sticky=(N,S,E,W))
            frame.columnconfigure(1, weight=3)
            frame.columnconfigure(2, weight=1)
            window = self.winfo_toplevel()
            window.columnconfigure(0, weight=1)
            self.geometry("+{0}+{1}".format(dialogX+150,dialogY+100))

            #self.bind("<Return>", self.ok)
            #self.bind("<Escape>", self.close)

            self.protocol("WM_DELETE_WINDOW", self.dialogClose)
            self.grab_set()

            self.wait_window(self)

        def dialogOk(self, event=None):
            result = self.tester.transform(
                self.trRegName.get(),
                self.trNameName.value,
                self.sourceVar.get())
            if isinstance(result, XPathContext.XPathException):
                self.resultVar.set(str(result))
            else:
                self.resultVar.set(str(result))

        def dialogClose(self, event=None):
            self.tester.modelXbrl.close()
            self.parent.focus_set()
            self.destroy()

        def dialogTrRegComboBoxSelected(self, *args):
            self.trNameName["values"] = self.tester.getTrNames( self.trRegName.get() )

        def dialogTrNameComboBoxSelected(self, *args):
            pass

    def guiTransformationTester():
        tester = TransformTester(cntlr, isCmdLine=True)
        DialogTransformTester( tester )
        tester.modelXbrl.close()

    menu.add_command(label="Transformtion Tester",
                     underline=0,
                     command=lambda: guiTransformationTester() )


__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Transformation tester',
    'version': '1.0',
    'description': '''Transformation Tester''',
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrCmdLine.Options': cmdLineOptionExtender,
    'CntlrCmdLine.Utility.Run': cmdLineRun,
    'CntlrWinMain.Menu.Tools': transformationTesterMenuExtender

}
