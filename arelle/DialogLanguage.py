"""
See COPYRIGHT.md for copyright information.
"""
from tkinter import E, EW, N, S, Toplevel, W, messagebox

try:
    from tkinter.ttk import Frame, Button, Label, Entry
except ImportError:
    from ttk import Frame, Button, Label, Entry

import regex as re

from arelle import Locale
from arelle.CntlrWinTooltip import ToolTip
from arelle.UiUtil import checkbox, gridCombobox, gridHdr, label
from arelle.typing import TypeGetText

_: TypeGetText

'''
allow user to override system language codes for user interface and labels
'''


def askLanguage(mainWin):
    DialogLanguage(mainWin)


class DialogLanguage(Toplevel):
    def __init__(self, mainWin):
        super(DialogLanguage, self).__init__(mainWin.parent)
        self.mainWin = mainWin
        self.parent = mainWin.parent
        parentGeometry = re.match(r"(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", self.parent.geometry())
        dialogX = int(parentGeometry.group(3))
        dialogY = int(parentGeometry.group(4))
        self.transient(self.parent)
        self.title(_("arelle - User Interface and Labels language code settings"))
        self.languageCodes = Locale.languageCodes()
        if systemLocales := Locale.availableLocales():  # unix/Mac locale -a supported locale codes
            localeOptionTitles = [
                title
                for title, labelCode in self.languageCodes.items()
                if Locale.bcp47LangToPosixLocale(labelCode) in systemLocales
            ]
        else:
            localeOptionTitles = self.languageCodes.keys()
        localeOptions = (_("System default locale ({0})").format(mainWin.modelManager.defaultLang), *sorted(localeOptionTitles))
        labelLanguageOptions = (_("System default language ({0})").format(mainWin.modelManager.defaultLang), *sorted(self.languageCodes.keys()))
        self.uiLang = Locale.posixLocaleToBCP47Lang(mainWin.config.get("userInterfaceLangOverride", ""))
        if self.uiLang == "" or self.uiLang == mainWin.modelManager.defaultLang:
            self.uiLangIndex = 0
        else:
            self.uiLangIndex = None
            for i, langName in enumerate(localeOptions):
                if i > 0 and self.uiLang == self.languageCodes.get(langName):
                    self.uiLangIndex = i
                    break
        self.labelLang = mainWin.config.get("labelLangOverride", "")
        if self.labelLang == "" or self.labelLang == mainWin.modelManager.defaultLang:
            self.labelLangIndex = 0
        else:
            self.labelLangIndex = None
            for i, langName in enumerate(labelLanguageOptions):
                if i > 0 and self.labelLang == self.languageCodes.get(langName):
                    self.labelLangIndex = i
                    break

        frame = Frame(self)

        defaultLanguage = mainWin.modelManager.defaultLang
        for langName, langCode in self.languageCodes.items():
            if mainWin.modelManager.defaultLang == langCode:
                defaultLanguage += ", " + langName
                break
        gridHdr(frame, 0, 0, _(
                 "The system default language is: {0} \n\n"
                 "You may override with a different language for user interface language and locale settings, and for language of taxonomy linkbase labels to display. \n\n").format(
                defaultLanguage),
              columnspan=5, wraplength=400)
        label(frame, 0, 1, _("User Interface:"))
        self.cbUiLang = gridCombobox(frame, 1, 1, values=localeOptions, selectindex=self.uiLangIndex, columnspan=4)
        label(frame, 0, 2, _("Labels:"))
        self.cbLabelLang = gridCombobox(frame, 1, 2, values=labelLanguageOptions, selectindex=self.labelLangIndex, columnspan=4)
        self.cbUiLang.focus_set()
        self.cbDisableRtl = checkbox(frame, 0, 3,  _('Disable rtl String'), 'disableRtlSting')
        ToolTip(self.cbDisableRtl, _('Disable reversing string read order for right to left languages, useful for some locale settings.'), wraplength=240)
        self.cbDisableRtl.valueVar.set(self.mainWin.config.get('disableRtl', 0))
        okButton = Button(frame, text=_("OK"), command=self.ok)
        cancelButton = Button(frame, text=_("Cancel"), command=self.close)
        okButton.grid(row=3, column=2, sticky=E, pady=3)
        cancelButton.grid(row=3, column=3, columnspan=2, sticky=EW, pady=3, padx=3)
        frame.grid(row=0, column=0, sticky=(N,S,E,W))
        frame.columnconfigure(1, weight=1)
        window = self.winfo_toplevel()
        window.columnconfigure(0, weight=1)
        self.geometry("+{0}+{1}".format(dialogX+50,dialogY+100))

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.close)

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.grab_set()
        self.wait_window(self)

    def ok(self, event=None):
        self.mainWin.config['disableRtl'] = self.cbDisableRtl.value
        Locale.setDisableRTL(self.cbDisableRtl.value)
        labelLangIndex = self.cbLabelLang.valueIndex
        if labelLangIndex >= 0 and labelLangIndex != self.labelLangIndex: # changed
            if labelLangIndex == 0:
                langCode = self.mainWin.modelManager.defaultLang
            else:
                langCode = self.languageCodes[self.cbLabelLang.value]
            self.mainWin.config["labelLangOverride"] = langCode
            self.mainWin.labelLang = langCode

        uiLangIndex = self.cbUiLang.valueIndex
        if uiLangIndex >= 0 and uiLangIndex != self.uiLangIndex: # changed
            if uiLangIndex == 0:
                langCode = self.mainWin.modelManager.defaultLang
            else:
                langCode = self.languageCodes[self.cbUiLang.value]

            localeCode = Locale.findCompatibleLocale(langCode)
            if localeCode is not None:
                newLocale = Locale.getUserLocale(localeCode)
                self.mainWin.modelManager.locale = newLocale
            else:
                messagebox.showerror(_("User interface locale error"),
                                     _("Locale setting {0} is not supported on this system")
                                     .format(localeCode),
                                     parent=self)
                return
            if uiLangIndex != 0: # not the system default
                self.mainWin.config["userInterfaceLangOverride"] = localeCode
            else: # use system default
                self.mainWin.config.pop("userInterfaceLangOverride", None)
            self.mainWin.setUiLanguage(localeCode)

            if messagebox.askyesno(
                    _("User interface language changed"),
                    _("Should Arelle restart with changed user interface language, if there are any unsaved changes they would be lost!"),
                   parent=self):
                self.mainWin.uiThreadQueue.put((self.mainWin.quit, [None, True]))
            else:
                messagebox.showwarning(
                    _("User interface language changed"),
                    _("Please restart Arelle for the change in user interface language."),
                   parent=self)
        self.close()

    def close(self, event=None):
        self.parent.focus_set()
        self.destroy()
