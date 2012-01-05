'''
Created on Oct 5, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle import ViewFile, XbrlConst
from collections import defaultdict

def viewConcepts(modelXbrl, outFile, lang=None):
    modelXbrl.modelManager.showStatus(_("viewing concepts"))
    view = ViewConcepts(modelXbrl, outFile, lang)
    view.addRow(["Label","Name","ID","Abs&#173;tract","Substi&#173;tu&#173;tion Group","Type","Facets"], asHeader=True)
    view.view(modelXbrl.modelDocument)
    view.close()
    
class ViewConcepts(ViewFile.View):
    def __init__(self, modelXbrl, outFile, lang):
        super().__init__(modelXbrl, outFile, "concepts", lang)
        
    def view(self, modelDocument):
        # sort by labels
        lbls = defaultdict(list)
        for concept in self.modelXbrl.qnameConcepts.values():
            lbls[concept.label(lang=self.lang)].append(concept.objectId())
        srtLbls = sorted(lbls)
        for label in srtLbls:
            for objectId in lbls[label]:
                concept = self.modelXbrl.modelObject(objectId)
                if concept.modelDocument.targetNamespace not in (
                         XbrlConst.xbrli, XbrlConst.link, XbrlConst.xlink, XbrlConst.xl,
                         XbrlConst.xbrldt):
                    self.addRow([concept.label(lang=self.lang),
                                 concept.name,
                                 concept.id,
                                 concept.abstract,
                                 concept.substitutionGroupQname,
                                 concept.typeQname,
                                 # facets if any, sorted and separated by ;
                                 " ".join("{0}={1}".format(
                                       name,
                                       sorted(value) if isinstance(value,set) else value
                                       ) for name,value in sorted(concept.type.facets.items())) \
                                       if concept.type is not None and concept.type.facets else ''
                                ])
