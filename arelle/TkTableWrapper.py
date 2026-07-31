# Copyright (c) 2008, Guilherme Polo
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""
This contains a wrapper class for the tktable widget as well a class for using
tcl arrays that are, in some instances, required by tktable.
"""
from __future__ import annotations

__author__ = "Guilherme Polo <ggpolo@gmail.com>"

__all__ = ["ArrayVar", "Table"]

import os
import platform
import sys
import tkinter
from tkinter import Variable, Widget, messagebox, Event, Menu, Tk
from pathlib import Path
from typing import TYPE_CHECKING, Any


from arelle.SystemInfo import PlatformOS
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from collections.abc import Iterable
    from tkinter import Misc

_: TypeGetText


def _setup_master(master: Misc | None) -> Misc:
    if master is None:
        if tkinter._support_default_root:  # type: ignore[attr-defined]
            master = tkinter._default_root or Tk()  # type: ignore[attr-defined]
        else:
            raise RuntimeError("No master specified and Tkinter is "
                               "configured to not support default master")
    return master


class ArrayVar(Variable):
    """Class for handling Tcl arrays.

    An array is actually an associative array in Tcl, so this class supports
    some dict operations.
    """

    def __init__(self, master: Misc | None = None, name: str | None = None) -> None:
        # Tkinter.Variable.__init__ is not called on purpose! I don't wanna
        # see an ugly _default value in the pretty array.
        self._master = _setup_master(master)
        self._tk = self._master.tk
        if name:
            self._name = name
        else:
            self._name = "PY_VAR%s" % id(self)

    def __del__(self) -> None:
        if bool(self._tk.call("info", "exists", self._name)):
            self._tk.globalunsetvar(self._name)  # type: ignore[no-untyped-call]

    def __len__(self) -> int:
        return int(self._tk.call("array", "size", str(self)))

    def __getitem__(self, key: Any) -> Any:
        return self.get(key)

    def __setitem__(self, key: Any, value: Any) -> None:
        self.set(**{str(key): value})

    def names(self) -> Any:
        return self._tk.call("array", "names", self._name)

    def get(self, key: Any = None) -> Any:
        if key is None:
            flatten_pairs = self._tk.call("array", "get", str(self))
            return dict(list(zip(flatten_pairs[::2], flatten_pairs[1::2])))

        return self._tk.globalgetvar(str(self), str(key))  # type: ignore[no-untyped-call]

    def set(self, **kw: Any) -> None:  # type: ignore[override]
        self._tk.call("array", "set", str(self), tkinter._flatten(list(kw.items())))  # type: ignore[attr-defined]

    def unset(self, pattern: str | None = None) -> None:
        """Unsets all of the elements in the array. If pattern is given, only
        the elements that match pattern are unset. """
        self._tk.call("array", "unset", str(self), pattern)


_TKTABLE_LOADED: bool = False


class Table(Widget):
    """Create and manipulate tables."""
    _w: str
    _switches: tuple[str, ...] = ("holddimensions", "holdselection", "holdtags", "holdwindows", "keeptitles", "-")
    _tabsubst_format: tuple[str, ...] = ("%c", "%C", "%i", "%r", "%s", "%S", "%W")
    _tabsubst_commands: tuple[str, ...] = ("browsecommand", "browsecmd", "command",
                          "selectioncommand", "selcmd",
                          "validatecommand", "valcmd")

    def __init__(self, master: Misc | None = None, **kw: Any) -> None:
        master = _setup_master(master)
        global _TKTABLE_LOADED
        if not _TKTABLE_LOADED:
            tktable_lib = os.environ.get("TKTABLE_LIBRARY")
            if not tktable_lib:
                plat = PlatformOS.getPlatformOS()
                machine = platform.machine()
                lib_dir = Path(__file__).parent / "resources" / "libs" / "TkTable"
                if plat == PlatformOS.MACOS:
                    if machine == "arm64":
                        lib_dir = lib_dir / "macos-arm64"
                    else:
                        lib_dir = lib_dir / "macos-x86_64"
                elif plat == PlatformOS.WINDOWS:
                    lib_dir = lib_dir / "win-x86_64"
                else:
                    lib_dir = lib_dir / "linux-x86_64"
                if lib_dir.exists():
                    tktable_lib = str(lib_dir)
            if tktable_lib:
                master.tk.eval("global auto_path; "
                               "lappend auto_path {%s}" % tktable_lib)
            try:
                master.tk.call("package", "require", "Tktable")
                _TKTABLE_LOADED = True
            except Exception as ex:
                messagebox.showerror(_("Exception"),
                    _("Unable to locate or to load Tktable.  \n\n"
                      "GUI functions requiring tables, such as TableLinkbase, are likely to be unusable. \n\n"
                      "Environment parameter TKTABLE_LIBRARY may be used to specify the location of Tktable. \n\n"
                      "Details: {}").format(ex))
        # force minimum padding
        if not "padx" in kw:
            kw["padx"] = 1
        if not "pady" in kw:
            kw["pady"] = 1
        if _TKTABLE_LOADED:
            Widget.__init__(self, master, "table", kw)
        self.contextMenuClick: str = "<Button-2>" if sys.platform == "darwin" else "<Button-3>"
        self.isInitialized: bool = _TKTABLE_LOADED

    def _options(self, cnf: Any, kw: Any = None) -> tuple[str, ...]:
        if kw:
            cnf = tkinter._cnfmerge((cnf, kw))  # type: ignore[attr-defined]
        else:
            cnf = tkinter._cnfmerge(cnf)  # type: ignore[attr-defined]

        res: tuple[str, ...] = ()
        for k, v in cnf.items():
            if callable(v):
                if k in self._tabsubst_commands:
                    v = "%s %s" % (self._register(v, self._tabsubst),  # type: ignore[attr-defined]
                                   " ".join(self._tabsubst_format))
                else:
                    v = self._register(v)  # type: ignore[attr-defined]
            res += ("-%s" % k, v)

        return res

    def _tabsubst(self, *args: Any) -> tuple[Event, ...]:
        if len(args) != len(self._tabsubst_format):
            return args

        tk = self.tk
        c, C, i, r, s, S, W = args
        e = Event()

        e.widget = self
        e.c = tk.getint(c)  # type: ignore[attr-defined]
        e.i = tk.getint(i)  # type: ignore[attr-defined]
        e.r = tk.getint(r)  # type: ignore[attr-defined]
        e.C = "%d,%d" % (e.r, e.c)  # type: ignore[attr-defined]
        e.s = s  # type: ignore[attr-defined]
        e.S = S  # type: ignore[attr-defined]
        try:
            e.W = self._nametowidget(W)  # type: ignore[attr-defined]
        except KeyError:
            e.W = None  # type: ignore[attr-defined]

        return (e,)

    def _handle_switches(self, args: Iterable[str] | None) -> tuple[str, ...]:
        args = args or ()
        return tuple(("-%s" % x) for x in args if x in self._switches)

    def activate(self, index: str | int) -> None:
        """Set the active cell to the one indicated by index."""
        self.tk.call(self._w, "activate", index)

    def bbox(self, first: str, last: str | None = None) -> tuple[tuple[str, str], ...]:  # type: ignore[override]
        """Return the bounding box for the specified cell (range) as a
        4-tuple of x, y, width and height in pixels. It clips the box to
        the visible portion, if any, otherwise an empty tuple is returned."""
        return self._getints(self.tk.call(self._w, "bbox", first, last)) or ()  # type: ignore[attr-defined]

    def clear(self, option: str, first: str | None = None, last: str | None = None) -> None:
        """This is a convenience routine to clear certain state information
        managed by the table. first and last represent valid table indices.
        If neither are specified, then the command operates on the whole
        table."""
        self.tk.call(self._w, "clear", option, first, last)

    def clear_cache(self, first: str | None = None, last: str | None = None) -> None:
        """Clear the specified section of the cache, if the table has been
        keeping one."""
        self.clear("cache", first, last)

    def clear_sizes(self, first: str | None = None, last: str | None = None) -> None:
        """Clear the specified row and column areas of specific height/width
        dimensions. When just one index is specified, for example 2,0, that
        is interpreted as row 2 and column 0."""
        self.clear("sizes", first, last)

    def clear_tags(self, first: str | None = None, last: str | None = None) -> None:
        """Clear the specified area of tags (all row, column and cell tags)."""
        self.clear("tags", first, last)

    def clear_all(self, first: str | None = None, last: str | None = None) -> None:
        """Perform all of the above clear functions on the specified area."""
        self.clear("all", first, last)

    def curselection(self, value: str | None = None) -> Any:
        """With no arguments, it returns the sorted indices of the currently
        selected cells. Otherwise it sets all the selected cells to the given
        value if there is an associated ArrayVar and the state is not
        disabled."""
        result = self.tk.call(self._w, "curselection", value)
        if value is None:
            return result
        return None

    def curvalue(self, value: str | None = None) -> Any:
        """If no value is given, the value of the cell being edited (indexed
        by active) is returned, else it is set to the given value. """
        return self.tk.call(self._w, "curvalue", value)

    def delete_active(self, index1: str | int | None, index2: str | int | None = None) -> None:
        """Deletes text from the active cell. If only one index is given,
        it deletes the character after that index, otherwise it deletes from
        the first index to the second. index can be a number, insert or end."""
        self.tk.call(self._w, "delete", "active", index1, index2)

    def delete_cols(self, index: str | int, count: int | None = None, switches: Iterable[str] | None = None) -> None:
        args = self._handle_switches(switches) + (index, count)
        self.tk.call(self._w, "delete", "cols", *args)

    def delete_rows(self, index: str | int, count: int | None = None, switches: Iterable[str] | None = None) -> None:
        args = self._handle_switches(switches) + (index, count)
        self.tk.call(self._w, "delete", "rows", *args)

    def get(self, first: str, last: str | None = None) -> Any:
        """Returns the value of the cells specified by the table indices
        first and (optionally) last."""
        return self.tk.call(self._w, "get", first, last)

    def height(self, row: int | None = None, **kwargs: Any) -> int | dict[str, str] | None:
        """If row and kwargs are not given, a list describing all rows for
        which a width has been set is returned.
        If row is given, the height of that row is returnd.
        If kwargs is given, then it sets the key/value pairs, where key is a
        row and value represents the height for the row."""
        if row is None and not kwargs:
            pairs = self.tk.splitlist(self.tk.call(self._w, "height"))
            return dict(pair.split() for pair in pairs)
        elif row:
            return int(self.tk.call(self._w, "height", str(row)))

        args = tkinter._flatten(list(kwargs.items()))  # type: ignore[attr-defined]
        self.tk.call(self._w, "height", *args)
        return None

    def hidden(self, *args: Any) -> int:
        """When called without args, it returns all the hidden cells (those
        cells covered by a spanning cell). If one index is specified, it
        returns the spanning cell covering that index, if any. If multiple
        indices are specified, it returns 1 if all indices are hidden cells,
        0 otherwise."""
        return self.tk.call(self._w, "hidden", *args)  # type: ignore[no-any-return]

    def icursor(self, arg: str | None = None) -> int:
        """If arg is not specified, return the location of the insertion
        cursor in the active cell. Otherwise, set the cursor to that point in
        the string.

        0 is before the first character, you can also use insert or end for
        the current insertion point or the end of the text. If there is no
        active cell, or the cell or table is disabled, this will return -1."""
        return self.tk.call(self._w, "icursor", arg)  # type: ignore[no-any-return]

    def index(self, index: str | int, rc: str | None = None) -> str | int:
        """Return the integer cell coordinate that corresponds to index in the
        form row, col. If rc is specified, it must be either 'row' or 'col' so
        only the row or column index is returned."""
        res = self.tk.call(self._w, "index", index, rc)
        if rc is None:
            return res  # type: ignore[no-any-return]
        else:
            return int(res)

    def insert_active(self, index: str | int, value: str) -> None:
        """The value is a text string which is inserted at the index postion
        of the active cell. The cursor is then positioned after the new text.
        index can be a number, insert or end. """
        self.tk.call(self._w, "insert", "active", index, value)

    def insert_cols(self, index: str | int, count: int | None = None, switches: Iterable[str] | None = None) -> None:
        args = self._handle_switches(switches) + (index, count)
        self.tk.call(self._w, "insert", "cols", *args)

    def insert_rows(self, index: str | int, count: int | None = None, switches: Iterable[str] | None = None) -> None:
        args = self._handle_switches(switches) + (index, count)
        self.tk.call(self._w, "insert", "rows", *args)

    def reread(self) -> None:
        """Rereads the old contents of the cell back into the editing buffer.
        Useful for a key binding when <Escape> is pressed to abort the edit
        (a default binding)."""
        self.tk.call(self._w, "reread")

    def scan_mark(self, x: int, y: int) -> None:
        self.tk.call(self._w, "scan", "mark", x, y)

    def scan_dragto(self, x: int, y: int) -> None:
        self.tk.call(self._w, "scan", "dragto", x, y)

    def see(self, index: str | int) -> None:
        self.tk.call(self._w, "see", index)

    def selection_anchor(self, index: str | int) -> None:
        self.tk.call(self._w, "selection", "anchor", index)

    def selection_clear(self, first: str, last: str | None = None) -> None:  # type: ignore[override]
        self.tk.call(self._w, "selection", "clear", first, last)

    def selection_includes(self, index: str | int) -> bool:
        return self.getboolean(self.tk.call(self._w, "selection", "includes", index))

    def selection_set(self, first: str, last: str | None = None) -> None:
        self.tk.call(self._w, "selection", "set", first, last)

    def set(self, rc: str | None = None, index: str | int | None = None, *args: Any, **kwargs: Any) -> Any:
        """If rc is specified (either 'row' or 'col') then it is assumes that
        args (if given) represents values which will be set into the
        subsequent columns (if row is specified) or rows (for col).
        If index is not None and args is not given, then it will return the
        value(s) for the cell(s) specified.

        If kwargs is given, assumes that each key in kwargs is a index in this
        table and sets the specified index to the associated value. Table
        validation will not be triggered via this method.

        Note that the table must have an associated array (defined through the
        variable option) in order to this work."""
        if not args and index is not None:
            call_args: tuple[str | int | None, ...]
            if rc:
                call_args = (rc, index)
            else:
                call_args = (index,)
            return self.tk.call(self._w, "set", *call_args)

        if rc is None:
            flat_args = tkinter._flatten(list(kwargs.items()))  # type: ignore[attr-defined]
            self.tk.call(self._w, "set", *flat_args)
        else:
            self.tk.call(self._w, "set", rc, index, args)
        return None

    def spans(self, index: str | int | None = None, **kwargs: Any) -> Any:
        """Manipulate row/col spans.

        When called with no arguments, all known spans are returned as a dict.
        When called with only the index, the span for that index only is
        returned, if any. Otherwise kwargs is assumed to contain keys/values
        pairs used to set spans. A span starts at the row,col defined by a key
        and continues for the specified number of rows,cols specified by
        its value. A span of 0,0 unsets any span on that cell."""
        if kwargs:
            args = tkinter._flatten(list(kwargs.items()))  # type: ignore[attr-defined]
            self.tk.call(self._w, "spans", *args)
            return None
        else:
            return self.tk.call(self._w, "spans", index)

    def tag_cell(self, tagname: str, *args: Any) -> Any:
        return self.tk.call(self._w, "tag", "cell", tagname, *args)

    def tag_cget(self, tagname: str, option: str) -> Any:
        return self.tk.call(self._w, "tag", "cget", tagname, "-%s" % option)

    def tag_col(self, tagname: str, *args: Any) -> Any:
        return self.tk.call(self._w, "tag", "col", tagname, *args)

    def tag_configure(self, tagname: str, option: str | None = None, **kwargs: Any) -> Any:
        """Query or modify options associated with the tag given by tagname.

        If no option is specified, a dict describing all of the available
        options for tagname is returned. If option is specified, then the
        command returns a list describing the one named option. Lastly, if
        kwargs is given then it corresponds to option-value pairs that should
        be modified."""
        if option is None and not kwargs:
            split1 = self.tk.splitlist(
                self.tk.call(self._w, "tag", "configure", tagname))

            result: dict[Any, Any] = {}
            for item in split1:
                res = self.tk.splitlist(item)
                result[res[0]] = res[1:]

            return result

        elif option:
            return self.tk.call(self._w, "tag", "configure", tagname, "-%s" % option)

        else:
            args: tuple[Any, ...] = ()
            for key, val in kwargs.items():
                args += ("-%s" % key, val)

            self.tk.call(self._w, "tag", "configure", tagname, *args)

    def tag_delete(self, tagname: str) -> None:
        self.tk.call(self._w, "tag", "delete", tagname)

    def tag_exists(self, tagname: str) -> bool:
        return self.getboolean(self.tk.call(self._w, "tag", "exists", tagname))

    def tag_includes(self, tagname: str, index: str | int) -> bool:
        return self.getboolean(self.tk.call(self._w, "tag", "includes", tagname, index))

    def tag_lower(self, tagname: str, belowthis: str | None = None) -> None:
        self.tk.call(self._w, "tag", "lower", belowthis)

    def tag_names(self, pattern: str | None = None) -> Any:
        return self.tk.call(self._w, "tag", "names", pattern)

    def tag_raise(self, tagname: str, abovethis: str | None = None) -> None:
        self.tk.call(self._w, "tag", "raise", tagname, abovethis)

    def tag_row(self, tagname: str, *args: Any) -> Any:
        return self.tk.call(self._w, "tag", "row", tagname, *args)

    def validate(self, index: str | int) -> int:
        """Explicitly validates the specified index based on the current
        callback set for the validatecommand option. Return 0 or 1 based on
        whether the cell was validated."""
        return self.tk.call(self._w, "validate", index)  # type: ignore[no-any-return]

    @property
    def version(self) -> Any:
        """Return tktable"s package version."""
        return self.tk.call(self._w, "version")

    def width(self, column: int | None = None, **kwargs: Any) -> int | dict[str, str] | None:
        """If column and kwargs are not given, a dict describing all columns
        for which a width has been set is returned.
        If column is given, the width of that column is returnd.
        If kwargs is given, then it sets the key/value pairs, where key is a
        column and value represents the width for the column."""
        if column is None and not kwargs:
            pairs = self.tk.splitlist(self.tk.call(self._w, "width"))
            return dict(pair.split() for pair in pairs)
        elif column is not None:
            return int(self.tk.call(self._w, "width", str(column)))

        args = tkinter._flatten(list(kwargs.items()))  # type: ignore[attr-defined]
        self.tk.call(self._w, "width", *args)
        return None

    def window_cget(self, index: str | int, option: str) -> Any:
        return self.tk.call(self._w, "window", "cget", index, option)

    def window_configure(self, index: str | int, option: str | None = None, **kwargs: Any) -> Any:
        """Query or modify options associated with the embedded window given
        by index. This should also be used to add a new embedded window into
        the table.

        If no option is specified, a dict describing all of the available
        options for index is returned. If option is specified, then the
        command returns a list describing the one named option. Lastly, if
        kwargs is given then it corresponds to option-value pairs that should
        be modified."""
        if option is None and not kwargs:
            return self.tk.call(self._w, "window", "configure", index)
        elif option:
            return self.tk.call(self._w, "window", "configure", index, "-%s" % option)
        else:
            args: tuple[Any, ...] = ()
            for key, val in kwargs.items():
                args += ("-%s" % key, val)

            self.tk.call(self._w, "window", "configure", index, *args)

    def window_delete(self, *indexes: str | int) -> None:
        self.tk.call(self._w, "window", "delete", *indexes)

    def window_move(self, index_from: str | int, index_to: str | int) -> None:
        self.tk.call(self._w, "window", "move", index_from, index_to)

    def window_names(self, pattern: str | None = None) -> Any:
        return self.tk.call(self._w, "window", "names", pattern)

    def xview(self, index: str | int | None = None) -> tuple[float, float] | None:
        """If index is not given a tuple containing two fractions is returned,
        each fraction is between 0 and 1. Together they describe the
        horizontal span that is visible in the window.

        If index is given the view in the window is adjusted so that the
        column given by index is displayed at the left edge of the window."""
        res = self.tk.call(self._w, "xview", index)
        if index is None:
            return self._getdoubles(res)  # type: ignore[attr-defined,no-any-return]
        return None

    def xview_moveto(self, fraction: float) -> None:
        """Adjusts the view in the window so that fraction of the total width
        of the table text is off-screen to the left. The fraction parameter
        must be a fraction between 0 and 1."""
        self.tk.call(self._w, "xview", "moveto", fraction)


    def xview_scroll(self, *L: str | int) -> None:
        # change by frank gao for attach scrollbar 11/11/2010
        """Shift the view in the window left or right according to number and
        what. The 'number' parameter must be an integer. The 'what' parameter
        must be either units or pages or an abbreviation of one of these.

        If 'what' is units, the view adjusts left or right by number cells on
        the display; if it is pages then the view adjusts by number screenfuls.
        If 'number' is negative then cells farther to the left become visible;
        if it is positive then cells farther to the right become visible. """
        op, howMany = L[0], L[1]
        if op == "scroll":
            units = L[2]
            self.tk.call(self._w, "xview", "scroll", howMany, units)
        elif op == "moveto":
            self.tk.call(self._w, "xview", "moveto", howMany)

    def yview(self, index: str | int | None = None) -> tuple[float, float] | None:
        """If index is not given a tuple containing two fractions is returned,
        each fraction is between 0 and 1. The first element gives the position
        of the table element at the top of the window, relative to the table
        as a whole. The second element gives the position of the table element
        just after the last one in the window, relative to the table as a
        whole.

        If index is given the view in the window is adjusted so that the
        row given by index is displayed at the top of the window."""
        res = self.tk.call(self._w, "yview", index)
        if index is None:
            return self._getdoubles(res)  # type: ignore[attr-defined,no-any-return]
        return None

    def yview_moveto(self, fraction: float) -> None:
        """Adjusts the view in the window so that the element given by
        fraction appears at the top of the window. The fraction parameter
        must be a fraction between 0 and 1."""
        self.tk.call(self._w, "yview", "moveto", fraction)

    def yview_scroll(self, *L: str | int) -> None:
        # change by frank gao for attach scrollbar 11/11/2010
        """Adjust the view in the window up or down according to number and
        what. The 'number' parameter must be an integer. The 'what' parameter
        must be either units or pages or an abbreviation of one of these.

        If 'what' is units, the view adjusts up or down by number cells; if it
        is pages then the view adjusts by number screenfuls.
        If 'number' is negative then earlier elements become visible; if it
        is positive then later elements become visible. """
        op, howMany = L[0], L[1]
        if op == "scroll":
            units = L[2]
            self.tk.call(self._w, "yview", "scroll", howMany, units)
        elif op == "moveto":
            self.tk.call(self._w, "yview", "moveto", howMany)

    def contextMenu(self) -> Menu:
        try:
            return self.menu
        except AttributeError:
            self.menu: Menu = Menu(self, tearoff=0)
            self.bind(self.contextMenuClick, self.popUpMenu)
            return self.menu

    def popUpMenu(self, event: Event) -> None:
        self.menu.post(event.x_root, event.y_root)

    def moveCell(self, y: int, x: int) -> None:
        self.tk.call("::tk::table::MoveCell", self._w, y, x)


# Sample test taken from tktable cvs, original tktable python wrapper, but heavily modified to fit the Arelle needs
def sample_test() -> None:
    from tkinter import Tk, Scrollbar, N, S, W, E, ttk, TclError
    import numpy

    def test_cmd(event: Event) -> Any:
        if event.i == 0:  # type: ignore[attr-defined]
            return arr[event.r, event.c]  # type: ignore[attr-defined]
        else:
            arr[event.r, event.c] = event.S  # type: ignore[attr-defined]
            return "set"

    def browsecmd(event: Event) -> None:
        print("event:", event.__dict__)
        print("curselection:", test.curselection())
        print("active cell index:", test.index("active"))
        activeRow = int(test.index("active", "row"))
        activeCol = int(test.index("active", "col"))
        print("active:", activeRow)
        print("anchor:", test.index("anchor", "row"))
        # the following line is operational, it shows that it is possible
        # to modiy programmatically the content of a cell.
        # var[test.index("active")] = "toto"

    def comboValueChanged(event: Event) -> None:
        combobox = event.widget
        print("Selected value in combobox: " + combobox.get())  # type: ignore[attr-defined]

    root = Tk()
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    numrows, numcols = 6250, 40

    #Using ArrayVar consumes double as much memory as NumPy+command
    #var = ArrayVar(root)
    #for y in range(0, numrows):
    #    for x in range(0, numcols):
    #        index = "%i,%i" % (y, x)
    #        var[index] = index
    arr = numpy.empty((numrows + 2, numcols), dtype=object)
    for y in range(numrows):
        for x in range(numcols):
            arr[y, x] = "%i,%i" % (y, x)

    test = Table(root,
                 rows=numrows,
                 cols=numcols,
                 state="normal",
                 width=6,
                 height=6,
                 titlerows=2,
                 titlecols=2,
                 roworigin=0,
                 colorigin=0,
                 selectmode="extended",
                 selecttype="cell",
                 rowstretch="last",
                 colstretch="last",
                 rowheight=-26,
                 colwidth=15,
                 browsecmd=browsecmd,
                 flashmode="off",
                 anchor="e",
                 #variable=var,
                 usecommand=1,
                 background="#fffffffff",
                 relief="sunken",
                 command=test_cmd,
                 takefocus=False,
                 rowseparator="\n"
                 # drawmode="slow"
                 )

    # http://effbot.org/zone/tkinter-scrollbar-patterns.htm
    verticalScrollbar = Scrollbar(root, orient="vertical", command=test.yview_scroll)
    horizontalScrollbar = Scrollbar(root, orient="horizontal", command=test.xview_scroll)
    test.configure(xscrollcommand=horizontalScrollbar.set, yscrollcommand=verticalScrollbar.set)  # type: ignore[call-arg]
    verticalScrollbar.grid(column=1, row=0, sticky=(N, S))
    horizontalScrollbar.grid(column=0, row=1, sticky=(W, E))

    kwargs = {"4,5": "5,3", "0,0": "0,1"}
    test.spans(index=None, **kwargs)
    for y in range(2, numrows):
        for x in range(2, numcols):
            if (x % 2 == 0 and y % 2 == 1) or (x % 2 == 1 and y % 2 == 0):
                index = "%i,%i" % (y, x)
                test.tag_cell("disabled", index)
    for x in range(2, numcols):
        index = "%i,%i" % (0, x)
        test.tag_cell("border", index)
        index = "%i,%i" % (1, x)
        test.tag_cell("border", index)
    for y in range(1, numrows):
        index = "%i,%i" % (y, 0)
        test.tag_cell("border-left-right", index)
        index = "%i,%i" % (y, 1)
        test.tag_cell("border", index)

    for y in range(2, numrows):
        cities = ("Brussels", "Luxembourg", "Strasbourg", "Trier", "Rome")
        combobox = ttk.Combobox(test, values=cities, state="readonly")
        test.window_configure("%i,9" % y, window=combobox, sticky=(N, E, S, W))
        combobox.bind(sequence="<<ComboboxSelected>>",
                      func=comboValueChanged,
                      add="+")

    def cellRight(event: Event, *args: Any) -> None:
        widget = event.widget
        titleRows = int(widget.cget("titlerows"))
        titleCols = int(widget.cget("titlecols"))
        top = int(widget.cget("roworigin")) + titleRows
        left = int(widget.cget("colorigin")) + titleCols
        try:
            col = int(widget.index("active", "col"))  # type: ignore[attr-defined]
            row = int(widget.index("active", "row"))  # type: ignore[attr-defined]
        except TclError:
            row, col = top - 1, left
        maxRows = int(widget.cget("rows"))
        maxCols = int(widget.cget("cols"))

        widget.selection_clear("all")  # type: ignore[call-arg]
        if row < top:
            if (col < left):
                index = "%i,%i" % (top, left)
            else:
                index = "%i,%i" % (top, col)
            widget.activate(index)  # type: ignore[attr-defined]
            widget.see(index)  # type: ignore[attr-defined]
            widget.selection_set(index)  # type: ignore[attr-defined]
        elif col < left:
            index = "%i,%i" % (row, left)
            widget.activate(index)  # type: ignore[attr-defined]
            widget.see(index)  # type: ignore[attr-defined]
            widget.selection_set(index)  # type: ignore[attr-defined]
        elif col < maxCols - titleCols - 1:
            widget.moveCell(0, 1)  # type: ignore[attr-defined]
        elif row < maxRows - titleCols - 1:
            widget.moveCell(1, left - col)  # type: ignore[attr-defined]
        else:
            widget.moveCell(top - row, left - col)  # type: ignore[attr-defined]

    def cellDown(event: Event, *args: Any) -> str:
        widget = event.widget
        titleRows = int(widget.cget("titlerows"))
        titleCols = int(widget.cget("titlecols"))
        top = int(widget.cget("roworigin")) + titleRows
        left = int(widget.cget("colorigin")) + titleCols
        try:
            col = int(widget.index("active", "col"))  # type: ignore[attr-defined]
            row = int(widget.index("active", "row"))  # type: ignore[attr-defined]
        except TclError:
            row, col = top - 1, left
        maxRows = int(widget.cget("rows"))
        maxCols = int(widget.cget("cols"))

        widget.selection_clear("all")  # type: ignore[call-arg]
        if row < top:
            if (col < left):
                index = "%i,%i" % (top, left)
            else:
                index = "%i,%i" % (top, col)
            widget.activate(index)  # type: ignore[attr-defined]
            widget.see(index)  # type: ignore[attr-defined]
            widget.selection_set(index)  # type: ignore[attr-defined]
        elif col < left:
            index = "%i,%i" % (row, left)
            widget.activate(index)  # type: ignore[attr-defined]
            widget.see(index)  # type: ignore[attr-defined]
            widget.selection_set(index)  # type: ignore[attr-defined]
        elif row < maxRows - titleRows - 1:
            widget.moveCell(1, 0)  # type: ignore[attr-defined]
        elif col < maxCols - titleCols - 1:
            widget.moveCell(top - row, 1)  # type: ignore[attr-defined]
        else:
            widget.moveCell(top - row, left - col)  # type: ignore[attr-defined]
        return "break"  # do not insert return in cell content

    menu = test.contextMenu()
    menu.add_command(label="Quit", underline=0, command=root.destroy)
    test.bind("<Tab>", func=cellRight, add="+")
    test.bind("<Return>", func=cellDown)
    test.tag_cell("border-left-top", "-2,-2")
    test.tag_raise("border-left-top", abovethis="title")
    test.tag_raise("border-left-right", abovethis="title")
    test.tag_raise("border", abovethis="title")
    test.grid(column=0, row=0, sticky=(N, W, S, E))
    test.tag_configure("sel", background="#000400400")
    test.tag_configure("active", background="#000a00a00")
    test.tag_configure("title", anchor="w", bg="#d00d00d00", fg="#000000000", relief="flat")
    test.tag_configure("disabled", bg="#d00d00d00", fg="#000000000", relief="flat", state="disabled")
    test.tag_configure("border-left-top", relief="ridge", borderwidth=(1, 0, 1, 0))
    test.tag_configure("border-left-right", relief="ridge", borderwidth=(1, 1, 0, 0))
    test.tag_configure("border", relief="ridge", borderwidth=(1, 1, 1, 1))

    data = ("py", "t", "h", "o", "n", "", "+", "", "Tk", "")

    def add_new_data(*args: Any) -> None:
        #test.config(state="normal")
        test.insert_rows("end", 1)
        r = test.index("end").split(",")[0]  # type: ignore[union-attr] # get row number <str>
        args = (r,) + args
        idx = r + ",1"
        test.set("row", idx, *args)
        test.see(idx)
        #test.config(state="disabled")

    root.after(3000, add_new_data, *data)
    root.after(4000, add_new_data, *data)
    root.mainloop()

if __name__ == "__main__":
    sample_test()
