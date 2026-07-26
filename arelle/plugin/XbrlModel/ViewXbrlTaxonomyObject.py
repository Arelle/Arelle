'''
See COPYRIGHT.md for copyright information.

Tkinter tree views of a compiled XBRL model's objects.

These panes replace Arelle's ordinary taxonomy views when a compiled model is opened; the
plugin's `xbrlModelViews` hook (`__init__.py`) creates one per object class and passes the full
pane list so each pane's View menu can reopen any of them.

Panes come in two shapes, because a Treeview has a single column set for the whole tree:

  * A *structural* pane (`STRUCTURAL_CLASSES`) is deliberately heterogeneous -- the Groups pane
    holds groups, then their cubes and networks, then cube dimensions, then domain networks and
    their members on successive rows. Naming columns after the pane's top-level class would
    mislabel every nested row, so these panes use `STRUCTURAL_COLUMNS`, which mean the same thing
    whatever the row's object type is.
  * Every other pane is homogeneous -- one object class per row -- and keeps that class's own
    properties as columns.

Both end in a "detail" column holding whatever has no column of its own, as name=value pairs.

Whatever the pane, a row is written by `insertRow`: the tree column shows the object's label in
the pane's current label role and language, and every other cell is set BY COLUMN NAME, so a
value only ever appears under a heading that names it, however deeply nested the row is.

The Groups pane is the model's reporting structure rather than a flat list: `viewGroups` nests
groups under the groupTree (oim-taxonomy#grouptree-object) in relationship order, each followed
by its group contents, with anything the tree does not reach under an "(ungrouped)" node.

The context menu offers expand/collapse, Find, copy to clipboard (including Copy JSON, the
selected object serialized), language, label role, name style (prefixed QNames or local names)
and the View list. Selecting a row calls `viewTaxonomyObject`, which syncs the other panes, the
Properties pane and the JSON pane. The Properties pane renders `XbrlObject.propertyView` (in
`XbrlObject.py`, not here); the JSON pane (`ViewXbrlObjectJson`) renders the object's compiled
JSON via `SaveModel.saveableObjects`. Both sit in the upper-left tab window beside each other.
'''
from typing import ForwardRef, GenericAlias, Union, get_origin
from collections import defaultdict
from decimal import Decimal
import json
from arelle import ViewWinTree, XbrlConst
from arelle.ModelValue import QName, qname
from ordered_set import OrderedSet
from .XbrlConcept import XbrlConcept
from .XbrlCube import XbrlCube, conceptCoreDim, unitCoreDim
from .XbrlDimension import XbrlDomainNetwork
from .XbrlFact import XbrlFact
from .XbrlGroup import XbrlGroup, XbrlGroupTree
from .XbrlImportTaxonomy import XbrlImportTaxonomy
from .XbrlNetwork import XbrlNetwork
from .XbrlObject import XbrlObject
from .XbrlConst import qnStdLabel

# A Treeview has one column set for the whole tree, but the structural panes are deliberately
# heterogeneous: a Groups pane holds groups, then cubes and networks, then cube dimensions,
# then domain networks and their members on successive rows. Naming the columns after the
# pane's top-level class therefore mislabels every nested row. These panes instead use columns
# that mean the same thing whatever the row's object type is, with everything else summarized
# into "detail" as name=value pairs.
STRUCTURAL_CLASSES = (XbrlGroup, XbrlGroupTree, XbrlCube, XbrlNetwork, XbrlDomainNetwork)
STRUCTURAL_COLUMNS = ("object", "name", "kind", "detail")

# The property that best discriminates one object type from another in a structural pane,
# shown in the "kind" column. The first one an object has wins.
KIND_PROPERTIES = ("cubeType", "dimension", "relationshipTypeName", "dataType",
                   "domainDataType", "root", "groupURI")

# Columns the Facts pane shows in place of the factValues collection (see viewXbrlTaxonomyObject).
FACT_VALUE_COLUMNS = (("value", str), ("decimals", int))

# Column widths by column name; anything else gets DEFAULT_COLUMN_WIDTH (or NUMERIC_COLUMN_WIDTH
# for a numeric property). Like every other Arelle view these are startup defaults only -- the
# GUI persists window geometry and the tab splitters, never column widths, so a width the user
# drags is deliberately not remembered across sessions.
COLUMN_WIDTHS = {"#0": 280, "object": 110, "name": 240, "kind": 180, "value": 200, "detail": 400}
DEFAULT_COLUMN_WIDTH = 120
NUMERIC_COLUMN_WIDTH = 50

# Only one column stretches to take up the pane's spare width, and every change in that width --
# the window or a sash being dragged, or another column being widened -- is taken out of it. The
# infrastructure views make the TREE column the stretcher, which is why dragging any column there
# squeezes the leftmost one, down to Tk's 20px default minimum. Here the last column ("detail",
# free text that is also available in full from the tooltip) absorbs it instead, so the label
# column keeps the width it was given and a drag only resizes what was dragged.
MINIMUM_COLUMN_WIDTHS = {"#0": 60, "detail": 120}
DEFAULT_MINIMUM_COLUMN_WIDTH = 20

# A group's role URI is its "kind", and it is the trailing path segment that identifies it --
# but a cell clipped on the right shows only "http://www.example.com/ro...". Such values are
# shortened from the left so the tail survives; getToolTip hands back the untruncated text.
URI_MAX_LEN = 40


def shortenUri(text):
    """A URI reduced to the trailing path segments that fit in URI_MAX_LEN, else text unchanged."""
    if len(text) <= URI_MAX_LEN or not text.startswith(("http://", "https://")):
        return text
    segments = text.partition("://")[2].split("/")
    shortened = segments[-1]
    for segment in reversed(segments[:-1]):
        if len(shortened) + len(segment) + 1 > URI_MAX_LEN:
            break
        shortened = f"{segment}/{shortened}"
    return f"…/{shortened}"


def isParentAliasType(propType):
    """True if a property's type annotation names the object's parent (e.g. `module: XbrlModuleAlias`).

    The parent back-reference is always the first declared property and is never shown as a
    column -- it is the same value for every row of the pane."""
    if isinstance(propType, str): # an unresolved TypeAlias, e.g. "XbrlModule"
        return True
    if get_origin(propType) is Union:
        return any((arg.__forward_arg__ if isinstance(arg, ForwardRef) else getattr(arg, "__name__", "")
                    ).startswith("Xbrl")
                   for arg in propType.__args__)
    return getattr(propType, "__name__", "").startswith("Xbrl")


def homogeneousPropNameTypes(objClass):
    """The pane class's own scalar properties in declaration order, skipping the parent
       back-reference. Plain builtin generics (list[str], dict[K,V]) get no column of their own;
       propertyView expands them, so their contents land in the "detail" column."""
    initialParentObjProp = True
    for propName, propType in objClass.propertyNameTypes():
        if initialParentObjProp:
            initialParentObjProp = False
            if isParentAliasType(propType):
                continue
        if propName == "properties":
            continue # propertyView expands these into one propertyType=value entry each, so a
                     # "properties" column could never be filled -- they belong in "detail"
        if not isinstance(propType, GenericAlias):
            yield propName, propType


def objectTypeName(obj):
    """The object's type as it appears in the "object" column: XbrlCubeDimension -> cubeDimension."""
    className = type(obj).__name__
    if className.startswith("Xbrl") and len(className) > 4:
        return f"{className[4].lower()}{className[5:]}"
    return className


def objectJson(obj):
    """The compiled-model JSON for a single taxonomy object, as shown in the JSON pane and by
       Copy JSON. Reuses the save path's per-object serializer (SaveModel.saveableObjects) so the
       text matches what SaveModel would write; "full" mode (no prune) emits the object as-is.
       Returns "" for anything the serializer cannot handle (e.g. a grouping row's non-object)."""
    from .SaveModel import saveableObjects
    try:
        return json.dumps(saveableObjects(obj, "", fileExt=".json", txmyPrefixes={}), indent=2)
    except Exception:
        return ""


def findObjects(dialog, modelXbrl, pattern, isRE, isXP, options):
    """DialogFind.Objects hook: search a compiled XBRL model's concepts and facts for the Find
    dialog, mapping its concept/fact field checkboxes onto OIM object properties. Returns the
    dialog's objsList of (kind, sortKey, objectId) tuples, where objectId is an "_..._index" id
    the compiled model's viewModelObject resolves. Returns None to decline -- when the loaded model
    is not a compiled XBRL model, or the expression is xpath (not evaluated here) -- so the
    dialog's built-in ModelConcept/ModelFact search runs unchanged for ordinary DTSes."""
    if pattern is None or not isRE or getattr(modelXbrl, "namedObjects", None) is None:
        return None
    o = options
    wantConcept = any(o.get(k) for k in ("conceptLabel", "conceptName", "conceptType", "conceptPer", "conceptBal"))
    wantFact = any(o.get(k) for k in ("factLabel", "factName", "factValue", "factCntx", "factUnit"))
    if not (wantConcept or wantFact):
        return [] # claim the model, but no concept/fact field selected -- nothing to match
    lang = modelXbrl.modelManager.defaultLang
    objsList = []
    def objId(obj):
        return f"_0_{obj.xbrlMdlObjIndex}"
    def label(qn):
        return str(modelXbrl.labelValue(qn, qnStdLabel, lang) or "") if qn is not None else ""
    def balance(concept):
        for prop in getattr(concept, "properties", None) or ():
            if getattr(getattr(prop, "property", None), "localName", None) == "balance":
                return str(getattr(prop, "value", ""))
        return ""
    def conceptQnOf(fact):
        qn = (fact.factDimensions or {}).get(conceptCoreDim)
        if isinstance(qn, str) and ":" in qn:
            qn = qname(qn, fact.module._prefixNamespaces)
        return qn
    if wantConcept:
        for c in modelXbrl.filterNamedObjects(XbrlConcept):
            if ((o.get("conceptName") and pattern.search(str(c.name))) or
                (o.get("conceptLabel") and pattern.search(label(c.name))) or
                (o.get("conceptType") and c.dataType and pattern.search(str(c.dataType))) or
                (o.get("conceptPer") and c.periodType and pattern.search(str(c.periodType))) or
                (o.get("conceptBal") and pattern.search(balance(c)))):
                objsList.append(("c", str(c.name), objId(c)))
    if wantFact:
        for f in modelXbrl.filterNamedObjects(XbrlFact):
            cq = conceptQnOf(f)
            dims = f.factDimensions or {}
            values = [str(fv.value) for fv in (f.factValues or ()) if getattr(fv, "value", None) is not None]
            unit = dims.get(unitCoreDim)
            if ((o.get("factName") and cq is not None and pattern.search(str(cq))) or
                (o.get("factLabel") and cq is not None and pattern.search(label(cq))) or
                (o.get("factValue") and any(pattern.search(v) for v in values)) or
                (o.get("factCntx") and pattern.search("; ".join(f"{k}={v}" for k, v in dims.items()))) or
                (o.get("factUnit") and unit is not None and pattern.search(str(unit)))):
                objsList.append(("f", label(cq) or str(f.name), objId(f)))
    return objsList


def viewXbrlTaxonomyObject(xbrlCompMdl, objClass, tabWin, header, additionalViews=None):
    """View an XBRL taxonomy object class in a tree view.
    :param xbrlCompMdl: Compiled ModelXbrl
    :param objClass: Xbrl Model object class to view
    :param tabWin: parent tab window for view
    :param header: header for view
    :param additionalViews: additional views to add to view menu (list of (viewName"""
    xbrlCompMdl.modelManager.showStatus("viewing concepts")
    view = ViewXbrlTxmyObj(xbrlCompMdl, objClass, tabWin, header)
    view.isStructuralPane = objClass in STRUCTURAL_CLASSES
    if view.isStructuralPane:
        view.propNameTypes = [("label", str)] + [(colName, str) for colName in STRUCTURAL_COLUMNS]
    else:
        view.propNameTypes = list(homogeneousPropNameTypes(objClass))
        # for a named object the tree column shows its label, and its name becomes a column of
        # its own -- so the name heading describes what is under it
        if view.propNameTypes and view.propNameTypes[0][0] == "name":
            view.propNameTypes.insert(0, ("label", str))
        if objClass is XbrlFact:
            # a fact's value and decimals live on its factValue objects, but they are what a
            # reader scans a fact list for, so they get columns of their own in place of the
            # collection -- whose full contents the Properties pane shows as expandable rows
            view.propNameTypes = [nameType
                                  for propName, propType in view.propNameTypes
                                  for nameType in (FACT_VALUE_COLUMNS if propName == "factValues"
                                                   else ((propName, propType),))]
        # whatever propertyView reports that has no column of its own (an object's properties,
        # references, a fact's dimensions) is summarized here rather than being dropped
        view.propNameTypes.append(("detail", str))
    view.colNames = tuple(propName for propName, _propType in view.propNameTypes[1:])
    view.treeView["columns"] = view.colNames
    stretchCol = view.colNames[-1] if view.colNames else "#0"
    firstCol = True
    for propName, propType in view.propNameTypes:
        if firstCol:
            firstCol = False
            colName = "#0"
        else:
            colName = propName
        if colName in COLUMN_WIDTHS:
            w = COLUMN_WIDTHS[colName]
        elif propType in (int, float, Decimal): # propType is the annotation, not a value
            w = NUMERIC_COLUMN_WIDTH
        else:
            w = DEFAULT_COLUMN_WIDTH
        view.treeView.column(colName, width=w, anchor="w",
                             minwidth=MINIMUM_COLUMN_WIDTHS.get(colName, DEFAULT_MINIMUM_COLUMN_WIDTH),
                             stretch=(colName == stretchCol))
        view.treeView.heading(colName, text=propName)
    view.treeView["displaycolumns"] = view.colNames
    # reference objects have no label of their own; they are shown by their own properties
    view.labelrole = None if objClass.__name__ == "XbrlReference" else qnStdLabel
    view.view()
    view.treeView.bind("<<TreeviewSelect>>", view.treeviewSelect, '+')
    view.treeView.bind("<Enter>", view.treeviewEnter, '+')
    view.treeView.bind("<Leave>", view.treeviewLeave, '+')

    # languages menu
    menu = view.contextMenu()
    if objClass.__name__ != "XbrlConcept":
        view.menuAddExpandCollapse() # for tree view panes but not for Concept table pane
    view.menuAddFind()
    view.menuAddClipboard()
    view.menuAddCopyJson()
    view.menuAddLangs()

    view.menuAddLabelRoles(usedLabelroles=
        (("1Name",XbrlConst.conceptNameLabelRole),
         ("2Standard Label", qnStdLabel)) +
        tuple((f"3{t}", t) for t in sorted((lt for lt in xbrlCompMdl.labelTypes if lt)) if t != qnStdLabel))
    view.menuAddNameStyle()
    # every pane -- including the ones opened on load -- is listed in the View menu, so a pane
    # closed here can be opened again
    view.menuAddViews(addClose=True, additionalViews=additionalViews, additionalViewMethod=viewXbrlTaxonomyObject)

class ViewXbrlTxmyObj(ViewWinTree.ViewTree):
    """View of XBRL taxonomy object class in a tree view.   """
    def __init__(self, xbrlCompMdl, objClass, tabWin, header):
        super(ViewXbrlTxmyObj, self).__init__(xbrlCompMdl, tabWin, header, True, None)
        self.xbrlCompMdl = xbrlCompMdl
        self.objClass = objClass
        self.isStructuralPane = objClass in STRUCTURAL_CLASSES
        # a tree pane's child-row order carries meaning (relationship / import order), so it opens
        # unsorted and never sorts nested rows -- see setColumnsSortable and sortNestedRows. The
        # import pane keeps homogeneous columns but is still tree-shaped.
        self.isTreePane = self.isStructuralPane or objClass is XbrlImportTaxonomy
        self.nameIsPrefixed = True # the Name Style menu toggles this; prefixed is the default
        self.blockSelectEvent = 1
        self.blockViewModelObject = 0
        self.findPattern = ""
        self.fullCellText = {} # (node, column) -> untruncated text, for cells shortened to fit

    # ── row rendering ──────────────────────────────────────────────────
    #
    # Every row in every pane is written by insertRow: the tree column shows the object's
    # label in the pane's current label role and language, and the remaining cells are set
    # BY COLUMN NAME. A value is therefore only ever shown under a heading that names it,
    # however deeply nested the row is and whatever its object type.
    # ──────────────────────────────────────────────────────────────────

    def nameText(self, qn):
        """A QName as the Name Style menu asks for it."""
        if qn is None:
            return ""
        if isinstance(qn, QName) and not self.nameIsPrefixed:
            return qn.localName
        return str(qn)

    def labelText(self, qn):
        """The label of a named object in the pane's label role and language, falling back to
           its name (the Name Style menu applies to the fallback and to the Name label role)."""
        if qn is None:
            return ""
        if self.labelrole is None or self.labelrole == XbrlConst.conceptNameLabelRole:
            return self.nameText(qn)
        label = self.xbrlCompMdl.labelValue(qn, self.labelrole, self.lang, fallbackToName=False)
        return str(label) if label else self.nameText(qn)

    def objLabel(self, obj):
        """Tree-column text for an object: its label if it is named, else the label of whatever
           it identifies (a cube dimension is shown by its dimension), else its first property."""
        if isinstance(obj, XbrlFact):
            # a fact's name is a generated identifier (exp:f12345); a reader expects the label of
            # the concept it reports, which is its xbrl:concept dimension. The name is a column.
            conceptQn = (obj.factDimensions or {}).get(conceptCoreDim)
            if isinstance(conceptQn, str) and ":" in conceptQn:
                # dimension values are still prefixed strings until validation resolves them
                # (ValidateFacts.resolveFactConcept); resolve a copy, never mutate from a view
                conceptQn = qname(conceptQn, obj.module._prefixNamespaces)
            if isinstance(conceptQn, QName):
                return self.labelText(conceptQn)
        for propName in ("name", "dimension", "target", "forObject", "xbrlModelName"):
            val = getattr(obj, propName, None)
            if isinstance(val, QName):
                return self.labelText(val)
        propView = obj.propertyView
        if propView and isinstance(propView[0], (list, tuple)) and len(propView[0]) > 1:
            return str(propView[0][1])
        return objectTypeName(obj)

    def collectionText(self, val):
        """A collection cell: a count for objects (their contents are shown as child rows or in
           the object's own pane), the values themselves for scalars such as QName references."""
        items = list(val.values() if isinstance(val, dict) else val)
        if any(isinstance(item, XbrlObject) for item in items):
            if all(getattr(item, "value", None) is not None for item in items):
                return ", ".join(str(item.value) for item in items) # e.g. a fact's values
            return f"({len(items)})"
        return ", ".join(str(item) for item in items)

    def factDimensionMembers(self, fact):
        """The named objects a fact's dimension values point at -- its concept, explicit members,
           unit, etc. Used to cross-index a fact so selecting one of those objects reveals it, and
           to reveal one of them when the fact itself has no row in a pane. Period and entity
           dimension values are not named objects and resolve to nothing, so they are skipped."""
        for dimVal in (fact.factDimensions or {}).values():
            qn = dimVal
            if isinstance(qn, str) and ":" in qn:
                qn = qname(qn, fact.module._prefixNamespaces)
            if isinstance(qn, QName):
                memberObj = self.xbrlCompMdl.namedObjects.get(qn)
                if memberObj is not None:
                    yield memberObj

    def factValueCells(self, obj):
        """(value, decimals) for a fact, gathered from its factValue objects -- usually one, but a
           fact may carry several, so they are joined rather than showing only the first."""
        factValues = obj.factValues or ()
        return ("; ".join(str(fv.value) for fv in factValues if fv.value is not None),
                "; ".join(str(fv.decimals) for fv in factValues if fv.decimals is not None))

    def kindProperty(self, obj):
        """The property that discriminates this object's row from rows of a different object
           type in the same pane -- a cube's cubeType, a cube dimension's dimension, a network's
           relationship type, a concept's data type."""
        for propName in KIND_PROPERTIES:
            if getattr(obj, propName, None) is not None:
                return propName
        return None

    def rowValues(self, obj, skipNames=(), rowText=None):
        """(cells by column name, detail text) for an object.

        propertyView reports (name, value) pairs plus two shapes that carry more: an expanded
        collection [name, "(n)", [...]] and a reference ("references", refType, ((type, value), ...)).
        Everything is keyed by its property name; whatever this pane has no column for is
        collected into the detail column rather than being dropped or, worse, written under
        some other property's heading."""
        cells = {}
        detail = []
        for propViewEntry in obj.propertyView:
            if not isinstance(propViewEntry, (list, tuple)) or len(propViewEntry) < 2:
                continue # a malformed propertyView entry, e.g. a nested value with no name
            propName = str(propViewEntry[0])
            if propName in skipNames:
                continue
            if propName == "label" and str(propViewEntry[1]) == rowText:
                continue # the tree column already shows it
            if propName == "references" and len(propViewEntry) > 2:
                propName = f"references {propViewEntry[1]}"
                propVal = "; ".join(f"{refProp[0]}={refProp[1]}" for refProp in propViewEntry[2])
            else:
                val = getattr(obj, propName, None)
                if isinstance(val, (set, frozenset, list, tuple, dict, OrderedSet)):
                    # a collection is one row here, so summarize it -- propertyView's expanded
                    # form is for the Properties pane, which can nest it
                    propVal = self.collectionText(val)
                elif isinstance(val, QName):
                    propVal = self.nameText(val)
                else:
                    propVal = str(propViewEntry[1])
            if propName in self.colNames and propName not in cells:
                cells[propName] = propVal
            else:
                detail.append(f"{propName}={propVal}")
        return cells, "; ".join(detail)

    def insertRow(self, parentNode, obj, textPrefix=""):
        """Insert one row for obj and return its node."""
        objLabel = self.objLabel(obj)
        rowText = textPrefix + objLabel
        skipNames = ()
        if self.isStructuralPane:
            # name and kind get dedicated columns below; don't repeat them in detail
            skipNames = tuple(propName for propName in ("name", self.kindProperty(obj)) if propName)
        elif isinstance(obj, XbrlFact):
            skipNames = ("factValues",) # shown as the value and decimals columns instead
        cells, detail = self.rowValues(obj, skipNames, objLabel)
        if isinstance(obj, XbrlFact) and "value" in self.colNames:
            cells["value"], cells["decimals"] = self.factValueCells(obj)
        if self.isStructuralPane:
            cells["object"] = objectTypeName(obj)
            cells["name"] = self.nameText(getattr(obj, "name", None))
            kindProp = self.kindProperty(obj)
            kindVal = getattr(obj, kindProp, None) if kindProp else None
            cells["kind"] = self.nameText(kindVal) if isinstance(kindVal, QName) else (
                "" if kindVal is None else str(kindVal))
        if detail and "detail" in self.colNames:
            cells["detail"] = detail
        node = self.treeView.insert(parentNode, "end",
                                    f"_{self.id}_{obj.xbrlMdlObjIndex}",
                                    text=rowText,
                                    tags=("odd" if self.nodeNum & 1 else "even",))
        self.tag_has[f"_{obj.xbrlMdlObjIndex}"].append(node)
        if isinstance(obj, XbrlFact):
            # also index the fact under each of its dimension members, so selecting a concept /
            # member / unit in another pane (or finding one) reveals a fact that uses it -- the
            # Facts pane holds only facts, so those objects have no row of their own here
            for memberObj in self.factDimensionMembers(obj):
                self.tag_has[f"_{memberObj.xbrlMdlObjIndex}"].append(node)
        self.id += 1
        self.nodeNum += 1
        for colName in self.colNames:
            cellText = cells.get(colName, "")
            shortened = shortenUri(cellText)
            if shortened != cellText:
                self.fullCellText[(node, colName)] = cellText
            self.treeView.set(node, colName, shortened)
        return node

    # ── pane rendering ─────────────────────────────────────────────────

    def view(self):
        # remember which objects were expanded so a re-render (label role, language, name style,
        # sort) does not collapse a tree the user has opened -- keyed by object index, which is
        # stable across rebuilds even though the node ids are not
        priorOpen = self._captureOpenState()
        # a tree pane's child rows are ordered (relationship / import order), so it opens unsorted
        self.setColumnsSortable(startUnsorted=self.isTreePane)
        self.tag_has = defaultdict(list)
        self.fullCellText = {}
        self.clearTreeView()
        self.id = 1
        self.nodeNum = 0
        if self.objClass is XbrlGroup:
            self.viewGroups() # the Groups pane is the reporting structure, not a flat list
        elif self.objClass is XbrlImportTaxonomy:
            self.viewImportTree() # nest imported modules under the module that imports them
        else:
            if self.objClass is XbrlNetwork:
                objs = self.xbrlCompMdl.filterNetworks()
            else:
                # in a tag pane (labels, references) the label role doubles as a type filter, so
                # the pane shows the labels of the selected type. "Name" is a display sentinel
                # rather than a label type, so it must not filter every row out.
                typeFilter = None if self.labelrole == XbrlConst.conceptNameLabelRole else self.labelrole
                objs = self.xbrlCompMdl.filterNamedObjects(self.objClass, typeFilter, self.lang)
            for obj in objs: # this is a yield generator
                self.viewChildren(self.insertRow("", obj), obj)
        self._restoreOpenState(priorOpen)

    def _captureOpenState(self):
        """Object indexes of the currently-expanded object rows, before the tree is rebuilt."""
        openIdx = set()
        if not hasattr(self, "tag_has"): # first build -- nothing to remember
            return openIdx
        def walk(node):
            for n in self.treeView.get_children(node):
                if n.startswith("_") and str(self.treeView.item(n, "open")) in ("1", "true"):
                    openIdx.add(n.rpartition("_")[2])
                walk(n)
        try:
            walk("")
        except Exception:
            pass # tkinter can raise mid-teardown; a lost expand state is not worth an error
        return openIdx

    def _restoreOpenState(self, openIdx):
        """Re-expand the object rows that were open before the rebuild (see _captureOpenState)."""
        for idx in openIdx:
            for node in self.tag_has.get(f"_{idx}", ()):
                if self.treeView.exists(node):
                    self.treeView.item(node, open=True)

    def viewChildren(self, node, obj):
        """Render whatever an object contains below its own row."""
        if isinstance(obj, XbrlGroup):
            self.viewGroupContent(node, obj)
        elif isinstance(obj, XbrlCube):
            self.viewDims(node, obj)
        elif isinstance(obj, (XbrlNetwork, XbrlDomainNetwork, XbrlGroupTree)):
            self.viewRoots(node, obj)

    def viewImportTree(self):
        """The import pane as a tree: each imported module nested under the module that imports it,
           so the hierarchy shows which taxonomy imports which. Roots are the modules imported by no
           other module (typically the entry-point taxonomy). If the graph is wholly cyclic -- e.g.
           a model of only the mutually-importing built-ins -- every module is shown as a root so
           none is hidden. A row whose imported module is already an ancestor on the path (the
           built-ins import each other) is marked "(loop)" and not re-descended."""
        modules = self.xbrlCompMdl.xbrlModels
        importedTargets = {it.xbrlModelName
                           for mod in modules.values()
                           for it in (getattr(mod, "importedTaxonomies", None) or ())}
        roots = [name for name in modules if name not in importedTargets]
        if not roots: # fully cyclic (built-ins only) -- show every module rather than nothing
            roots = list(modules)
        for name in roots:
            module = modules.get(name)
            if module is not None:
                self.viewModuleImports(self.insertRow("", module), module, {name})

    def viewModuleImports(self, parentNode, module, visited):
        """Insert one row per import directive of `module`, each recursing into the imported
           module's own imports; `visited` is the module QNames on the path, for loop detection."""
        for importObj in getattr(module, "importedTaxonomies", None) or ():
            target = importObj.xbrlModelName
            loop = target in visited
            node = self.insertRow(parentNode, importObj, textPrefix="(loop) " if loop else "")
            if loop:
                continue
            targetModule = self.xbrlCompMdl.xbrlModels.get(target)
            if targetModule is not None:
                visited.add(target)
                self.viewModuleImports(node, targetModule, visited)
                visited.discard(target)

    def viewGroups(self):
        """The Groups pane is the reporting structure: groups nested under the model's groupTree
           (oim-taxonomy#grouptree-object), each group followed by its group contents.

           A group no group tree reaches is still shown, under an "(ungrouped)" node, so the pane
           never hides part of the model; with no group tree at all the pane is the flat list of
           groups it has always been."""
        rendered = set()
        for groupTree in getattr(self.xbrlCompMdl, "groupTrees", None) or ():
            relationshipsFrom = self.xbrlCompMdl.effectiveRelationshipsFrom(groupTree)
            for groupQn in self.xbrlCompMdl.effectiveRelationshipRoots(groupTree):
                self.viewGroupNode("", groupQn, relationshipsFrom, rendered, set())
        ungrouped = [obj for obj in self.xbrlCompMdl.filterNamedObjects(XbrlGroup)
                     if obj.name not in rendered]
        if not ungrouped:
            return
        parentNode = ""
        if rendered: # some groups are in a tree and these are not -- say so rather than mixing them in
            parentNode = self.treeView.insert("", "end", f"ungrouped{self.id}",
                                              text=_("(ungrouped)"),
                                              tags=("odd" if self.nodeNum & 1 else "even",))
            self.id += 1
            self.nodeNum += 1
        for obj in ungrouped:
            self.viewGroupContent(self.insertRow(parentNode, obj), obj)

    def viewGroupNode(self, parentNode, groupQn, relationshipsFrom, rendered, visited):
        """One group of the group tree: its child groups, then its own group contents."""
        groupObj = self.xbrlCompMdl.namedObjects.get(groupQn)
        if not isinstance(groupObj, XbrlGroup):
            return # a group tree relationship whose target is missing or not a group
        loop = groupQn in visited
        node = self.insertRow(parentNode, groupObj, textPrefix="(loop) " if loop else "")
        if loop:
            return
        rendered.add(groupQn)
        visited.add(groupQn)
        for relObj in relationshipsFrom.get(groupQn, ()):
            self.viewGroupNode(node, relObj.target, relationshipsFrom, rendered, visited)
        visited.discard(groupQn)
        self.viewGroupContent(node, groupObj)

    def viewGroupContent(self, parentNode, obj):
        # related content for the Group object are under tagged content
        for relatedObjQn in self.xbrlCompMdl.groupContents.get(obj.name, None) or ():
            relatedObj = self.xbrlCompMdl.namedObjects.get(relatedObjQn)
            if relatedObj is None:
                continue
            node = self.insertRow(parentNode, relatedObj)
            if not isinstance(relatedObj, XbrlGroup): # group contents are networks, cubes and
                self.viewChildren(node, relatedObj)  # table templates -- never a group

    def viewDims(self, parentNode, obj):
        for cubeDim in obj.cubeDimensions or ():
            node = self.insertRow(parentNode, cubeDim)
            domName = cubeDim.domainNetwork
            if domName:
                domObj = self.xbrlCompMdl.namedObjects.get(domName)
                if domObj is not None:
                    self.viewRoots(self.insertRow(node, domObj), domObj)

    def viewRoots(self, parentNode, obj):
        if not isinstance(obj, (XbrlDomainNetwork, XbrlNetwork, XbrlGroupTree)):
            return
        relationshipsFrom = self.xbrlCompMdl.effectiveRelationshipsFrom(obj)
        for qn in self.xbrlCompMdl.effectiveRelationshipRoots(obj):
            rootObj = self.xbrlCompMdl.namedObjects.get(qn)
            if rootObj is not None:
                node = self.insertRow(parentNode, rootObj)
                for relObj in relationshipsFrom.get(qn, ()):
                    self.viewRelationships(node, relationshipsFrom, relObj, {qn})

    def viewRelationships(self, parentNode, relationshipsFrom, relObj, visited):
        target = relObj.target
        targetObj = self.xbrlCompMdl.namedObjects.get(target)
        if targetObj is None:
            return
        loop = target in visited
        node = self.insertRow(parentNode, targetObj, textPrefix="(loop) " if loop else "")
        if loop:
            return
        visited.add(target)
        for relTgtObj in relationshipsFrom.get(target, ()):
            self.viewRelationships(node, relationshipsFrom, relTgtObj, visited)
        visited.discard(target)

    # ── interaction ────────────────────────────────────────────────────

    def getToolTip(self, rowId, colId):
        """Hovering a cell that was shortened to fit shows its full text; the detail column shows
           its name=value pairs one per line; anything else falls back to the base view's own
           tooltip (the displayed value, when it is clipped)."""
        if rowId and colId and colId != "#0":
            try:
                colName = self.colNames[int(colId[1:]) - 1]
            except (ValueError, IndexError):
                return None
            if colName == "detail":
                # the detail cell packs several properties as "a=1; b=2"; one per line reads far
                # more easily in the tooltip than the single wrapped run the base view would show
                detail = self.treeView.set(rowId, "detail")
                return detail.replace("; ", "\n") if detail else None
            return self.fullCellText.get((rowId, colName))
        return None

    def sortNestedRows(self, parentNode, col, reverse):
        # A tree pane's child rows carry meaning in their order -- group tree order, cube
        # dimension order, relationship order, import order -- so only its top-level rows sort.
        if self.isTreePane and parentNode != '':
            return
        super(ViewXbrlTxmyObj, self).sortNestedRows(parentNode, col, reverse)

    def objectForNode(self, node):
        """The taxonomy object a tree row stands for, or None for a grouping row such as
           "(ungrouped)". Object rows carry the object index as the tail of their node id."""
        if node and node.startswith("_"):
            try:
                return self.xbrlCompMdl.xbrlObjects[int(node.rpartition("_")[2])]
            except (ValueError, IndexError):
                return None
        return None

    def menuAddCopyJson(self):
        if self.menu and self.modelXbrl.modelManager.cntlr.hasClipboard:
            self.menu.add_command(label=_("Copy JSON"), underline=5, command=self.copyJsonToClipboard)

    def copyJsonToClipboard(self, *ignore):
        obj = self.objectForNode(getattr(self, "menuRow", None))
        if obj is not None:
            js = objectJson(obj)
            if js:
                self.modelXbrl.modelManager.cntlr.clipboardData(text=js)

    def menuAddFind(self):
        if self.menu:
            self.menu.add_command(label=_("Find..."), underline=0, command=self.find)

    def find(self):
        from tkinter.simpledialog import askstring
        pattern = askstring(_("Find"), _("Find in {0}").format(self.tabTitle),
                            initialvalue=self.findPattern, parent=self.viewFrame)
        if not pattern:
            return
        self.findPattern = pattern
        pattern = pattern.lower()
        nodes = []
        self.findNodes("", nodes)
        selection = self.treeView.selection()
        # resume after the current selection so repeating Find walks through the matches
        start = (nodes.index(selection[0]) + 1) if (selection and selection[0] in nodes) else 0
        for node in nodes[start:] + nodes[:start]:
            values = [self.treeView.item(node, "text")] + [self.treeView.set(node, c) for c in self.colNames]
            if any(pattern in str(value).lower() for value in values):
                self.setTreeItemOpenToRoot(node)
                self.treeView.see(node)
                self.treeView.selection_set(node)
                return
        self.modelXbrl.modelManager.cntlr.showStatus(_("{0} not found in {1}").format(self.findPattern, self.tabTitle), 5000)

    def findNodes(self, parentNode, nodes):
        for node in self.treeView.get_children(parentNode):
            nodes.append(node)
            self.findNodes(node, nodes)

    def setTreeItemOpenToRoot(self, node):
        """Open a found node's ancestors so see() can scroll it into view."""
        parentNode = self.treeView.parent(node)
        while parentNode:
            self.treeView.item(parentNode, open=True)
            parentNode = self.treeView.parent(parentNode)

    def treeviewEnter(self, *args):
        self.blockSelectEvent = 0

    def treeviewLeave(self, *args):
        self.blockSelectEvent = 1

    def treeviewSelect(self, event):
        if self.blockSelectEvent == 0 and self.blockViewModelObject == 0:
            self.blockViewModelObject += 1
            selection = self.treeView.selection()
            # only object rows have an object id; grouping rows such as "(ungrouped)" do not
            if selection and selection[0].startswith("_"):
                self.xbrlCompMdl.viewTaxonomyObject(selection[0])
            self.blockViewModelObject -= 1

    def viewModelObject(self, txmyObj):
        if self.blockViewModelObject == 0:
            self.blockViewModelObject += 1
            try:
                if not self._revealObject(txmyObj) and isinstance(txmyObj, XbrlFact):
                    # a fact has no row in the concept / network / unit panes; reveal a related
                    # object that does (its concept, member, unit) so selecting a fact syncs them
                    for memberObj in self.factDimensionMembers(txmyObj):
                        if self._revealObject(memberObj):
                            break
            except (AttributeError, KeyError, ValueError):
                    self.treeView.selection_set(())
            self.blockViewModelObject -= 1

    def _revealObject(self, txmyObj):
        """Scroll to and select the row for txmyObj, if this pane has one. Returns True if found."""
        items = self.tag_has.get(f"_{getattr(txmyObj, 'xbrlMdlObjIndex', None)}")
        if items:
            for item in items:
                if self.treeView.exists(item):
                    self.setTreeItemOpenToRoot(item)
                    self.treeView.see(item)
                    self.treeView.selection_set(item)
                    return True
        return False


def viewXbrlObjectJson(xbrlCompMdl, tabWin):
    """Create the JSON pane: a read-only text view of the selected object's compiled JSON, sitting
       in the upper-left tab window beside the Properties pane. Registered as a model view so
       `viewTaxonomyObject` updates it on selection like every other pane. One per model."""
    ViewXbrlObjectJson(xbrlCompMdl, tabWin)


class ViewXbrlObjectJson:
    """Read-only JSON view of the currently selected taxonomy object.

    Not a tree, so it does not subclass ViewWinTree.ViewTree; it replicates only the frame
    registration ViewTree does (add a tab, join modelXbrl.views, remove on close) and renders
    the selected object via `objectJson`. Being in modelXbrl.views is what makes
    `viewTaxonomyObject` -> `viewModelObject` reach it on every selection.
    """
    def __init__(self, xbrlCompMdl, tabWin):
        from tkinter import Frame, Text, Scrollbar, Menu, N, S, E, W, VERTICAL, HORIZONTAL, END, DISABLED, NORMAL
        self._END, self._DISABLED, self._NORMAL = END, DISABLED, NORMAL
        self.modelXbrl = xbrlCompMdl
        self.xbrlCompMdl = xbrlCompMdl
        self.tabWin = tabWin
        self.tabTitle = "JSON"
        self.viewFrame = Frame(tabWin)
        self.viewFrame.view = self
        self.viewFrame.grid(row=0, column=0, sticky=(N, S, E, W))
        tabWin.add(self.viewFrame, text=self.tabTitle)
        vScrollbar = Scrollbar(self.viewFrame, orient=VERTICAL)
        hScrollbar = Scrollbar(self.viewFrame, orient=HORIZONTAL)
        self.text = Text(self.viewFrame, wrap="none", font=("Courier", 11),
                         yscrollcommand=vScrollbar.set, xscrollcommand=hScrollbar.set)
        self.text.grid(row=0, column=0, sticky=(N, S, E, W))
        hScrollbar["command"] = self.text.xview
        hScrollbar.grid(row=1, column=0, sticky=(E, W))
        vScrollbar["command"] = self.text.yview
        vScrollbar.grid(row=0, column=1, sticky=(N, S))
        self.viewFrame.columnconfigure(0, weight=1)
        self.viewFrame.rowconfigure(0, weight=1)
        # right-click copies the whole JSON (the text is read-only, so give an explicit copy path)
        self.menu = Menu(self.viewFrame, tearoff=0)
        self.menu.add_command(label=_("Copy"), underline=0, command=self.copyToClipboard)
        self.text.bind(xbrlCompMdl.modelManager.cntlr.contextMenuClick, self._popUpMenu, "+")
        self.text.configure(state=DISABLED)
        xbrlCompMdl.views.append(self)

    def _setText(self, s):
        self.text.configure(state=self._NORMAL)
        self.text.delete("1.0", self._END)
        self.text.insert(self._END, s)
        self.text.configure(state=self._DISABLED)

    def _popUpMenu(self, event):
        self.menu.post(event.x_root, event.y_root)

    def copyToClipboard(self, *ignore):
        text = self.text.get("1.0", self._END).rstrip("\n")
        if text:
            self.modelXbrl.modelManager.cntlr.clipboardData(text=text)

    def viewModelObject(self, txmyObj):
        self._setText(objectJson(txmyObj))

    def select(self):
        self.tabWin.select(self.viewFrame)

    def close(self, *ignore):
        if self.modelXbrl is not None:
            try:
                del self.viewFrame.view
                self.tabWin.forget(self.viewFrame)
                self.modelXbrl.views.remove(self)
            except (ValueError, AttributeError):
                pass
            self.modelXbrl = None
