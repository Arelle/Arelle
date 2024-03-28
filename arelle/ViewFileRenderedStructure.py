'''
See COPYRIGHT.md for copyright information.
'''
import os, io, json
from collections import OrderedDict
from arelle import ViewFile
from arelle.ModelObject import ModelObject
from arelle.Aspect import Aspect, aspectModels, aspectRuleAspects, aspectModelAspect, aspectStr
from arelle.ModelInstanceObject import ModelDimensionValue
from arelle.ModelRenderingObject import (StrctMdlNode, StrctMdlTable, StrctMdlBreakdown, StrctMdlStructuralNode,
                                         OPEN_ASPECT_ENTRY_SURROGATE, ROLLUP_SPECIFIES_MEMBER, ROLLUP_IMPLIES_DEFAULT_MEMBER,
                                         ROLLUP_FOR_CONCEPT_RELATIONSHIP_NODE, ROLLUP_FOR_DIMENSION_RELATIONSHIP_NODE,
                                         ROLLUP_FOR_CLOSED_DEFINITION_NODE, ROLLUP_FOR_OPEN_DEFINITION_NODE,
                                         ROLLUP_FOR_DEFINITION_NODE)
from arelle.rendering.RenderingResolution import resolveTableStructure
from arelle.rendering.RenderingLayout import layoutTable
from arelle.ModelValue import QName
from arelle import XbrlConst

def viewRenderedStructuralModel(modelXbrl, outfile, lang=None, viewTblELR=None, sourceView=None, cssExtras=""):
    modelXbrl.modelManager.showStatus(_("saving rendered structure"))
    view = ViewRenderedStructuralModel(modelXbrl, outfile, lang, cssExtras)
    view.view(outfile, viewTblELR)
    view.close(noWrite=True) # written out below
    modelXbrl.modelManager.showStatus(_("rendering table saved to {0}").format(outfile), clearAfter=5000)

class ViewRenderedStructuralModel(ViewFile.View):
    def __init__(self, modelXbrl, outfile, lang, cssExtras):
        # find table model namespace based on table namespace
        self.tableModelNamespace = XbrlConst.tableModel
        for xsdNs in modelXbrl.namespaceDocs.keys():
            if xsdNs in (XbrlConst.tableMMDD, XbrlConst.table):
                self.tableModelNamespace = xsdNs + "/model"
                break
        super(ViewRenderedStructuralModel, self).__init__(modelXbrl, outfile,
                                               'dummyObject',
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


    def tableModelQName(self, localName):
        return '{' + self.tableModelNamespace + '}' + localName

    def viewReloadDueToMenuAction(self, *args):
        self.view()

    def view(self, outfile, viewTblELR=None):
        if viewTblELR is not None:
            tblELRs = (viewTblELR,)
        else:
            tblELRs = self.modelXbrl.relationshipSet("Table-rendering").linkRoleUris

        for tblELR in tblELRs:
            self.zOrdinateChoices = {}

            strctMdlTable = resolveTableStructure(self, tblELR)

            # uncomment below for debugging Definition and Structural Models
            def jsonStrctMdlEncoder(obj, indent="\n"):
                if isinstance(obj, StrctMdlNode):
                    o = OrderedDict()
                    o["object"] = obj.__repr__()
                    if obj.xlinkLabel is not None:
                        o["defnMdlNode"] = f"{obj.defnMdlNode.modelXbrl.modelDocument.basename} line {obj.defnMdlNode.sourceline} {obj.xlinkLabel}"
                    if isinstance(obj, StrctMdlTable):
                        o["entryFile"] = obj.defnMdlNode.modelXbrl.modelDocument.basename,
                    if obj.axis:
                        o["axis"] = obj.axis
                    if obj.isAbstract:
                        o["abstract"] = True
                    if isinstance(obj, StrctMdlStructuralNode):
                        if obj.hasChildRollup:
                            o["hasChildRollup"] = True
                        if obj.rollup:
                            o["rollup"] = {ROLLUP_SPECIFIES_MEMBER:"rollup specifies member",
                                           ROLLUP_IMPLIES_DEFAULT_MEMBER:"rollup implies default member",
                                           ROLLUP_FOR_CONCEPT_RELATIONSHIP_NODE:"rollup for concept relationship nesting",
                                           ROLLUP_FOR_DIMENSION_RELATIONSHIP_NODE:"rollup for concept relationship nesting",
                                           ROLLUP_FOR_CLOSED_DEFINITION_NODE:"rollup for closed definition node",
                                           ROLLUP_FOR_OPEN_DEFINITION_NODE:"rollup for open definition node",
                                           ROLLUP_FOR_DEFINITION_NODE:"rollup for definition node"}[obj.rollup]
                        o["structuralDepth"] = obj.structuralDepth
                        _aspectsCovered = obj.aspectsCovered()
                        if _aspectsCovered:
                            o["aspectsCovered"] = OrderedDict((aspectStr(a),
                                                               str(v.stringValue if isinstance(v,ModelObject) else v
                                                                   ).replace(OPEN_ASPECT_ENTRY_SURROGATE, "OPEN_ASPECT_ENTRY_"))
                                                              for a in _aspectsCovered
                                                              if a != Aspect.DIMENSIONS
                                                              for v in (obj.aspectValue(a),))
                    if obj.tagSelector:
                        o["tagSelector"] = obj.tagSelector
                    if obj.strctMdlChildNodes:
                        o["strctMdlChildNodes"] = obj.strctMdlChildNodes
                    return o
                raise TypeError("Type {} is not supported for json output".format(type(obj).__name__))
            with io.open(outfile, 'wt') as fh:
                json.dump(strctMdlTable, fh, ensure_ascii=False, indent=2, default=jsonStrctMdlEncoder)
