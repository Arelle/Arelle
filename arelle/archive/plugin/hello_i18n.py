'''
Hello dolly is a simple "Hello world" to demonstrate how plug-ins
are written for Arelle

See COPYRIGHT.md for copyright information.
'''
from arelle.Version import copyrightLabel

def menuEntender(cntlr, menu):
    menu.add_command(label="Hello i18n", underline=0, command=lambda: menuCommand(cntlr) )

def menuCommand(cntlr):
    i10L_world = _("Hello World");
    cntlr.addToLog(i10L_world)
    import tkinter
    tkinter.messagebox.showinfo(_("Prints 'Hello World'"), i10L_world, parent=cntlr.parent)

'''
   Do not use _( ) in pluginInfo itself (it is applied later, after loading
'''
__pluginInfo__ = {
    'name': 'Hello i18n',
    'version': '0.9',
    'description': '''Minimal plug-in that demonstrates i18n internationalization by localized gettext.''',
    'localeURL': "locale",
    'localeDomain': 'hello_i18n',
    'license': 'Apache-2',
    'author': 'R\u00e9gis D\u00e9camps',
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': menuEntender
}
