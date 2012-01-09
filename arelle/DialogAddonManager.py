from tkinter import Toplevel, Frame, PanedWindow, constants, tix, Label, Entry, StringVar
import sys
from tkinter.constants import LEFT, HORIZONTAL
from tkinter.ttk import Treeview


__author__ = 'Régis Décamps <regis.decamps@banque-france.fr>'

class DialogAddonManager(Toplevel):
    def __init__(self, controller):
        super().__init__(controller.parent)
        self.loaded_addons = controller.loaded_addons
        self.title(_("Manage add-ons"))

        pane = PanedWindow(self)

        #addon list
        addonList = AddonTreeview(controller, pane, self.on_item_selected)
        addonList.pack()

        # details of the selected addon
        detailsFrame = Frame(pane)
        detailsFrame.pack()

        Label(detailsFrame, text=_("Author")).grid(row=0, column=0)
        self.val_author=StringVar()
        lbl_author = Label(detailsFrame, textvariable=self.val_author)
        lbl_author.grid(row=0,column=1)

        Label(detailsFrame, text=_("Description")).grid(row=1, column=0)
        self.val_desc=StringVar()
        lbl_desc = Label(detailsFrame, textvariable=self.val_desc)
        lbl_desc.grid(row=1,column=1)

        # finish
        pane.pack()
        self.wait_window(self)

    def on_item_selected(self, event):
        name_selected = event.widget.focus()
        module_selected = self.loaded_addons[name_selected]
        self.val_author.set(module_selected.__author__)
        self.val_desc.set(module_selected.__desc__)

class AddonTreeview(Treeview):
    def __init__(self, controller, master, callback, **kw):
        super().__init__(master, *kw)
        self['columns'] = ('version')
        self.heading(0, text=_("Name"))
        self.heading('version', text=_("Version"))
        self.pack(expand=1, fill=tix.BOTH, padx=10, pady=10, side=tix.LEFT)
        self.bind('<<TreeviewSelect>>', callback)

        loaded_modules = sys.modules.keys()
        for (addon_name, addon) in controller.loaded_addons.items():
            self.insert('', 'end', addon_name, text=addon_name, values=(addon.__version__))
