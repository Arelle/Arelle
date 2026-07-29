"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from arelle import ViewFile
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.FileSource import FileNamedStringIO
    from arelle.ModelXbrl import ModelXbrl

_: TypeGetText


def viewRoleTypes(
    modelXbrl: ModelXbrl | None,
    outfile: str | FileNamedStringIO | None,
    header: str,
    isArcrole: bool = False,
    lang: str | None = None,
) -> None:
    modelXbrl.modelManager.showStatus(_("viewing arcrole types") if isArcrole else _("viewing role types"))  # type: ignore[union-attr]
    view = ViewRoleTypes(modelXbrl, outfile, header, isArcrole, lang)
    view.view()
    view.close()


class ViewRoleTypes(ViewFile.View):
    def __init__(
        self,
        modelXbrl: ModelXbrl | None,
        outfile: str | FileNamedStringIO | None,
        header: str,
        isArcrole: bool,
        lang: str | None,
    ) -> None:
        super(ViewRoleTypes, self).__init__(modelXbrl, outfile, header, lang)
        self.isArcrole = isArcrole

    def view(self) -> None:
        # determine relationships indent depth for dimensions linkbases
        # set up treeView widget and tabbed pane
        if self.isArcrole:
            heading = ["Arcrole URI", "Definition", "Cycles Allowed", "Used On"]
            xmlRowElementName = "arcroleType"
        else:
            heading = ["Role URI", "Definition", "Used On"]
            xmlRowElementName = "roleType"
        self.addRow(heading, asHeader=True)  # must do after determining tree depth

        roletypes = self.modelXbrl.arcroleTypes if self.isArcrole else self.modelXbrl.roleTypes  # type: ignore[union-attr]
        for roleUri in sorted(roletypes.keys()):
            for modelRoleType in roletypes[roleUri]:
                attr = {"definedIn": modelRoleType.modelDocument.basename}
                cols: list[str] = [roleUri, modelRoleType.genLabel(lang=self.lang, strip=True) or modelRoleType.definition or ""]
                if self.isArcrole:
                    cols.append(modelRoleType.cyclesAllowed)  # type: ignore[arg-type]
                cols.append(", ".join(str(usedOn) for usedOn in modelRoleType.usedOns))

                self.addRow(cols, treeIndent=0, xmlRowElementName=xmlRowElementName, xmlRowEltAttr=attr)
