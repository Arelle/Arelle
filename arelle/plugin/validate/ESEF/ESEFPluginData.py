"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass

from arelle.Cntlr import Cntlr
from arelle.utils.PluginData import PluginData


@dataclass
class ESEFPluginData(PluginData):
    esefAuthority: str | None = None
    esefInstanceValidated: bool = False
    nonEsefInstanceExcluded: bool = False

    @staticmethod
    def get(cntlr: Cntlr, name: str) -> ESEFPluginData:
        pluginData = cntlr.getPluginData(name)
        if pluginData is None:
            pluginData = ESEFPluginData(name)
            cntlr.setPluginData(pluginData)
        elif not isinstance(pluginData, ESEFPluginData):
            raise RuntimeError(f"PluginData already set for {pluginData.name} with unexpected type {type(pluginData)}.")
        return pluginData

    def reset(self) -> None:
        self.esefAuthority = None
        self.esefInstanceValidated = False
        self.nonEsefInstanceExcluded = False
