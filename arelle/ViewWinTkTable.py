'''
Created on Apr 5, 2015

@author: Acsone S. A.
(c) Copyright 2015 Mark V Systems Limited, All rights reserved.
'''

from arelle.UITkTable import ScrolledTkTableFrame
from arelle.ViewWinPane import ViewPane

class ViewTkTable(ViewPane):
    def __init__(self, modelXbrl, tabWin, tabTitle,
                 table, hasToolTip=False, lang=None):
        contentView = ScrolledTkTableFrame(tabWin, table)
        super(ViewTkTable, self).__init__(modelXbrl, tabWin, tabTitle,
                                       contentView, hasToolTip=hasToolTip,
                                       lang=lang)
        self.table = self.viewFrame.table

        self.table.contextMenuClick = self.contextMenuClick

    def contextMenu(self):
        super(ViewTkTable, self).contextMenu()
        self.bindContextMenu(self.table)
        return self.menu
