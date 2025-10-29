"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from arelle import PluginManager

if TYPE_CHECKING:
    from arelle.Cntlr import Cntlr
    from arelle.FileSource import FileSource


class ValidateFileSource:
    def __init__(self, cntrl: Cntlr, filesource: FileSource):
        self._cntrl = cntrl
        self._filesource = filesource

    def validate(self) -> None:
        for pluginXbrlMethod in PluginManager.pluginClassMethods("Validate.FileSource"):
            pluginXbrlMethod(self._cntrl, self._filesource)
