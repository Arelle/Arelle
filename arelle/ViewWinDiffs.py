'''
See COPYRIGHT.md for copyright information.
'''
from collections import defaultdict
import os
from tkinter import *
try:
    from tkinter.ttk import *
except ImportError:
    from ttk import *
from arelle.ViewWinRelationshipSet import viewRelationshipSet
from arelle.ViewWinConcepts import viewConcepts
from arelle import ModelVersObject, XbrlConst

class ViewWinDiffs:
    def __init__(self, modelVersReport, tabWin, lang=None):
        self.modelVersReport = modelVersReport
        #check for both from and to DTS
        versReport = modelVersReport.modelDocument
        if not hasattr(versReport, "xmlDocument") or not hasattr(versReport, "fromDTS") or not hasattr(versReport, "toDTS"):
            return
        self.fromDTS = versReport.fromDTS
        self.toDTS = versReport.toDTS

        self.tabWin = tabWin
        width = int( self.tabWin.winfo_width() / 2 )
        self.paneWin = PanedWindow(tabWin, orient=HORIZONTAL)
        self.paneWin.grid(row=1, column=0, sticky=(N, S, E, W))
        tabWin.add(self.paneWin,text="DTSes")
        tabWin.select(self.paneWin)
        self.tabWinBtmLf = Notebook(self.paneWin, width=width)
        self.tabWinBtmLf.grid(row=0, column=0, sticky=(N, S, E, W))
        self.paneWin.add(self.tabWinBtmLf)
        self.tabWinBtmRt = Notebook(self.paneWin, width=width)
        self.tabWinBtmRt.grid(row=0, column=0, sticky=(N, S, E, W))
        self.paneWin.add(self.tabWinBtmRt)
        viewRelationshipSet(self.fromDTS, self.tabWinBtmLf,
                            XbrlConst.parentChild, lang=lang,
                            treeColHdr=_("From DTS Presentation"))
        viewRelationshipSet(self.fromDTS, self.tabWinBtmLf,
                            XbrlConst.summationItem, lang=lang,
                            treeColHdr=_("From DTS Calculation"))
        viewRelationshipSet(self.fromDTS, self.tabWinBtmLf,
                            "XBRL-dimensions", lang=lang,
                            treeColHdr=_("From DTS Dimension"))
        viewConcepts(self.fromDTS, self.tabWinBtmLf, "From Concepts", lang=lang)
        viewRelationshipSet(self.toDTS, self.tabWinBtmRt,
                            XbrlConst.parentChild, lang=lang,
                            treeColHdr=_("To DTS Presentation"))
        viewRelationshipSet(self.toDTS, self.tabWinBtmRt,
                            XbrlConst.summationItem, lang=lang,
                            treeColHdr=_("To DTS Calculation"))
        viewRelationshipSet(self.toDTS, self.tabWinBtmRt,
                            "XBRL-dimensions", lang=lang,
                            treeColHdr=_("To DTS Dimension"))
        viewConcepts(self.toDTS, self.tabWinBtmRt, "To Concepts", lang=lang)

        modelVersReport.views.append(self)
        self.fromDTS.views.append(self)
        self.toDTS.views.append(self)

        self.blockViewModelObject = 0


    def close(self):
        if self in self.fromDTS.views:
            self.fromDTS.views.remove(self)
        if self in self.toDTS.views:
            self.toDTS.views.remove(self)
        self.fromDTS.close()
        self.toDTS.close()
        self.tabWin.forget(self.paneWin)
        self.modelVersReport.views.remove(self)
        self.modelVersReport = None

    def viewModelObject(self, modelObject):
        if self.blockViewModelObject == 0:
            try:
                self.blockViewModelObject += 1  # prevent recursion
                if isinstance(modelObject, ModelVersObject.ModelConceptChange):
                    fromConcept = modelObject.fromConcept
                    if fromConcept is not None:
                        self.fromDTS.viewModelObject(fromConcept.objectId())
                    toConcept = modelObject.toConcept
                    if toConcept is not None:
                        self.toDTS.viewModelObject(toConcept.objectId())
                elif isinstance(modelObject, ModelVersObject.ModelRelationships):
                    if modelObject.isFromDTS:
                        self.fromDTS.viewModelObject(modelObject.fromRelationship.objectId())
                    else:
                        self.toDTS.viewModelObject(modelObject.fromRelationship.objectId())
                elif isinstance(modelObject, (ModelVersObject.ModelInstanceAspect, ModelVersObject.ModelInstanceMemberAspect)):
                    if modelObject.isFromDTS:
                        self.fromDTS.viewModelObject(modelObject.sourceDtsObject.objectId())
                    else:
                        self.toDTS.viewModelObject(modelObject.sourceDtsObject.objectId())
                elif modelObject.modelXbrl != self.modelVersReport:  # propogate event to versiong report's modelXbrl
                    self.modelVersReport.viewModelObject(modelObject)
            except Exception:
                pass
            self.blockViewModelObject -= 1  # unblock
