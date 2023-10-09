'''
Created on Sep 13, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import os
from datetime import timedelta
from collections import OrderedDict
from copy import deepcopy
from lxml import etree
from arelle import ViewFile
from arelle.FormulaEvaluator import aspectMatches
from arelle.FunctionXs import xsString
from arelle.ModelObject import ModelObject
from arelle.ModelFormulaObject import Aspect, aspectModels, aspectRuleAspects, aspectModelAspect, aspectStr
from arelle.ModelInstanceObject import ModelDimensionValue
from arelle.PrototypeInstanceObject import FactPrototype
from arelle.PythonUtil import OrderedSet
from arelle.ModelRenderingObject import (StrctMdlBreakdown, StrctMdlStructuralNode,
                                         DefnMdlClosedDefinitionNode, DefnMdlRuleDefinitionNode, DefnMdlAspectNode,
                                         OPEN_ASPECT_ENTRY_SURROGATE, ROLLUP_SPECIFIES_MEMBER, ROLLUP_FOR_DIMENSION_RELATIONSHIP_NODE,
                                         aspectStrctNodes)
from arelle.RenderingResolution import resolveTableStructure, RENDER_UNITS_PER_CHAR
from arelle.ModelValue import QName
from arelle.ModelXbrl import DEFAULT
from arelle.ViewFile import HTML, XML
# change tableModel for namespace needed for consistency suite
'''
from arelle.XbrlConst import (tableModelMMDD as tableModelNamespace,
                              tableModelMMDDQName as tableModelQName)
'''
from arelle import XbrlConst
from arelle.XmlUtil import innerTextList, child, elementFragmentIdentifier, addQnameValue
from collections import defaultdict

emptySet = set()
emptyList = []

headerOmittedRollupAspects  = {
    Aspect.CONCEPT,
    Aspect.COMPLETE_SEGMENT, Aspect.COMPLETE_SCENARIO, Aspect.NON_XDT_SEGMENT, Aspect.NON_XDT_SCENARIO,
    Aspect.VALUE, Aspect.SCHEME,
    Aspect.PERIOD_TYPE, Aspect.START, Aspect.END, Aspect.INSTANT,
    Aspect.UNIT_MEASURES, Aspect.MULTIPLY_BY, Aspect.DIVIDE_BY}


def viewRenderedGrid(modelXbrl, outfile, lang=None, viewTblELR=None, sourceView=None, diffToFile=False, cssExtras=""):
    modelXbrl.modelManager.showStatus(_("saving rendered tagle"))
    view = ViewRenderedGrid(modelXbrl, outfile, lang, cssExtras)

    if sourceView is not None:
        if sourceView.lytMdlTblMdl:
            lytMdlTblMdl = sourceView.lytMdlTblMdl
        else:
            lytMdlTblMdl = layoutTable(sourceView)
    else:
        layoutTable(view)
        lytMdlTblMdl = view.lytMdlTblMdl
    if view.tblElt is not None: # may be None if there is no table
        view.view(lytMdlTblMdl)
    view.close()
    modelXbrl.modelManager.showStatus(_("rendered table saved to {0}").format(outfile), clearAfter=5000)

class ViewRenderedGrid(ViewFile.View):
    def __init__(self, modelXbrl, outfile, lang, cssExtras):
        # find table model namespace based on table namespace
        self.tableModelNamespace = XbrlConst.tableModel
        for xsdNs in modelXbrl.namespaceDocs.keys():
            if xsdNs in (XbrlConst.tableMMDD, XbrlConst.table):
                self.tableModelNamespace = xsdNs + "/model"
                break
        super(ViewRenderedGrid, self).__init__(modelXbrl, outfile,
                                               'tableModel',
                                               lang,
                                               style="rendering",
                                               cssExtras=cssExtras)
        class nonTkBooleanVar():
            def __init__(self, value=True):
                self.value = value
            def set(self, value):
                self.value = value
            def get(self):
                return self.value
        # context menu boolean vars (non-tkinter boolean
        self.ignoreDimValidity = nonTkBooleanVar(value=True)
        self.openBreakdownLines = 0 # layout model conformance suite requires no open entry lines
    def viewReloadDueToMenuAction(self, *args):
        self.view()

    def view(self, lytMdlTblMdl):
        
        for lytMdlTableSet in lytMdlTblMdl.lytMdlTableSets:
            self.tblElt.append(etree.Comment(f"TableSet linkbase file: {lytMdlTableSet.srcFile}, line {lytMdlTableSet.srcLine}"))
            self.tblElt.append(etree.Comment(f"TableSet linkrole: {lytMdlTableSet.srcLinkrole}"))
            tblSetHdr = etree.SubElement(self.tblElt, "{http://www.w3.org/1999/xhtml}tr")
            etree.SubElement(tblSetHdr, "{http://www.w3.org/1999/xhtml}td").text = lytMdlTableSet.label
            for lytMdlTable in lytMdlTableSet.lytMdlTables:
                # each Z is a separate table in the outer table
                zTableRow = etree.SubElement(self.tblElt, "{http://www.w3.org/1999/xhtml}tr")
                zRowCell = etree.SubElement(zTableRow, "{http://www.w3.org/1999/xhtml}td")
                zCellTable = etree.SubElement(zRowCell, "{http://www.w3.org/1999/xhtml}table",
                                              attrib={"border":"1", "cellspacing":"0", "cellpadding":"4", "style":"font-size:8pt;"})
                lytMdlXHdrs = lytMdlTable.lytMdlAxisHeaders("x")
                lytMdlYHdrs = lytMdlTable.lytMdlAxisHeaders("y")
                nbrXcolHdrs = sum(lytMdlHeader.maxNumLabels
                                  for lytMdlGroup in lytMdlXHdrs.lytMdlGroups
                                  for lytMdlHeader in lytMdlGroup.lytMdlHeaders
                                  if not all(lytMdlCell.isOpenAspectEntrySurrogate for lytMdlCell in lytMdlHeader.lytMdlCells))
                nbrYrowHdrs = sum(lytMdlHeader.maxNumLabels
                                  for lytMdlGroup in lytMdlYHdrs.lytMdlGroups
                                  for lytMdlHeader in lytMdlGroup.lytMdlHeaders)
                # build y row headers
                numYrows = max((sum(lytMdlCell.span
                                   for ytMdlYHdr in lytMdlYGrp.lytMdlHeaders
                                   for lytMdlCell in ytMdlYHdr.lytMdlCells)
                                for lytMdlYGrp in lytMdlYHdrs.lytMdlGroups))
                yRowHdrs = [[] for i in range(numYrows)] # list of list of row header elements for each row
                for lytMdlYGrp in lytMdlYHdrs.lytMdlGroups:
                    for lytMdlYHdr in lytMdlYGrp.lytMdlHeaders:
                        yRow = 0
                        if all(lytMdlCell.isOpenAspectEntrySurrogate for lytMdlCell in lytMdlYHdr.lytMdlCells):
                            continue # skip header with only open aspect entry surrogate
                        for lytMdlYCell in lytMdlYHdr.lytMdlCells:
                            for iLabel in range(lytMdlYHdr.maxNumLabels):
                                if lytMdlYCell.isOpenAspectEntrySurrogate:
                                    continue # strip all open aspect entry surrogates from layout model file
                                attrib = {"style":"max-width:100em;"}
                                if lytMdlYCell.rollup:
                                    attrib["class"] = "yAxisTopSpanLeg"
                                else:
                                    attrib["class"] = "yAxisHdr"
                                if lytMdlYCell.span > 1:
                                    attrib["rowspan"] = str(lytMdlYCell.span)
                                rowHdrElt = etree.Element("{http://www.w3.org/1999/xhtml}th", attrib=attrib)
                                rowHdrElt.text = lytMdlYCell.labelXmlText(iLabel,"\u00a0")
                                yRowHdrs[yRow].append(rowHdrElt)
                            yRow += lytMdlYCell.span
                firstColHdr = True
                for lytMdlGroup in lytMdlXHdrs.lytMdlGroups:
                    for lytMdlHeader in lytMdlGroup.lytMdlHeaders:
                        if all(lytMdlCell.isOpenAspectEntrySurrogate for lytMdlCell in lytMdlHeader.lytMdlCells):
                            continue # skip header with only open aspect entry surrogate
                        for iLabel in range(lytMdlHeader.maxNumLabels):
                            rowElt = etree.SubElement(zCellTable, "{http://www.w3.org/1999/xhtml}tr")
                            if firstColHdr:
                                etree.SubElement(rowElt, "{http://www.w3.org/1999/xhtml}th",
                                                 attrib={"class":"tableHdr",
                                                         "style":"max-width:100em;",
                                                         "colspan": str(nbrYrowHdrs),
                                                         "rowspan": str(nbrXcolHdrs)}
                                                 ).text = lytMdlTableSet.label
                                firstColHdr = False
                            for lytMdlCell in lytMdlHeader.lytMdlCells:
                                if lytMdlCell.isOpenAspectEntrySurrogate:
                                    continue # strip all open aspect entry surrogates from layout model file
                                attrib = {"style":"max-width:100em;"}
                                if lytMdlCell.rollup:
                                    attrib["class"] = "xAxisSpanLeg"
                                else:
                                    attrib["class"] = "xAxisHdr"
                                if lytMdlCell.span > 1:
                                    attrib["colspan"] = str(lytMdlCell.span)
                                etree.SubElement(rowElt, "{http://www.w3.org/1999/xhtml}th", attrib=attrib
                                                 ).text = lytMdlCell.labelXmlText(iLabel,"\u00a0")
                yRowNum = 0
                for lytMdlZCell in lytMdlTable.lytMdlBodyChildren:
                    for lytMdlYCell in lytMdlZCell.lytMdlBodyChildren:
                        for lytMdlXCell in lytMdlYCell.lytMdlBodyChildren:
                            if not any(lytMdlCell.isOpenAspectEntrySurrogate for lytMdlCell in lytMdlXCell.lytMdlBodyChildren):
                                rowElt = etree.SubElement(zCellTable, "{http://www.w3.org/1999/xhtml}tr")
                                if yRowNum < len(yRowHdrs):
                                    for rowHdrElt in yRowHdrs[yRowNum]:
                                        rowElt.append(rowHdrElt)
                                for lytMdlCell in lytMdlXCell.lytMdlBodyChildren:
                                    justify = "left"
                                    for f, v, justify in lytMdlCell.facts:
                                        break;
                                    colElt = etree.SubElement(rowElt, "{http://www.w3.org/1999/xhtml}td",
                                                              attrib={"class":"cell",
                                                                      "style":f"text-align:{justify};width:8em;"}
                                                     ).text = "\n".join(v for f, v, justify in lytMdlCell.facts)
                                yRowNum += 1
       