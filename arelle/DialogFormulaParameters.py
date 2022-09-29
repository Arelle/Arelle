'''
See COPYRIGHT.md for copyright information.
'''
from tkinter import Toplevel, N, S, E, W
try:
    from tkinter.ttk import Frame, Button
except ImportError:
    from ttk import Frame, Button
import regex as re
from arelle.UiUtil import (gridHdr, gridCell, gridCombobox, label, checkbox)

'''
caller checks accepted, if True, caller retrieves url
'''
def getParameters(mainWin):
    dialog = DialogFormulaParameters(mainWin, mainWin.modelManager.formulaOptions.__dict__.copy())
    if dialog.accepted:
        mainWin.modelManager.formulaOptions.__dict__.update(dialog.options)
        mainWin.config["formulaParameters"] = dialog.options
        mainWin.saveConfig()


class DialogFormulaParameters(Toplevel):
    def __init__(self, mainWin, options):
        parent = mainWin.parent
        self.modelManager = mainWin.modelManager
        super(DialogFormulaParameters, self).__init__(parent)
        self.parent = parent
        self.options = options
        parentGeometry = re.match("(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", parent.geometry())
        dialogX = int(parentGeometry.group(3))
        dialogY = int(parentGeometry.group(4))
        self.accepted = False

        self.transient(self.parent)
        self.title(_("Formula Parameters and Trace Options"))

        frame = Frame(self)

        '''
        dialogFrame = Frame(frame, width=500)
        dialogFrame.columnconfigure(0, weight=1)
        dialogFrame.rowconfigure(0, weight=1)
        dialogFrame.grid(row=0, column=0, columnspan=4, sticky=(N, S, E, W), padx=3, pady=3)
        '''

        # mainWin.showStatus(_("loading formula options and parameters"))

        # load grid
        gridHdr(frame, 1, 0, "Parameters", columnspan=3)
        gridHdr(frame, 1, 1, "QName")
        gridHdr(frame, 2, 1, "Type")
        gridHdr(frame, 3, 1, "Value")

        self.gridCells = []
        y = 2
        dataTypes = ("xs:string", "xs:integer", "xs:decimal", "xs:boolean", "xs:date", "xs:datetime", "xs:QName")
        for parameter in options["parameterValues"].items():
            paramQname, paramTypeValue = parameter
            if isinstance(paramTypeValue, (tuple,list)):
                paramType, paramValue = paramTypeValue  # similar to modelTestcaseObject, where values() are (type,value)
            else:
                paramType = None
                paramValue = paramTypeValue
            self.gridCells.append( (
                gridCell(frame, 1, y, paramQname),
                gridCombobox(frame, 2, y, paramType, values=dataTypes),
                gridCell(frame, 3, y, paramValue)) )
            y += 1
        # extra entry for new cells
        for i in range(5):
            self.gridCells.append( (
                gridCell(frame, 1, y),
                gridCombobox(frame, 2, y, values=dataTypes),
                gridCell(frame, 3, y)) )
            y += 1
        y += 1

        # checkbox entries
        label(frame, 1, y, "Parameter Trace:")
        label(frame, 1, y + 3, "API Calls Trace:")
        label(frame, 1, y + 8, "Testcase Results:")
        label(frame, 2, y, "Variable Set Trace:")
        label(frame, 3, y, "Variables Trace:")
        self.checkboxes = (
           checkbox(frame, 1, y + 1,
                    "Expression Result",
                    "traceParameterExpressionResult"),
           checkbox(frame, 1, y + 2,
                    "Input Value",
                    "traceParameterInputValue"),
           checkbox(frame, 1, y + 4,
                    "Expression Source",
                    "traceCallExpressionSource"),
           checkbox(frame, 1, y + 5,
                    "Expression Code",
                    "traceCallExpressionCode"),
           checkbox(frame, 1, y + 6,
                    "Expression Evaluation",
                    "traceCallExpressionEvaluation"),
           checkbox(frame, 1, y + 7,
                    "Expression Result",
                    "traceCallExpressionResult"),
           checkbox(frame, 1, y + 9,
                    "Capture Warnings",
                    "testcaseResultsCaptureWarnings"),
           gridCombobox(frame, 1, y + 10, padx=24,
                        attr="testcaseResultOptions",
                        values=("match-any", "match-all")),

           checkbox(frame, 2, y + 1,
                    "Expression Source",
                    "traceVariableSetExpressionSource"),
           checkbox(frame, 2, y + 2,
                    "Expression Code",
                    "traceVariableSetExpressionCode"),
           checkbox(frame, 2, y + 3,
                    "Expression Evaluation",
                    "traceVariableSetExpressionEvaluation"),
           checkbox(frame, 2, y + 4,
                    "Expression Result",
                    "traceVariableSetExpressionResult"),
           checkbox(frame, 2, y + 5,
                    "Assertion Result Counts",
                    "traceAssertionResultCounts"),
           checkbox(frame, 2, y + 6,
                    "Assertion Satisfied [info]",
                    "traceSatisfiedAssertions"),
           checkbox(frame, 2, y + 7,
                    "Assertion Unsatisfied [error]",
                    "errorUnsatisfiedAssertions"),
           checkbox(frame, 2, y + 8,
                    "Assertion Unsatisfied [info]",
                    "traceUnsatisfiedAssertions"),
           checkbox(frame, 2, y + 9,
                    "Formula Rules",
                    "traceFormulaRules"),
           checkbox(frame, 2, y + 10,
                    "Evaluation Timing",
                    "timeVariableSetEvaluation"),
           checkbox(frame, 3, y + 1,
                    "Variable Dependencies",
                    "traceVariablesDependencies"),
           checkbox(frame, 3, y + 2,
                    "Variables Order",
                    "traceVariablesOrder"),
           checkbox(frame, 3, y + 3,
                    "Expression Source",
                    "traceVariableExpressionSource"),
           checkbox(frame, 3, y + 4,
                    "Expression Code",
                    "traceVariableExpressionCode"),
           checkbox(frame, 3, y + 5,
                    "Expression Evaluation",
                    "traceVariableExpressionEvaluation"),
           checkbox(frame, 3, y + 6,
                    "Expression Result",
                    "traceVariableExpressionResult"),
           checkbox(frame, 3, y + 7,
                    "Filter Winnowing",
                    "traceVariableFilterWinnowing"),
           checkbox(frame, 3, y + 8,
                    "Filters Result",
                    "traceVariableFiltersResult")

           # Note: if adding to this list keep ModelFormulaObject.FormulaOptions in sync

           )
        y += 11

        mainWin.showStatus(None)

        label(frame, 1, y, "IDs:")
        self.idsEntry = gridCell(frame, 1, y, options.get("runIDs"))
        self.idsEntry.grid(columnspan=2, padx=30)
        _w = 8 if self.modelManager.cntlr.isMac else 12
        okButton = Button(frame, text=_("OK"), width=_w, command=self.ok)
        cancelButton = Button(frame, text=_("Cancel"), width=_w, command=self.close)
        okButton.grid(row=y, column=3, sticky=W, pady=3)
        cancelButton.grid(row=y, column=3, sticky=E, pady=3, padx=3)

        frame.grid(row=0, column=0, sticky=(N,S,E,W))
        frame.columnconfigure(1, weight=3)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=3)
        window = self.winfo_toplevel()
        window.columnconfigure(0, weight=1)
        self.geometry("+{0}+{1}".format(dialogX+50,dialogY+100))

        #self.bind("<Return>", self.ok)
        #self.bind("<Escape>", self.close)

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.grab_set()
        self.wait_window(self)

    def setOptions(self):
        # set formula options
        for checkbox in self.checkboxes:
            self.options[checkbox.attr] = checkbox.value
        parameterValues = {}
        for paramCells in self.gridCells:
            qnameCell, typeCell, valueCell = paramCells
            if qnameCell.value != "" and valueCell.value != "":
                # stored as strings, so they can be saved in json files
                parameterValues[qnameCell.value] = (typeCell.value, valueCell.value)
        self.options["parameterValues"] = parameterValues
        self.options["runIDs"] = self.idsEntry.value

    def ok(self, event=None):
        self.setOptions()
        self.accepted = True
        self.close()

    def close(self, event=None):
        self.parent.focus_set()
        self.destroy()
