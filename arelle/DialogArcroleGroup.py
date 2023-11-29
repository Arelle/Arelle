'''
See COPYRIGHT.md for copyright information.
'''
from tkinter import Toplevel, N, S, E, W, PhotoImage
try:
    from tkinter.ttk import Frame, Button
except ImportError:
    from ttk import Frame, Button
import os
import regex as re
from arelle.UiUtil import gridHdr, gridCell, gridCombobox, label, checkbox
from arelle.CntlrWinTooltip import ToolTip
from arelle import XbrlConst

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
        parentGeometry = re.match(r"(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", parent.geometry())
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
        groupLabel = label(frame, 1, 0, _("Group:"))
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
        groupToolTipMessage = _("Select an existing arcrole group, or enter a name for a new arcrole group.  "
                                "If selecting an existing group, it can be edited, and changes will be saved in the config file.  "
                                "If nothing is changed for an existing group, the saved setting is not disturbed.  "
                                "Arcroles with checkboxes below are shown only for arcroles that have relationships in the loaded DTS, "
                                "but if an existing group is selected with more arcroles (that were not in the current DTS) then "
                                "the prior setting with not-present arcroles is preserved. ")
        ToolTip(self.groupName, text=groupToolTipMessage, wraplength=360)
        ToolTip(groupLabel, text=groupToolTipMessage, wraplength=360)
        clearImage = PhotoImage(file=os.path.join(mainWin.imagesDir, "toolbarDelete.gif"))
        clearGroupNameButton = Button(frame, image=clearImage, width=12, command=self.clearGroupName)
        clearGroupNameButton.grid(row=0, column=3, sticky=W)
        ToolTip(clearGroupNameButton, text=_("Remove the currently selected arcrole group from the config file. "
                                             "After removing, you may select another arcrole, but must select 'OK' for the "
                                             "removal to be saved. "),
                wraplength=240)
        arcrolesLabel = label(frame, 1, 1, _("Arcroles:"))
        ToolTip(arcrolesLabel, text=_("Shows all the arcroles that are present in this DTS. "),
                wraplength=240)
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

        self.options[XbrlConst.arcroleGroupDetect] = XbrlConst.arcroleGroupDetect in arcroleGroup
        self.autoOpen = checkbox(frame, 1, y, _("detect"), XbrlConst.arcroleGroupDetect)
        self.autoOpen.grid(sticky=W, columnspan=2)
        self.checkboxes.append(self.autoOpen)
        ToolTip(self.autoOpen, text=_("If checked, this arcrole group will be detected if any arcrole of the group is present in a DTS, for example to open a treeview pane. "),
                wraplength=240)
        okButton = Button(frame, text=_("OK"), width=8, command=self.ok)
        cancelButton = Button(frame, text=_("Cancel"), width=8, command=self.close)
        cancelButton.grid(row=y, column=1, sticky=E, columnspan=3, pady=3, padx=3)
        okButton.grid(row=y, column=1, sticky=E, columnspan=3, pady=3, padx=64)
        ToolTip(okButton, text=_("Open a treeview with named arcrole group and selected arcroles. "
                                 "If any changes were made to checkboxes or name, save in the config. "),
                wraplength=240)
        ToolTip(cancelButton, text=_("Close this dialog, without saving arcrole group changes or opening a view pane. "),
                wraplength=240)

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
