'''
Created on Mar, 30 2015

@author: Acsone S. A.
(c) Copyright 2015 Mark V Systems Limited, All rights reserved.
'''

import numpy

from arelle import TkTableWrapper
from tkinter import *
try:
    from tkinter.ttk import *
    _Combobox = ttk.Combobox
except ImportError:
    from ttk import *
    _Combobox = Combobox

LEFT_JUSTIFIED = 0;
RIGHT_JUSTIFIED = 1;

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


class XbrlTable(TkTableWrapper.Table):
    '''
    This class implements all the GUI elements needed for representing
    the sliced 2D-view of an Xbrl Table
    '''

    TG_TOP_LEFT = 'top-left-cell'
    TG_LEFT_JUSTIFIED = 'left'
    TG_RIGHT_JUSTIFIED = 'right'
    JUSTIFICATIONS = set(TG_LEFT_JUSTIFIED, TG_RIGHT_JUSTIFIED)

    TG_BG_WHITE = 'bg-white'
    TG_BG_DEFAULT = TG_BG_WHITE
    TG_BG_YELLOW = 'bg-yellow'
    TG_BG_ORANGE = 'bg-orange'
    TG_BG_BLUE = 'bg-blue'
    TG_BG_GREEN = 'bg-green'
    # The value is a TK RGB value
    COLOURS = {
                TG_BG_WHITE : '#fffffffff',
                TG_BG_YELLOW : '#ff0ff0cc0',
                TG_BG_ORANGE : '#ff0cc0990',
                TG_BG_BLUE : '#cc0ff0990',
                TG_BG_GREEN : '#cc0ff0ff0'
               }

    TG_DISABLED = 'disabled'
    
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
    BORDER_NAMES = [None,
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
    
    def cellRight(self, event, *args):
        widget = event.widget
        titleRows = int(widget.cget('titlerows'))
        titleCols = int(widget.cget('titlecols'))
        top = int(widget.cget('roworigin'))+titleRows
        left = int(widget.cget('colorigin'))+titleCols
        try:
            col = int(widget.index('active', 'col'))
            row = int(widget.index('active', 'row'))
        except (TclError):
            row, col = top-1, left
        maxRows = int(widget.cget('rows'))
        maxCols = int(widget.cget('cols'))

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
        elif col<maxCols-titleCols-1:
            widget.moveCell(0, 1)
        elif row<maxRows-titleCols-1:
            widget.moveCell(1, left-col)
        else:
            widget.moveCell(top-row, left-col)


    def cellDown(self, event, *args):
        widget = event.widget
        titleRows = int(widget.cget('titlerows'))
        titleCols = int(widget.cget('titlecols'))
        top = int(widget.cget('roworigin'))+titleRows
        left = int(widget.cget('colorigin'))+titleCols
        try:
            col = int(widget.index('active', 'col'))
            row = int(widget.index('active', 'row'))
        except (TclError):
            row, col = top-1, left
        maxRows = int(widget.cget('rows'))
        maxCols = int(widget.cget('cols'))

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
        elif row<maxRows-titleRows-1:
            widget.moveCell(1, 0)
        elif col<maxCols-titleCols-1:
            widget.moveCell(top-row, 1)
        else:
            widget.moveCell(top-row, left-col)
        return 'break' # do not insert return in cell content


    def valueCommand(self, event):
        if event.i == 0:
            return self.data[event.r, event.c]
        else:
            self.data[event.r, event.c] = event.S
            self.isModified[Coordinate(event.r, event.c)] = True
            return 'set'


    def __init__(self, parentWidget, rows, columns, titleRows, titleColumns,
                 tableName, browsecmd):
        '''
        The initial size of the table (including the header sizes) must be
        supplied at table creation time.
        The contextual menu will have to be created later
        with a 'widget.contextMenu()' command.
        The Tab and Return key are bound to cell navigation.
        '''
        self.data = numpy.empty((rows, columns), dtype=str)
        self.objectIds = numpy.empty((rows, columns), dtype=str)
        self.isModified = dict()
        self.data.fill('')
        self.objectIds.fill('')

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
                                        rowstretch='last',
                                        colstretch='last',
                                        rowheight=-26,
                                        colwidth=15,
                                        flashmode='off',
                                        anchor='e',
                                        usecommand=1,
                                        background='#fffffffff',
                                        relief='sunken',
                                        command=self.valueCommand,
                                        takefocus=False,
                                        rowseparator='\n',
                                        browsecmd=browsecmd)

        # http://effbot.org/zone/tkinter-scrollbar-patterns.htm
        verticalScrollbar = Scrollbar(parentWidget, orient='vertical',
                                      command=self.yview_scroll)
        horizontalScrollbar = Scrollbar(parentWidget, orient='horizontal',
                                        command=parentWidget.xview_scroll)
        parentWidget.config(xscrollcommand=horizontalScrollbar.set,
                            yscrollcommand=verticalScrollbar.set)
        #Set the layout of the newly created widgets
        verticalScrollbar.grid(column="1", row='0', sticky=(N, S))
        horizontalScrollbar.grid(column="0", row='1', sticky=(W, E))
        self.grid(column="0", row='0', sticky=(N, W, S, E))

        # Extra key bindings for navigating through the table:
        # Tab: go right
        # Return (and Enter): go down
        self.bind("<Tab>", func=self.cellRight, add="+")
        self.bind("<Return>", func=self.cellDown)

        # Configure the graphical appearance of the cells by using tags
        self.tag_configure('sel', background = '#000400400')
        self.tag_configure('active', background = '#000a00a00')
        self.tag_configure('title', anchor='w', bg='#d00d00d00',
                           fg='#000000000', relief='flat')
        self.tag_configure(self.TG_DISABLED, bg='#d00d00d00', fg='#000000000',
                           relief='flat', state='disabled')
        for tagname, brdrwidth in self.BORDERWIDTHS.items():
            self.tag_raise(tagname, abovethis='title')
            self.tag_configure(tagname, relief='ridge', borderwidth=brdrwidth)
        for tagname, colour in self.COLOURS.items():
            self.tag_configure(tagname, bg=colour)
        self.tag_raise(self.TG_LEFT_JUSTIFIED, abovethis='title')
        self.tag_configure(self.TG_LEFT_JUSTIFIED, anchor='w')
        self.tag_raise(self.TG_RIGHT_JUSTIFIED, abovethis='title')
        self.tag_configure(self.TG_RIGHT_JUSTIFIED, anchor='e')

        # The content of the left/top corner cell can already be defined
        topCell = '0,0'
        if titleColumns+titleRows-2 > 0:
            self.spans(index=topCell, '%i,%i'% (titleRows-1, titleColumns-1))
        self.tag_cell(self.TG_TOP_LEFT, topCell)
        self.tag_raise(self.TG_TOP_LEFT, abovethis='title')
        self.tag_configure(self.TG_TOP_LEFT, anchor='ne')
        self.tag_cell(self.TG_BORDER_ALL, topCell)
        self.set(index=topCell, tableName)


    def set(self, rc=None, index=None, objectId=None, *args, **kwargs):
        super(XbrlTable, self).set(rc=rc, index=index, *args, **kwargs)
        if objectId is not None:
            row = self.index(index=index, rc='row')
            col = self.index(index=index, rc='col')
            self.objectIds[row, col] = objectId


    def getAndResetModificationStatus(self, index):
        value = self.get(key=index)
        row = self.index(index=index, rc='row')
        col = self.index(index=index, rc='col')
        del self.isModified[Coordinate(row, col)]
        return value


    def initCellValue(self, value, x, y, backgroundColourTag=None,
                     justification='left', objectId=None):
        '''
        Initialise the content of a cell. The resulting cell will be writable.
        '''
        cellIndex = '%i,%i'% (y, x)
        if justification in self.JUSTIFICATIONS:
            self.tag_cell(justification, cellIndex)
        if ((backgroundColourTag is not None) 
            and backgroundColourTag in self.COULOURS):
            self.tag_cell(backgroundColourTag, cellIndex)
        self.set(index=cellIndex, objectId=objectId, value)


    def _setValueFromCombobox(self, event):
        combobox = event.widget
        self.set(index=combobox.tableIndex, combobox.get())


    def initCellCombobox(self, value, values, x, y, isOpen=False,
                         objectId=None, selectindex=None, 
                         comboboxselected=None, onClick=None, codes=dict()):
        '''
        Initialise the content of a cell as a combobox.
        The combobox is read-only, no new value can be added to the combobox.
        '''
        cellIndex = '%i,%i'% (y, x)
        combobox = _Combobox(self, values=values,
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
        self.bind("<<ComboboxSelected>>", self._setValueFromCombobox)
        if comboboxselected:
            self.bind("<<ComboboxSelected>>", comboboxselected, '+')
        if onClick:
            self.bind("<1>", onClick)
        self.window_configure(cellIndex,
                              window=combobox,
                              sticky=(N, E, S, W))
        self.set(index=cellIndex, objectId=objectId, combobox.get())
        return combobox

    def initReadonlyCell(self, x, y, colspan, rowspan):
        '''
        Make the specified cell read-only
        '''
        cellIndex = '%i,%i'% (y, x)
        self.tag_cell(self.TG_DISABLED, cellIndex)

    def initHeaderCellValue(self, value, x, y, colspan, rowspan,
                            justification):
        '''
        Initialise the read-only content of a header cell.
        '''
        cellIndex = '%i,%i'% (y, x)
        if justification in self.JUSTIFICATIONS:
            self.tag_cell(justification, cellIndex)
        if colspan+rowspan > 0:
            self.spans(index=cellIndex, '%i,%i'% (rowspan, colspan))
        self.set(index=cellIndex, value)

    def initHeaderCombobox(self, x, y, value='', values=(), colspan=None,
                           rowspan=None, isOpen=True, objectId=None,
                           selectindex=None, comboboxselected=None,
                           onClick=None, codes=dict()):
        '''
        Initialise the read-only content of a header cell as a combobox.
        New values can be added to the combobox if isOpen==True.
        '''
        if colspan+rowspan > 0:
            cellIndex = '%i,%i'% (y, x)
            self.spans(index=cellIndex, '%i,%i'% (rowspan, colspan))
        return self.initCellCombobox(value, values, x, y, isOpen=isOpen,
                                     objectId=objectId, selectindex=selectindex,
                                     omboboxselected=comboboxselected,
                                     onClick=onClick, codes=codes)


    def initHeaderBorder(self, x, y,
                         hasLeftBorder=False, hasTopBorder=False,
                         hasRightBorder=False, hasBottomBorder=False):
        '''
        Set the border around a header cell. The border will always have the
        same size.
        '''
        borders = 0
        currentBorder = 1
        if hasBottomBorder:
            borders = currentBorder
        currentBorder *= 2
        if hasTopBorder:
            borders += currentBorder
        currentBorder *= 2
        if hasRightBorder:
            borders += currentBorder
        currentBorder *= 2
        if hasLeftBorder:
            borders += currentBorder
        if borders > 0:
            cellIndex = '%i,%i'% (y, x)
            self.tag_cell(self.BORDER_NAMES[borders], cellIndex)
