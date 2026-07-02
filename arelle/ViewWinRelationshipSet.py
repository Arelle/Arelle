'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

from collections import defaultdict
import os
from typing import TYPE_CHECKING, Any

from arelle import ViewWinTree, XbrlConst, Locale
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.ModelDtsObject import ModelRelationship, ModelConcept, ModelResource
from arelle.ModelObject import ModelObject
from arelle.ViewFileRelationshipSet import hasCalcArcrole
from arelle.ViewUtil import viewReferences, groupRelationshipSet, groupRelationshipLabel, baseSetArcroleLabel
from arelle.XbrlConst import conceptNameLabelRole, documentationLabel, widerNarrower
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from tkinter.ttk import Notebook

    from arelle.ModelXbrl import ModelXbrl
    from arelle.ModelValue import QName

_: TypeGetText


def viewRelationshipSet(
    modelXbrl: ModelXbrl,
    tabWin: Notebook,
    arcrole: str | list[Any] | tuple[Any, ...],
    linkrole: str | None = None,
    linkqname: QName | None = None,
    arcqname: QName | None = None,
    lang: str | None = None,
    treeColHdr: str | None = None,
    showLinkroles: bool = True,
    showRelationships: bool = True,
    showColumns: bool = True,
    expandAll: bool = False,
    hasTableIndex: bool = False,
    noRelationshipsMsg: bool = True,
) -> bool:
    arcroleName = groupRelationshipLabel(arcrole)  # type: ignore[no-untyped-call]
    relationshipSet = groupRelationshipSet(modelXbrl, arcrole, linkrole, linkqname, arcqname)  # type: ignore[no-untyped-call]
    if not relationshipSet:
        if noRelationshipsMsg:
            modelXbrl.modelManager.addToLog(_("no relationships for {0}").format(arcroleName))
        return False

    modelXbrl.modelManager.showStatus(_("viewing relationships {0}").format(arcroleName))
    view = ViewRelationshipSet(modelXbrl, tabWin, arcrole, linkrole, linkqname, arcqname, lang,
                               treeColHdr, showLinkroles, showRelationships, showColumns,
                               expandAll, hasTableIndex)
    view.view(firstTime=True, relationshipSet=relationshipSet)
    view.treeView.bind("<<TreeviewSelect>>", view.treeviewSelect, "+")
    view.treeView.bind("<Enter>", view.treeviewEnter, "+")
    view.treeView.bind("<Leave>", view.treeviewLeave, "+")

    # pop up menu
    view.contextMenu()
    view.menuAddExpandCollapse()
    view.menuAddClipboard()
    view.menuAddLangs()
    view.menuAddLabelRoles(includeConceptName=True)
    view.menuAddViews()

    return True


class ViewRelationshipSet(ViewWinTree.ViewTree):
    tabName: str

    def __init__(
        self,
        modelXbrl: ModelXbrl,
        tabWin: Notebook,
        arcrole: str | list[Any] | tuple[Any, ...],
        linkrole: str | None = None,
        linkqname: QName | None = None,
        arcqname: QName | None = None,
        lang: str | None = None,
        treeColHdr: str | None = None,
        showLinkroles: bool = True,
        showRelationships: bool = True,
        showColumns: bool = True,
        expandAll: bool = False,
        hasTableIndex: bool = False,
    ) -> None:
        if isinstance(arcrole, (list, tuple)):
            tabName = arcrole[0]
        else:
            tabName = baseSetArcroleLabel(arcrole)[1:]

        super(ViewRelationshipSet, self).__init__(modelXbrl, tabWin, tabName, True, lang)
        self.arcrole = arcrole
        self.linkrole = linkrole
        self.linkqname = linkqname
        self.arcqname = arcqname
        self.treeColHdr = treeColHdr
        self.showLinkroles = showLinkroles
        self.showRelationships = showRelationships
        self.showColumns = showColumns
        self.expandAllOnFirstDisplay = expandAll
        self.hasTableIndex = hasTableIndex
        self.isResourceArcrole = False

    def view(self, firstTime: bool = False, relationshipSet: ModelRelationshipSet | None = None) -> bool | None:  # type: ignore[override,return]
        self.blockSelectEvent = 1
        self.blockViewModelObject = 0
        self.tag_has: defaultdict[str, list[str]] = defaultdict(list) # temporary until Tk 8.6
        # relationship set based on linkrole parameter, to determine applicable linkroles
        if relationshipSet is None:
            relationshipSet = groupRelationshipSet(self.modelXbrl, self.arcrole, self.linkrole, self.linkqname, self.arcqname)  # type: ignore[no-untyped-call]
        if not relationshipSet:
            self.modelXbrl.modelManager.addToLog(_("no relationships for {0}").format(groupRelationshipLabel(self.arcrole)))  # type: ignore[no-untyped-call]
            return False

        if firstTime:
            self.showReferences = False
            # set up treeView widget and tabbed pane
            hdr = self.treeColHdr if self.treeColHdr else _("{0} Relationships").format(groupRelationshipLabel(self.arcrole))  # type: ignore[no-untyped-call]
            self.treeView.heading("#0", text=hdr)
            if self.showColumns:
                if self.arcrole == XbrlConst.parentChild: # extra columns
                    self.treeView.column("#0", width=300, anchor="w")
                    self.treeView["columns"] = ("preferredLabel", "type", "references")
                    self.treeView.column("preferredLabel", width=64, anchor="w", stretch=False)
                    self.treeView.heading("preferredLabel", text=_("Pref. Label"))
                    self.treeView.column("type", width=100, anchor="w", stretch=False)
                    self.treeView.heading("type", text=_("Type"))
                    self.treeView.column("references", width=200, anchor="w", stretch=False)
                    self.treeView.heading("references", text=_("References"))
                elif hasCalcArcrole(self.arcrole):  # type: ignore[arg-type]
                    self.treeView.column("#0", width=300, anchor="w")
                    self.treeView["columns"] = ("weight", "balance")
                    self.treeView.column("weight", width=48, anchor="w", stretch=False)
                    self.treeView.heading("weight", text=_("Weight"))
                    self.treeView.column("balance", width=70, anchor="w", stretch=False)
                    self.treeView.heading("balance", text=_("Balance"))
                elif self.arcrole == "XBRL-dimensions":    # add columns for dimensional information
                    self.treeView.column("#0", width=300, anchor="w")
                    self.treeView["columns"] = ("arcrole", "contextElement", "closed", "usable")
                    self.treeView.column("arcrole", width=100, anchor="w", stretch=False)
                    self.treeView.heading("arcrole", text="Arcrole")
                    self.treeView.column("contextElement", width=50, anchor="center", stretch=False)
                    self.treeView.heading("contextElement", text="Context")
                    self.treeView.column("closed", width=40, anchor="center", stretch=False)
                    self.treeView.heading("closed", text="Closed")
                    self.treeView.column("usable", width=40, anchor="center", stretch=False)
                    self.treeView.heading("usable", text="Usable")
                elif self.arcrole == "Table-rendering":    # add columns for dimensional information
                    self.treeView.column("#0", width=160, anchor="w")
                    self.treeView["columns"] = ("axis", "abstract", "merge", "header", "priItem", "dims")
                    self.treeView.column("axis", width=28, anchor="center", stretch=False)
                    self.treeView.heading("axis", text="Axis")
                    self.treeView.column("abstract", width=24, anchor="center", stretch=False)
                    self.treeView.heading("abstract", text="Abs")
                    self.treeView.column("merge", width=26, anchor="center", stretch=False)
                    self.treeView.heading("merge", text="Mrg")
                    self.treeView.column("header", width=160, anchor="w", stretch=False)
                    self.treeView.heading("header", text="Header")
                    self.treeView.column("priItem", width=100, anchor="w", stretch=False)
                    self.treeView.heading("priItem", text="Primary Item")
                    self.treeView.column("dims", width=150, anchor="w", stretch=False)
                    self.treeView.heading("dims", text=_("Dimensions"))
                elif self.arcrole == widerNarrower:
                    self.treeView.column("#0", width=300, anchor="w")
                    self.treeView["columns"] = ("wider", "documentation", "references")
                    self.treeView.column("wider", width=100, anchor="w", stretch=False)
                    self.treeView.heading("wider", text=_("Wider"))
                    self.treeView.column("documentation", width=200, anchor="w", stretch=False)
                    self.treeView.heading("documentation", text=_("Documentation"))
                    self.treeView.column("references", width=200, anchor="w", stretch=False)
                    self.treeView.heading("references", text=_("References"))
                elif isinstance(self.arcrole, (list,tuple)) or XbrlConst.isResourceArcrole(self.arcrole):
                    self.isResourceArcrole = True
                    self.showReferences = isinstance(self.arcrole, str) and self.arcrole.endswith("-reference")
                    self.treeView.column("#0", width=160, anchor="w")
                    self.treeView["columns"] = ("arcrole", "resource", "resourcerole", "lang")
                    self.treeView.column("arcrole", width=100, anchor="w", stretch=False)
                    self.treeView.heading("arcrole", text="Arcrole")
                    self.treeView.column("resource", width=60, anchor="w", stretch=False)
                    self.treeView.heading("resource", text="Resource")
                    self.treeView.column("resourcerole", width=100, anchor="w", stretch=False)
                    self.treeView.heading("resourcerole", text="Resource Role")
                    self.treeView.column("lang", width=36, anchor="w", stretch=False)
                    self.treeView.heading("lang", text="Lang")
        self.clearTreeView()
        self.id = 1

        # sort URIs by definition
        linkroleUris: list[tuple[str, str, str]] = []
        linkroleUriChildren: dict[str, list[str]] = {}
        for linkroleUri in relationshipSet.linkRoleUris:
            modelRoleTypes = self.modelXbrl.roleTypes.get(linkroleUri)
            if modelRoleTypes:
                roledefinition = ((self.hasTableIndex and getattr(modelRoleTypes[0], "_tableIndex", False)) or
                                  self.modelXbrl.roleTypeDefinition(linkroleUri, self.lang))
                roleId = modelRoleTypes[0].objectId(self.id)  # type: ignore[arg-type]
                if (self.hasTableIndex and hasattr(modelRoleTypes[0], "_tableChildren")):
                    linkroleUriChildren[linkroleUri] = [roleType.roleURI
                                                        for roleType in modelRoleTypes[0]._tableChildren]
            else:
                roledefinition = linkroleUri
                roleId = "node{0}".format(self.id)
            self.id += 1
            linkroleUris.append((roledefinition, linkroleUri, roleId))  # type: ignore[arg-type]
        # entry may be ((table group, order, role definition), uri, id) or (str definition, uri, id)
        linkroleUris.sort(key=lambda d:d[0] if isinstance(d[0], tuple) else ("9noTableKey", d[0], ""))

        def insertLinkroleChildren(parentNode: str, childUris: list[str]) -> None:
            for childUri in childUris:
                for roledefinition, linkroleUri, roleId in linkroleUris:
                    if childUri == linkroleUri: # and isinstance(roledefinition, tuple): # tableGroup
                        if isinstance(roledefinition, tuple):
                            _nextTableGroup, _order, roledefinition = roledefinition
                        else:
                            modelRoleTypes = self.modelXbrl.roleTypes.get(linkroleUri)
                            roledefinition = (modelRoleTypes[0].genLabel(lang=self.lang, strip=True) or  # type: ignore[index]
                                              modelRoleTypes[0].definition or  # type: ignore[index]
                                              linkroleUri)
                        childId = "_{}{}".format(self.id, roleId)
                        self.id += 1
                        childNode = self.treeView.insert(parentNode, "end", childId, text=roledefinition, tags=("ELR",))
                        if childUri in linkroleUriChildren:
                            insertLinkroleChildren(childNode, linkroleUriChildren[childUri])
                        break

        # for each URI in definition order
        tableGroup = ""
        for roledefinition, linkroleUri, roleId in linkroleUris:
            if self.showLinkroles:
                if isinstance(roledefinition, tuple): # tableGroup
                    nextTableGroup, _order, roledefinition = roledefinition
                    if tableGroup != nextTableGroup:
                        self.treeView.insert("", "end", nextTableGroup, text=nextTableGroup[1:], tags=("Group",))
                        if not tableGroup: # first tableGroup item, expand it
                            self.setTreeItemOpen(nextTableGroup, open=True)
                        tableGroup = nextTableGroup
                linknode = self.treeView.insert(tableGroup, "end", roleId, text=roledefinition, tags=("ELR",))
                # add tableChildren as child nodes
                if linkroleUri in linkroleUriChildren:
                    insertLinkroleChildren(linknode, linkroleUriChildren[linkroleUri])
            else:
                linknode = ""
            if self.showRelationships:
                linkRelationshipSet = groupRelationshipSet(self.modelXbrl, self.arcrole, linkroleUri, self.linkqname, self.arcqname)  # type: ignore[no-untyped-call]
                for rootConcept in linkRelationshipSet.rootConcepts:
                    self.viewConcept(rootConcept, rootConcept, "", self.labelrole, linknode, 1, linkRelationshipSet, set())
                    self.tag_has[linkroleUri].append(linknode)

        if self.expandAllOnFirstDisplay:
            self.expandAll()

    def viewConcept(
        self,
        concept: ModelConcept | ModelFact | DefnMdlTable | ModelResource | DefnMdlRuleDefinitionNode,
        modelObject: ModelObject,
        labelPrefix: str,
        preferredLabel: str | None,
        parentnode: str,
        n: int,
        relationshipSet: ModelRelationshipSet,
        visited: set[ModelConcept | ModelFact | DefnMdlTable | ModelResource | DefnMdlRuleDefinitionNode],
    ) -> None:
        if concept is None:
            return
        try:
            isRelation = isinstance(modelObject, ModelRelationship)
            if isinstance(concept, ModelConcept):
                text = labelPrefix + concept.label(preferredLabel, lang=self.lang, linkroleHint=relationshipSet.linkrole)  # type: ignore[operator,arg-type]
                if (self.arcrole in ("XBRL-dimensions", XbrlConst.hypercubeDimension) and
                    concept.isTypedDimension and
                    concept.typedDomainElement is not None):
                    text += " (typedDomain={0})".format(concept.typedDomainElement.qname)
            elif isinstance(concept, ModelFact):
                if concept.concept is not None:
                    text = labelPrefix + concept.concept.label(preferredLabel, lang=self.lang, linkroleHint=relationshipSet.linkrole)  # type: ignore[operator,arg-type]
                else:
                    text = str(concept.qname)
                if concept.contextID:
                    text += " [" + concept.contextID + "] = " + concept.effectiveValue  # type: ignore[operator]
            elif self.arcrole == "Table-rendering":
                text = concept.localName
            elif isinstance(concept, DefnMdlTable):
                text = (concept.genLabel(lang=self.lang, strip=True) or concept.localName)
            elif isinstance(concept, ModelResource):
                if self.showReferences:
                    text = (concept.viewText() or concept.localName)
                else:
                    text = (Locale.rtlString(concept.textValue.strip(), lang=concept.xmlLang) or concept.localName)
            else:   # just a resource
                text = concept.localName
                # add recognized attributes
                if concept.localName == "enumeration" and concept.get("value"):
                    text += ' {}="{}"'.format("value", concept.get("value"))
            childnode = self.treeView.insert(parentnode, "end", modelObject.objectId(self.id), text=text, tags=("odd" if n & 1 else "even",))  # type: ignore[arg-type]
            childRelationshipSet = relationshipSet
            if self.arcrole == XbrlConst.parentChild: # extra columns
                if isRelation:
                    preferredLabel = modelObject.preferredLabel  # type: ignore[attr-defined]
                    if preferredLabel and preferredLabel.startswith("http://"):
                        preferredLabel = os.path.basename(preferredLabel)
                    self.treeView.set(childnode, "preferredLabel", preferredLabel)
                self.treeView.set(childnode, "type", concept.niceType)  # type: ignore[union-attr]
                self.treeView.set(childnode, "references", viewReferences(concept))  # type: ignore[no-untyped-call]
            elif hasCalcArcrole(self.arcrole):  # type: ignore[arg-type]
                if isRelation:
                    self.treeView.set(childnode, "weight", "{:+0g} ".format(modelObject.weight))  # type: ignore[attr-defined]
                self.treeView.set(childnode, "balance", concept.balance)
            elif self.arcrole == "XBRL-dimensions" and isRelation: # extra columns
                relArcrole = modelObject.arcrole  # type: ignore[attr-defined]
                self.treeView.set(childnode, "arcrole", os.path.basename(relArcrole))
                if relArcrole in (XbrlConst.all, XbrlConst.notAll):
                    self.treeView.set(childnode, "contextElement", modelObject.contextElement)  # type: ignore[attr-defined]
                    self.treeView.set(childnode, "closed", modelObject.closed)  # type: ignore[attr-defined]
                elif relArcrole in (XbrlConst.dimensionDomain, XbrlConst.domainMember):
                    self.treeView.set(childnode, "usable", modelObject.usable)  # type: ignore[attr-defined]
                childRelationshipSet = self.modelXbrl.relationshipSet(XbrlConst.consecutiveArcrole.get(relArcrole,"XBRL-dimensions"),
                                                                      modelObject.consecutiveLinkrole)  # type: ignore[attr-defined]
            elif self.arcrole == "Table-rendering": # extra columns
                try:
                    header = concept.header(lang=self.lang, strip=True, evaluate=False)  # type: ignore[union-attr]
                except AttributeError:
                    header = None # could be a filter
                if isRelation and header is None:
                    header = "{0} {1}".format(os.path.basename(modelObject.arcrole), concept.xlinkLabel)  # type: ignore[attr-defined]
                self.treeView.set(childnode, "header", header)
                if concept.get("abstract") == "true":
                    self.treeView.set(childnode, "abstract", "\u2713") # checkmark unicode character
                if concept.get("merge") == "true":
                    self.treeView.set(childnode, "merge", "\u2713") # checkmark unicode character
                if isRelation:
                    self.treeView.set(childnode, "axis", modelObject.axis)  # type: ignore[attr-defined]
                    if isinstance(concept, DefnMdlRuleDefinitionNode):
                        self.treeView.set(childnode, "priItem", concept.aspectValue(None, Aspect.CONCEPT))  # type: ignore[no-untyped-call]
                        self.treeView.set(
                            childnode, "dims", " ".join(
                                ("{0},{1}".format(
                                    dim, dimAspectVal.stringValue if isinstance(dimAspectVal, ModelObject) else
                                    (dimAspectVal or concept.variableRefs())
                                    )
                                 for dim in (concept.aspectValue(None, Aspect.DIMENSIONS, inherit=False) or [])  # type: ignore[no-untyped-call]
                                 for dimAspectVal in (concept.aspectValue(None, dim),)  # type: ignore[no-untyped-call]
                                 if dimAspectVal is not None)
                            )
                        )
            elif self.arcrole == widerNarrower:
                if isRelation:
                    otherWider = [modelRel.fromModelObject
                                  for modelRel in childRelationshipSet.toModelObject(concept)
                                  if modelRel.fromModelObject != modelObject.fromModelObject]  # type: ignore[attr-defined]
                    self.treeView.set(
                        childnode, "wider", ", ".join(
                            w.label(  # type: ignore[union-attr]
                                preferredLabel,
                                lang=self.lang,
                                linkroleHint=relationshipSet.linkrole,
                            ) for w in otherWider
                        )
                    )
                self.treeView.set(
                    childnode, "documentation", concept.label(  # type: ignore[union-attr]
                        documentationLabel,
                        lang=self.lang,
                        linkroleHint=relationshipSet.linkrole,  # type: ignore[arg-type]
                        fallbackToQname=False,
                    )
                )
                self.treeView.set(childnode, "references", viewReferences(concept))  # type: ignore[no-untyped-call]
            elif self.isResourceArcrole: # resource columns
                if isRelation:
                    self.treeView.set(childnode, "arcrole", os.path.basename(modelObject.arcrole))  # type: ignore[attr-defined]
                if isinstance(concept, ModelResource):
                    self.treeView.set(childnode, "resource", concept.localName)
                    self.treeView.set(childnode, "resourcerole", os.path.basename(concept.role or ""))
                    self.treeView.set(childnode, "lang", concept.xmlLang)
            self.id += 1
            self.tag_has[modelObject.objectId()].append(childnode)
            if isRelation:
                self.tag_has[modelObject.toModelObject.objectId()].append(childnode)  # type: ignore[attr-defined]
            if concept not in visited:
                visited.add(concept)
                for modelRel in childRelationshipSet.fromModelObject(concept):
                    nestedRelationshipSet = childRelationshipSet
                    targetRole = modelRel.targetRole
                    if hasCalcArcrole(self.arcrole):  # type: ignore[arg-type]
                        childPrefix = "({:0g}) ".format(modelRel.weight)  # type: ignore[str-format]  # format without .0 on integer weights
                    elif targetRole is None or len(targetRole) == 0:
                        targetRole = relationshipSet.linkrole  # type: ignore[assignment]
                        childPrefix = ""
                    else:
                        nestedRelationshipSet = self.modelXbrl.relationshipSet(childRelationshipSet.arcrole, targetRole)
                        childPrefix = "(via targetRole) "
                    toConcept = modelRel.toModelObject
                    if toConcept in visited:
                        childPrefix += "(loop)"
                    labelrole = modelRel.preferredLabel
                    if not labelrole or self.labelrole == conceptNameLabelRole:
                        labelrole = self.labelrole
                    n += 1 # child has opposite row style of parent
                    self.viewConcept(toConcept, modelRel, childPrefix, labelrole, childnode, n, nestedRelationshipSet, visited)  # type: ignore[arg-type]
                visited.remove(concept)
        except AttributeError:
            return # bad object, don't try to display

    def getToolTip(self, tvRowId: str, tvColId: str) -> str | None:
        # override tool tip when appropriate
        if self.arcrole == "Table-rendering" and tvColId in ("#0", "#4"):
            try:
                modelObject = self.modelXbrl.modelObject(tvRowId) # this is a relationship object
                if isinstance(modelObject, ModelRelationship):
                    modelResource = modelObject.toModelObject
                else:
                    modelResource = modelObject
                if tvColId == "#0":
                    return modelResource.definitionNodeView  # type: ignore[union-attr,no-any-return]
                elif tvColId == "#4":
                    return " \n".join(": ".join(l)
                                      for l in modelResource.definitionLabelsView)  # type: ignore[union-attr]
                else:
                    return None
            except (AttributeError, KeyError):
                try: # rendering filter relationships
                    if tvColId == "#0":
                        modelResource = modelObject.toModelObject  # type: ignore[union-attr]
                        return "{0}: {1}\ncomplement: {2}\ncover: {3}\n{4}".format(
                                modelResource.localName, modelResource.viewExpression,
                                str(modelObject.isComplemented).lower(),  # type: ignore[union-attr]
                                str(modelObject.isCovered).lower(),  # type: ignore[union-attr]
                                "\n".join("{0}: {1}".format(p[0], p[1])
                                          for p in modelResource.propertyView
                                          if p and len(p) >= 2))
                except (AttributeError, KeyError):
                    pass
        return None

    def treeviewEnter(self, *args: Any) -> None:
        self.blockSelectEvent = 0

    def treeviewLeave(self, *args: Any) -> None:
        self.blockSelectEvent = 1

    def treeviewSelect(self, *args: Any) -> None:
        if self.blockSelectEvent == 0 and self.blockViewModelObject == 0:
            self.blockViewModelObject += 1
            selection = self.treeView.selection()
            if selection is not None and len(selection)>0:
                self.modelXbrl.viewModelObject(selection[0])
            self.blockViewModelObject -= 1

    def viewModelObject(self, modelObject: ModelObject) -> None:
        if self.blockViewModelObject == 0:
            self.blockViewModelObject += 1
            try:
                # check if modelObject is a relationship in given linkrole
                linkroleId: str | None = None
                if isinstance(modelObject, ModelRelationship):
                    linkroleIds = self.tag_has.get(modelObject.linkrole)  # type: ignore[arg-type]
                    if linkroleIds:
                        linkroleId = linkroleIds[0]
                # get concept of fact or toConcept of relationship, role obj if roleType
                conceptId = modelObject.viewConcept.objectId()  # type: ignore[attr-defined]
                items = self.tag_has.get(conceptId)
                if items:
                    for item in items:
                        if self.treeView.exists(item):
                            if linkroleId is None or self.hasAncestor(item, linkroleId):
                                self.treeView.see(item)
                                self.treeView.selection_set(item)
                                break
            except (AttributeError, KeyError):
                    self.treeView.selection_set(())
            self.blockViewModelObject -= 1

    def hasAncestor(self, node: str, ancestor: str) -> bool:
        if node == ancestor:
            return True
        elif node:
            return self.hasAncestor(self.treeView.parent(node), ancestor)
        return False

from arelle.ModelRenderingObject import DefnMdlRuleDefinitionNode, DefnMdlTable
from arelle.ModelFormulaObject import Aspect
