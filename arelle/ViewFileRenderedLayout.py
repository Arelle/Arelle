"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from datetime import timedelta
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from lxml import etree

from arelle import ViewFile
from arelle.FunctionXs import xsString
from arelle.ModelObject import ModelObject
from arelle.Aspect import Aspect, aspectStr
from arelle.rendering.RenderingLayout import layoutTable
from arelle import XbrlConst
from arelle.XmlUtil import elementFragmentIdentifier, addQnameValue

if TYPE_CHECKING:
    from arelle.FileSource import FileNamedStringIO
    from arelle.ModelRenderingObject import LytMdlTableModel
    from arelle.ModelXbrl import ModelXbrl
    from arelle.typing import TypeGetText

    _: TypeGetText


def viewRenderedLayout(
    modelXbrl: ModelXbrl,
    outfile: str | FileNamedStringIO | None,
    lang: str | None = None,
    viewTblELR: str | None = None,
    sourceView: Any = None,
    diffToFile: bool = False,
    cssExtras: str = "",
) -> None:
    modelXbrl.modelManager.showStatus(_("saving rendering"))
    view = ViewRenderedLayout(modelXbrl, outfile, lang, cssExtras)

    if sourceView is not None:
        if sourceView.lytMdlTblMdl:
            lytMdlTblMdl = sourceView.lytMdlTblMdl
        else:
            lytMdlTblMdl = layoutTable(sourceView)  # type: ignore[no-untyped-call]
    else:
        layoutTable(view)  # type: ignore[no-untyped-call]
        lytMdlTblMdl = view.lytMdlTblMdl
    if view.tblElt is not None: # may be None if there is no table
        view.view(lytMdlTblMdl)
    if diffToFile and outfile:
        from arelle.ValidateInfoset import validateRenderingInfoset
        validateRenderingInfoset(modelXbrl, outfile, view.xmlDoc)  # type: ignore[arg-type]
        view.close(noWrite=True)
    else:
        view.close()
    modelXbrl.modelManager.showStatus(_("rendering saved to {0}").format(outfile), clearAfter=5000)


class ViewRenderedLayout(ViewFile.View):
    lytMdlTblMdl: LytMdlTableModel

    def __init__(
        self,
        modelXbrl: ModelXbrl,
        outfile: str | FileNamedStringIO | None,
        lang: str | None,
        cssExtras: str,
    ) -> None:
        # find table model namespace based on table namespace
        self.tableModelNamespace = XbrlConst.tableModel
        for xsdNs in modelXbrl.namespaceDocs.keys():
            if xsdNs in (XbrlConst.tableMMDD, XbrlConst.table):
                self.tableModelNamespace = xsdNs + "/model"
                break
        super(ViewRenderedLayout, self).__init__(modelXbrl, outfile,
                                               f'tableModel xmlns="{self.tableModelNamespace}" xmlns:xbrli="http://www.xbrl.org/2003/instance"',
                                               lang,
                                               style="rendering",
                                               cssExtras=cssExtras)
        class nonTkBooleanVar():
            def __init__(self, value: bool = True) -> None:
                self.value = value
            def set(self, value: bool) -> None:
                self.value = value
            def get(self) -> bool:
                return self.value
        # context menu boolean vars (non-tkinter boolean
        self.ignoreDimValidity = nonTkBooleanVar(value=True)


    def tableModelQName(self, localName: str) -> str:
        return "{" + self.tableModelNamespace + "}" + localName

    def viewReloadDueToMenuAction(self, *args: Any) -> None:
        self.view()  # type: ignore[call-arg]

    def view(self, lytMdlTblMdl: LytMdlTableModel) -> None:
        assert self.tblElt is not None
        assert self.modelXbrl is not None

        self.tblElt.append(etree.Comment("Entry point file: {0}".format(lytMdlTblMdl.entryPointUrl)))

        for lytMdlTableSet in lytMdlTblMdl.lytMdlTableSets:
            tableSetElt = etree.SubElement(self.tblElt, self.tableModelQName("tableSet"))
            tableSetElt.append(etree.Comment(f"TableSet linkbase file: {lytMdlTableSet.srcFile}, line {lytMdlTableSet.srcLine}"))
            tableSetElt.append(etree.Comment(f"TableSet linkrole: {lytMdlTableSet.srcLinkrole}"))
            etree.SubElement(tableSetElt, self.tableModelQName("label")).text = lytMdlTableSet.label
            for lytMdlTable in lytMdlTableSet.lytMdlTables:
                tableElt = etree.SubElement(tableSetElt, self.tableModelQName("table"))
                for name, value in lytMdlTable.strctMdlTable.tblParamValues.items():
                    tableElt.append(etree.Comment(f' ${name} = "{value}" '))
                for lytMdlHeaders in lytMdlTable.lytMdlHeaders:
                    hdrsElt = etree.SubElement(tableElt, self.tableModelQName("headers"), attrib={"axis": lytMdlHeaders.axis})
                    for lytMdlGroup in lytMdlHeaders.lytMdlGroups:
                        groupElt = etree.SubElement(hdrsElt, self.tableModelQName("group"))
                        groupElt.append(etree.Comment(f"Breakdown node file: {lytMdlGroup.srcFile}, line {lytMdlGroup.srcLine}"))
                        if lytMdlGroup.label:
                            etree.SubElement(groupElt, self.tableModelQName("label")).text=lytMdlGroup.label
                        for lytMdlHeader in lytMdlGroup.lytMdlHeaders:
                            if all(lytMdlCell.isOpenAspectEntrySurrogate for lytMdlCell in lytMdlHeader.lytMdlCells):
                                continue # skip header with only open aspect entry surrogates
                            hdrElt = etree.SubElement(groupElt, self.tableModelQName("header"))
                            for lytMdlCell in lytMdlHeader.lytMdlCells:
                                if lytMdlCell.isOpenAspectEntrySurrogate:
                                    continue # strip all open aspect entry surrogates from layout model file
                                attrib: dict[str, str] = {}
                                if lytMdlCell.span > 1:
                                    attrib["span"] = str(lytMdlCell.span)
                                if lytMdlCell.rollup:
                                    attrib["rollup"] = "true"
                                cellElt = etree.SubElement(hdrElt, self.tableModelQName("cell"), attrib)
                                if lytMdlCell.id:
                                    cellElt.append(etree.Comment(f"Cell id {lytMdlCell.id}"))
                                for label, role, lang in lytMdlCell.labels:
                                    if role or lang:
                                        cellElt.append(etree.Comment(f"Label role: {role}, lang {lang}"))
                                    labelElt = etree.SubElement(cellElt, self.tableModelQName("label")).text = label
                                for lytMdlConstraint in lytMdlCell.lytMdlConstraints:
                                    constraintAttrib: dict[str, str] | None = None
                                    if lytMdlConstraint.tag:
                                        constraintAttrib = {"tag": lytMdlConstraint.tag}
                                    constraintElt = etree.SubElement(cellElt, self.tableModelQName("constraint"), constraintAttrib)
                                    etree.SubElement(constraintElt, self.tableModelQName("aspect")).text=aspectStr(lytMdlConstraint.aspect)  # type: ignore[arg-type]
                                    valueElt = etree.SubElement(constraintElt, self.tableModelQName("value"))
                                    aspect = lytMdlConstraint.aspect
                                    aspectValue = lytMdlConstraint.value
                                    if aspect == Aspect.PERIOD:
                                        if isinstance(aspectValue, ModelObject):
                                            for perElt in aspectValue.iterchildren():
                                                valueElt.append(deepcopy(perElt))
                                        elif isinstance(aspectValue, dict) and "periodType" in aspectValue:
                                            if aspectValue["periodType"] == "duration":
                                                aspectElt = etree.Element("{http://www.xbrl.org/2003/instance}startDate")
                                                aspectElt.text = f"{aspectValue['startDate'].strftime('%Y-%m-%dT%H:%M:%S.%f')}Z"
                                                valueElt.append(aspectElt)

                                                aspectElt = etree.Element("{http://www.xbrl.org/2003/instance}endDate")
                                                aspectElt.text = f"{(aspectValue['endDate'] + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S.%f')}Z"
                                                valueElt.append(aspectElt)
                                            elif aspectValue["periodType"] == "instant":
                                                aspectElt = etree.Element("{http://www.xbrl.org/2003/instance}instant")
                                                aspectElt.text = f"{(aspectValue['instant'] + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S.%f')}Z"
                                                valueElt.append(aspectElt)
                                            elif aspectValue["periodType"] == "forever":
                                                aspectElt = etree.Element("{http://www.xbrl.org/2003/instance}forever")
                                                valueElt.append(aspectElt)
                                    elif aspect == Aspect.ENTITY_IDENTIFIER:
                                        if isinstance(aspectValue, ModelObject):
                                            valueElt.append(deepcopy(aspectValue))
                                        elif isinstance(aspectValue, dict):
                                            aspectElt = etree.Element("{http://www.xbrl.org/2003/instance}identifier", {"scheme": aspectValue["scheme"]})
                                            aspectElt.text = str(aspectValue["identifier"])
                                            valueElt.append(aspectElt)
                                    elif aspect == Aspect.UNIT:
                                        aspectElt = etree.SubElement(valueElt, "{http://www.xbrl.org/2003/instance}unit")
                                        if isinstance(aspectValue, ModelObject):
                                            for unitElt in aspectValue.iterchildren():
                                                aspectElt.append(deepcopy(unitElt))
                                        elif isinstance(aspectValue, dict):
                                            for m in aspectValue["measures"]:
                                                etree.SubElement(aspectElt, "{http://www.xbrl.org/2003/instance}measure").text = str(m)
                                    else:
                                        if isinstance(aspectValue, ModelObject):
                                            valueElt.append(deepcopy(aspectValue))
                                        elif not (aspectValue is None and aspect in self.modelXbrl.qnameConcepts and self.modelXbrl.qnameConcepts[aspect].isExplicitDimension):
                                            # don't put None for value of explicit dimension which id defaulted
                                            valueElt.text = xsString(None, None, addQnameValue(self.xmlDoc, aspectValue))  # type: ignore[arg-type]
                for lytMdlZCell in lytMdlTable.lytMdlBodyChildren:
                    zCellsElt = etree.SubElement(tableElt, self.tableModelQName("cells"), attrib={"axis": "z"})
                    for lytMdlYCell in lytMdlZCell.lytMdlBodyChildren:  # type: ignore[union-attr]
                        yCellsElt = etree.SubElement(zCellsElt, self.tableModelQName("cells"), attrib={"axis": "y"})
                        for lytMdlXCell in lytMdlYCell.lytMdlBodyChildren:  # type: ignore[union-attr]
                            if not any(lytMdlCell.isOpenAspectEntrySurrogate for lytMdlCell in lytMdlXCell.lytMdlBodyChildren):  # type: ignore[union-attr]
                                xCellsElt = etree.SubElement(yCellsElt, self.tableModelQName("cells"), attrib={"axis": "x"})
                                for lytMdlCell in lytMdlXCell.lytMdlBodyChildren:  # type: ignore[union-attr,assignment]
                                    if lytMdlCell.isOpenAspectEntrySurrogate:
                                        continue
                                    cellElt = etree.SubElement(xCellsElt, self.tableModelQName("cell"))
                                    for f, v, justify in lytMdlCell.facts:  # type: ignore[attr-defined]
                                        cellElt.append(etree.Comment(
                                            f"{f.qname}: context {f.contextID}, value {v[:32]}, file {f.modelDocument.basename}, line {f.sourceline}"))
                                        if v is not None:
                                            etree.SubElement(cellElt, self.tableModelQName("fact")
                                                ).text = f"{f.modelDocument.basename}#{elementFragmentIdentifier(f)}"
