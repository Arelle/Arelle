'''
@author: Acsone S. A.
See COPYRIGHT.md for copyright information.
'''

import numpy

from arelle import TkTableWrapper
from tkinter import *
from tkinter import messagebox
try:
    from tkinter.ttk import *
    from tkinter.ttk import Combobox as _Combobox
except ImportError:
    from ttk import *
    _Combobox = Combobox
from arelle.CntlrWinTooltip import ToolTip

USE_resizeTableCells = False # disable for now since actually worse for many tables

class Coordinate(object):
    def __init__(self, row, column):
        self.x = int(column)
        self.y = int(row)


    def __str__(self):
        return "%i,%i"%(self.y,self.x)


    def __repr__(self):
        return self.__str__()


    def __eq__(self, other):
        return self.x == other.x and self.y == other.y


    def __ne__(self, other):
        return not(self.__eq__(other))


    def __lt__(self, other):
        return self._ne_(other) and (self.y < other.y
                                      or (self.y == other.y
                                          and self.x < other.x))


    def __gt__(self, other):
        return self._ne_(other) and (self.y > other.y
                                      or (self.y == other.y
                                          and self.x > other.x))


    def __hash__(self):
        return self.__str__().__hash__()


class MyToolTip(ToolTip):
    def __init__(self, master, text='', delay=500, **opts):
        super(MyToolTip, self).__init__(master, text, delay, **opts)

    def motion(self, event=None):
        # no need to follow the mouse if tooltip hidden
        if self.master.mouseMotion(event):
            super(MyToolTip, self).motion(event)


class TableCombobox(_Combobox):
    @property
    def valueIndex(self):
        value = self.get()
        values = self["values"]
        if value in values:
            return values.index(value)
        return -1


class XbrlTable(TkTableWrapper.Table):
    '''
    This class implements all the GUI elements needed for representing
    the sliced 2D-view of an Xbrl Table
    '''

    TG_PREFIX = 'cFmt'
    TG_TOP_LEFT = 'top-left-cell'
    TG_LEFT_JUSTIFIED = 'left'
    TG_RIGHT_JUSTIFIED = 'right'
    TG_CENTERED = 'center'
    TG_TOP_LEFT_JUSTIFIED = 'top-left'
    ANCHOR_POSITIONS = {
                        TG_LEFT_JUSTIFIED : W,
                        TG_RIGHT_JUSTIFIED : E,
                        TG_CENTERED : CENTER,
                        TG_TOP_LEFT_JUSTIFIED : NW
                      }
    JUSTIFICATIONS = {
                        TG_LEFT_JUSTIFIED : LEFT,
                        TG_RIGHT_JUSTIFIED : RIGHT,
                        TG_CENTERED : CENTER,
                        TG_TOP_LEFT_JUSTIFIED : LEFT
                      }

    TG_BG_WHITE = 'bg-white'
    TG_BG_DEFAULT = TG_BG_WHITE
    TG_BG_YELLOW = 'bg-yellow'
    TG_BG_ORANGE = 'bg-orange'
    TG_BG_VIOLET = 'bg-violet'
    TG_BG_GREEN = 'bg-green'
    # The value is a TK RGB value
    COLOURS = {
                TG_BG_WHITE : '#fffffffff',
                TG_BG_YELLOW : '#ff0ff0cc0',
                TG_BG_ORANGE : '#ff0cc0990',
                TG_BG_VIOLET : '#ff0cc0ff0',
                TG_BG_GREEN : '#cc0ff0990'
               }

    TG_DISABLED = 'disabled-cells'

    TG_NO_BORDER = 'no-border'
    TG_BORDER_ALL = 'border-all'
    TG_BORDER_LEFT = 'border-left'
    TG_BORDER_TOP = 'border-top'
    TG_BORDER_RIGHT = 'border-right'
    TG_BORDER_BOTTOM = 'border-bottom'
    TG_BORDER_LEFT_TOP = 'border-left-top'
    TG_BORDER_LEFT_RIGHT = 'border-left-right'
    TG_BORDER_LEFT_BOTTOM = 'border-left-bottom'
    TG_BORDER_TOP_RIGHT = 'border-top-right'
    TG_BORDER_TOP_BOTTOM = 'border-top-bottom'
    TG_BORDER_RIGHT_BOTTOM = 'border-right-bottom'
    TG_BORDER_TOP_RIGHT_BOTTOM = 'border-top-right-bottom'
    TG_BORDER_RIGHT_BOTTOM_LEFT = 'border-right-bottom-left'
    TG_BORDER_BOTTOM_LEFT_TOP = 'border-bottom-left-top'
    TG_BORDER_LEFT_TOP_RIGHT = 'border-left-top-right'

    # (left, right, top, bottom)
    BORDERWIDTHS = {
                        TG_NO_BORDER : (0, 0, 0, 0),
                        TG_BORDER_ALL : (1, 1, 1, 1),
                        TG_BORDER_LEFT : (1, 0, 0, 0),
                        TG_BORDER_TOP : (0, 0, 1, 0),
                        TG_BORDER_RIGHT : (0, 1, 0, 0),
                        TG_BORDER_BOTTOM : (0, 0, 0, 1),
                        TG_BORDER_LEFT_TOP : (1, 0, 1, 0),
                        TG_BORDER_LEFT_RIGHT : (1, 1, 0, 0),
                        TG_BORDER_LEFT_BOTTOM : (1, 0, 0, 1),
                        TG_BORDER_TOP_RIGHT : (0, 1, 1, 0),
                        TG_BORDER_TOP_BOTTOM : (0, 0, 1, 1),
                        TG_BORDER_RIGHT_BOTTOM : (0, 1, 0, 1),
                        TG_BORDER_TOP_RIGHT_BOTTOM : (0, 1, 1, 1),
                        TG_BORDER_RIGHT_BOTTOM_LEFT : (1, 1, 0, 1),
                        TG_BORDER_BOTTOM_LEFT_TOP : (1, 0, 1, 1),
                        TG_BORDER_LEFT_TOP_RIGHT : (1, 1, 1, 0)
                    }

    # 2^0 = bottom
    # 2^1 = top
    # 2^2 = right
    # 2^3 = left
    BORDER_NAMES = [TG_NO_BORDER,
                    TG_BORDER_BOTTOM,
                    TG_BORDER_TOP,
                    TG_BORDER_TOP_BOTTOM,
                    TG_BORDER_RIGHT,
                    TG_BORDER_RIGHT_BOTTOM,
                    TG_BORDER_TOP_RIGHT,
                    TG_BORDER_TOP_RIGHT_BOTTOM,
                    TG_BORDER_LEFT,
                    TG_BORDER_LEFT_BOTTOM,
                    TG_BORDER_LEFT_TOP,
                    TG_BORDER_BOTTOM_LEFT_TOP,
                    TG_BORDER_LEFT_RIGHT,
                    TG_BORDER_RIGHT_BOTTOM_LEFT,
                    TG_BORDER_LEFT_TOP_RIGHT,
                    TG_BORDER_ALL]

    MAX_COLUMN_WIDTH = 20 # Limit for automatically set column width
    MAX_ROW_HEIGHT = 50 # Limit for automatically set row height
    MAX_COLUMN_WIDTH_PLUS_1 = MAX_COLUMN_WIDTH+1
    DEFAULT_COLUMN_WIDTH = 6
    DEFAULT_ROW_HEIGHT = 2

    def mouseMotion(self, event):
        hideToolTip = True
        indexArg, coord = self.getCoordinatesFromEventXY(event)
        if coord is not None:
            if self.lastMouseCoordinates is None or (coord.x != self.lastMouseCoordinates.x or coord.y != self.lastMouseCoordinates.y):
                self.lastMouseCoordinates = coord
                if self.isHeaderCell(coord):
                    tooltipText = event.widget.data[coord.y, coord.x]
                    # tuple x, y, width and height in pixels
                    bbox = self.bbox(indexArg)
                    estimatedWidth = len(tooltipText) * 8
                    #print("estimated= "  + str(estimatedWidth) + " width= " + str(bbox[2]))
                    if estimatedWidth > bbox[2]:
                        #print(tooltipText)
                        self.headerToolTipText.set(tooltipText)
                        self.headerToolTip.configure(state="normal")
                        self.headerToolTip._show()
                        hideToolTip = False
                        self.toolTipShown = True
            else:
                hideToolTip = False

        if hideToolTip and self.toolTipShown:
            self.headerToolTipText.set("")
            self.headerToolTip.configure(state="disabled")
            self.headerToolTip._hide()
        return self.toolTipShown

    def getCoordinatesFromEventXY(self, event):
        indexArg = "@"+str(event.x)+","+str(event.y) # (see http://tktable.sourceforge.net/tktable/doc/tkTable.html#sect6)
        coordStr = self.index(indexArg)
        coordList = coordStr.split(",")
        row = int(coordList[0])
        col = int(coordList[1])
        widget = event.widget
        dataShape = widget.data.shape
        totalRows = dataShape[0]
        totalColumns = dataShape[1]
        if row < totalRows and col < totalColumns:
            coord = Coordinate(row, col)
            return (indexArg, coord)
        return (None, None)

    def cellRight(self, event, *args):
        widget = event.widget
        titleRows = int(widget.cget('titlerows'))
        titleCols = int(widget.cget('titlecols'))
        rowOrigin = int(widget.cget('roworigin'))
        colOrigin = int(widget.cget('colorigin'))
        top = rowOrigin+titleRows
        left = colOrigin+titleCols
        try:
            col = widget.index('active', 'col')
            row = widget.index('active', 'row')
        except (TclError):
            row, col = top-1, left
        maxRows = rowOrigin+int(widget.cget('rows'))
        maxCols = colOrigin+int(widget.cget('cols'))

        widget.selection_clear('all')
        if row<top:
            if (col<left):
                index = '%i,%i'% (top, left)
            else:
                index = '%i,%i'% (top, col)
            widget.activate(index)
            widget.see(index)
            widget.selection_set(index)
        elif col<left:
            index = '%i,%i'% (row, left)
            widget.activate(index)
            widget.see(index)
            widget.selection_set(index)
        elif col<maxCols-1:
            widget.moveCell(0, 1)
        elif row<maxRows-1:
            widget.moveCell(1, left-col)
        else:
            widget.moveCell(top-row, left-col)
        return 'break' # do not execute other handlers!


    def cellDown(self, event, *args):
        widget = event.widget
        titleRows = int(widget.cget('titlerows'))
        titleCols = int(widget.cget('titlecols'))
        rowOrigin = int(widget.cget('roworigin'))
        colOrigin = int(widget.cget('colorigin'))
        top = rowOrigin+titleRows
        left = colOrigin+titleCols
        try:
            col = widget.index('active', 'col')
            row = widget.index('active', 'row')
        except (TclError):
            row, col = top-1, left
        maxRows = rowOrigin+int(widget.cget('rows'))
        maxCols = colOrigin+int(widget.cget('cols'))

        widget.selection_clear('all')
        if row<top:
            if (col<left):
                index = '%i,%i'% (top, left)
            else:
                index = '%i,%i'% (top, col)
            widget.activate(index)
            widget.see(index)
            widget.selection_set(index)
        elif col<left:
            index = '%i,%i'% (row, left)
            widget.activate(index)
            widget.see(index)
            widget.selection_set(index)
        elif row<maxRows-1:
            widget.moveCell(1, 0)
        elif col<maxCols-1:
            widget.moveCell(top-row, 1)
        else:
            widget.moveCell(top-row, left-col)
        return 'break' # do not insert return in cell content


    def _valueCommand(self, event):
        widget = event.widget
        dataShape = widget.data.shape
        totalRows = dataShape[0]
        totalColumns = dataShape[1]
        row = event.r
        col = event.c
        if event.i == 0:
            if (row<totalRows) and (col<totalColumns):
                self.currentCellCoordinates = Coordinate(row, col)
                return widget.data[row, col]
            else:
                return ''
        else:
            if (row<totalRows) and (col<totalColumns):
                widget.data[row, col] = event.S
                self.currentCellCoordinates = Coordinate(row, col)
                widget.modifiedCells[self.currentCellCoordinates] = True
            return 'set'


    def __init__(self, parentWidget, rows, columns, titleRows, titleColumns,
                 tableName=None, browsecmd=None):
        '''
        The initial size of the table (including the header sizes) must be
        supplied at table creation time.
        The contextual menu will have to be created later
        with a 'widget.contextMenu()' command.
        The Tab and Return key are bound to cell navigation.
        '''
        self.data = numpy.empty((rows, columns), dtype=object)
        self.objectIds = numpy.empty((rows, columns), dtype=object)
        self.maxColumnWidths = numpy.empty(columns, dtype=int)
        self.maxRowHeights = numpy.empty(rows, dtype=int)
        self.modifiedCells = dict()
        self.currentCellCoordinates = None
        self.data.fill('')
        self.objectIds.fill('')
        self.maxColumnWidths.fill(0)
        self.maxRowHeights.fill(0)
        self.titleRows = titleRows
        self.titleColumns = titleColumns

        if browsecmd is None:
            if USE_resizeTableCells:
                super(XbrlTable, self).__init__(parentWidget,
                                            rows=rows,
                                            cols=columns,
                                            state='normal',
                                            titlerows=titleRows,
                                            titlecols=titleColumns,
                                            roworigin=0,
                                            colorigin=0,
                                            selectmode='extended',
                                            selecttype='cell',
                                            rowstretch='none',
                                            colstretch='none',
                                            rowheight=self.DEFAULT_ROW_HEIGHT,
                                            colwidth=self.DEFAULT_COLUMN_WIDTH,
                                            flashmode='off',
                                            anchor=NE,
                                            usecommand=1,
                                            background='#d00d00d00',
                                            relief='ridge',
                                            command=self._valueCommand,
                                            takefocus=False,
                                            rowseparator='\n',
                                            wrap=1,
                                            borderwidth=(1, 1, 0, 0),
                                            multiline=1)
            else:
                super(XbrlTable, self).__init__(parentWidget,
                                            rows=rows,
                                            cols=columns,
                                            state='normal',
                                            titlerows=titleRows,
                                            titlecols=titleColumns,
                                            roworigin=0,
                                            colorigin=0,
                                            selectmode='extended',
                                            selecttype='cell',
                                            rowstretch='none',
                                            colstretch='none',
                                            rowheight=-30,
                                            colwidth=15,
                                            flashmode='off',
                                            anchor=NE,
                                            usecommand=1,
                                            background='#d00d00d00',
                                            relief='ridge',
                                            command=self._valueCommand,
                                            takefocus=False,
                                            rowseparator='\n',
                                            wrap=1,
                                            borderwidth=(1, 1, 0, 0),
                                            multiline=1)
        else:
            if USE_resizeTableCells:
                super(XbrlTable, self).__init__(parentWidget,
                                                rows=rows,
                                                cols=columns,
                                                state='normal',
                                                titlerows=titleRows,
                                                titlecols=titleColumns,
                                                roworigin=0,
                                                colorigin=0,
                                                selectmode='extended',
                                                selecttype='cell',
                                                rowstretch='none',
                                                colstretch='none',
                                                rowheight=self.DEFAULT_ROW_HEIGHT,
                                                colwidth=self.DEFAULT_COLUMN_WIDTH,
                                                flashmode='off',
                                                anchor=NE,
                                                usecommand=1,
                                                background='#d00d00d00',
                                                relief='ridge',
                                                command=self._valueCommand,
                                                takefocus=False,
                                                rowseparator='\n',
                                                wrap=1,
                                                multiline=1,
                                                borderwidth=(1, 1, 0, 0),
                                                browsecmd=browsecmd)
            else:
                super(XbrlTable, self).__init__(parentWidget,
                                                rows=rows,
                                                cols=columns,
                                                state='normal',
                                                titlerows=titleRows,
                                                titlecols=titleColumns,
                                                roworigin=0,
                                                colorigin=0,
                                                selectmode='extended',
                                                selecttype='cell',
                                                rowstretch='none',
                                                colstretch='none',
                                                rowheight=-30,
                                                colwidth=15,
                                                flashmode='off',
                                                anchor=NE,
                                                usecommand=1,
                                                background='#d00d00d00',
                                                relief='ridge',
                                                command=self._valueCommand,
                                                takefocus=False,
                                                rowseparator='\n',
                                                wrap=1,
                                                multiline=1,
                                                borderwidth=(1, 1, 0, 0),
                                                browsecmd=browsecmd)

        self.lastMouseCoordinates = None
        self.toolTipShown = False
        self.headerToolTipText = StringVar()
        self.headerToolTip = MyToolTip(self, textvariable=self.headerToolTipText, wraplength=480, follow_mouse=True, state="disabled")

        # Extra key bindings for navigating through the table:
        # Tab: go right
        # Return (and Enter): go down
        self.bind("<Tab>", func=self.cellRight)
        self.bind("<Return>", func=self.cellDown)
        if False:
            self.bind("<Motion>", func=self.mouseMotion)

        # Configure the graphical appearance of the cells by using tags
        self.tag_configure('sel', background = '#b00e00e60',
                           fg='#000000000')
        self.tag_configure('active', background = '#000f70ff0',
                           fg='#000000000')
        self.tag_configure('title', anchor='w', bg='#d00d00d00',
                           fg='#000000000', relief='ridge')
        self.tag_configure(XbrlTable.TG_DISABLED, bg='#d00d00d00',
                           fg='#000000000',
                           relief='flat', state='disabled')

        if rows+columns > 2:
            # The content of the left/top corner cell can already be defined
            topCell = '0,0'
            if titleColumns+titleRows-2 > 0:
                cellSpans = {topCell : '%i,%i'% (titleRows-1, titleColumns-1)}
                self.spans(index=None, **cellSpans)
            self.format_cell(XbrlTable.TG_TOP_LEFT, topCell)
            self.tag_raise(XbrlTable.TG_TOP_LEFT, abovethis='title')
            self.tag_configure(XbrlTable.TG_TOP_LEFT, anchor='ne')
            self.format_cell(XbrlTable.TG_BORDER_ALL, topCell)
            indexValue = {topCell:tableName}
            self.set(**indexValue)


    def _applyFormat(self, tagname, option):
        self.tag_raise(tagname, abovethis='title')
        if option in XbrlTable.BORDERWIDTHS:
            operand_a = XbrlTable.BORDERWIDTHS[option]
            operand_b = tuple(self.tag_cget(tagname, 'borderwidth'))
            if len(operand_b)==0:
                operand_b = XbrlTable.BORDERWIDTHS[XbrlTable.TG_NO_BORDER]
            else:
                operand_b = (int(elem) for elem in operand_b if elem!=' ')
            c = tuple(a | b for a,b in zip (operand_a, operand_b))
            self.tag_configure(tagname, relief='ridge',
                               borderwidth=c)
        elif option in XbrlTable.COLOURS:
            self.tag_configure(tagname, bg=XbrlTable.COLOURS[option])
        elif option in XbrlTable.ANCHOR_POSITIONS:
            self.tag_configure(tagname,
                               anchor=XbrlTable.ANCHOR_POSITIONS[option])
            self.tag_configure(tagname,
                               justify=\
                               XbrlTable.JUSTIFICATIONS[option])


    def format_cell(self, option, index):
        tagname = XbrlTable.TG_PREFIX+index
        self.tag_cell(tagname, index)
        self._applyFormat(tagname, option)


    def set(self, rc=None, index=None, objectId=None, *args, **kwargs):
        super(XbrlTable, self).set(rc=rc, index=index, *args, **kwargs)
        if objectId is not None:
            if index is None:
                index = next(iter(kwargs.keys()))
            row = self.index(index, 'row')
            col = self.index(index, 'col')
            self.objectIds[row, col] = objectId


    def clearModificationStatus(self):
        self.modifiedCells.clear()


    def getObjectId(self, coordinate):
        return str(self.objectIds[coordinate.y, coordinate.x])


    def setObjectId(self, coordinate, objectId):
        self.objectIds[coordinate.y, coordinate.x] = objectId


    def getTableValue(self, coordinate):
        return self.data[coordinate.y, coordinate.x]


    def isHeaderCell(self, coordinate):
        return (coordinate.y < self.titleRows
                or coordinate.x < self.titleColumns)


    def getCoordinatesOfModifiedCells(self):
        return self.modifiedCells.keys()


    def getCurrentCellCoordinates(self):
        return self.currentCellCoordinates

    def initCellValue(self, value, x, y,
                      backgroundColourTag='bg-white',
                      justification='left', objectId=None):
        '''
        Initialise the content of a cell. The resulting cell will be writable.
        '''
        cellIndex = '%i,%i'% (y, x)
        if justification in XbrlTable.ANCHOR_POSITIONS:
            self.format_cell(justification, cellIndex)
        if ((backgroundColourTag is not None)
            and backgroundColourTag in XbrlTable.COLOURS):
            self.format_cell(backgroundColourTag, cellIndex)
        self.format_cell(XbrlTable.TG_BORDER_ALL, cellIndex)
        if value is None:
            value = "" #This is to overcome the fact that we sometimes get spurious stuff when switching tables
        indexValue = {cellIndex:value}
        self.set(objectId=objectId, **indexValue)


    def _setValueFromCombobox(self, event):
        combobox = event.widget
        indexValue = {combobox.tableIndex:combobox.get()}
        self.set(**indexValue)
        return "OK"


    def initCellCombobox(self, value, values, x, y, isOpen=False,
                         objectId=None, selectindex=None,
                         comboboxselected=None, codes=dict()):
        '''
        Initialise the content of a cell as a combobox.
        If isOpen=False, the combobox will be read-only, no new value can
        be added to the combobox.
        '''
        cellIndex = '%i,%i'% (y, x)
        combobox = TableCombobox(self, values=values,
                                 state='active' if isOpen else 'readonly')
        combobox.codes = codes
        combobox.tableIndex = cellIndex
        if selectindex is not None:
            combobox.current(selectindex)
        elif value:
            combobox.set(value)
        try:
            contextMenuBinding = self.bind(self.contextMenuClick)
            if contextMenuBinding:
                self.bind(self.contextMenuClick, contextMenuBinding)
        except AttributeError:
            pass
        combobox.bind(sequence="<<ComboboxSelected>>",
                  func=self._setValueFromCombobox,
                  add='+')
        if comboboxselected:
            combobox.bind(sequence="<<ComboboxSelected>>",
                      func=comboboxselected,
                      add='+')
        self.window_configure(cellIndex,
                              window=combobox,
                              sticky=(N, E, S, W))
        indexValue = {cellIndex:combobox.get()}
        self.set(objectId=objectId, **indexValue)
        combobox.objectId = objectId
        return combobox


    def initReadonlyCell(self, x, y):
        '''
        Make the specified cell read-only
        '''
        cellIndex = '%i,%i'% (y, x)
#        hiddenStatus = self.hidden(cellIndex)
#        if hiddenStatus is None or str(hiddenStatus)='0'\
#            or len(str(hiddenStatus))==0:
#            pass
        self.tag_cell(XbrlTable.TG_DISABLED, cellIndex)

    def _updateMaxSizes(self, value, x, y, colspan, rowspan, minWidth=0):
        '''
        :param value: object
        :param x: int
        :param y: int
        :param colspan: int
        :param rowspan: int
        Here, we compute the size of the current header cell.
        The computation takes into account the colspan and the rowspan.
        If there is a row- or columnspan, the length is gathered uniformly
        among all spanned cells.
        We base our computations on the length of value (converted to a string).
        We keep everything on a line except when the width exceeds self.MAX_COLUMN_WIDTH.
        In the later case, we start wrapping the text on subsequent lines and thus the
        height of the line increases.
        '''
        if colspan < 0:
            colspan = 0
        if rowspan < 0:
            rowspan = 0
        dataShape = self.data.shape
        totalRows = dataShape[0]
        totalColumns = dataShape[1]
        if value is not None:
            valueSize = len(str(value))
            colspanPlus1 = colspan+1
            rowspanPlus1 = rowspan+1
            colWidthBeforeWrapping = (valueSize+colspan)//colspanPlus1 # round towards infinity
            if colWidthBeforeWrapping<minWidth:
                colWidthBeforeWrapping = minWidth
            rowHeight = (colWidthBeforeWrapping+self.MAX_COLUMN_WIDTH)//self.MAX_COLUMN_WIDTH_PLUS_1
            rowHeight = (rowHeight+rowspan)//rowspanPlus1
            for i in range(x, x+colspanPlus1):
                if self.maxColumnWidths[i]<colWidthBeforeWrapping:
                    self.maxColumnWidths[i] = colWidthBeforeWrapping
            for i in range(y, y+rowspanPlus1):
                if self.maxRowHeights[i]<rowHeight:
                    self.maxRowHeights[i] = rowHeight

    def _updateMaxComboboxSizes(self, codes, x, y, colspan, rowspan):
        '''
        This method works like _updateMaxSizes, but for a list of values
        :param codes: list()
        :param x: int
        :param y: int
        :param colspan: int
        :param rowspan: int
        '''
        value = ""
        if len(codes)>0:
            value = codes[0]
            valueLength = len(str(value)) if value is not None else 0
            for code in codes:
                if code is not None:
                    codeLength = len(str(code))
                    if valueLength < codeLength:
                        value = code
                        valueLength = codeLength
        self._updateMaxSizes(value, x, y, colspan, rowspan, minWidth=10)

    def initHeaderCellValue(self, value, x, y, colspan, rowspan,
                            justification, objectId=None,
                            isRollUp=False):
        '''
        Initialise the read-only content of a header cell.
        '''
        cellIndex = '%i,%i'% (y, x)
        if justification in XbrlTable.ANCHOR_POSITIONS:
            self.format_cell(justification, cellIndex)
        if colspan+rowspan > 0:
            cellSpans = {cellIndex : '%i,%i'% (rowspan, colspan)}
            self.spans(index=None, **cellSpans)
        indexValue = {cellIndex:value}
        self.set(objectId=objectId, **indexValue)
        if USE_resizeTableCells:
            self._updateMaxSizes(value, x, y, colspan, rowspan)
        self.initHeaderBorder(x, y,
                              hasLeftBorder=True, hasTopBorder=True,
                              hasRightBorder=True,
                              hasBottomBorder=not isRollUp)
        if isRollUp:
            # In this case, we can afford a reduced column width since the label can span over the other rolled up columns
            self.tk.call(self._w, 'width', x, 3)


    def initCellSpan(self, x, y, colspan, rowspan):
        '''
        Set the row and column span for the given cell
        '''
        if colspan+rowspan > 0:
            cellSpans = {'%i,%i'% (y, x) : '%i,%i'% (rowspan, colspan)}
            self.spans(index=None, **cellSpans)


    def initHeaderCombobox(self, x, y, value='', values=(), colspan=0,
                           rowspan=0, isOpen=True, objectId=None,
                           selectindex=None, comboboxselected=None,
                           codes=dict(),
                           isRollUp=False):
        '''
        Initialise the read-only content of a header cell as a combobox.
        New values can be added to the combobox if isOpen==True.
        '''
        cellIndex = '%i,%i'% (y, x)
        if colspan+rowspan > 0:
            cellSpans = { cellIndex : '%i,%i'% (rowspan, colspan)}
            self.spans(index=None, **cellSpans)
        self.initHeaderBorder(x, y,
                              hasLeftBorder=True, hasTopBorder=True,
                              hasRightBorder=True,
                              hasBottomBorder=not isRollUp)
        if USE_resizeTableCells:
            self._updateMaxComboboxSizes(codes, x, y, colspan, rowspan)
        return self.initCellCombobox(value, values, x, y, isOpen=isOpen,
                                     objectId=objectId, selectindex=selectindex,
                                     comboboxselected=comboboxselected,
                                     codes=codes)


    def drawBordersAroundCell(self, x, y, borders):
        '''
        The borders are coded in an integer:
        2^0 = bottom
        2^1 = top
        2^2 = right
        2^3 = left
        '''
        if borders > 0:
            cellIndex = '%i,%i'% (y, x)
            self.format_cell(XbrlTable.BORDER_NAMES[borders], cellIndex)


    def initHeaderBorder(self, x, y,
                         cellsToTheRight=0, cellsBelow=0,
                         hasLeftBorder=False, hasTopBorder=False,
                         hasRightBorder=False, hasBottomBorder=False):
        '''
        Set the border around a group of header cells.
        The rectangular group of cells will start at position (x,y) and
        possibly extend cellsToTheRight cells to the right and/or
        cellsBelow cells below the given position.
        The border will always have the same size.
        '''
        lastX = x + cellsToTheRight
        lastY = y + cellsBelow
        currentBorder = 1
        if hasBottomBorder:
            # If needed draw bottom border
            for i in range(x, lastX+1):
                self.drawBordersAroundCell(i, lastY, currentBorder)
        currentBorder *= 2
        if hasTopBorder:
            # If needed draw top border
            for i in range(x, lastX+1):
                self.drawBordersAroundCell(i, y, currentBorder)
        currentBorder *= 2
        if hasRightBorder:
            # If needed draw right border
            for j in range(y, lastY+1):
                self.drawBordersAroundCell(lastX, j, currentBorder)
        currentBorder *= 2
        if hasLeftBorder:
            # If needed draw left border
            for j in range(y, lastY+1):
                self.drawBordersAroundCell(x, j, currentBorder)


    def resizeTable(self, rows, columns, titleRows=-1, titleColumns=-1,
                    clearData=True):
        '''
        Resize a table. Only positive increases are allowed.
        Negative increases will be ignored.
        All numbers are absolute numbers and the actual increase will be
        computed by this method.
        If titleRows or titleColumns is less than 0, the corresponding axis
        will not be updated either.
        '''
        try:
            currentCols = int(self.cget('cols'))
            currentRows = int(self.cget('rows'))
            deltaCols = columns - currentCols
            deltaRows = rows - currentRows
            if abs(deltaRows)+abs(deltaCols) > 0:
                self.data.resize([rows, columns])
                self.objectIds.resize([rows, columns])
                self.maxColumnWidths.resize(columns)
                self.maxRowHeights.resize(rows)
            if deltaRows>0:
                self.insert_rows('end', deltaRows)
                self.config(rows=rows)
            elif deltaRows<0:
                self.delete_rows('end', count=abs(deltaRows))
                self.config(rows=rows)
            if deltaCols>0:
                self.insert_cols('end', deltaCols)
                self.config(cols=columns)
            elif deltaCols<0:
                self.delete_cols('end', count=abs(deltaCols))
                self.config(cols=columns)
            if titleRows>=0:
                self.config(titlerows=titleRows)
                self.titleRows = titleRows
            if titleColumns>=0:
                self.config(titlecols=titleColumns)
                self.titleColumns = titleColumns
            if clearData:
                # reset the data whatever the resize pattern is.
                self.data.fill('')
                self.objectIds.fill('')
                self.maxColumnWidths.fill(0)
                self.maxRowHeights.fill(0)
        except Exception as err:
            # Such exception may happen e.g. when quickly switching tables (things are apparently not thread safe)
            messagebox.showwarning(_("arelle - Error"),
                        "Failed resize table:\n{0}".format(err),
                        parent=self.master.view.modelXbrl.modelManager.cntlr.parent)


    def clearSpans(self):
        cellSpans = dict()
        valueIsIndex = True
        # self.spans returns an even list of values (starting at value 1)
        # The odd values are indices.
        # The even values are the spans, they are ignored in this context
        for index in self.spans():
            if valueIsIndex:
                cellSpans[index] = '0,0' # reset span
            valueIsIndex = not(valueIsIndex)
        if len(cellSpans)>0:
            self.spans(index=None, **cellSpans)


    def clearTags(self):
        for tagname in self.tag_names(XbrlTable.TG_PREFIX+'*'):
            self.tag_delete(tagname)


    def disableUnusedCells(self):
        rows, cols = self.objectIds.shape
        iteratorObj = numpy.nditer(self.objectIds[self.titleRows:rows,
                                                  self.titleColumns:cols],
                                   flags=['refs_ok', 'multi_index'])
        while not iteratorObj.finished:
            value = iteratorObj[0]
            row = self.titleRows+iteratorObj.multi_index[0]
            col = self.titleColumns+iteratorObj.multi_index[1]
            if value=='':
                self.initReadonlyCell(col, row)
            _ = iteratorObj.iternext()
        # Set the selection to the first cell
        rowOrigin = int(self.cget('roworigin'))
        colOrigin = int(self.cget('colorigin'))
        top = rowOrigin+self.titleRows
        left = colOrigin+self.titleColumns
        index = '%i,%i'% (top, left)
        self.activate(index)
        self.see(index)
        self.selection_set(index)

    def resizeTableCells(self):
        if USE_resizeTableCells:
            colsToResize = dict()
            rowsToResize = dict()
            for i, width in enumerate(self.maxColumnWidths):
                if width > self.DEFAULT_COLUMN_WIDTH:
                    colsToResize[str(i)] = width if width < self.MAX_COLUMN_WIDTH else self.MAX_COLUMN_WIDTH
            self.width(**colsToResize)
            colsToResize.clear()
            for i, height in enumerate(self.maxRowHeights):
                if height > self.DEFAULT_ROW_HEIGHT:
                    rowsToResize[str(i)] = height if height < self.MAX_ROW_HEIGHT else self.MAX_ROW_HEIGHT
            self.height(**rowsToResize)
            rowsToResize.clear()

class ScrolledTkTableFrame(Frame):
    def __init__(self, parent, browseCmd, *args, **kw):
        Frame.__init__(self, parent, *args, **kw)

        # must be resized later
        table = XbrlTable(self, 1, 1, 0, 0, browsecmd=browseCmd)
        self.table = table
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        # http://effbot.org/zone/tkinter-scrollbar-patterns.htm
        self.verticalScrollbar = Scrollbar(self, orient='vertical',
                                           command=table.yview_scroll)
        self.horizontalScrollbar = Scrollbar(self, orient='horizontal',
                                             command=table.xview_scroll)
        table.config(xscrollcommand=self.horizontalScrollbar.set,
                     yscrollcommand=self.verticalScrollbar.set)
        self.verticalScrollbar.grid(column="1", row='0', sticky=(N, S))
        self.horizontalScrollbar.grid(column="0", row='1', sticky=(W, E))
        self.table.grid(column="0", row='0', sticky=(N, W, S, E))
        self.verticalScrollbarWidth = self.verticalScrollbar.winfo_reqwidth()+5
        self.horizontalScrollbarHeight = self.horizontalScrollbar.winfo_reqheight()+5


    def clearGrid(self):
        self.table.xview_moveto(0)
        self.table.yview_moveto(0)
        for widget in self.table.winfo_children():
                widget.destroy()
        self.table.clear_all()
        self.table.selection_clear('all')
        self.table.clearSpans()
        self.table.clearTags()
        self.update_idletasks()
