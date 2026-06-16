'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

from collections.abc import Callable, Sequence
from tkinter import (
    E,
    HORIZONTAL,
    N,
    NW,
    S,
    VERTICAL,
    W,
    Canvas,
    Event,
    Frame,
    Misc,
    Scrollbar,
    StringVar,
)

from tkinter.ttk import (
    Checkbutton,
    Combobox as _Combobox,
    Entry,
    Label,
    Radiobutton,
    Separator,
)
from typing import Any

TOPBORDER = 1
LEFTBORDER = 2
RIGHTBORDER = 3
BOTTOMBORDER = 4
CENTERCELL = 5
borderImage = None


class gridBorder(Separator):
    def __init__(
        self,
        master: Misc,
        x: int,
        y: int,
        border: int,
        columnspan: int | None = None,
        rowspan: int | None = None,
    ) -> None:
        Separator.__init__(self, master=master)
        sticky: tuple[str, ...] = ()
        if border in (TOPBORDER, BOTTOMBORDER):
            x = x * 2 - 1
            if columnspan: columnspan = columnspan * 2 + 1
            else: columnspan = 3
            self.config(orient="horizontal")
            sticky = (E, W)
        if border in (LEFTBORDER, RIGHTBORDER):
            y = y * 2 - 1
            if rowspan: rowspan = rowspan * 2 + 1
            else: rowspan = 3
            self.config(orient="vertical")
            sticky = (N, S)
        if border == TOPBORDER:
            rowspan = None
            y = y * 2 - 1
            master.rowconfigure(y, weight=0, uniform="noStretch")
        elif border == BOTTOMBORDER:
            if rowspan:
                y = (y + rowspan - 1) * 2 + 1
                rowspan = None
            else:
                y = y * 2 + 1
            master.rowconfigure(y, weight=0, uniform="noStretch")
        elif border == LEFTBORDER:
            columnspan = None
            x = x * 2 - 1
            master.columnconfigure(x, weight=0, uniform="noStretch")
        elif border == RIGHTBORDER:
            if columnspan:
                x = (x + columnspan - 1) * 2 + 1
                columnspan = None
            else:
                x = x * 2 + 1
            master.columnconfigure(x, weight=0, uniform="noStretch")
        if columnspan and columnspan > 1 and rowspan and rowspan > 1:
            self.grid(column=x, row=y, sticky=sticky, columnspan=columnspan, rowspan=rowspan)
        elif columnspan and columnspan > 1:
            self.grid(column=x, row=y, sticky=sticky, columnspan=columnspan)
        elif rowspan and rowspan > 1:
            self.grid(column=x, row=y, sticky=sticky, rowspan=rowspan)
        else:
            self.grid(column=x, row=y, sticky=sticky)
        self.x: int = x
        self.y: int = y
        self.columnspan: int | None = columnspan
        self.rowspan: int | None = rowspan
        # copy bindings
        try:
            contextMenuClick = master.contextMenuClick  # type: ignore[attr-defined]
            contextMenuBinding = master.bind(contextMenuClick)
            if contextMenuBinding:
                self.bind(contextMenuClick, contextMenuBinding)
        except AttributeError:
            pass


class gridSpacer(Frame):
    def __init__(self, master: Misc, x: int, y: int, where: int) -> None:
        Frame.__init__(self, master=master)
        if where == CENTERCELL:
            offset = 0
        elif where in (TOPBORDER, LEFTBORDER):
            offset = -1
        else:
            offset = 1
        x = x * 2 + offset
        y = y * 2 + offset
        self.grid(column=x, row=y)  # same dimensions as separator in col/row headers
        self.x: int = x
        self.y: int = y
        self.config(width=2, height=2)  # need same default as Spacer, which is 2 pixels (shadow pixel and highlight pixel)
        if where in (TOPBORDER, BOTTOMBORDER):
            master.rowconfigure(y, weight=0, uniform="noStretch")
        elif where in (LEFTBORDER, RIGHTBORDER):
            master.columnconfigure(x, weight=0, uniform="noStretch")
        # copy bindings
        try:
            contextMenuClick = master.contextMenuClick  # type: ignore[attr-defined]
            contextMenuBinding = master.bind(contextMenuClick)
            if contextMenuBinding:
                self.bind(contextMenuClick, contextMenuBinding)
        except AttributeError:
            pass


class gridHdr(Label):
    def __init__(
        self,
        master: Misc,
        x: int,
        y: int,
        text: str | None,
        columnspan: int | None = None,
        rowspan: int | None = None,
        anchor: str = 'center',
        padding: Any = None,
        wraplength: int | None = None,
        width: int | None = None,
        minwidth: int | None = None,
        stretchCols: bool = True,
        stretchRows: bool = True,
        objectId: Any = None,
        onClick: Callable[[Event[Any]], object] | None = None,
    ) -> None:
        Label.__init__(self, master=master)
        if isinstance(master.master.master, scrolledHeaderedFrame):  # type: ignore[union-attr]
            x = x * 2
            y = y * 2
            if columnspan: columnspan = columnspan * 2 - 1
            if rowspan: rowspan = rowspan * 2 - 1
        self.config(  # type: ignore[call-overload]
            text=text if text is not None else "",
            width=width,
            anchor=anchor,
        )
        if padding:
            self.config(padding=padding)
        if wraplength:
            self.config(wraplength=wraplength)
        if columnspan and columnspan > 1 and rowspan and rowspan > 1:
            self.grid(column=x, row=y, sticky=(E, W, N, S), columnspan=columnspan, rowspan=rowspan)
        elif columnspan and columnspan > 1:
            self.grid(column=x, row=y, sticky=(E, W, N, S), columnspan=columnspan)
        elif rowspan and rowspan > 1:
            self.grid(column=x, row=y, sticky=(E, W, N, S), rowspan=rowspan)
        else:
            self.grid(column=x, row=y, sticky=(E, W, N, S))
        self.x: int = x
        self.y: int = y
        self.columnspan: int | None = columnspan
        self.rowspan: int | None = rowspan
        self.objectId = objectId

        if minwidth:
            master.columnconfigure(x, minsize=minwidth)

        if stretchCols:
            master.columnconfigure(x, weight=1)
        else:
            master.columnconfigure(x, weight=0, uniform="noStretch")
        if stretchRows:
            master.rowconfigure(y, weight=1)
        else:
            master.rowconfigure(y, weight=0, uniform="noStretch")
        # copy bindings
        try:
            contextMenuClick = master.contextMenuClick  # type: ignore[attr-defined]
            contextMenuBinding = master.bind(contextMenuClick)
            if contextMenuBinding:
                self.bind(contextMenuClick, contextMenuBinding)
        except AttributeError:
            pass
        if isinstance(master.master.master, scrolledHeaderedFrame):  # type: ignore[union-attr]
            self.bind("<Configure>", master.master.master._configure_cell)  # type: ignore[union-attr]
        if onClick:
            self.bind("<1>", onClick)


class gridCell(Entry):
    def __init__(
        self,
        master: Misc,
        x: int,
        y: int,
        value: str | None = "",
        width: int | None = None,
        justify: str | None = None,
        objectId: Any = None,
        onClick: Callable[[Event[Any]], object] | None = None,
    ) -> None:
        Entry.__init__(self, master=master)
        self.valueVar: StringVar = StringVar()
        self.valueVar.trace_add("write", self.valueChanged)
        self.config(  # type: ignore[call-overload]
            textvariable=self.valueVar,
            justify=justify,
            width=width,
        )
        if isinstance(master.master.master, scrolledHeaderedFrame):  # type: ignore[union-attr]
            x = x * 2
            y = y * 2
        self.grid(column=x, row=y, sticky=(N, S, E, W))
        self.x: int = x
        self.y: int = y
        if value is not None:
            self.valueVar.set(value)
        self.objectId = objectId
        # copy bindings
        try:
            contextMenuClick = master.contextMenuClick  # type: ignore[attr-defined]
            contextMenuBinding = master.bind(contextMenuClick)
            if contextMenuBinding:
                self.bind(contextMenuClick, contextMenuBinding)
        except AttributeError:
            pass
        if isinstance(master.master.master, scrolledHeaderedFrame):  # type: ignore[union-attr]
            self.bind("<Configure>", master.master.master._configure_cell)  # type: ignore[union-attr]
        if onClick:
            self.bind("<1>", onClick)
        self.isChanged: bool = False

    @property
    def value(self) -> str:
        return self.valueVar.get()

    def setValue(self, value: str) -> None:
        return self.valueVar.set(value)

    def valueChanged(self, *args: Any) -> None:
        self.isChanged = True


class gridCombobox(_Combobox):
    def __init__(
        self,
        master: Misc,
        x: int,
        y: int,
        value: str = "",
        values: Sequence[str] = (),
        width: int | None = None,
        objectId: Any = None,
        columnspan: int | None = None,
        selectindex: int | None = None,
        comboboxselected: Callable[[Event[Any]], object] | None = None,
        state: str | None = None,
        padx: int | str | None = None,
        attr: str | None = None,
    ) -> None:
        _Combobox.__init__(self, master=master)
        self.attr: str | None = attr
        self.valueVar: StringVar = StringVar()
        self.valueVar.trace_add("write", self.valueChanged)
        self.config(
            textvariable=self.valueVar,
            background="#ff8ff8ff8",
            foreground="#000000000",
            width=width,  # type: ignore[arg-type]
            state=state  # type: ignore[arg-type]
        )
        self["values"] = values
        if isinstance(master.master.master, scrolledHeaderedFrame):  # type: ignore[union-attr]
            x = x * 2
            y = y * 2
            if columnspan: columnspan = columnspan * 2 - 1
        if columnspan and columnspan > 1:
            self.grid(column=x, row=y, sticky=(E,W), columnspan=columnspan, padx=padx)  # type: ignore[arg-type]
        else:
            self.grid(column=x, row=y, sticky=(E,W), padx=padx)  # type: ignore[arg-type]
        if selectindex is not None:
            self.valueVar.set(values[selectindex])
        elif value:
            self.valueVar.set(value)
        elif attr:
            try:
                options = master.master.options  # type: ignore[union-attr]
                if attr in options:
                    self.valueVar.set(options[attr] or "")
            except AttributeError:
                pass
        self.objectId = objectId
        # copy bindings
        try:
            contextMenuClick = master.contextMenuClick  # type: ignore[attr-defined]
            contextMenuBinding = master.bind(contextMenuClick)
            if contextMenuBinding:
                self.bind(contextMenuClick, contextMenuBinding)
        except AttributeError:
            pass
        if comboboxselected:
            self.bind("<<ComboboxSelected>>", comboboxselected)
        self.isChanged = False

    @property
    def value(self) -> str:
        return self.valueVar.get()

    @property
    def valueIndex(self) -> int:
        value = self.valueVar.get()
        values = self["values"]
        if value in values:
            return list(values).index(value)
        return -1

    def valueChanged(self, *args: Any) -> None:
        self.isChanged = True


class label(Label):
    def __init__(self, master: Misc, x: int, y: int, text: str) -> None:
        Label.__init__(self, master=master, text=text)
        self.grid(column=x, row=y, sticky=W, padx=8)


class checkbox(Checkbutton):
    def __init__(
        self,
        master: Misc,
        x: int,
        y: int,
        text: str,
        attr: str | None = None,
        columnspan: int | None = None,
        onclick: Callable[[checkbox], object] | None = None,
    ) -> None:
        self.attr: str | None = attr
        self.onclick: Callable[[checkbox], object] | None = onclick
        self.valueVar: StringVar = StringVar()
        self.valueVar.trace_add("write", self.valueChanged)
        Checkbutton.__init__(self, master=master, text=text, variable=self.valueVar)
        self.grid(column=x, row=y, sticky=W, padx=24)
        if columnspan:
            self.grid(columnspan=columnspan)
        try:
            options = master.master.options  # type: ignore[union-attr]
            if attr in options:
                self.valueVar.set(options[attr])
        except AttributeError:
            pass
        self.isChanged = False

    @property
    def value(self) -> bool:
        return self.valueVar.get() == "1"

    def valueChanged(self, *args: Any) -> None:
        self.isChanged = True
        if self.onclick is not None:
            self.onclick(self)


class radiobutton(Radiobutton):
    def __init__(
        self,
        master: Misc,
        x: int,
        y: int,
        text: str,
        value: str,
        attr: str | None = None,
        valueVar: StringVar | None = None,
    ) -> None:
        self.attr: str | None = attr
        self.valueVar: StringVar = valueVar if valueVar else StringVar()
        Radiobutton.__init__(self, master=master, text=text, variable=self.valueVar, value=value)
        self.grid(column=x, row=y, sticky=W, padx=24)
        try:
            options = master.master.options  # type: ignore[union-attr]
            if attr in options:
                self.valueVar.set(options[attr])
        except AttributeError:
            pass

    @property
    def value(self) -> str:
        return self.valueVar.get()


class scrolledFrame(Frame):
    def __init__(self, parent: Misc, *args: Any, **kw: Any) -> None:
        Frame.__init__(self, parent, *args, **kw)

        vscrollbar = Scrollbar(self, orient=VERTICAL)
        hscrollbar = Scrollbar(self, orient=HORIZONTAL)
        self.canvas: Canvas = Canvas(
            self,
            bd=0,
            highlightthickness=0,
            yscrollcommand=vscrollbar.set,
            xscrollcommand=hscrollbar.set,
        )
        canvas = self.canvas
        self.grid(row=0, column=0, sticky=(N, S, E, W))
        canvas.grid(row=0, column=0, sticky=(N, S, E, W))
        vscrollbar.grid(row=0, column=1, sticky=(N, S))
        hscrollbar.grid(row=1, column=0, sticky=(E, W))
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

    def _configure_interior(self, event: Event[Any]) -> None:
        # update the scrollbars to match the size of the inner frame
        interiorW = self.interior.winfo_reqwidth()
        interiorH = self.interior.winfo_reqheight()
        self.canvas.config(scrollregion=(0, 0, interiorW, interiorH))
        ''' needed if scrolling only in 1 direction (for the axis that doesn't have scrollbar)
        if interiorW != self.canvas.winfo_width():
            # update the canvas's width to fit the inner frame
            self.canvas.config(width=interiorW)
        if interiorH != self.canvas.winfo_height():
            self.canvas.config(height=interiorH)
        '''

    def _configure_canvas(self, event: Event[Any]) -> None:
        ''' needed if only scrolling in one direction
        canvasW = self.canvas.winfo_width()
        if self.interior.winfo_reqwidth() != canvasW:
            # update the inner frame's width to fill the canvas
            self.canvas.itemconfigure(self.interior_id, width=canvasW)
        canvasH = self.canvas.winfo_height()
        if self.interior.winfo_reqheight() != canvasH:
            self.canvas.itemconfigure(self.interior_id, height=canvasH)
        '''

    def clearGrid(self) -> None:
        x, y = self.size()
        for widget in self.winfo_children():
            widget.destroy()
        if x > 1 and y > 1:  # not gridTblHdr
            for x in range(x):
                self.tk.call(('grid', 'columnconfigure', str(self), x, '-minsize', 0))
            for y in range(y):
                self.tk.call(('grid', 'rowconfigure', str(self), y, '-minsize', 0))
            self.config(width=1, height=1)
        self.update()
        self.colsConfigured = False


class scrolledHeaderedFrame(Frame):
    def __init__(self, parent: Misc, *args: Any, **kw: Any) -> None:
        Frame.__init__(self, parent, *args, **kw)

        self.colsConfigured = False
        self.bodyCellsConfigured = False
        self.blockConfigureCell = False
        self.hdrVscrollbar = Scrollbar(self, orient=VERTICAL)
        self.hdrHscrollbar = Scrollbar(self, orient=HORIZONTAL)
        self.bodyVscrollbar = Scrollbar(self, orient=VERTICAL)
        self.bodyHscrollbar = Scrollbar(self, orient=HORIZONTAL)
        self.colHdrCanvas = Canvas(
            self,
            bd=0,
            highlightthickness=0,
            yscrollcommand=self.hdrVscrollbar.set
        )
        self.rowHdrCanvas = Canvas(
            self,
            bd=0,
            highlightthickness=0,
            xscrollcommand=self.hdrHscrollbar.set
        )
        self.bodyCanvas = Canvas(
            self,
            bd=0,
            highlightthickness=0,
            yscrollcommand=self.bodyVscrollbar.set,
            xscrollcommand=self.bodyHscrollbar.set
        )
        self.grid(row=0, column=0, sticky=(N, S, E, W))
        self.tblHdrInterior = Frame(self)
        self.tblHdrInterior.grid(row=1, column=0, sticky=(N, S, E, W))
        self.colHdrCanvas.grid(row=1, column=1, sticky=(N, W, E))
        self.rowHdrCanvas.grid(row=2, column=0, sticky=(N, W, S))
        self.bodyCanvas.grid(row=2, column=1, sticky=(N, S, E, W))
        self.hdrVscrollbar.grid(row=1, column=2, sticky=(N, S))
        self.hdrHscrollbar.grid(row=3, column=0, sticky=(E, W))
        self.bodyVscrollbar.grid(row=2, column=2, sticky=(N, S))
        self.bodyHscrollbar.grid(row=3, column=1, sticky=(E, W))
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

    def _vscroll_body(self, *args: Any) -> None:
        self.rowHdrCanvas.yview(*args)
        self.bodyCanvas.yview(*args)

    def _hscroll_body(self, *args: Any) -> None:
        self.colHdrCanvas.xview(*args)
        self.bodyCanvas.xview(*args)

    def _mousewheel(self, event: Event[Any]) -> str:
        # on linux:  if (event.num == 4): delta = -1 elif (event.num == 5): delta = 1 else: delta = event.delta
        self.rowHdrCanvas.yview("scroll", event.delta, "units")
        self.bodyCanvas.yview("scroll", event.delta, "units")
        return "break"  # don't do default scrolling

    def clearGrid(self) -> None:
        self.colHdrCanvas.xview_moveto(0)
        self.colHdrCanvas.yview_moveto(0)
        self.rowHdrCanvas.xview_moveto(0)
        self.rowHdrCanvas.yview_moveto(0)
        self.bodyCanvas.xview_moveto(0)
        self.bodyCanvas.yview_moveto(0)
        for grid in (self.tblHdrInterior, self.colHdrInterior, self.rowHdrInterior, self.bodyInterior):
            x, y = grid.size()
            for widget in grid.winfo_children():
                widget.destroy()
            if x > 1 and y > 1:  # not gridTblHdr
                for x in range(x):
                    grid.tk.call(('grid', 'columnconfigure', grid._w, x, '-minsize', 0))  # type: ignore[attr-defined]
                for y in range(y):
                    grid.tk.call(('grid', 'rowconfigure', grid._w, y, '-minsize', 0))  # type: ignore[attr-defined]
                grid.config(width=1, height=1)
                grid.master.config(width=1, height=1, scrollregion=(0, 0, 1, 1))  # type: ignore[attr-defined]
        self.update()
        self.colsConfigured = False

    def _configure_colHdrInterior(self, event: Event[Any]) -> None:
        interiorW = self.colHdrInterior.winfo_reqwidth()
        interiorH = self.colHdrInterior.winfo_reqheight()
        raiseHeight = interiorH != self.colHdrCanvas.winfo_height()
        # tkinter bug, mac won't display col headers without setting height here and below
        # 1 pixel higher, not needed on PC/linux
        self.colHdrCanvas.config(height=interiorH, scrollregion=(0, 0, interiorW, interiorH))
        if raiseHeight:  # update the canvas's width to fit the inner frame
            self.colHdrCanvas.config(height=interiorH + 1)

    def _configure_rowHdrInterior(self, event: Event[Any]) -> None:
        interiorW = self.rowHdrInterior.winfo_reqwidth()
        interiorH = self.rowHdrInterior.winfo_reqheight()
        # width doesn't set wide enough when first expanding, force by setting wider before scroll region
        widenWidth = interiorW != self.rowHdrCanvas.winfo_width() and interiorW != 1  # 1 means nothing set yet
        # tkinter bug?  right side of row headers is clipped without setting it 1 pixel wider below
        # and then back on next configure event.  Would like to remove first config of width.
        # also: mac won't display at all without this trick
        self.rowHdrCanvas.config(width=interiorW, scrollregion=(0, 0, interiorW, interiorH))
        if widenWidth:  # update the canvas's width to fit the inner frame
            self.rowHdrCanvas.config(width=interiorW + 1)  # remove if tkinter issue gets solved

    def _configure_bodyInterior(self, event: Event[Any]) -> None:
        interiorW = self.bodyInterior.winfo_reqwidth()
        interiorH = self.bodyInterior.winfo_reqheight()
        self.bodyCanvas.config(scrollregion=(0, 0, interiorW, interiorH))

    def _configure_colHdrCanvas(self, event: Event[Any]) -> None:
        canvasH = self.colHdrCanvas.winfo_height()
        if self.colHdrInterior.winfo_reqheight() != canvasH:
            self.colHdrCanvas.itemconfigure(self.colHdrInterior_id, height=canvasH)

    def _configure_rowHdrCanvas(self, event: Event[Any]) -> None:
        canvasW = self.rowHdrCanvas.winfo_width()
        if self.rowHdrInterior.winfo_reqwidth() != canvasW:
            self.rowHdrCanvas.itemconfigure(self.rowHdrInterior_id, width=canvasW)
        # set table header wrap length
        tblHdr = self.tblHdrInterior
        if hasattr(tblHdr, "tblHdrLabel") and canvasW > tblHdr.tblHdrWraplength:  # type: ignore[attr-defined]
            tblHdr.tblHdrWraplength = canvasW - 4  # type: ignore[attr-defined]
            tblHdr.tblHdrLabel.config(wraplength=canvasW - 4)

    def _configure_bodyCanvas(self, event: Event[Any]) -> None:
        pass

    def _configure_interiors(self, event: Event[Any]) -> None:
        bodyW = self.bodyInterior.winfo_reqwidth()
        bodyH = self.bodyInterior.winfo_reqheight()
        colHdrW = self.colHdrInterior.winfo_reqwidth()
        colHdrH = self.colHdrInterior.winfo_reqheight()
        rowHdrW = self.rowHdrInterior.winfo_reqwidth()
        rowHdrH = self.rowHdrInterior.winfo_reqheight()
        bodyW = max(bodyW, colHdrW)
        bodyH = max(bodyH, rowHdrH)
        self.bodyCanvas.config(scrollregion=(0, 0, bodyW, bodyH))
        self.colHdrCanvas.config(scrollregion=(0, 0, bodyW, colHdrH))
        self.rowHdrCanvas.config(scrollregion=(0, 0, rowHdrW, bodyH))

    def _configure_canvases(self, event: Event[Any]) -> None:
        canvasH = self.colHdrCanvas.winfo_height()
        if self.colHdrInterior.winfo_reqheight() != canvasH:
            self.colHdrCanvas.itemconfigure(self.colHdrInterior_id, height=canvasH)
        canvasW = self.rowHdrCanvas.winfo_width()
        if self.rowHdrInterior.winfo_reqwidth() != canvasW:
            self.rowHdrCanvas.itemconfigure(self.rowHdrInterior_id, width=canvasW)

    def _configure_cell(self, event: Event[Any]) -> None:
        self.blockConfigureCell = True
        cell = event.widget
        x = cell.x
        y = cell.y
        cellW = cell.winfo_reqwidth()
        cellH = cell.winfo_reqheight()
        isColHdrCell = event.widget.master == self.colHdrInterior
        isRowHdrCell = event.widget.master == self.rowHdrInterior
        isBodyCell = event.widget.master == self.bodyInterior
        if isColHdrCell:
            if hasattr(cell, 'columnspan') and cell.columnspan:
                columnspan = cell.columnspan  # this is the non borders columns spanned
            else:
                columnspan = 1
            cellspan = ((columnspan + 1) // 2)
            w = int((cellW - ((columnspan - 1) / 2)) / cellspan)
            wWiderAlloced = 0
            wNumWider = 0
            for X in range(x, x + columnspan, 2):  # spanned cols divided equally over their columns
                bodyColW = self.bodyInterior.tk.call(('grid', 'columnconfigure', str(self.bodyInterior), X, '-minsize'))
                if bodyColW > w:
                    wWiderAlloced += bodyColW
                    wNumWider += 1
            if cellspan - wNumWider > 0 and cellW > wWiderAlloced:
                W = int((cellW - wWiderAlloced) / (cellspan - wNumWider))
                for X in range(x, x + columnspan, 2):  # spanned cols divided equally over their columns
                    bodyColW = self.bodyInterior.tk.call(('grid', 'columnconfigure', self.bodyInterior._w, X, '-minsize'))  # type: ignore[attr-defined]
                    if W > bodyColW:  # even cells only
                        self.bodyInterior.tk.call(('grid', 'columnconfigure', self.bodyInterior._w, X, '-minsize', W))  # type: ignore[attr-defined]
        if isRowHdrCell:
            rowspan = getattr(cell, 'rowspan', None) or 1
            bodyRowH = self.bodyInterior.tk.call(('grid', 'rowconfigure', self.bodyInterior._w, y, '-minsize'))  # type: ignore[attr-defined]
            cellHperRow = (cellH - (rowspan // 2 * 3)) / ((rowspan + 1) // 2)  # rowspan includes spanned separators
            if cellHperRow > bodyRowH:
                for ySpanned in range(y + rowspan - 1, y - 1, -2):
                    self.bodyInterior.tk.call(('grid', 'rowconfigure', self.bodyInterior._w, ySpanned, '-minsize', cellHperRow))  # type: ignore[attr-defined]
        if isBodyCell:
            rowHdrH = self.rowHdrInterior.tk.call(('grid', 'rowconfigure', self.rowHdrInterior._w, y, '-minsize'))  # type: ignore[attr-defined]
            if cellH > rowHdrH:
                self.rowHdrInterior.tk.call(('grid', 'rowconfigure', self.rowHdrInterior._w, y, '-minsize', cellH))  # type: ignore[attr-defined]
            colHdrW = self.colHdrInterior.tk.call(('grid', 'columnconfigure', self.colHdrInterior._w, x, '-minsize'))  # type: ignore[attr-defined]
            if cellW > colHdrW:
                self.colHdrInterior.tk.call(('grid', 'columnconfigure', self.colHdrInterior._w, x, '-minsize', cellW))  # type: ignore[attr-defined]
            elif colHdrW > cellW:
                self.bodyInterior.tk.call(('grid', 'columnconfigure', self.bodyInterior._w, x, '-minsize', colHdrW))  # type: ignore[attr-defined]
        self.blockConfigureCell = False

    def conformHdrsToBody(self) -> None:
        self.colsConfigured = True
        # non-spanned cells
        hdrCells = self.colHdrInterior.children
        hdrCellSortKeys: list[tuple[int, int, int, str]] = []  # sort by col span, column row in header
        for hdrCellId, hdrCell in hdrCells.items():
            if not hdrCell.x & 1:  # type: ignore[attr-defined]
                colspan = hdrCell.columnspan if hasattr(hdrCell, "columnspan") and hdrCell.columnspan else 1
                hdrCellSortKeys.append((colspan, hdrCell.x, -hdrCell.y, hdrCellId))  # type: ignore[attr-defined]
        hdrCellSortKeys.sort()
        for columnspan, x, y, hdrCellId in hdrCellSortKeys:
            hdrCell = hdrCells[hdrCellId]
            hdrCellW = hdrCell.winfo_reqwidth()
            w = int(hdrCellW / columnspan)
            wWiderAlloced = 0
            wNumWider = 0
            for X in range(x, x + columnspan * 2, 2):  # spanned cols divided equally over their columns
                bodyColW = self.bodyInterior.tk.call(('grid', 'columnconfigure', self.bodyInterior._w, X, '-minsize'))  # type: ignore[attr-defined]
                if bodyColW > w:  # even cells only
                    wWiderAlloced += bodyColW
                    wNumWider += 1
            if columnspan - wNumWider > 0 and hdrCellW > wWiderAlloced:
                W = int((hdrCellW - wWiderAlloced) / (columnspan - wNumWider))
                for X in range(x, x + columnspan * 2, 2):  # spanned cols divided equally over their columns
                    bodyColW = self.bodyInterior.tk.call(('grid', 'columnconfigure', self.bodyInterior._w, X, '-minsize'))  # type: ignore[attr-defined]
                    if W > bodyColW:  # even (body) cells only
                        self.bodyInterior.tk.call(('grid', 'columnconfigure', self.bodyInterior._w, X, '-minsize', W))  # type: ignore[attr-defined]

    def conformBodyCellsToHeader(self) -> None:
        self.bodyCellsConfigured = True

        for bodyCell in self.bodyInterior.children.values():
            if isinstance(bodyCell, gridSpacer):
                continue
            bodyCellW = bodyCell.winfo_reqwidth()
            bodyCellH = bodyCell.winfo_reqheight()
            x = bodyCell.x  # type: ignore[attr-defined]
            hdrColW = self.colHdrInterior.tk.call(('grid', 'columnconfigure', self.colHdrInterior._w, x, '-minsize'))  # type: ignore[attr-defined]
            if bodyCellW < hdrColW:
                self.bodyInterior.tk.call(('grid', 'columnconfigure', self.bodyInterior._w, x, '-minsize', hdrColW))  # type: ignore[attr-defined]
            y = bodyCell.y  # type: ignore[attr-defined]
            rowColH = self.colHdrInterior.tk.call(('grid', 'rowconfigure', self.rowHdrInterior._w, y, '-minsize'))  # type: ignore[attr-defined]
            if bodyCellH < rowColH:
                self.bodyInterior.tk.call(('grid', 'rowconfigure', self.bodyInterior._w, y, '-minsize', rowColH))  # type: ignore[attr-defined]
