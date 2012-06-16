'''
Created on Jun 15, 2012

@author: Mark V Systems Limited
(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''
from tkinter import Toplevel, N, S, E, W, PhotoImage
from tkinter.ttk import Frame, Button
import os, re
from arelle.UiUtil import gridHdr, gridCell, gridCombobox, label, checkbox

'''
caller checks accepted, if True, caller retrieves url
'''
def getArcroleGroup(mainWin, modelXbrl):
    dialog = DialogArcroleGroup(mainWin, modelXbrl)
    return dialog.selectedGroup

  
class DialogArcroleGroup(Toplevel):
    def __init__(self, mainWin, modelXbrl):
        parent = mainWin.parent
        super(DialogArcroleGroup, self).__init__(parent)
        self.mainWin = mainWin
        self.parent = parent
        self.modelXbrl = modelXbrl
        parentGeometry = re.match("(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", parent.geometry())
        dialogX = int(parentGeometry.group(3))
        dialogY = int(parentGeometry.group(4))
        self.selectedGroup = None

        self.transient(self.parent)
        self.title(_("Select Arcrole Group"))
        
        frame = Frame(self)

        '''
        dialogFrame = Frame(frame, width=500)
        dialogFrame.columnconfigure(0, weight=1)
        dialogFrame.rowconfigure(0, weight=1)
        dialogFrame.grid(row=0, column=0, columnspan=4, sticky=(N, S, E, W), padx=3, pady=3)
        '''
        
        # mainWin.showStatus(_("loading formula options and parameters"))
        
        # load grid
        label(frame, 1, 0, "Group:")
        self.arcroleGroups = mainWin.config.get("arcroleGroups", {})
        arcroleGroupSelected = self.mainWin.config.get("arcroleGroupSelected")
        if arcroleGroupSelected in self.arcroleGroups:
            arcroleGroup = self.arcroleGroups[arcroleGroupSelected]
        else:
            arcroleGroup = []
            arcroleGroupSelected = None
        self.groupName = gridCombobox(frame, 2, 0, 
                                      value=arcroleGroupSelected,
                                      values=sorted(self.arcroleGroups.keys()), 
                                      comboboxselected=self.comboBoxSelected)
        clearImage = PhotoImage(file=os.path.join(mainWin.imagesDir, "toolbarDelete.gif"))
        clearGroupNameButton = Button(frame, image=clearImage, width=12, command=self.clearGroupName)
        clearGroupNameButton.grid(row=0, column=3, sticky=W)
        label(frame, 1, 1, "Arcroles:")
        from arelle.ModelRelationshipSet import baseSetArcroles
        self.options = {}
        self.checkboxes = []
        y = 1
        for name, arcrole in baseSetArcroles(self.modelXbrl):
            if arcrole.startswith("http://"):
                self.options[arcrole] = arcrole in arcroleGroup
                self.checkboxes.append( 
                   checkbox(frame, 2, y, 
                            name[1:], 
                            arcrole, 
                            columnspan=2)
                )
                y += 1
        
        mainWin.showStatus(None)

        okButton = Button(frame, text=_("OK"), width=8, command=self.ok)
        cancelButton = Button(frame, text=_("Cancel"), width=8, command=self.close)
        cancelButton.grid(row=y, column=1, sticky=E, columnspan=3, pady=3, padx=3)
        okButton.grid(row=y, column=1, sticky=E, columnspan=3, pady=3, padx=86)
        
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
        
    def ok(self, event=None):
        groupName = self.groupName.value
        arcrolesSelected = [checkbox.attr for checkbox in self.checkboxes if checkbox.value]
        if groupName:
            self.mainWin.config["arcroleGroupSelected"] = groupName
            if groupName not in self.arcroleGroups or any(checkbox.isChanged for checkbox in self.checkboxes):
                self.arcroleGroups[groupName] = arcrolesSelected
                self.mainWin.config["arcroleGroups"] = self.arcroleGroups
                self.mainWin.saveConfig()
            self.selectedGroup = (groupName, arcrolesSelected)
        self.close()
        
    def close(self, event=None):
        self.parent.focus_set()
        self.destroy()

    def comboBoxSelected(self, *args):
        arcroles = self.arcroleGroups.get(self.groupName.value, [])
        for checkbox in self.checkboxes:
            checkbox.valueVar.set( checkbox.attr in arcroles )
            checkbox.isChanged = False
        
    def clearGroupName(self):
        groupName = self.groupName.value
        if groupName and groupName in self.arcroleGroups:
            del self.arcroleGroups[groupName]
        self.groupName.valueVar.set('')
        self.groupName["values"] = sorted(self.arcroleGroups.keys())
        for checkbox in self.checkboxes:
            checkbox.valueVar.set( False )
            checkbox.isChanged = False
