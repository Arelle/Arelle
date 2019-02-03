'''
Created on Feb 1, 2019

@author: Mark V Systems Limited
(c) Copyright 2019 Mark V Systems Limited, All rights reserved.

This plugin allows GUI users to test transforms,

Custom extensions are also made available when their plugin has been loaded
(e.g., for SEC custom transforms use plugin transforms/SEC, validate/EFM or EdgarRenderer)

Errors are shown both in results field as well as reported in the message pane.
'''
from tkinter import Toplevel, StringVar, N, S, E, EW, W, PhotoImage
try:
    from tkinter.ttk import Frame, Button, Entry
except ImportError:
    from ttk import Frame, Button
import os, re
from arelle.FunctionIxt import ixtNamespaces, ixtNamespaceFunctions
from arelle.UiUtil import gridHdr, gridCell, gridCombobox, label, checkbox
from arelle.CntlrWinTooltip import ToolTip
from arelle.ModelFormulaObject import Trace
from arelle.XmlUtil import setXmlns
from arelle import ModelDocument, ModelXbrl, ValidateXbrl, XbrlConst, XPathParser, XPathContext

class DialogTransformTester(Toplevel):
    def __init__(self, mainWin):
        parent = mainWin.parent
        super(DialogTransformTester, self).__init__(parent)
        self.mainWin = mainWin
        self.parent = parent
        parentGeometry = re.match("(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", parent.geometry())
        dialogX = int(parentGeometry.group(3))
        dialogY = int(parentGeometry.group(4))
        self.selectedGroup = None

        self.transient(self.parent)
        self.title(_("Transformation Tester"))
        
        frame = Frame(self)
        
        # setup tester
        xml = "<rootElement/>"
        self.modelXbrl = ModelXbrl.create(mainWin.modelManager, ModelDocument.Type.UnknownNonXML, initialXml=xml, isEntry=True)
        self.validator = ValidateXbrl.ValidateXbrl(self.modelXbrl)
        self.validator.validate(self.modelXbrl)  # required to set up
        mainWin.showStatus(_("Initializing Formula Grammar"))
        XPathParser.initializeParser(mainWin.modelManager)
        mainWin.showStatus(None)

        self.trRegs = sorted(ixtNamespaces.keys())
        self.trReg = self.trRegs[-1] # default is latest
        self.trPrefixNSs = dict((qn.prefix, qn.namespaceURI) 
                                  for qn in self.modelXbrl.modelManager.customTransforms.keys())
        self.trRegs.extend(sorted(self.trPrefixNSs.keys()))
        self.trPrefixNSs.update(ixtNamespaces)
        self.trNames = self.getTrNames()

        # load grid
        trRegLabel = label(frame, 0, 0, _("Registry:"))
        self.trRegName = gridCombobox(frame, 1, 0, 
                                      value=self.trReg,
                                      values=self.trRegs, 
                                      comboboxselected=self.trRegComboBoxSelected)
        trRegToolTipMessage = _("Select Transformation Registry")
        ToolTip(self.trRegName, text=trRegToolTipMessage, wraplength=360)
        ToolTip(trRegLabel, text=trRegToolTipMessage, wraplength=360)
        
        trNameLabel = label(frame, 0, 1, _("Transform:"))
        self.trNameName = gridCombobox(frame, 1, 1, 
                                      value="",
                                      values=self.trNames, 
                                      comboboxselected=self.trNameComboBoxSelected)
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

        
        mainWin.showStatus(None)

        btnPad = 2 if mainWin.isMSW else 0 # buttons too narrow on windows
        okButton = Button(frame, text=_("Transform"), width=8 + btnPad, command=self.ok)
        cancelButton = Button(frame, text=_("Done"), width=4 + btnPad, command=self.close)
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
        
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.grab_set()
        
        self.wait_window(self)
        
    def ok(self, event=None):
        trName = self.trNameName.value
        sourceValue = self.sourceVar.get()
        try:                            
            self.modelXbrl.modelManager.showStatus(_("Executing call"))
            elt =self.modelXbrl.modelDocument.xmlRootElement
            callExprStack = XPathParser.parse(self.validator, 
                                              '{}("{}")'.format(trName, sourceValue),
                                              elt, trName + " call", Trace.CALL)
            xpathContext = XPathContext.create(self.modelXbrl, sourceElement=elt)
            result = xpathContext.evaluate(callExprStack)
            while result and isinstance(result, (tuple,list,set)):
                result = next(iter(result)) # de-sequence result
            self.resultVar.set(str(result))
        except XPathContext.XPathException as err:
            self.resultVar.set(str(err))
            self.modelXbrl.error(err.code, err.message)
        
    def close(self, event=None):
        self.modelXbrl.close()
        self.parent.focus_set()
        self.destroy()

    def trRegComboBoxSelected(self, *args):
        self.trReg = self.trRegName.get()
        self.trNames = self.getTrNames()
        self.trNameName["values"] = self.trNames
        
    def trNameComboBoxSelected(self, *args):
        pass
        
    def getTrNames(self):
        self.trNS = self.trPrefixNSs[self.trReg]
        self.trPrefix = self.trReg.split()[0] # for ixt remove TRn part
        setXmlns(self.modelXbrl.modelDocument, self.trPrefix, self.trNS)
        if self.trNS in ixtNamespaceFunctions:
            return sorted("{}:{}".format(self.trPrefix, key)
                          for key in ixtNamespaceFunctions[self.trNS].keys())
        # custom transforms
        return sorted(str(trQn)
                      for trQn in self.modelXbrl.modelManager.customTransforms.keys()
                      if trQn.prefix == self.trPrefix)
        

def transformationTesterMenuExtender(cntlr, menu, *args, **kwargs):
    def transformationTester():
        DialogTransformTester(cntlr)

    menu.add_command(label="Transformtion Tester", 
                     underline=0, 
                     command=lambda: transformationTester() )


__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Transformation tester',
    'version': '1.0',
    'description': '''Transformation Tester''',
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2019 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': transformationTesterMenuExtender

}
