"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from arelle.Cntlr import Cntlr
from arelle.ModelValue import qname
from arelle.ModelXbrl import ModelXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginData import PluginData
from .Util import AUTHORITY_CODES

_: TypeGetText


@dataclass
class ESEFPluginData(PluginData):
    _esefAuthority: str | None = None
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
        self._esefAuthority = None
        self.esefInstanceValidated = False
        self.nonEsefInstanceExcluded = False


    def getEsefAuthority(
            self,
            modelXbrl: ModelXbrl,
            parameters: dict[Any, Any] | None,
    ) -> str | None:
        cntlr = modelXbrl.modelManager.cntlr
        esefAuthority = self._esefAuthority
        disclosureSystem = modelXbrl.modelManager.disclosureSystem
        if disclosureSystem is not None and disclosureSystem.authority is not None:
            esefAuthority = disclosureSystem.authority
        if not esefAuthority and cntlr.hasGui and cntlr.config is not None:
            esefAuthority = cntlr.config.get("esefAuthority") or None
        formulaAuthority = None
        if parameters:
            # formula parameter backwards compatibility for legacy users.
            p = parameters.get(qname("authority", noPrefixIsNoNamespace=True))
            if p and len(p) == 2 and p[1] not in ("null", "None", None):
                formulaAuthority = p[1]
        if esefAuthority and formulaAuthority and esefAuthority != formulaAuthority:
            modelXbrl.error(
                "Arelle.conflictingESEFAuthorityParameters",
                _(
                    "ESEF Authority '%(esefAuthority)s' conflicts with formula parameter authority '%(formulaAuthority)s'."
                    " Continuing with '%(esefAuthority)s'."
                ),
                modelObject=modelXbrl,
                esefAuthority=esefAuthority,
                formulaAuthority=formulaAuthority,
            )
        authority = esefAuthority or formulaAuthority
        if authority and authority not in AUTHORITY_CODES:
            modelXbrl.error(
                "Arelle.invalidESEFAuthority",
                _("Invalid authority '%(authority)s'. Valid values: %(validValues)s."),
                modelObject=modelXbrl,
                authority=authority,
                validValues=", ".join(sorted(AUTHORITY_CODES)),
            )
            return None
        return authority

    def setEsefAuthority(self, authority: str) -> None:
        self._esefAuthority = authority
