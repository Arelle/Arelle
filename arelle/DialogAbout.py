'''
See COPYRIGHT.md for copyright information.
'''
from tkinter import Toplevel, PhotoImage, N, S, E, W, EW, NW
try:
    from tkinter.ttk import Label, Button, Frame
except ImportError:
    from ttk import Label, Button, Frame
try:
    from regex import match as re_match
except ImportError:
    from re import match as re_match
'''
caller checks accepted, if True, caller retrieves url
'''
def about(parent, title, imageFile, body):
    dialog = DialogAbout(parent, title, imageFile, body)
    return None


class DialogAbout(Toplevel):
    def __init__(self, parent, title, imageFile, body):
        super(DialogAbout, self).__init__(parent)
        self.parent = parent
        parentGeometry = re_match("(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", parent.geometry())
        dialogX = int(parentGeometry.group(3))
        dialogY = int(parentGeometry.group(4))
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

    def ok(self, event=None):
        self.close()

    def close(self, event=None):
        self.parent.focus_set()
        self.destroy()
