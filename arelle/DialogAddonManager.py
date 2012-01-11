from tkinter import Toplevel, Frame, PanedWindow, constants, tix, Label, Entry, StringVar, Button
import sys
from tkinter.constants import LEFT, HORIZONTAL, DISABLED, ACTIVE
from tkinter.ttk import Treeview
from arelle import apf

__author__ = 'Régis Décamps <regis.decamps@banque-france.fr>'

TAG_INACTIVE = 'inactive'

class DialogAddonManager(Toplevel):
    def __init__(self, controller):
        super().__init__(controller.parent)
        self.controller = controller
        self.log = controller.addToLog
        self.loaded_addons = controller.loaded_addons
        self.disabled_addons = {}
        for name in controller.config['disabled_addons']:
            self.disabled_addons[name] = apf.get_module_info(name)

        self.title(_("Manage add-ons"))
        #pane = PanedWindow(self)

        #addon list
        addon_tree = AddonTreeview(self)
        addon_tree.grid(row=0, column=0, rowspan=2)

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
            callback = self.on_button_enable(name_selected)
            self.button.config(text=_("Enable"), command=callback)
            module_selected = self.disabled_addons[name_selected]
        else:
            callback = self.on_button_disable(name_selected)
            self.button.config(text=_("Disable"), command=callback)
            module_selected = self.loaded_addons[name_selected]
        self.val_author.set(module_selected.__author__)
        self.val_desc.set(module_selected.__desc__)
        self.button.config(state=ACTIVE)

    def on_button_enable(self, name_selected):
        def callback():
            try:
                self.loaded_addons[name_selected] = apf.load_plugins(name=name_selected)
                self.log(_("Plugin %(plugin)s loaded successfully. You may have to restart Arelle.") %
                         {'plugin': name_selected})
                del self.disabled_addons[name_selected]
                self.controller.config['disabled_addons'].remove(name_selected)
                self.button.config(state=DISABLED)
            except:
                self.log(_("Failed to load module: %(error)s") % {'error': sys.exc_info()})

        return callback

    def on_button_disable(self, name_selected):
        def callback():
            try:
                self.disabled_addons[name_selected] = sys.modules[name_selected]
                self.controller.config['disabled_addons'].append(name_selected)
                self.log(_("Plugin %(plugin)s disabled in config. You may have to restart Arelle.") %
                         {'plugin': name_selected})
                self.button.config(state=DISABLED)
            except:
                self.log(_("Failed to disable module: %(error)s") % {'error': sys.exc_info()})

        return callback


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
