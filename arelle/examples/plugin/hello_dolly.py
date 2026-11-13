"""
Hello dolly is a simple "Hello world" to demonstrate how plug-ins
are written for Arelle

See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from optparse import OptionParser
from random import randint
from tkinter import Menu
from typing import Any

from arelle.CntlrCmdLine import CntlrCmdLine
from arelle.CntlrWinMain import CntlrWinMain
from arelle.RuntimeOptions import RuntimeOptions
from arelle.typing import TypeGetText
from arelle.Version import copyrightLabel

_: TypeGetText


LYRICS =  ["I said hello, dolly,......well, hello, dolly",
            "It's so nice to have you back where you belong ",
            "You're lookin' swell, dolly.......i can tell, dolly ",
            "You're still glowin'...you're still crowin'...you're still goin' strong ",
            "I feel that room swayin'......while the band's playin' ",
            "One of your old favourite songs from way back when ",
            "So..... take her wrap, fellas.......find her an empty lap, fellas ",
            "Dolly'll never go away again"]


def randomLyric() -> str:
    """ A random lyrics."""
    return LYRICS[randint(0, len(LYRICS) - 1)]


def helloMenuEntender(cntlr: CntlrWinMain, menu: Menu, *args: Any, **kwargs: Any) -> None:
    menu.add_command(label="Hello Dolly", underline=0, command=lambda: helloMenuCommand(cntlr, "Hello Dolly") )


def helloMenuCommand(cntlr: CntlrWinMain, label: str) -> None:
    hello_dolly = randomLyric()
    cntlr.addToLog(hello_dolly)
    from tkinter import messagebox
    messagebox.showinfo(label, hello_dolly, parent=cntlr.parent)


def helloCommandLineOptionExtender(parser: OptionParser, *args: Any, **kwargs: Any) -> None:
    parser.add_option("--hello_dolly",
                      action="store_true",
                      dest="hello_dolly",
                      help=_('Print a random lyric from "Hello, Dolly"'))


def helloCommandLineUtilityRun(cntlr: CntlrCmdLine, options: RuntimeOptions, **kwargs: Any) -> None:
    if getattr(options, "hello_dolly", False):
        hello_dolly = randomLyric()
        try:
            cntlr.addToLog("[info] " + hello_dolly)
        except:
            print(hello_dolly)


__pluginInfo__ = {
    "name": "Hello Dolly",
    "version": "0.9",
    "description": "This is not just a plug-in, it symbolizes the hope and enthusiasm "
                    "of an entire generation summed up in two words sung most famously "
                    "by Louis Armstrong: Hello, Dolly. When activated you will randomly "
                    "see a lyric from Hello, Dolly.",
    "license": "Apache-2",
    "author": "R\xe9gis D\xce9camps",
    "copyright": copyrightLabel,
    # classes of mount points (required)
    "CntlrWinMain.Menu.Tools": helloMenuEntender,
    "CntlrCmdLine.Options": helloCommandLineOptionExtender,
    "CntlrCmdLine.Utility.Run": helloCommandLineUtilityRun,
}
