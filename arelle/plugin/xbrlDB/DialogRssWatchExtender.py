'''
DialogRssWatchExtender extends DialogRssWatch for XBRL databases.

It is separate from the xbrlDB __init__.py module so that it can be removed when 
compiling server versions where Python has no GUI facilities.  The imports of GUI
facilities would cause compilation of the server-related modules to fail, otherwise.

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).
and does not apply to the XBRL US Database schema and description.

'''

def dialogRssWatchDBextender(dialog, frame, row, options, cntlr, openFileImage, openDatabaseImage):
    from tkinter import PhotoImage, N, S, E, W
    from tkinter.simpledialog import askstring
    from arelle.CntlrWinTooltip import ToolTip
    from arelle.UiUtil import gridCell, label
    try:
        from tkinter.ttk import Button
    except ImportError:
        from ttk import Button
        
    def enterConnectionString():
        from arelle.DialogUserPassword import askDatabase
        # (user, password, host, port, database)
        db = askDatabase(cntlr.parent, dialog.cellDBconnection.value.split(',') if dialog.cellDBconnection.value else None)
        if db:
            dbConnectionString = ','.join(db)
            dialog.options["xbrlDBconnection"] = dbConnectionString 
            dialog.cellDBconnection.setValue(dbConnectionString)
        else:  # deleted
            dialog.options.pop("xbrlDBconnection", "")  # remove entry
    label(frame, 1, row, "DB Connection:")
    dialog.cellDBconnection = gridCell(frame,2, row, options.get("xbrlDBconnection",""))
    ToolTip(dialog.cellDBconnection, text=_("Enter an XBRL Database (Postgres) connection string.  "
                                           "E.g., host,port,user,password,db[,timeout].  "), wraplength=240)
    enterDBconnectionButton = Button(frame, image=openDatabaseImage, width=12, command=enterConnectionString)
    enterDBconnectionButton.grid(row=row, column=3, sticky=W)
