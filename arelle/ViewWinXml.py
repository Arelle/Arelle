"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import io
from tkinter import END
from tkinter.ttk import Notebook
from typing import TYPE_CHECKING

from lxml import etree

from arelle import XmlUtil, ViewWinList
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.ModelXbrl import ModelXbrl

_: TypeGetText


def viewXml(modelXbrl: ModelXbrl, tabWin: Notebook, tabTitle: str, xmlDoc: etree._ElementTree | etree._Element) -> None:
    modelXbrl.modelManager.showStatus(_("viewing xml"))
    view = ViewXml(modelXbrl, tabWin, tabTitle)
    view.view(xmlDoc)
    menu = view.contextMenu()
    view.menuAddSaveClipboard()
    menu.add_command(label=_("Validate"), underline=0, command=view.validate)

class ViewXml(ViewWinList.ViewList):
    def __init__(self, modelXbrl: ModelXbrl, tabWin: Notebook, tabTitle: str) -> None:
        super(ViewXml, self).__init__(modelXbrl, tabWin, tabTitle, True)

    def view(self, xmlDoc: etree._ElementTree | etree._Element) -> None:
        fh = io.StringIO()
        XmlUtil.writexml(fh, xmlDoc, encoding="utf-8")
        for line in fh.getvalue().split("\n"):
            self.listBox.insert(END, line)
        fh.close()

    def validate(self) -> None:
        try:
            from arelle import Validate
            Validate.validate(self.modelXbrl)  # type: ignore[arg-type]
        except Exception as err:
            self.modelXbrl.exception("exception", _(r"Validation exception: \s%(error)s"), error=err, exc_info=True)  # type: ignore[arg-type,union-attr]
