"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from tkinter import Toplevel, PhotoImage, N, S, E, W, EW, NW, Event
from tkinter.ttk import Label, Button, Frame
from typing import TYPE_CHECKING, Any

from regex import match as re_match

from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from tkinter import Tk

_: TypeGetText


"""
caller checks accepted, if True, caller retrieves url
"""
def about(parent: Tk | Toplevel, title: str, imageFile: str, body: str) -> None:
    dialog = DialogAbout(parent, title, imageFile, body)
    return None


class DialogAbout(Toplevel):
    def __init__(self, parent: Tk | Toplevel, title: str, imageFile: str, body: str) -> None:
        super(DialogAbout, self).__init__(parent)
        self.parent = parent
        parentGeometry = re_match(r"(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", parent.geometry())
        dialogX = int(parentGeometry.group(3))  # type: ignore[union-attr]
        dialogY = int(parentGeometry.group(4))  # type: ignore[union-attr]
        self.transient(self.parent)
        self.title(title)

        frame = Frame(self)
        image = PhotoImage(file=imageFile)
        aboutImage = Label(frame, image=image)
        aboutBody = Label(frame, text=body, wraplength=500)
        okButton = Button(frame, text=_("OK"), command=self.ok)
        okButton.focus_set()
        aboutImage.grid(row=0, column=0, sticky=NW, pady=20, padx=16)
        aboutBody.grid(row=0, column=1, columnspan=2, sticky=EW, pady=3, padx=0)
        okButton.grid(row=1, column=2, sticky=EW, pady=3)

        frame.grid(row=0, column=0, sticky=(N,S,E,W))
        frame.columnconfigure(1, weight=1)
        window = self.winfo_toplevel()
        window.columnconfigure(0, weight=1)
        self.geometry("+{0}+{1}".format(dialogX+200,dialogY+200))

        self.bind("<Alt-u>", lambda *ignore: okButton.focus_set())
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.close)

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.grab_set()
        self.wait_window(self)

    def ok(self, event: Event[Any] | None = None) -> None:
        self.close()

    def close(self, event: Event[Any] | None = None) -> None:
        self.parent.focus_set()
        self.destroy()
