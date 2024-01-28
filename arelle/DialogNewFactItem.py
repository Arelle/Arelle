'''
See COPYRIGHT.md for copyright information.
'''
from tkinter import Toplevel, N, S, E, W, messagebox
try:
    from tkinter.ttk import Frame, Button
except ImportError:
    from ttk import Frame, Button
import regex as re
from arelle.ModelInstanceObject import NewFactItemOptions
from arelle.ModelValue import dateTime
from arelle import XmlUtil
from arelle.UiUtil import gridCell, gridCombobox, label
from arelle.CntlrWinTooltip import ToolTip

'''
caller checks accepted, if True, caller retrieves url
'''
def getNewFactItemOptions(mainWin, newInstanceOptions=None):
    if newInstanceOptions is None: newInstanceOptions = NewFactItemOptions()
    # use prior prevOptionValues for those keys not in existing newInstanceOptions
    for prevOptionKey, prevOptionValue in mainWin.config.get("newFactItemOptions",{}).items():
        if not getattr(newInstanceOptions, prevOptionKey, None):
            newInstanceOptions.__dict__[prevOptionKey] = prevOptionValue
    dialog = DialogNewFactItemOptions(mainWin, newInstanceOptions)
    if dialog.accepted:
        if dialog.options is not None: # pickle as strings, DateTime won't unpickle right
            mainWin.config["newFactItemOptions"] = dialog.options.__dict__.copy()
        mainWin.saveConfig()
        return True
    return False

monetaryUnits = ("AED", "AFN", "ALL", "AMD", "ANG", "AON", "ARP", "ATS", "AUD", "AWF", "AZM",
                 "AZN", "BAK", "BBD", "BDT", "BEF", "BGL", "BHD", "BIF", "BMD", "BND", "BOB",
                 "BRR", "BSD", "BTR", "BWP", "BYR", "BZD", "CAD", "CHF", "CLP", "CNY", "COP",
                 "CRC", "CSK", "CUP", "CVE", "CYP", "DEM", "DJF", "DKK", "DOP", "DZD", "ECS",
                 "EEK", "EGP", "ERN", "ESP", "ETB", "EUR", "FIM", "FJD", "FKP", "FRF", "GBP",
                 "GEL", "GHC", "GIP", "GMD", "GNF", "GRD", "GTQ", "GYD", "HKD", "HNL", "HRK",
                 "HTG", "HUF", "IDR", "IEP", "IEP", "ILS", "INR", "IQD", "IRR", "ISK", "ITL",
                 "JMD", "JOD", "JPY", "KES", "KGS", "KHR", "KMF", "KPW", "KRW", "KWD", "KYD",
                 "KZT", "LAK", "LBP", "LKR", "LRD", "LSL", "LTL", "LUF", "LVL", "LYD", "MAD",
                 "MDL", "MGF", "MKD", "MMK", "MNT", "MOP", "MRO", "MTL", "MUR", "MVR", "MWK",
                 "MXP", "MYR", "MZM", "NAD", "NGN", "NIO", "NLG", "NOK", "NPR", "NZD", "OMR",
                 "PAB", "PEN", "PGK", "PHP", "PKR", "PLN", "PTE", "PYG", "QAR", "ROL", "RSD",
                 "RUR", "RWF", "SAR", "SBD", "SBL", "SCR", "SDD", "SEK", "SGD", "SHP", "SIT",
                 "SKK", "SLL", "SOS", "SRG", "STD", "SVC", "SYP", "SZL", "THB", "TJR", "TMM",
                 "TND", "TOP", "TRL", "TTD", "TWD", "TZS", "UAH", "UGX", "USD", "UYU", "UZS",
                 "VEB", "VND", "VUV", "WST", "XAF", "XAG", "XAU", "XCD", "XDR", "XOF", "XPD",
                 "XPF", "XPT", "YER", "YUN", "ZAR", "ZMK", "ZRN", "ZWD",)

decimalsPattern = re.compile(r"^(INF|-?[0-9]+)$")

class DialogNewFactItemOptions(Toplevel):
    def __init__(self, mainWin, options):
        self.mainWin = mainWin
        parent = mainWin.parent
        super(DialogNewFactItemOptions, self).__init__(parent)
        self.parent = parent
        self.options = options
        parentGeometry = re.match(r"(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", parent.geometry())
        dialogX = int(parentGeometry.group(3))
        dialogY = int(parentGeometry.group(4))
        self.accepted = False

        self.transient(self.parent)
        self.title(_("New Fact Item Options"))

        frame = Frame(self)

        label(frame, 1, 1, "Entity scheme:")
        self.cellEntityIdentScheme = gridCell(frame, 2, 1, getattr(options,"entityIdentScheme",""), width=50)
        ToolTip(self.cellEntityIdentScheme, text=_("Enter the scheme for the context entity identifier"), wraplength=240)
        label(frame, 1, 2, "Entity identifier:")
        self.cellEntityIdentValue = gridCell(frame, 2, 2, getattr(options,"entityIdentValue",""))
        ToolTip(self.cellEntityIdentValue, text=_("Enter the entity identifier value (e.g., stock ticker)"), wraplength=240)
        label(frame, 1, 3, "Start date:")
        self.cellStartDate = gridCell(frame, 2, 3, getattr(options,"startDate",""))
        ToolTip(self.cellStartDate, text=_("Enter the start date for the report period (e.g., 2010-01-01)"), wraplength=240)
        label(frame, 1, 4, "End date:")
        self.cellEndDate = gridCell(frame, 2, 4, getattr(options,"endDate",""))
        ToolTip(self.cellEndDate, text=_("Enter the end date for the report period (e.g., 2010-12-31)"), wraplength=240)
        label(frame, 1, 5, "Monetary unit:")
        self.cellMonetaryUnit = gridCombobox(frame, 2, 5, getattr(options,"monetaryUnit",""), values=monetaryUnits)
        ToolTip(self.cellMonetaryUnit, text=_("Select a monetary unit (e.g., EUR)"), wraplength=240)
        label(frame, 1, 6, "Monetary decimals:")
        self.cellMonetaryDecimals = gridCell(frame, 2, 6, getattr(options,"monetaryDecimals","2"))
        ToolTip(self.cellMonetaryDecimals, text=_("Enter decimals for monetary items"), wraplength=240)
        label(frame, 1, 7, "Non-monetary decimals:")
        self.cellNonMonetaryDecimals = gridCell(frame, 2, 7, getattr(options,"nonMonetaryDecimals","0"))
        ToolTip(self.cellNonMonetaryDecimals, text=_("Enter decimals for non-monetary items (e.g., stock shares)"), wraplength=240)

        cancelButton = Button(frame, text=_("Cancel"), width=8, command=self.close)
        ToolTip(cancelButton, text=_("Cancel operation, discarding changes and entries"))
        okButton = Button(frame, text=_("OK"), width=8, command=self.ok)
        ToolTip(okButton, text=_("Accept the options as entered above"))
        cancelButton.grid(row=8, column=1, columnspan=3, sticky=E, pady=3, padx=3)
        okButton.grid(row=8, column=1, columnspan=3, sticky=E, pady=3, padx=86)

        frame.grid(row=0, column=0, sticky=(N,S,E,W))
        frame.columnconfigure(2, weight=1)
        window = self.winfo_toplevel()
        window.columnconfigure(0, weight=1)
        self.geometry("+{0}+{1}".format(dialogX+50,dialogY+100))

        #self.bind("<Return>", self.ok)
        #self.bind("<Escape>", self.close)

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.grab_set()
        self.wait_window(self)

    def checkEntries(self):
        errors = []
        if not self.cellEntityIdentScheme.value:
            errors.append(_("Entity scheme invalid"))
        if not self.cellEntityIdentValue.value:
            errors.append(_("Entity identifier value invalid"))
        if not self.cellStartDate.value or dateTime(self.cellStartDate.value) is None:
            errors.append(_("Start date invalid"))
        if not self.cellEndDate.value or dateTime(self.cellEndDate.value) is None:
            errors.append(_("End date invalid"))
        if self.cellMonetaryUnit.value not in monetaryUnits:
            errors.append(_("Monetary unit invalid"))
        if not decimalsPattern.match(self.cellMonetaryDecimals.value):
            errors.append(_("Monetary decimals invalid"))
        if not decimalsPattern.match(self.cellNonMonetaryDecimals.value):
            errors.append(_("Non-monetary decimals invalid"))
        if errors:
            messagebox.showwarning(_("Dialog validation error(s)"),
                                "\n ".join(errors), parent=self)
            return False
        return True

    def setOptions(self):
        # set formula options
        self.options.entityIdentScheme = self.cellEntityIdentScheme.value
        self.options.entityIdentValue = self.cellEntityIdentValue.value
        # need datetime.datetime base class for pickling, not ModelValue class (unpicklable)
        self.options.startDate = self.cellStartDate.value
        self.options.endDate = self.cellEndDate.value
        self.options.monetaryUnit = self.cellMonetaryUnit.value
        self.options.monetaryDecimals = self.cellMonetaryDecimals.value
        self.options.nonMonetaryDecimals = self.cellNonMonetaryDecimals.value

    def ok(self, event=None):
        if not self.checkEntries():
            return
        self.setOptions()
        self.accepted = True
        self.close()

    def close(self, event=None):
        self.parent.focus_set()
        self.destroy()
