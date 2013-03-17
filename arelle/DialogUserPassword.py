'''
Created on Oct 10, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from tkinter import Toplevel, StringVar, N, S, E, W, EW, DISABLED, NORMAL
try:
    from tkinter.ttk import Frame, Button, Label, Entry
except ImportError:
    from ttk import Frame, Button, Label, Entry
from arelle.CntlrWinTooltip import ToolTip
from arelle.UiUtil import (checkbox)
import re, sys

'''
caller checks accepted, if True, caller retrieves url
'''
def askUserPassword(parent, host, realm, untilDoneEvent, result):
    dialog = DialogUserPassword(parent, _("Authentication Request"), host=host, realm=realm)
    if dialog.accepted:
        result.append( (dialog.user, dialog.password) )
    else:
        result.append( None )
    untilDoneEvent.set()

def askProxy(parent, priorProxySettings):
    if isinstance(priorProxySettings,(tuple,list)) and len(priorProxySettings) == 5:
        useOsProxy, urlAddr, urlPort, user, password = priorProxySettings
    else:
        useOsProxy = True
        urlAddr = urlPort = user = password = None
    dialog = DialogUserPassword(parent, _("Proxy Server"), urlAddr=urlAddr, urlPort=urlPort, useOsProxy=useOsProxy, user=user, password=password, showHost=False, showUrl=True, showUser=True, showRealm=False)
    if dialog.accepted:
        return (dialog.useOsProxyCb.value, dialog.urlAddr, dialog.urlPort, dialog.user, dialog.password)
    return None

def askDatabase(parent, priorDatabaseSettings):
    if isinstance(priorDatabaseSettings,(tuple,list)) and len(priorDatabaseSettings) == 5:
        urlAddr, urlPort, user, password, database = priorDatabaseSettings
    else:
        urlAddr = urlPort = user = password = database = None
    dialog = DialogUserPassword(parent, _("XBRL Database Server"), urlAddr=urlAddr, urlPort=urlPort, user=user, password=password, database=database, showHost=False, showUrl=True, showUser=True, showRealm=False, showDatabase=True)
    if dialog.accepted:
        return (dialog.urlAddr, dialog.urlPort, dialog.user, dialog.password, dialog.database)
    return None


class DialogUserPassword(Toplevel):
    def __init__(self, parent, title, host=None, realm=None, useOsProxy=None, urlAddr=None, urlPort=None, user=None, password=None, database=None, showUrl=False, showUser=False, showHost=True, showRealm=True, showDatabase=False):
        super(DialogUserPassword, self).__init__(parent)
        self.parent = parent
        parentGeometry = re.match("(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", parent.geometry())
        dialogX = int(parentGeometry.group(3))
        dialogY = int(parentGeometry.group(4))
        self.accepted = False
        self.transient(self.parent)
        self.title(title)
        self.urlAddrVar = StringVar()
        self.urlAddrVar.set(urlAddr if urlAddr else "")
        self.urlPortVar = StringVar()
        self.urlPortVar.set(urlPort if urlPort else "")
        self.userVar = StringVar()
        self.userVar.set(user if user else "")
        self.passwordVar = StringVar()
        self.passwordVar.set(password if password else "")
        self.databaseVar = StringVar()
        self.databaseVar.set(database if database else "")
        
        frame = Frame(self)
        y = 0
        if showHost:
            hostLabel = Label(frame, text=_("Host:"), underline=0)
            hostDisplay = Label(frame, text=host, width=30)
            if host and len(host) > 30:
                ToolTip(hostDisplay, text=host, wraplength=240)
            hostLabel.grid(row=y, column=0, sticky=W, pady=3, padx=3)
            hostDisplay.grid(row=y, column=1, columnspan=4, sticky=EW, pady=3, padx=3)
            y += 1
        if showRealm:
            realmLabel = Label(frame, text=_("Realm:"), underline=0)
            realmDisplay = Label(frame, text=realm, width=25)
            if realm and len(realm) > 30:
                ToolTip(realmDisplay, text=realm, wraplength=240)
            realmLabel.grid(row=y, column=0, sticky=W, pady=3, padx=3)
            realmDisplay.grid(row=y, column=1, columnspan=4, sticky=EW, pady=3, padx=3)
            y += 1
        self.enabledWidgets = []
        if useOsProxy is not None:
            if sys.platform.startswith("win"):
                hostProxy = _('Microsoft Windows Internet Settings')
            elif sys.platform in ("darwin", "macos"):
                hostProxy = _('Mac OS X System Configuration')
            else: # linux/unix
                hostProxy = _('environment variables')
            useOsProxyCb = checkbox(frame, 0, y, text=_("Use proxy server of {0}").format(hostProxy))
            useOsProxyCb.grid(columnspan=5)
            useOsProxyCb.valueVar.set(useOsProxy)
            ToolTip(useOsProxyCb, text=_("Check to use {0} \n"
                                         "Uncheck to specify: \n"
                                         "   No proxy if URL address is left blank, \n"
                                         "   Proxy via URL address if it is not blank, \n"
                                         "       with user and password (if provided)"
                                         ).format(hostProxy), wraplength=360)
            self.useOsProxyCb = useOsProxyCb
            useOsProxyCb.valueVar.trace("w", self.setEnabledState)

            y += 1
        if showUrl:
            urlAddrLabel = Label(frame, text=_("Address:"), underline=0)
            urlAddrEntry = Entry(frame, textvariable=self.urlAddrVar, width=16)
            urlPortLabel = Label(frame, text=_("Port:"), underline=0)
            urlPortEntry = Entry(frame, textvariable=self.urlPortVar, width=5)
            urlAddrEntry.focus_set()
            urlAddrLabel.grid(row=y, column=0, sticky=W, pady=3, padx=3)
            urlAddrEntry.grid(row=y, column=1, columnspan=2, sticky=EW, pady=3, padx=3)
            urlPortLabel.grid(row=y, column=3, sticky=W, pady=3, padx=3)
            urlPortEntry.grid(row=y, column=4, sticky=EW, pady=3, padx=3)
            ToolTip(urlAddrEntry, text=_("Enter URL address and port number \n"
                                         "  e.g., address: 168.1.2.3 port: 8080 \n"
                                         "  or address: proxy.myCompany.com port: 8080 \n"
                                         "  or leave blank to specify no proxy server"), wraplength=360)
            self.enabledWidgets.append(urlAddrEntry)
            self.enabledWidgets.append(urlPortEntry)
            y += 1
        userLabel = Label(frame, text=_("User:"), underline=0)
        userEntry = Entry(frame, textvariable=self.userVar, width=25)
        userLabel.grid(row=y, column=0, sticky=W, pady=3, padx=3)
        userEntry.grid(row=y, column=1, columnspan=4, sticky=EW, pady=3, padx=3)
        self.enabledWidgets.append(userEntry)
        y += 1
        if not showUrl:
            userEntry.focus_set()
        passwordLabel = Label(frame, text=_("Password:"), underline=0)
        passwordEntry = Entry(frame, textvariable=self.passwordVar, width=25, show="*")
        passwordLabel.grid(row=y, column=0, sticky=W, pady=3, padx=3)
        passwordEntry.grid(row=y, column=1, columnspan=4, sticky=EW, pady=3, padx=3)
        self.enabledWidgets.append(passwordEntry)
        y += 1
        if showDatabase:
            urlDatabaseLabel = Label(frame, text=_("Database:"), underline=0)
            urlDatabaseEntry = Entry(frame, textvariable=self.databaseVar, width=25)
            urlDatabaseLabel.grid(row=y, column=0, sticky=W, pady=3, padx=3)
            urlDatabaseEntry.grid(row=y, column=1, columnspan=4, sticky=EW, pady=3, padx=3)
            ToolTip(urlAddrEntry, text=_("Enter database name (optional) or leave blank"), wraplength=360)
            self.enabledWidgets.append(urlDatabaseEntry)
            y += 1
        okButton = Button(frame, text=_("OK"), command=self.ok)
        cancelButton = Button(frame, text=_("Cancel"), command=self.close)
        okButton.grid(row=y, column=2, sticky=E, pady=3)
        cancelButton.grid(row=y, column=3, columnspan=2, sticky=EW, pady=3, padx=3)
        y += 1
                
        if useOsProxy is not None:
            self.setEnabledState()

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
        if hasattr(self, "useOsProxyCb"):
            self.useOsProxy = self.useOsProxyCb.value
        self.urlAddr = self.urlAddrVar.get()
        if self.urlAddr.startswith("http://"): self.urlAddr = self.ulrAddr[7:] # take of protocol part if any
        self.urlPort = self.urlPortVar.get()
        self.user = self.userVar.get()
        self.password = self.passwordVar.get()
        self.database = self.databaseVar.get()
        self.accepted = True
        self.close()
        
    def close(self, event=None):
        self.parent.focus_set()
        self.destroy()
        
    def setEnabledState(self, *args):
        if hasattr(self, "useOsProxyCb"):
            state = DISABLED if self.useOsProxyCb.value else NORMAL
            for widget in self.enabledWidgets:
                widget.config(state=state)