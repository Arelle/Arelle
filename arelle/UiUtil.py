'''
Created on Jan 25, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from tkinter import *
from tkinter.ttk import *

TOPBORDER = 1
LEFTBORDER = 2
RIGHTBORDER = 3
BOTTOMBORDER = 4
CENTERCELL = 5
borderImage = None

class gridBorder(Separator):
    def __init__(self, master, x, y, border, columnspan=None, rowspan=None): 
        Separator.__init__(self, master=master) 
        if border in (TOPBORDER, BOTTOMBORDER):
            x = x * 2 - 1
            if columnspan: columnspan = columnspan * 2 + 1
            else: columnspan = 3
            self.config(orient="horizontal")
            sticky = (E,W)
        if border in (LEFTBORDER, RIGHTBORDER):
            y = y * 2 - 1
            if rowspan: rowspan = rowspan * 2 + 1
            else: rowspan = 3
            self.config(orient="vertical")
            sticky = (N,S)
        if border == TOPBORDER:
            rowspan = None
            y = y * 2 - 1
            self.rowconfigure(y, weight=0, uniform=1)
        elif border == BOTTOMBORDER:
            if rowspan:
                y = (y + rowspan - 1) * 2 + 1
                rowspan = None
            else:
                y = y * 2 + 1
            self.rowconfigure(y, weight=0, uniform=1)
        elif border == LEFTBORDER:
            columnspan = None
            x = x * 2 - 1
            self.columnconfigure(x, weight=0, uniform=1)
        elif border == RIGHTBORDER:
            if columnspan:
                x = (x + columnspan - 1) * 2 + 1
                columnspan = None
            else:
                x = x * 2 + 1
            self.columnconfigure(x, weight=0, uniform=1)
        if columnspan and columnspan > 1 and rowspan and rowspan > 1:
            self.grid(column=x, row=y, sticky=sticky, columnspan=columnspan, rowspan=rowspan)
        elif columnspan and columnspan > 1:
            self.grid(column=x, row=y, sticky=sticky, columnspan=columnspan)
        elif rowspan and rowspan > 1:
            self.grid(column=x, row=y, sticky=sticky, rowspan=rowspan)
        else:
            self.grid(column=x, row=y, sticky=sticky) 
        self.x = x
        self.y = y
        self.columnspan = columnspan
        self.rowspan = rowspan
        # copy bindings
        try:
            contextMenuBinding = master.bind(master.contextMenuClick)
            if contextMenuBinding:
                self.bind(master.contextMenuClick, contextMenuBinding)
        except AttributeError:
            pass
        #if isinstance(master.master.master, scrolledHeaderedFrame):
        #    self.bind("<Configure>", master.master.master._configure_cell)
  
class gridSpacer(Frame):
    def __init__(self, master, x, y, where): 
        Frame.__init__(self, master=master)
        if where == CENTERCELL:
            offset = 0
        elif where in (TOPBORDER, LEFTBORDER):
            offset = -1
        else:
            offset = 1 
        x = x * 2 + offset
        y = y * 2 + offset
        self.grid(column=x, row=y) # same dimensions as separator in col/row headers
        self.x = x
        self.y = y
        # copy bindings
        try:
            contextMenuBinding = master.bind(master.contextMenuClick)
            if contextMenuBinding:
                self.bind(master.contextMenuClick, contextMenuBinding)
        except AttributeError:
            pass
        #if isinstance(master.master.master, scrolledHeaderedFrame):
        #    self.bind("<Configure>", master.master.master._configure_cell)
  
class gridHdr(Label): 
    def __init__(self, master, x, y, text, columnspan=None, rowspan=None, anchor='center', padding=None, wraplength=None, width=None, objectId=None, onClick=None): 
        Label.__init__(self, master=master) 
        if isinstance(master.master.master, scrolledHeaderedFrame):
            x = x * 2
            y = y * 2
            if columnspan: columnspan = columnspan * 2 - 1
            if rowspan: rowspan = rowspan * 2 - 1
        self.config(text=text if text is not None else "",
                    #relief="solid", use border instead to effect row-col spanned cells properly 
                    #bg="#ffffff000", fg="#000000fff", 
                    #readonlybackground="#ddddddddd",
                    
                    #background="#888000000", 
                    width=width,
                    anchor=anchor) 
        if padding:
            self.config(padding=padding)
        if wraplength:
            self.config(wraplength=wraplength)
        if columnspan and columnspan > 1 and rowspan and rowspan > 1:
            self.grid(column=x, row=y, sticky=(E,W,N,S), columnspan=columnspan, rowspan=rowspan)
        elif columnspan and columnspan > 1:
            self.grid(column=x, row=y, sticky=(E,W,N,S), columnspan=columnspan)
        elif rowspan and rowspan > 1:
            self.grid(column=x, row=y, sticky=(E,W,N,S), rowspan=rowspan)
        else:
            self.grid(column=x, row=y, sticky=(E,W,N,S)) 
        self.x = x
        self.y = y
        self.columnspan = columnspan
        self.rowspan = rowspan
        self.objectId = objectId
        # copy bindings
        try:
            contextMenuBinding = master.bind(master.contextMenuClick)
            if contextMenuBinding:
                self.bind(master.contextMenuClick, contextMenuBinding)
        except AttributeError:
            pass
        if isinstance(master.master.master, scrolledHeaderedFrame):
            self.bind("<Configure>", master.master.master._configure_cell)
        if onClick:
            self.bind("<1>", onClick)
  
class gridCell(Entry): 
    def __init__(self, master, x, y, value="", width=None, justify=None, objectId=None, onClick=None): 
        Entry.__init__(self, master=master) 
        self.valueVar = StringVar() 
        self.config(textvariable=self.valueVar,
                    #relief="ridge", 
                    #bg="#ff8ff8ff8", fg="#000000000", 
                    justify=justify,
                    width=width,
                    ) 
        if isinstance(master.master.master, scrolledHeaderedFrame):
            x = x * 2
            y = y * 2
        self.grid(column=x, row=y, sticky=(N,S,E,W))
        self.x = x
        self.y = y
        if value is not None: 
            self.valueVar.set(value)
        self.objectId = objectId
        # copy bindings
        try:
            contextMenuBinding = master.bind(master.contextMenuClick)
            if contextMenuBinding:
                self.bind(master.contextMenuClick, contextMenuBinding)
        except AttributeError:
            pass
        if isinstance(master.master.master, scrolledHeaderedFrame):
            self.bind("<Configure>", master.master.master._configure_cell)
        if onClick:
            self.bind("<1>", onClick)
        
    @property
    def value(self):
        return self.valueVar.get()
    
    def setValue(self, value):
        return self.valueVar.set(value)
    
class gridCombobox(ttk.Combobox): 
    def __init__(self, master, x, y, value="", values=(), selectindex=None, comboboxselected=None): 
        ttk.Combobox.__init__(self, master=master) 
        self.valueVar = StringVar() 
        self.config(textvariable=self.valueVar,
                    background="#ff8ff8ff8", foreground="#000000000", 
                   # justify='center'
                    ) 
        self["values"] = values
        if isinstance(master.master.master, scrolledHeaderedFrame):
            x = x * 2
            y = y * 2
        self.grid(column=x, row=y, sticky=(E,W)) 
        if selectindex is not None:
            self.valueVar.set(values[selectindex])
        elif value: 
            self.valueVar.set(value)
        # copy bindings
        try:
            contextMenuBinding = master.bind(master.contextMenuClick)
            if contextMenuBinding:
                self.bind(master.contextMenuClick, contextMenuBinding)
        except AttributeError:
            pass
        if comboboxselected:
            self.bind("<<ComboboxSelected>>", comboboxselected)
        
    @property
    def value(self):
        return self.valueVar.get()
    
    @property
    def valueIndex(self):
        value = self.valueVar.get()
        values = self["values"]
        if value in values:
            return values.index(value)
        return -1
        
    
class label(Label):
    def __init__(self, master, x, y, text):
        Label.__init__(self, master=master, text=text) 
        #self.config(justify='left') 
        self.grid(column=x, row=y, sticky=W, padx=8) 
    
class checkbox(Checkbutton):
    def __init__(self, master, x, y, text, attr=None):
        self.attr = attr 
        self.valueVar = StringVar() 
        Checkbutton.__init__(self, master=master, text=text, variable=self.valueVar) 
        self.grid(column=x, row=y, sticky=W, padx=24) 
        try:
            options = master.master.options
            if attr and hasattr(options, attr):
                self.valueVar.set( getattr(options,attr) )
        except AttributeError:
            pass
        
    @property
    def value(self):
        if self.valueVar.get() == "1":
            return True
        else:
            return False
        
class radiobutton(Radiobutton):
    def __init__(self, master, x, y, text, value, attr=None, valueVar=None):
        self.attr = attr 
        self.valueVar = valueVar if valueVar else StringVar() 
        Radiobutton.__init__(self, master=master, text=text, variable=self.valueVar, value=value) 
        self.grid(column=x, row=y, sticky=W, padx=24) 
        try:
            options = master.master.options
            if attr and hasattr(options, attr):
                self.valueVar.set( getattr(options,attr) )
        except AttributeError:
            pass
        
    @property
    def value(self):
        return self.valueVar.get()
        
class scrolledFrame(Frame):
    def __init__(self, parent, *args, **kw):
        Frame.__init__(self, parent, *args, **kw)            

        vscrollbar = Scrollbar(self, orient=VERTICAL)
        hscrollbar = Scrollbar(self, orient=HORIZONTAL)
        self.canvas = canvas = Canvas(self, bd=0, highlightthickness=0,
                                      yscrollcommand=vscrollbar.set,
                                      xscrollcommand=hscrollbar.set)
        self.grid(row=0, column=0, sticky=(N,S,E,W))
        canvas.grid(row=0, column=0, sticky=(N,S,E,W))
        vscrollbar.grid(row=0, column=1, sticky=(N,S))
        hscrollbar.grid(row=1, column=0, sticky=(E,W))
        vscrollbar.config(command=canvas.yview)
        hscrollbar.config(command=canvas.xview)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        canvas.columnconfigure(0, weight=1)
        canvas.rowconfigure(0, weight=1)

        # reset the view
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

        # create a frame inside the canvas which will be scrolled with it
        self.interior = interior = Frame(canvas)
        self.interior_id = canvas.create_window(0, 0, window=interior, anchor=NW)
        interior.bind('<Configure>', self._configure_interior)
        canvas.bind('<Configure>', self._configure_canvas)
    
    def _configure_interior(self,event):
        # update the scrollbars to match the size of the inner frame
        interiorW = self.interior.winfo_reqwidth()
        interiorH = self.interior.winfo_reqheight()
        self.canvas.config(scrollregion=(0,0,interiorW,interiorH))
        ''' needed if scrolling only in 1 direction (for the axis that doesn't have scrollbar)
        if interiorW != self.canvas.winfo_width():
            # update the canvas's width to fit the inner frame
            self.canvas.config(width=interiorW)
        if interiorH != self.canvas.winfo_height():
            self.canvas.config(height=interiorH)
        '''

    def _configure_canvas(self, event):
        ''' needed if only scrolling in one direction
        canvasW = self.canvas.winfo_width()
        if self.interior.winfo_reqwidth() != canvasW:
            # update the inner frame's width to fill the canvas
            self.canvas.itemconfigure(self.interior_id, width=canvasW)
        canvasH = self.canvas.winfo_height()
        if self.interior.winfo_reqheight() != canvasH:
            self.canvas.itemconfigure(self.interior_id, height=canvasH)
        '''
        
class scrolledHeaderedFrame(Frame):
    def __init__(self, parent, *args, **kw):
        Frame.__init__(self, parent, *args, **kw)            

        self.colsConfigured = False
        self.hdrVscrollbar = Scrollbar(self, orient=VERTICAL)
        self.hdrHscrollbar = Scrollbar(self, orient=HORIZONTAL)
        self.bodyVscrollbar = Scrollbar(self, orient=VERTICAL)
        self.bodyHscrollbar = Scrollbar(self, orient=HORIZONTAL)
        self.colHdrCanvas = Canvas(self, bd=0, highlightthickness=0,
                                   yscrollcommand=self.hdrVscrollbar.set)
        self.rowHdrCanvas = Canvas(self, bd=0, highlightthickness=0,
                                 xscrollcommand=self.hdrHscrollbar.set)
        self.bodyCanvas = Canvas(self, bd=0, highlightthickness=0,
                                 yscrollcommand=self.bodyVscrollbar.set,
                                 xscrollcommand=self.bodyHscrollbar.set)
        self.grid(row=0, column=0, sticky=(N,S,E,W))
        self.tblHdrInterior = Frame(self)
        self.tblHdrInterior.grid(row=1, column=0, sticky=(N,S,E,W))
        self.colHdrCanvas.grid(row=1, column=1, sticky=(N,W,E))
        self.rowHdrCanvas.grid(row=2, column=0, sticky=(N,W,S))
        self.bodyCanvas.grid(row=2, column=1, sticky=(N,S,E,W))
        self.hdrVscrollbar.grid(row=1, column=2, sticky=(N,S))
        self.hdrHscrollbar.grid(row=3, column=0, sticky=(E,W))
        self.bodyVscrollbar.grid(row=2, column=2, sticky=(N,S))
        self.bodyHscrollbar.grid(row=3, column=1, sticky=(E,W))
        self.hdrVscrollbar.config(command=self.colHdrCanvas.yview)
        self.hdrHscrollbar.config(command=self.rowHdrCanvas.xview)
        self.bodyVscrollbar.config(command=self._vscroll_body)
        self.bodyHscrollbar.config(command=self._hscroll_body)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)
        '''
        self.rowHdrCanvas.columnconfigure(1, weight=1)
        self.colHdrCanvas.rowconfigure(2, weight=1)
        self.bodyCanvas.columnconfigure(1, weight=1)
        self.bodyCanvas.rowconfigure(2, weight=1)
        '''

        # reset the view
        self.colHdrCanvas.xview_moveto(0)
        self.colHdrCanvas.yview_moveto(0)
        self.rowHdrCanvas.xview_moveto(0)
        self.rowHdrCanvas.yview_moveto(0)
        self.bodyCanvas.xview_moveto(0)
        self.bodyCanvas.yview_moveto(0)

        # create a frame inside the canvas which will be scrolled with it
        self.colHdrInterior = Frame(self.colHdrCanvas)
        self.rowHdrInterior = Frame(self.rowHdrCanvas)
        self.bodyInterior = Frame(self.bodyCanvas)
        self.colHdrInterior_id = self.colHdrCanvas.create_window(0, 0, window=self.colHdrInterior, anchor=NW)
        self.rowHdrInterior_id = self.rowHdrCanvas.create_window(0, 0, window=self.rowHdrInterior, anchor=NW)
        self.bodyInterior_id = self.bodyCanvas.create_window(0, 0, window=self.bodyInterior, anchor=NW)
        self.colHdrInterior.bind('<Configure>', self._configure_colHdrInterior)
        self.rowHdrInterior.bind('<Configure>', self._configure_rowHdrInterior)
        self.bodyInterior.bind('<Configure>', self._configure_bodyInterior)
        self.colHdrCanvas.bind('<Configure>', self._configure_colHdrCanvas)
        self.rowHdrCanvas.bind('<Configure>', self._configure_rowHdrCanvas)
        self.bodyCanvas.bind('<Configure>', self._configure_bodyCanvas)
        '''
        self.colHdrInterior.bind('<Configure>', self._configure_interiors)
        self.rowHdrInterior.bind('<Configure>', self._configure_rowHdrInterior)
        self.bodyInterior.bind('<Configure>', self._configure_rowHdrInterior)
        self.colHdrCanvas.bind('<Configure>', self._configure_canvases)
        self.rowHdrCanvas.bind('<Configure>', self._configure_canvases)
        #self.bodyCanvas.bind('<Configure>', self._configure_canvases)
        '''
        # on linux Button-4, Button-5 events
        #self.rowHdrCanvas.bind("<MouseWheel>", self._mousewheel)
        #self.bodyCanvas.bind("<MouseWheel>", self._mousewheel)
        
    def _vscroll_body(self, *args):
        self.rowHdrCanvas.yview(*args)
        self.bodyCanvas.yview(*args)
    
    def _hscroll_body(self, *args):
        self.colHdrCanvas.xview(*args)
        self.bodyCanvas.xview(*args)
    
    def _mousewheel(self, event):
        # on linux:  if (event.num == 4): delta = -1 elif (event.num == 5): delta = 1 else: delta = event.delta
        self.rowHdrCanvas.yview("scroll", event.delta, "units")
        self.bodyCanvas.yview("scroll", event.delta, "units")
        return "break" #don't do default scrolling
    
    def clearGrid(self):
        self.colHdrCanvas.xview_moveto(0)
        self.colHdrCanvas.yview_moveto(0)
        self.rowHdrCanvas.xview_moveto(0)
        self.rowHdrCanvas.yview_moveto(0)
        self.bodyCanvas.xview_moveto(0)
        self.bodyCanvas.yview_moveto(0)
        for grid in (self.tblHdrInterior, self.colHdrInterior, self.rowHdrInterior, self.bodyInterior):
            x,y = grid.size()
            for widget in grid.winfo_children():
                widget.destroy()
            if x > 1 and y > 1: # not gridTblHdr
                for x in range(x): grid.tk.call( ('grid', 'columnconfigure', grid._w, x, '-minsize', 0 ) )
                for y in range(y): grid.tk.call( ('grid', 'rowconfigure', grid._w, y, '-minsize', 0 ) )
                grid.config(width=1,height=1)
                grid.master.config(width=1,height=1,scrollregion=(0,0,1,1))
        self.update()
        self.colsConfigured = False

    def _configure_colHdrInterior(self,event):
        if not self.colsConfigured:
            self.conformHdrsToBody()
        interiorW = self.colHdrInterior.winfo_reqwidth()
        interiorH = self.colHdrInterior.winfo_reqheight()
        self.colHdrCanvas.config(scrollregion=(0,0,interiorW,interiorH))
        if interiorH != self.colHdrCanvas.winfo_height(): # update the canvas's width to fit the inner frame
            self.colHdrCanvas.config(height=interiorH)
        #if interiorH != self.tblHdrInterior.winfo_height():
        #    self.tblHdrInterior.tk.call( ('grid', 'rowconfigure', self.tblHdrInterior._w, 1, '-minsize', interiorH ) )
    def _configure_rowHdrInterior(self,event):
        interiorW = self.rowHdrInterior.winfo_reqwidth()
        interiorH = self.rowHdrInterior.winfo_reqheight()
        self.rowHdrCanvas.config(scrollregion=(0,0,interiorW,interiorH))
        if interiorW != self.rowHdrCanvas.winfo_width(): # update the canvas's width to fit the inner frame
            self.rowHdrCanvas.config(width=interiorW)
        #if interiorW != self.tblHdrInterior.winfo_width() or \
        #   interiorW != self.tblHdrInterior.tk.call( ('grid', 'columnconfigure', self.tblHdrInterior._w, 1, '-minsize' ) ):
        #    self.tblHdrInterior.tk.call( ('grid', 'columnconfigure', self.tblHdrInterior._w, 1, '-minsize', interiorW ) )
    def _configure_bodyInterior(self,event):
        interiorW = self.bodyInterior.winfo_reqwidth()
        interiorH = self.bodyInterior.winfo_reqheight()
        self.bodyCanvas.config(scrollregion=(0,0,interiorW,interiorH))
    def _configure_colHdrCanvas(self, event):
        canvasH = self.colHdrCanvas.winfo_height()
        if self.colHdrInterior.winfo_reqheight() != canvasH:
            self.colHdrCanvas.itemconfigure(self.colHdrInterior_id, height=canvasH)
    def _configure_rowHdrCanvas(self, event):
        canvasW = self.rowHdrCanvas.winfo_width()
        if self.rowHdrInterior.winfo_reqwidth() != canvasW:
            self.rowHdrCanvas.itemconfigure(self.rowHdrInterior_id, width=canvasW)
    def _configure_bodyCanvas(self, event):
        #canvasW = self.rowHdrCanvas.winfo_width()
        #if self.rowHdrInterior.winfo_reqwidth() != canvasW:
        #    self.rowHdrCanvas.itemconfigure(self.rowHdrInterior_id, width=canvasW)
        pass
    def _configure_interiors(self,event):
        bodyW = self.bodyInterior.winfo_reqwidth()
        bodyH = self.bodyInterior.winfo_reqheight()
        colHdrW = self.colHdrInterior.winfo_reqwidth()
        colHdrH = self.colHdrInterior.winfo_reqheight()
        rowHdrW = self.rowHdrInterior.winfo_reqwidth()
        rowHdrH = self.rowHdrInterior.winfo_reqheight()
        bodyW = max(bodyW,colHdrW)
        bodyH = max(bodyH,rowHdrH)
        self.bodyCanvas.config(scrollregion=(0,0,bodyW,bodyH))
        self.colHdrCanvas.config(scrollregion=(0,0,bodyW,colHdrH))
        self.rowHdrCanvas.config(scrollregion=(0,0,rowHdrW,bodyH))
    def _configure_canvases(self, event):
        canvasH = self.colHdrCanvas.winfo_height()
        if self.colHdrInterior.winfo_reqheight() != canvasH:
            self.colHdrCanvas.itemconfigure(self.colHdrInterior_id, height=canvasH)
        canvasW = self.rowHdrCanvas.winfo_width()
        if self.rowHdrInterior.winfo_reqwidth() != canvasW:
            self.rowHdrCanvas.itemconfigure(self.rowHdrInterior_id, width=canvasW)
    def _configure_cell(self, event):
        cell = event.widget
        x = cell.x
        y = cell.y
        cellW = cell.winfo_reqwidth()
        cellH = cell.winfo_reqheight()
        isColHdrCell = event.widget.master == self.colHdrInterior
        isRowHdrCell = event.widget.master == self.rowHdrInterior
        isBodyCell = event.widget.master == self.bodyInterior
        if isColHdrCell:
            if hasattr(cell,'columnspan') and cell.columnspan:
                columnspan = cell.columnspan # this is the non borders columns spanned
            else:
                columnspan = 1
            w = int(cellW / columnspan)
            wWiderAlloced = 0
            wNumWider = 0
            for X in range(x, x + columnspan*2, 2): # spanned cols divided equally over their columns
                bodyColW = self.bodyInterior.tk.call( ('grid', 'columnconfigure', self.bodyInterior._w, X, '-minsize' ) )
                if bodyColW > w:
                    wWiderAlloced += bodyColW
                    wNumWider += 1
            if columnspan - wNumWider > 0 and cellW > wWiderAlloced:
                W = int((cellW - wWiderAlloced) / (columnspan - wNumWider))
                for X in range(x, x + columnspan*2, 2): # spanned cols divided equally over their columns
                    bodyColW = self.bodyInterior.tk.call( ('grid', 'columnconfigure', self.bodyInterior._w, X, '-minsize' ) )
                    if w > bodyColW: # even cells only
                        self.bodyInterior.tk.call( ('grid', 'columnconfigure', self.bodyInterior._w, X, '-minsize', W ) )
                        #self.bodyInterior.update()
            '''
            for X in range(x, x + columnspan*2, 2): # spanned cols divided equally over their columns
                w = int(cellW / columnspan)
                bodyColW = self.bodyInterior.tk.call( ('grid', 'columnconfigure', self.bodyInterior._w, X, '-minsize' ) )
                if cellW > bodyColW: # even (body) cells only
                    self.bodyInterior.tk.call( ('grid', 'columnconfigure', self.bodyInterior._w, X, '-minsize', w ) )
                    #self.bodyInterior.update()
            '''
        if isRowHdrCell:
            bodyRowH = self.bodyInterior.tk.call( ('grid', 'rowconfigure', self.bodyInterior._w, y, '-minsize' ) )
            if cellH > bodyRowH:
                self.bodyInterior.tk.call( ('grid', 'rowconfigure', self.bodyInterior._w, y, '-minsize', cellH ) )
                #self.bodyInterior.update()
        if isBodyCell:
            rowHdrH = self.rowHdrInterior.tk.call( ('grid', 'rowconfigure', self.rowHdrInterior._w, y, '-minsize' ) )
            if cellH > rowHdrH:
                self.rowHdrInterior.tk.call( ('grid', 'rowconfigure', self.rowHdrInterior._w, y, '-minsize', cellH ) )
                #self.rowHdrInterior.update()
            colHdrW = self.colHdrInterior.tk.call( ('grid', 'columnconfigure', self.colHdrInterior._w, x, '-minsize' ) )
            if cellW > colHdrW:
                self.colHdrInterior.tk.call( ('grid', 'columnconfigure', self.colHdrInterior._w, x, '-minsize', cellW ) )
                #self.colHdrInterior.update()
            elif colHdrW > cellW:
                self.bodyInterior.tk.call( ('grid', 'columnconfigure', self.bodyInterior._w, x, '-minsize', colHdrW ) )
                #self.bodyInterior.update()
    
    def conformHdrsToBody(self):
        self.colsConfigured = True
        # non-spanned cells
        
        '''
        for hdrCell in self.rowHdrInterior.children.values():
            hdrCellH = hdrCell.winfo_reqheight()
            y = hdrCell.y
            bodyColH = self.bodyInterior.tk.call( ('grid', 'rowconfigure', self.bodyInterior._w, y, '-minsize' ) )
            if hdrCellH > bodyColH:
                self.bodyInterior.tk.call( ('grid', 'rowconfigure', self.bodyInterior._w, y, '-minsize', hdrCellH ) )
        # set min width to body cells
        for bodyCell in self.bodyInterior.children.values():
            bodyCellW = bodyCell.winfo_reqwidth()
            bodyCellH = bodyCell.winfo_reqheight()
            x = bodyCell.x
            hdrColW = self.colHdrInterior.tk.call( ('grid', 'columnconfigure', self.colHdrInterior._w, x, '-minsize' ) )
            if bodyCellW > hdrColW:
                self.bodyInterior.tk.call( ('grid', 'columnconfigure', self.bodyInterior._w, x, '-minsize', bodyCellW ) )
            y = bodyCell.y
            rowColH = self.colHdrInterior.tk.call( ('grid', 'rowconfigure', self.rowHdrInterior._w, y, '-minsize' ) )
            if bodyCellH > rowColH:
                self.bodyInterior.tk.call( ('grid', 'rowconfigure', self.bodyInterior._w, y, '-minsize', bodyCellH ) )
        '''
        hdrCells = self.colHdrInterior.children
        hdrCellSortKeys = [] # sort by col span, column row in header
        for hdrCellId, hdrCell in hdrCells.items():
            if not hdrCell.x & 1:
                colspan = hdrCell.columnspan if hasattr(hdrCell,'columnspan') and hdrCell.columnspan else 1
                hdrCellSortKeys.append( (colspan, hdrCell.x, -hdrCell.y, hdrCellId) ) 
        hdrCellSortKeys.sort()
        for columnspan, x, y, hdrCellId in hdrCellSortKeys:
            hdrCell = hdrCells[hdrCellId]
            hdrCellW = hdrCell.winfo_reqwidth()
            w = int(hdrCellW / columnspan)
            wWiderAlloced = 0
            wNumWider = 0
            for X in range(x, x + columnspan*2, 2): # spanned cols divided equally over their columns
                bodyColW = self.bodyInterior.tk.call( ('grid', 'columnconfigure', self.bodyInterior._w, X, '-minsize' ) )
                if bodyColW > w: # even cells only
                    wWiderAlloced += bodyColW
                    wNumWider += 1
            if columnspan - wNumWider > 0 and hdrCellW > wWiderAlloced:
                W = int((hdrCellW - wWiderAlloced) / (columnspan - wNumWider))
                for X in range(x, x + columnspan*2, 2): # spanned cols divided equally over their columns
                    bodyColW = self.bodyInterior.tk.call( ('grid', 'columnconfigure', self.bodyInterior._w, X, '-minsize' ) )
                    if W > bodyColW: # even (body) cells only
                        self.bodyInterior.tk.call( ('grid', 'columnconfigure', self.bodyInterior._w, X, '-minsize', W ) )
                        #self.bodyInterior.update()
#self.colHdrInterior.update()
        #self.rowHdrInterior.update()
        #self.bodyInterior.update()
            