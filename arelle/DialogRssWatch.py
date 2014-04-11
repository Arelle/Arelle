'''
Created on Jan 25, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from tkinter import Toplevel, PhotoImage, messagebox, N, S, E, W
try:
    from tkinter.ttk import Frame, Button
except ImportError:
    from ttk import Frame, Button
import tkinter.filedialog
import os
try:
    import regex as re
except ImportError:
    import re
from arelle.ModelValue import dateTime
from arelle import XmlUtil
from arelle.UiUtil import gridCell, gridCombobox, label, checkbox
from arelle.CntlrWinTooltip import ToolTip
from arelle.PluginManager import pluginClassMethods
from arelle.UrlUtil import isValidAbsolute

'''
caller checks accepted, if True, caller retrieves url
'''
def getOptions(mainWin):
    dialog = DialogRssWatch(mainWin, mainWin.modelManager.rssWatchOptions)
    if dialog.accepted:
        mainWin.config["rssWatchOptions"] = dialog.options
        mainWin.saveConfig()

rssFeeds = {
    "US SEC US-GAAP Filings": "http://www.sec.gov/Archives/edgar/usgaap.rss.xml",
    # obsolete: "US SEC Voluntary Filings": "http://www.sec.gov/Archives/edgar/xbrlrss.xml",
    # obsolete: "US SEC Voluntary Risk/Return Filings": "http://www.sec.gov/Archives/edgar/xbrl-rr-vfp.rss.xml",
    "US SEC Mutual Fund Risk/Return Filings": "http://www.sec.gov/Archives/edgar/xbrl-rr.rss.xml",
    "US SEC All Filings": "http://www.sec.gov/Archives/edgar/xbrlrss.all.xml",
            }
  
emailPattern = re.compile(
      r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"  # dot-atom     
      r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-011\013\014\016-\177])*"' # quoted-string     
      r')@(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?$', re.IGNORECASE) 


class DialogRssWatch(Toplevel):
    def __init__(self, mainWin, options):
        self.mainWin = mainWin
        parent = mainWin.parent
        super(DialogRssWatch, self).__init__(parent)
        self.parent = parent
        self.options = options
        parentGeometry = re.match("(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", parent.geometry())
        dialogX = int(parentGeometry.group(3))
        dialogY = int(parentGeometry.group(4))
        self.accepted = False

        self.transient(self.parent)
        self.title(_("RSS Feed Processing Control"))
        
        frame = Frame(self)

        # checkbox entries
        row = 1 # row number (to allow future plugins
        label(frame, 1, row, "RSS Feed:")
        feedSources = sorted(rssFeeds.keys())
        self.cellFeed = gridCombobox(frame, 2, row, options.get("feedSource",""), values=feedSources)
        self.cellFeed.grid(pady=2)
        ToolTip(self.cellFeed, text=_("Select an RSS feed to process for item matching, formulas, and validations as selected below"), wraplength=240)
        row += 1
        label(frame, 1, row, "Match fact text:")
        self.cellMatchText = gridCell(frame, 2, row, options.get("matchTextExpr",""))
        ToolTip(self.cellMatchText, text=_("Enter a regular expression to be matched to the text of each filing instance fact item. "
                                           "Regular expressions may contain patterns to detect, such as ab.?c, for any single character between b and c, or ab.*c for any number of characters between b and c."), wraplength=240)
        row += 1
        label(frame, 1, row, "Formula file:")
        self.cellFormulaFile = gridCell(frame,2, row, options.get("formulaFileUri",""))
        ToolTip(self.cellFormulaFile, text=_("Select a formula linkbase to to evaluate each filing.  "
                                             "The formula linkbase may contain one or more assertions, the results of which is recorded in the log file.  "
                                             "If unsuccessful assertion alerts are selected and an e-mail address provided, the recipient will be notified of filings with assertions that do not pass."), wraplength=240)
        openFileImage = PhotoImage(file=os.path.join(mainWin.imagesDir, "toolbarOpenFile.gif"))
        chooseFormulaFileButton = Button(frame, image=openFileImage, width=12, command=self.chooseFormulaFile)
        chooseFormulaFileButton.grid(row=row, column=3, sticky=W)
        row += 1
        openDatabaseImage = PhotoImage(file=os.path.join(mainWin.imagesDir, "toolbarOpenDatabase.gif"))
        for pluginXbrlMethod in pluginClassMethods("DialogRssWatch.FileChoices"):
            pluginXbrlMethod(self, frame, row, options, mainWin, openFileImage, openDatabaseImage)
            row += 1
        label(frame, 1, row, "Log file:")
        self.cellLogFile = gridCell(frame,2, row, options.get("logFileUri",""))
        ToolTip(self.cellLogFile, text=_("Select a log file in which to save an activity log, including validation results, matched item text, and formula results.\n\n "
                                         "If file ends in .xml it is xml-formatted, otherwise it is text. "), wraplength=240)
        chooseLogFileButton = Button(frame, image=openFileImage, width=12, command=self.chooseLogFile)
        chooseLogFileButton.grid(row=row, column=3, sticky=W)
        row += 1
        label(frame, 1, row, "E-mail alerts to:")
        self.cellEmailAddress = gridCell(frame,2, row, options.get("emailAddress",""))
        ToolTip(self.cellEmailAddress, text=_("Specify e-mail recipient(s) for alerts per below."), wraplength=240)
        propertiesImage = PhotoImage(file=os.path.join(mainWin.imagesDir, "toolbarProperties.gif"))
        smtpSetupButton = Button(frame, image=propertiesImage, width=12, command=self.setupSmtp)
        smtpSetupButton.grid(row=row, column=3, sticky=W)
        ToolTip(smtpSetupButton, text=_("Enter/edit settings of outgoing e-mail server (SMTP)."), wraplength=240)
        row += 1
        label(frame, 1, row, "Latest pub date:")
        pubdate = getattr(options,"latestPubDate",None)
        self.cellLatestPubDate = gridCell(frame,2, row, str(pubdate) if pubdate else "")
        ToolTip(self.cellLatestPubDate, text=_("Specify pub dateTime of last processed submission.  Next item to examine will be after this dateTime."), wraplength=240)
        clearImage = PhotoImage(file=os.path.join(mainWin.imagesDir, "toolbarDelete.gif"))
        clearPubDateButton = Button(frame, image=clearImage, width=12, command=self.clearPubDate)
        clearPubDateButton.grid(row=row, column=3, sticky=W)
        ToolTip(clearPubDateButton, text=_("Clear pub dateTime so that next cycle processes all entries in RSS feed."), wraplength=240)
        row += 1
        label(frame, 2, row, "Validate:")
        row += 1
        self.checkboxes = (
           checkbox(frame, 2, row, 
                    "XBRL 2.1 and Dimensions rules", 
                    "validateXbrlRules"),
           checkbox(frame, 2, row+1, 
                    "Selected disclosure system rules", 
                    "validateDisclosureSystemRules"),
           checkbox(frame, 2, row+2,
                    "Calculation linkbase roll-up", 
                    "validateCalcLinkbase"),
           checkbox(frame, 2, row+3,
                    "Formula assertions", 
                    "validateFormulaAssertions"),
           # Note: if adding to this list keep ModelFormulaObject.FormulaOptions in sync
        )
        row += 4
        for pluginXbrlMethod in pluginClassMethods("DialogRssWatch.ValidateChoices"):
            pluginXbrlMethod(self, frame, row, options, mainWin)
            row += 1
        label(frame, 2, row, "Alert on:")
        row += 1
        self.checkboxes += (
           checkbox(frame, 2, row, 
                    "Facts with matching text", 
                    "alertMatchedFactText"),
           checkbox(frame, 2, row+1,
                    "Unsuccessful formula assertions", 
                    "alertAssertionUnsuccessful"),
           checkbox(frame, 2, row+2, 
                    "Validation errors", 
                    "alertValiditionError"),
           # Note: if adding to this list keep ModelFormulaObject.FormulaOptions in sync
           )
        row += 3
        
        mainWin.showStatus(None)

        cancelButton = Button(frame, text=_("Cancel"), width=8, command=self.close)
        ToolTip(cancelButton, text=_("Cancel operation, discarding changes and entries"))
        okButton = Button(frame, text=_("OK"), width=8, command=self.ok)
        ToolTip(okButton, text=_("Accept the options as entered above"))
        cancelButton.grid(row=row, column=1, columnspan=3, sticky=E, pady=3, padx=3)
        okButton.grid(row=row, column=1, columnspan=3, sticky=E, pady=3, padx=86)
        
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
        
    def chooseFormulaFile(self):
        filename = tkinter.filedialog.askopenfilename(
                            title=_("Choose formula file for RSS Watch"),
                            initialdir=self.options.get("rssWatchFormulaFileDir","."),
                            filetypes=[] if self.mainWin.isMac else [(_("XBRL files"), "*.*")],
                            defaultextension=".xml",
                            parent=self.parent)
        if filename:
            self.options["rssWatchFormulaFileDir"] = os.path.dirname(filename)
            self.cellFormulaFile.setValue(filename)
        
    def chooseLogFile(self):
        filename = tkinter.filedialog.asksaveasfilename(
                            title=_("Choose log file for RSS Watch"),
                            initialdir=self.options.get("rssWatchLogFileDir","."),
                            filetypes=[] if self.mainWin.isMac else [(_("Log files"), "*.*")],
                            defaultextension=".txt",
                            parent=self.parent)
        if filename:
            self.options["rssWatchLogFileDir"] = os.path.dirname(filename)
            self.cellLogFile.setValue(filename)
        
    def setupSmtp(self):
        from arelle.DialogUserPassword import askSmtp
        smtpSettings = askSmtp(self, self.options.get("smtpEmailSettings",()))
        if smtpSettings:
            self.options["smtpEmailSettings"] = smtpSettings
        
    def clearPubDate(self):
        self.cellLatestPubDate.setValue("")
        
    def checkEntries(self):
        errors = []
        if not self.cellFeed.value in rssFeeds and not isValidAbsolute(self.cellFeed.value):
            errors.append(_("RSS feed field contents invalid"))
        try:
            if self.cellMatchText.value:
                re.compile(self.cellMatchText.value)
        except Exception as err:
            errors.append(_("Match text field contents error {0}").format(err))
        if self.cellFormulaFile.value and not os.path.exists(self.cellFormulaFile.value):
            errors.append(_("Formula file not found {0}").format(self.cellFormulaFile.value))
        if self.cellLogFile.value and not os.path.exists(os.path.dirname(self.cellLogFile.value)):
            errors.append(_("Log file directory not found {0}").format(self.cellLogFile.value))
        if self.cellEmailAddress.value:
            if not emailPattern.match(self.cellEmailAddress.value):
                errors.append(_("E-mail address format error").format(self.cellLogFile.value))
            if not self.options.get("smtpEmailSettings"):
                errors.append(_("Please enter E-mail server settings (SMTP)"))
        if self.cellLatestPubDate.value and dateTime(self.cellLatestPubDate.value) is None:
            errors.append(_("Latest pub date field contents invalid"))
        if errors:
            messagebox.showwarning(_("Dialog validation error(s)"),
                                "\n ".join(errors), parent=self)
            return False
        return True
        
    def setOptions(self):
        # set formula options
        self.options["feedSource"] = self.cellFeed.value
        if self.cellFeed.value in rssFeeds:
            self.options["feedSourceUri"] = rssFeeds[self.cellFeed.value]
        else:
            self.options["feedSourceUri"] = self.cellFeed.value
        self.options["matchTextExpr"] = self.cellMatchText.value
        self.options["formulaFileUri"] = self.cellFormulaFile.value
        self.options["logFileUri"] = self.cellLogFile.value
        self.options["emailAddress"] = self.cellEmailAddress.value
        if self.cellLatestPubDate.value:
            # need datetime.datetime base class for pickling, not ModelValue class (unpicklable)
            self.options["latestPubDate"] = XmlUtil.datetimeValue(self.cellLatestPubDate.value)
        else:
            self.options["latestPubDate"] = None
        for checkbox in self.checkboxes:
            self.options[checkbox.attr] = checkbox.value
        
    def ok(self, event=None):
        if not self.checkEntries():
            return
        self.setOptions()
        self.accepted = True
        self.close()
        
    def close(self, event=None):
        self.parent.focus_set()
        self.destroy()
        
