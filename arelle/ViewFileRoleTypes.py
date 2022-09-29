'''
See COPYRIGHT.md for copyright information.
'''
from arelle import ModelObject, ModelDtsObject, XbrlConst, XmlUtil, ViewFile
from arelle.ModelDtsObject import ModelRelationship
from arelle.ViewUtil import viewReferences
import os

def viewRoleTypes(modelXbrl, outfile, header, isArcrole=False, lang=None):
    modelXbrl.modelManager.showStatus(_("viewing arcrole types") if isArcrole else _("viewing role types"))
    view = ViewRoleTypes(modelXbrl, outfile, header, isArcrole, lang)
    view.view()
    view.close()

class ViewRoleTypes(ViewFile.View):
    def __init__(self, modelXbrl, outfile, header, isArcrole, lang):
        super(ViewRoleTypes, self).__init__(modelXbrl, outfile, header, lang)
        self.isArcrole = isArcrole

    def view(self):
        # determine relationships indent depth for dimensions linkbases
        # set up treeView widget and tabbed pane
        if self.isArcrole:
            heading = ["Arcrole URI", "Definition", "Cycles Allowed", "Used On"]
            xmlRowElementName = "arcroleType"
            uriAttr = "arcroleURI"
        else:
            heading = ["Role URI", "Definition", "Used On"]
            xmlRowElementName = "roleType"
            uriAttr = "roleURI"
        self.addRow(heading, asHeader=True) # must do after determining tree depth

        roletypes = self.modelXbrl.arcroleTypes if self.isArcrole else self.modelXbrl.roleTypes
        for roleUri in sorted(roletypes.keys()):
            for modelRoleType in roletypes[roleUri]:
                attr = {"definedIn": modelRoleType.modelDocument.basename}
                cols = [roleUri, modelRoleType.genLabel(lang=self.lang, strip=True) or modelRoleType.definition or '']
                if self.isArcrole:
                    cols.append(modelRoleType.cyclesAllowed)
                cols.append(', '.join(str(usedOn)
                                      for usedOn in modelRoleType.usedOns))

                self.addRow(cols, treeIndent=0, xmlRowElementName=xmlRowElementName, xmlRowEltAttr=attr)
