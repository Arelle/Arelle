'''
Created on Feb 6, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from tkinter import *
try:
    from tkinter.ttk import *
except ImportError:
    from ttk import *
from arelle.CntlrWinTooltip import ToolTip
import io
from arelle import (XmlUtil, ViewWinList)

def viewXml(modelXbrl, tabWin, tabTitle, xmlDoc):
    modelXbrl.modelManager.showStatus(_("viewing xml"))
    view = ViewXml(modelXbrl, tabWin, tabTitle)
    view.view(xmlDoc)
    menu = view.contextMenu()
    view.menuAddSaveClipboard()
    menu.add_command(label=_("Validate"), underline=0, command=view.validate)

class ViewXml(ViewWinList.ViewList):
    def __init__(self, modelXbrl, tabWin, tabTitle):
        super(ViewXml, self).__init__(modelXbrl, tabWin, tabTitle, True)
    
    def view(self, xmlDoc):
        fh = io.StringIO()
        XmlUtil.writexml(fh, xmlDoc, encoding="utf-8")
        for line in fh.getvalue().split("\n"):
            self.listBox.insert(END, line)
        fh.close()
        
    def validate(self):
        try:
            from arelle import Validate
            import traceback
            Validate.validate(self.modelXbrl)
        except Exception as err:
            self.modelXbrl.exception("exception", _("Validation exception: \s%(error)s"), error=err, exc_info=True)
