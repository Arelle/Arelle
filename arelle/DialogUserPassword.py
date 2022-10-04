'''
See COPYRIGHT.md for copyright information.
'''
from tkinter import Toplevel, StringVar, N, S, E, W, EW, DISABLED, NORMAL, messagebox
try:
    from tkinter.ttk import Frame, Button, Label, Entry
except ImportError:
    from ttk import Frame, Button, Label, Entry
from arelle.CntlrWinTooltip import ToolTip
from arelle.UiUtil import checkbox, gridCombobox
import sys
import regex as re

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

def askSmtp(parent, priorSmtpSettings):
    if isinstance(priorSmtpSettings,(tuple,list)) and len(priorSmtpSettings) == 4:
        urlAddr, urlPort, user, password = priorSmtpSettings
    else:
        urlAddr = urlPort = user = password = None
    dialog = DialogUserPassword(parent, _("Outgoing E-mail Server (SMTP)"), urlAddr=urlAddr, urlPort=urlPort, user=user, password=password, showHost=False, showUrl=True, showUser=True, showRealm=False)
    if dialog.accepted:
        return (dialog.urlAddr, dialog.urlPort, dialog.user, dialog.password)
    return None

def askParams(parent, title, prompt1, prompt2):
    dialog = DialogUserPassword(parent, title, showHost=False, showRealm=False,
                                userLabel=prompt1, passwordLabel=prompt2, hidePassword=False)
    if dialog.accepted:
        return (dialog.user, dialog.password)

DBTypes = ("postgres", "mssqlSemantic", "mysqlSemantic", "orclSemantic",
           "pgSemantic", "sqliteSemantic", "pgOpenDB", "sqliteDpmDB", "rexster", "rdfDB", "json")
DBDescriptions = ("XBRL-US Postgres SQL",
                  "Semantic MSSQL SQL",
                  "Semantic MySQL SQL",
                  "Semantic Oracle SQL",
                  "Semantic Postgres SQL",
                  "Semantic SQLite SQL",
                  "Open Postgres SQL",
                  "DPM SQLite SQL",
                  "Rexter (Titan Cassandra)",
                  "RDF (Turtle, NanoSparqlServer)",
                  "JSON (JSON, MongoDB)")

def askDatabase(parent, priorDatabaseSettings):
    if isinstance(priorDatabaseSettings,(tuple,list)) and len(priorDatabaseSettings) == 7:
        urlAddr, urlPort, user, password, database, timeout, dbType = priorDatabaseSettings
    else:
        urlAddr = urlPort = user = password = database = timeout = dbType = None
    dialog = DialogUserPassword(parent, _("XBRL Database Server"), urlAddr=urlAddr, urlPort=urlPort, user=user, password=password, database=database, timeout=timeout, dbType=dbType, showHost=False, showUrl=True, showUser=True, showRealm=False, showDatabase=True)
    if dialog.accepted:
        return (dialog.urlAddr, dialog.urlPort, dialog.user, dialog.password, dialog.database, dialog.timeout, dialog.dbType)
    return None

def askInternetLogon(parent, url, quotedUrl, dialogCaption, dialogText, untilDoneEvent, result):
    # received Html suggests url may require web page logon (due to receivedHtml)
    r = messagebox.askyesnocancel(dialogCaption, dialogText)
    if r is None:
        result.append("cancel")
    elif r == False:
        result.append("no")
    else:
        import webbrowser
        webbrowser.open(quotedUrl, new=1, autoraise=True)
        r = messagebox.askretrycancel(dialogCaption,
                                      _("After logging on (by web browser, if applicable) click 'retry' to reload web file"))
        if r:
            result.append("retry")
        else:
            result.append("cancel")
    untilDoneEvent.set()

class DialogUserPassword(Toplevel):
    def __init__(self, parent, title, host=None, realm=None, useOsProxy=None, urlAddr=None, urlPort=None,
                 user=None, password=None, database=None, timeout=None, dbType=None,
                 showUrl=False, showUser=False, showHost=True, showRealm=True, showDatabase=False,
                 userLabel=None, passwordLabel=None, hidePassword=True):
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
        self.timeoutVar = StringVar()
        self.timeoutVar.set(timeout if timeout else "")

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
        userLabel = Label(frame, text=userLabel or _("User:"), underline=0)
        userEntry = Entry(frame, textvariable=self.userVar, width=25)
        userLabel.grid(row=y, column=0, sticky=W, pady=3, padx=3)
        userEntry.grid(row=y, column=1, columnspan=4, sticky=EW, pady=3, padx=3)
        self.enabledWidgets.append(userEntry)
        y += 1
        if not showUrl:
            userEntry.focus_set()
        passwordLabel = Label(frame, text=passwordLabel or _("Password:"), underline=0)
        passwordEntry = Entry(frame, textvariable=self.passwordVar, width=25, show=("*" if hidePassword else None))
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
            urlTimeoutLabel = Label(frame, text=_("Timeout:"), underline=0)
            urlTimeoutEntry = Entry(frame, textvariable=self.timeoutVar, width=25)
            urlTimeoutLabel.grid(row=y, column=0, sticky=W, pady=3, padx=3)
            urlTimeoutEntry.grid(row=y, column=1, columnspan=4, sticky=EW, pady=3, padx=3)
            ToolTip(urlAddrEntry, text=_("Enter timeout seconds (optional) or leave blank for default (60 secs.)"), wraplength=360)
            self.enabledWidgets.append(urlTimeoutEntry)
            y += 1
            dbTypeLabel = Label(frame, text=_("DB type:"), underline=0)
            dbTypeLabel.grid(row=y, column=0, sticky=W, pady=3, padx=3)
            self.cbDbType = gridCombobox(frame, 1, y, values=DBDescriptions,
                                         selectindex=DBTypes.index(dbType) if dbType in DBTypes else None)
            self.cbDbType.grid(columnspan=4, pady=3, padx=3)
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

    def checkEntries(self):
        errors = []
        if self.urlPort and not self.urlPort.isdigit():
            errors.append(_("Port number invalid"))
        if self.timeout and not self.timeout.isdigit():
            errors.append(_("Timeout seconds invalid"))
        if hasattr(self,"cbDbType") and self.cbDbType.value not in DBDescriptions:
            errors.append(_("DB type is invalid"))
        if errors:
            messagebox.showwarning(_("Dialog validation error(s)"),
                                "\n ".join(errors), parent=self)
            return False
        return True

    def ok(self, event=None):
        if hasattr(self, "useOsProxyCb"):
            self.useOsProxy = self.useOsProxyCb.value
        self.urlAddr = self.urlAddrVar.get()
        if self.urlAddr.startswith("http://"): self.urlAddr = self.ulrAddr[7:] # take of protocol part if any
        self.urlPort = self.urlPortVar.get()
        self.user = self.userVar.get()
        self.password = self.passwordVar.get()
        self.database = self.databaseVar.get()
        self.timeout = self.timeoutVar.get()
        self.dbType = DBTypes[DBDescriptions.index(self.cbDbType.value)] if hasattr(self,"cbDbType") and self.cbDbType.value in DBDescriptions else None
        if not self.checkEntries():
            return
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
