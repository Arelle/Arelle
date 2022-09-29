'''
See COPYRIGHT.md for copyright information.
'''

from arelle.UiUtil import scrolledHeaderedFrame
from arelle.ViewWinPane import ViewPane

class ViewGrid(ViewPane):
    def __init__(self, modelXbrl, tabWin, tabTitle,
                 hasToolTip=False, lang=None):
        contentView = scrolledHeaderedFrame(tabWin)
        super(ViewGrid, self).__init__(modelXbrl, tabWin, tabTitle,
                                       contentView, hasToolTip=hasToolTip,
                                       lang=lang)
        self.gridTblHdr = self.viewFrame.tblHdrInterior
        self.gridColHdr = self.viewFrame.colHdrInterior
        self.gridRowHdr = self.viewFrame.rowHdrInterior
        self.gridBody = self.viewFrame.bodyInterior

        self.gridTblHdr.contextMenuClick = self.contextMenuClick
        self.gridColHdr.contextMenuClick = self.contextMenuClick
        self.gridRowHdr.contextMenuClick = self.contextMenuClick
        self.gridBody.contextMenuClick = self.contextMenuClick

    def motion(self, *args):
        '''
        tvColId = self.gridBody.identify_column(args[0].x)
        tvRowId = self.gridBody.identify_row(args[0].y)
        if tvColId != self.toolTipColId or tvRowId != self.toolTipRowId:
            self.toolTipColId = tvColId
            self.toolTipRowId = tvRowId
            newValue = None
            if tvRowId and len(tvRowId) > 0:
                try:
                    col = int(tvColId[1:])
                    if col == 0:
                        newValue = self.gridBody.item(tvRowId,"text")
                    else:
                        values = self.gridBody.item(tvRowId,"values")
                        if col <= len(values):
                            newValue = values[col - 1]
                except ValueError:
                    pass
            self.setToolTip(newValue, tvColId)
        '''

    def setToolTip(self, text, colId="#0"):
        self.toolTip._hide()
        if isinstance(text,str) and len(text) > 0:
            width = self.gridBody.column(colId,"width")
            if len(text) * 8 > width or '\n' in text:
                self.toolTipText.set(text)
                self.toolTip.configure(state="normal")
                self.toolTip._schedule()
            else:
                self.toolTipText.set("")
                self.toolTip.configure(state="disabled")
        else:
            self.toolTipText.set("")
            self.toolTip.configure(state="disabled")

    def contextMenu(self):
        super(ViewGrid, self).contextMenu()
        self.bindContextMenu(self.gridBody)
        self.bindContextMenu(self.gridTblHdr)
        self.bindContextMenu(self.gridColHdr)
        self.bindContextMenu(self.gridRowHdr)
        return self.menu
