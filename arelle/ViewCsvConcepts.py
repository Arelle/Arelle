'''
Created on Oct 5, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle import (ViewCsv, XbrlConst)
from collections import defaultdict

def viewConcepts(modelXbrl, csvfile, lang=None):
    modelXbrl.modelManager.showStatus(_("viewing concepts"))
    view = ViewConcepts(modelXbrl, csvfile, lang)
    view.write(["Label","Name","ID","Abstract","Substitution Group","Type","Facets"])
    view.view(modelXbrl.modelDocument)
    view.close()
    
class ViewConcepts(ViewCsv.View):
    def __init__(self, modelXbrl, csvfile, lang):
        super().__init__(modelXbrl, csvfile, "Concepts", lang)
        
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
                    self.write([concept.label(lang=self.lang),
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
                                       if concept.type and concept.type.facets else ''
                                ])
