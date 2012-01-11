from tkinter import Toplevel, Frame, PanedWindow, constants, tix, Label, Entry, StringVar, Button
import sys
from tkinter.constants import LEFT, HORIZONTAL
from tkinter.ttk import Treeview
from arelle import apf

__author__ = 'Régis Décamps <regis.decamps@banque-france.fr>'

TAG_INACTIVE = 'inactive'

class DialogAddonManager(Toplevel):
    def __init__(self, controller):
        super().__init__(controller.parent)
        self.loaded_addons = controller.loaded_addons
        self.disabled_addons = {}
        for name in controller.disabled_addons:
            self.disabled_addons[name] = apf.get_module_info(name)

        self.title(_("Manage add-ons"))
        #pane = PanedWindow(self)

        #addon list
        addonList = AddonTreeview(self)
        addonList.grid(row=0, column=0, rowspan=2)

        # details of the selected addon
        detailsFrame = Frame(self)
        detailsFrame.grid(row=0, column=1)

        Label(detailsFrame, text=_("Author")).grid(row=0, column=0)
        self.val_author = StringVar()
        lbl_author = Label(detailsFrame, textvariable=self.val_author)
        lbl_author.grid(row=0, column=1)

        Label(detailsFrame, text=_("Description")).grid(row=1, column=0)
        self.val_desc = StringVar()
        lbl_desc = Label(detailsFrame, textvariable=self.val_desc)
        lbl_desc.grid(row=1, column=1)

        self.button = Button(self)
        self.button.grid(row=1, column=1)

        # finish
        #pane.pack()
        self.wait_window(self)

    def on_item_selected(self, event):
        name_selected = event.widget.focus()
        if name_selected in self.disabled_addons:
            self.button.config(text=_("Enable"), command=self.on_button_enable)
            module_selected = self.disabled_addons[name_selected]
        else:
            self.button.config(text=_("Disable"), command=self.on_button_disable)
            module_selected = self.loaded_addons[name_selected]
        self.val_author.set(module_selected.__author__)
        self.val_desc.set(module_selected.__desc__)

    def on_button_enable(self):
        pass

    def on_button_disable(self):
        pass


class AddonTreeview(Treeview):
    def __init__(self, master, **kw):
        super().__init__(master, *kw)
        self['columns'] = ('version')
        self.heading(0, text=_("Name"))
        self.heading('version', text=_("Version"))
        self.pack(expand=1, fill=tix.BOTH, padx=10, pady=10, side=tix.LEFT)
        self.bind('<<TreeviewSelect>>', master.on_item_selected)
        self.tag_configure(TAG_INACTIVE, background='light grey', foreground='dark grey')

        loaded_modules = sys.modules.keys()
        for (addon_name, addon) in master.loaded_addons.items():
            self.insert('', 'end', addon_name, text=addon_name, values=(addon.__version__))
        for (addon_name, addon) in master.disabled_addons.items():
            self.insert('', 'end', addon_name, text=addon_name, values=(addon.__version__), tags=(TAG_INACTIVE))
