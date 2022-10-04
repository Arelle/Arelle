'''
See COPYRIGHT.md for copyright information.
'''
from arelle import ViewFile, XbrlConst
from collections import defaultdict

def viewConcepts(modelXbrl, outFile, labelrole=None, lang=None):
    modelXbrl.modelManager.showStatus(_("viewing concepts"))
    view = ViewConcepts(modelXbrl, outFile, labelrole, lang)
    view.view(modelXbrl.modelDocument)
    view.close()

COL_WIDTHS = {
    "Label": 60,
    "Name": 60,
    "ID": 40,
    "Namespace": 60,
    "Abstract": 8,
    "Substitution Group": 12,
    "Type": 32,
    "Period Type": 16,
    "Balance": 16,
    "Nillable": 5,
    "Typed Domain Ref": 20,
    "Facets": 60,
    "Documentation": 100
    }

class ViewConcepts(ViewFile.View):
    def __init__(self, modelXbrl, outFile, labelrole, lang):
        super(ViewConcepts, self).__init__(modelXbrl, outFile, "concepts", lang)
        self.labelrole = labelrole

    def view(self, modelDocument):
        # check for optional attributes nillable and typedDomainRef usage
        hasTypedDomainRef = False
        hasDifferentNillables = False
        priorNillable = None
        excludedNamespaces = XbrlConst.ixbrlAll.union(
            (XbrlConst.xbrli, XbrlConst.link, XbrlConst.xlink, XbrlConst.xl,
             XbrlConst.xbrldt,
             XbrlConst.xhtml))
        # sort by labels
        lbls = defaultdict(list)
        for concept in set(self.modelXbrl.qnameConcepts.values()): # may be twice if unqualified (with and without namespace)
            lbls[concept.label(preferredLabel=self.labelrole, lang=self.lang)].append(concept.objectId())
            if concept.modelDocument.targetNamespace not in excludedNamespaces:
                if not hasTypedDomainRef and concept.typedDomainRef:
                    hasTypedDomainRef = True
                if priorNillable is None:
                    priorNillable = concept.nillable
                elif not hasDifferentNillables and concept.nillable != priorNillable:
                    hasDifferentNillables = True
        # header
        headings = ["Label","Name","ID","Namespace","Abs\u00ADtract","Substi\u00ADtu\u00ADtion Group","Type","Per\u00ADiod Type", "Bal\u00ADance"]
        if hasDifferentNillables:
            headings.append("Nillable")
        if hasTypedDomainRef:
            headings.append("Typed Domain Ref")
        headings.append("Facets")
        headings.append("Doc\u00ADu\u00ADmen\u00ADta\u00ADtion")
        self.setColWidths([COL_WIDTHS.get(hdg.replace('\u00AD',''), 8) for hdg in headings])
        self.addRow(headings, asHeader=True)
        srtLbls = sorted(lbls)
        for label in srtLbls:
            for objectId in lbls[label]:
                concept = self.modelXbrl.modelObject(objectId)
                if concept.modelDocument.targetNamespace not in (
                         XbrlConst.xbrli, XbrlConst.link, XbrlConst.xlink, XbrlConst.xl,
                         XbrlConst.xbrldt):
                    cols = [concept.label(preferredLabel=self.labelrole, lang=self.lang, strip=True, linkroleHint=XbrlConst.defaultLinkRole),
                            concept.name,
                            concept.id,
                            concept.qname.namespaceURI,
                            concept.abstract,
                            concept.substitutionGroupQname,
                            concept.typeQname,
                            concept.periodType,
                            concept.balance]
                    if hasDifferentNillables:
                        cols.append(concept.nillable)
                    if hasTypedDomainRef:
                        cols.append(concept.typedDomainRef or '')
                    if concept.type is not None and concept.type.facets:
                        # facets if any, sorted and separated by ;
                        cols.append(" ".join("{0}={1}".format(
                                       name,
                                       sorted(value.keys()) if isinstance(value,dict) else value
                                       ) for name,value in sorted(concept.type.facets.items())))
                    else:
                        cols.append("")
                    cols.append(concept.label(preferredLabel=XbrlConst.documentationLabel, fallbackToQname=False, lang=self.lang, strip=True, linkroleHint=XbrlConst.defaultLinkRole))
                    self.addRow(cols)
