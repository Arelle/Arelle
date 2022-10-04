'''
@author: Acsone S. A.
See COPYRIGHT.md for copyright information.
'''

from arelle.UITkTable import ScrolledTkTableFrame
from arelle.ViewWinPane import ViewPane

class ViewTkTable(ViewPane):
    def __init__(self, modelXbrl, tabWin, tabTitle,
                 hasToolTip=False, lang=None, browseCmd=None):
        contentView = ScrolledTkTableFrame(tabWin, browseCmd)
        super(ViewTkTable, self).__init__(modelXbrl, tabWin, tabTitle,
                                       contentView, hasToolTip=hasToolTip,
                                       lang=lang)
        self.table = self.viewFrame.table
        self.setHeightAndWidth()
        self.table.contextMenuClick = self.contextMenuClick

    def contextMenu(self):
        super(ViewTkTable, self).contextMenu()
        self.bindContextMenu(self.table)
        return self.menu

    def setHeightAndWidth(self):
        frameWidth = self.tabWin.winfo_width()
        frameHeight = self.tabWin.winfo_height()
        self.table.config(maxheight=frameHeight-self.viewFrame.horizontalScrollbarHeight,
                          maxwidth=frameWidth-self.viewFrame.verticalScrollbarWidth)
