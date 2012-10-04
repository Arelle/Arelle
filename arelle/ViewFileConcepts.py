'''
Created on Oct 5, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle import ViewFile, XbrlConst
from collections import defaultdict

def viewConcepts(modelXbrl, outFile, labelrole=None, lang=None):
    modelXbrl.modelManager.showStatus(_("viewing concepts"))
    view = ViewConcepts(modelXbrl, outFile, labelrole, lang)
    view.view(modelXbrl.modelDocument)
    view.close()
    
class ViewConcepts(ViewFile.View):
    def __init__(self, modelXbrl, outFile, labelrole, lang):
        super(ViewConcepts, self).__init__(modelXbrl, outFile, "concepts", lang)
        self.labelrole = labelrole
        
    def view(self, modelDocument):
        # header
        self.addRow(["Label","Name","ID","Abs\u00ADtract","Substi\u00ADtu\u00ADtion Group","Type","Facets","Doc\u00ADu\u00ADmen\u00ADta\u00ADtion"], asHeader=True)
        # sort by labels
        lbls = defaultdict(list)
        for concept in self.modelXbrl.qnameConcepts.values():
            lbls[concept.label(preferredLabel=self.labelrole, lang=self.lang)].append(concept.objectId())
        srtLbls = sorted(lbls)
        for label in srtLbls:
            for objectId in lbls[label]:
                concept = self.modelXbrl.modelObject(objectId)
                if concept.modelDocument.targetNamespace not in (
                         XbrlConst.xbrli, XbrlConst.link, XbrlConst.xlink, XbrlConst.xl,
                         XbrlConst.xbrldt):
                    self.addRow([concept.label(preferredLabel=self.labelrole, lang=self.lang, strip=True, linkroleHint=XbrlConst.defaultLinkRole),
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
                                       if concept.type is not None and concept.type.facets else '',
                                 concept.label(preferredLabel=XbrlConst.documentationLabel, fallbackToQname=False, lang=self.lang, strip=True, linkroleHint=XbrlConst.defaultLinkRole)
                                ])
