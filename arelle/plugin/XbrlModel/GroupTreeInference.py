"""
See COPYRIGHT.md for copyright information.

Group tree inference for the legacy taxonomy loader.

A legacy XBRL 2.1 DTS carries no explicit cross-role organisation -- the section
hierarchy that SEC's interactive-data viewer (and our ixbrl-viewer cube view) render as
an accordion is *derived* from role-naming conventions. This module reconstructs that
hierarchy as an OIM <<group tree object>> (``xbrl:taxonomy-group`` relationships) so both
object-semantics consumers and viewers can drill down through sections rather than facing
a flat list of cubes.

Two jurisdiction strategies, selected by which base taxonomy the resolved DTS contains:

  * ``SEC``  -- when a ``dei:`` namespace is present (the filing went to EDGAR, even for
                an IFRS filer). Ports the classification in EDGAR/render/Summary.py: an
                ordered finite-state machine over each role's definition text
                (``NNNN - Statement|Disclosure|Document - name``) assigns
                Cover / Statements / Notes / Policies / Tables / Details, and
                Policies/Tables/Details nest under their related note by lexical-prefix
                ("paternity") similarity.
  * ``IFRS`` -- when an IFRS namespace is present. Deterministic: the ``[NNNNNN]`` role
                number embedded in the definition orders the roles, and its range maps to
                a top-level node (general ``[1xxxxx]`` / statements ``[2xxxxx]``-``[7xxxxx]``
                / notes ``[8xxxxx]``).

When neither base taxonomy is present, no group tree is produced and the caller emits a
flat group listing (the viewer falls back to a flat cube view).

``xbrl:taxonomy-group`` relationships MUST target a <<group object>> QName
(oimte:invalidTaxonomyGroupTarget), so the intermediate *category* nodes (Cover,
Statements, ...) -- which are not roles -- are synthesised as abstract group objects with
labels and returned to the caller to emit alongside the per-role groups. Every top-level
relationship is anchored to xbrl:rootSource (oim-taxonomy §group tree object).
"""
from __future__ import annotations

import re
from typing import Optional

# Root anchor for top-level groups in a group tree (oim-taxonomy §group tree object): the
# taxonomy-group `source` of a top-level group is xbrl:rootSource, not the model QName, so a
# tree imported from a base taxonomy re-homes under the importing model without rewriting.
_ROOT_SOURCE = "xbrl:rootSource"

# ---- strategy detection -----------------------------------------------------------------

_DEI_NS_HINT = "xbrl.sec.gov/dei"
_IFRS_NS_HINT = "xbrl.ifrs.org"


def _dtsNamespaces(modelXbrl) -> set[str]:
    """Every namespace URI reachable in the resolved DTS: prefix bindings plus the
    namespaces of declared concepts (a base taxonomy is always present as one or both)."""
    nss = set((getattr(modelXbrl, "prefixedNamespaces", None) or {}).values())
    for qn in getattr(modelXbrl, "qnameConcepts", {}) or {}:
        if qn is not None and qn.namespaceURI:
            nss.add(qn.namespaceURI)
    return nss


def _detectStrategy(modelXbrl) -> Optional[str]:
    nss = _dtsNamespaces(modelXbrl)
    # dei wins even for an IFRS filer: dei means the report was filed to EDGAR, so EDGAR
    # rendering conventions are what a consumer/viewer expects.
    if any(_DEI_NS_HINT in ns for ns in nss):
        return "SEC"
    if any(_IFRS_NS_HINT in ns for ns in nss):
        return "IFRS"
    return None


def _roleDefinition(modelXbrl, roleUri: str) -> str:
    for rt in (getattr(modelXbrl, "roleTypes", {}).get(roleUri) or ()):
        d = getattr(rt, "definition", None)
        if d:
            return d
    return roleUri


# ---- shared tree assembly ---------------------------------------------------------------

def _prefixOf(qname: str) -> str:
    return qname.partition(":")[0]


def _catGroupName(prefix: str, cat: str) -> str:
    return f"{prefix}:group_cat_{re.sub(r'[^0-9A-Za-z]+', '', cat)}"


class _TreeBuilder:
    """Accumulates synthesised category groups (created lazily, once each) and the ordered
    taxonomy-group relationships, keeping every top-level category rooted at the model."""
    def __init__(self, modelName: str, catLabels: dict[str, str]):
        self.modelName = modelName
        self.prefix = _prefixOf(modelName)
        self.catLabels = catLabels
        self.extraGroups: list[dict] = []
        self.extraLabels: list[dict] = []
        self._catGroup: dict[str, str] = {}      # category -> synthesised group QName
        self._catOrder: list[str] = []           # categories in first-seen order
        self._childrenOf: dict[str, list[str]] = {}  # sourceGroup -> [targetGroup...]

    def category(self, cat: str) -> str:
        """The group QName for a category, synthesising the group + label on first use."""
        g = self._catGroup.get(cat)
        if g is None:
            g = _catGroupName(self.prefix, cat)
            self._catGroup[cat] = g
            self._catOrder.append(cat)
            self.extraGroups.append({"name": g})
            self.extraLabels.append({"forObject": g, "language": "en",
                                     "value": self.catLabels.get(cat, cat),
                                     "labelType": "xbrl:label"})
        return g

    def add(self, sourceGroup: str, targetGroup: str) -> None:
        self._childrenOf.setdefault(sourceGroup, []).append(targetGroup)

    def groupTree(self, canonicalOrder: list[str]) -> Optional[dict]:
        """Emit relationships: xbrl:rootSource -> category (in canonicalOrder), then each
        parent -> its children in insertion order. Returns None when nothing was placed.
        Top-level groups are anchored to xbrl:rootSource per oim-taxonomy §group tree object
        (the root source, not the model QName, so an imported tree re-homes cleanly)."""
        rels: list[dict] = []
        order = 0
        seenCats = [c for c in canonicalOrder if c in self._catGroup]
        seenCats += [c for c in self._catOrder if c not in canonicalOrder]
        for cat in seenCats:
            order += 1
            rels.append({"source": _ROOT_SOURCE, "target": self._catGroup[cat], "order": order})
        for sourceGroup, targets in self._childrenOf.items():
            for i, tgt in enumerate(targets, start=1):
                rels.append({"source": sourceGroup, "target": tgt, "order": i})
        if not rels:
            return None
        treeLocal = self.modelName.partition(":")[2] or "model"
        return {"name": f"{self.prefix}:{treeLocal}GroupTree", "relationships": rels}


# ---- SEC strategy (ported from EDGAR/render/Summary.py) ---------------------------------

_secStatement = re.compile(r'.* +\- +Statement +\- .*')
_secDisclosure = re.compile(r'.* +\- +Disclosure +\- +.*')
_secDocument = re.compile(r'.* +\- +Document +\- +.*')
_secParenthetical = re.compile(r'.*\-.+-.*Paren.+')
_secPolicy = re.compile(r'.*\(.*Polic.*\).*')
_secTable = re.compile(r'.*\(Table.*\).*')
_secDetail = re.compile(r'.*\(Detail.*\).*')
_secShortName = re.compile(r'^\s*[\d.]+\s*-\s*(?:Statement|Disclosure|Schedule|Document)\s*-\s*(.*\S)\s*$')

_SEC_CAT_LABELS = {
    "Cover": "Cover", "Statements": "Financial Statements",
    "Notes": "Notes to Financial Statements", "Policies": "Accounting Policies",
    "Tables": "Notes Tables", "Details": "Notes Details", "Uncategorized": "Uncategorized",
}
_SEC_ORDER = ["Cover", "Statements", "Notes", "Policies", "Tables", "Details", "Uncategorized"]


def _isStatement(n): return _secStatement.match(n) is not None
def _isDisclosure(n): return _secDisclosure.match(n) is not None
def _isDocument(n): return _secDocument.match(n) is not None
def _isParenthetical(n): return _secParenthetical.match(n) is not None
def _isPolicy(n): return _secPolicy.match(n) is not None
def _isTable(n): return _secTable.match(n) is not None
def _isDetail(n): return _secDetail.match(n) is not None
def _isUncategorized(n): return n == 'UncategorizedItems'


def _secClassify(state: str, longName: str) -> str:
    """The EDGAR finite-state machine: current category given the previous one and this
    role's definition text. Faithful to Summary.classifyReportFiniteStateMachine (the
    Risk/Return fund path is intentionally omitted -- those forms are not compiled here)."""
    Cover, Statements, Notes = 'Cover', 'Statements', 'Notes'
    Policies, Tables, Details, Uncat = 'Policies', 'Tables', 'Details', 'Uncategorized'
    if state in ('', Uncat):
        if _isUncategorized(longName): return Uncat
        if _isParenthetical(longName): return Cover
        if _isStatement(longName): return Statements
        if _isPolicy(longName): return Notes
        if _isTable(longName): return Tables
        if _isDetail(longName): return Details
        return Cover
    if state == Cover:
        if _isUncategorized(longName): return Uncat
        if _isStatement(longName): return Statements
        if _isParenthetical(longName) or _isDocument(longName): return Cover
        if _isPolicy(longName): return Notes
        if _isTable(longName): return Tables
        if _isDetail(longName): return Details
        return Notes
    if state == Statements:
        if _isUncategorized(longName): return Uncat
        if _isStatement(longName) or _isParenthetical(longName): return Statements
        if _isPolicy(longName): return Notes
        if _isTable(longName): return Tables
        if _isDetail(longName): return Details
        return Notes
    if state == Notes:
        if _isPolicy(longName): return Policies
        if _isTable(longName): return Tables
        if _isDetail(longName): return Details
        if _isDisclosure(longName): return Notes
        return Uncat
    if state == Policies:
        if _isUncategorized(longName): return Uncat
        if _isTable(longName): return Tables
        if _isDetail(longName): return Details
        if _isParenthetical(longName) or _isPolicy(longName): return Policies
        return Uncat
    if state == Tables:
        if _isUncategorized(longName): return Uncat
        if _isDetail(longName): return Details
        if _isParenthetical(longName) or _isTable(longName): return Tables
        return Uncat
    if state == Details:
        if _isUncategorized(longName): return Uncat
        if _isParenthetical(longName) or _isDetail(longName): return Details
        return Uncat
    return Uncat


def _shortName(longName: str) -> str:
    m = _secShortName.match(longName)
    return m.group(1) if m else longName


def _commonPrefix(a: str, b: str) -> int:
    i = 0
    for c in a:
        if i < len(b) and b[i] == c:
            i += 1
        else:
            break
    return i


def _paternityScore(parentShort: str, childShort: str) -> float:
    parentShort = parentShort.split(' (')[0]
    childShort = childShort.split(' (')[0]
    if not childShort:
        return 0
    return _commonPrefix(parentShort, childShort) * 100 / len(childShort)


def _secSortKey(defn: str, roleUri: str):
    m = re.match(r'\s*(\d+(?:\.\d+)*)', defn)
    return (0, [int(p) for p in m.group(1).split('.')], roleUri) if m else (1, [], roleUri)


def _secGroupTree(modelXbrl, modelName, roleGroups):
    tb = _TreeBuilder(modelName, _SEC_CAT_LABELS)
    threshold = 75
    # roles in SEC sort-number order (document order), not the caller's roleUri sort.
    ordered = sorted(((roleUri, g, _roleDefinition(modelXbrl, roleUri)) for roleUri, g in roleGroups),
                     key=lambda t: _secSortKey(t[2], t[0]))
    # paternity bookkeeping, mirroring Summary.getReportParentIfExists
    level1PolicyNote: list[tuple] = []   # the first "...Accounting..." note (>=1 by construction)
    level1OtherNotes: list[tuple] = []
    level2PolicyNotes: list[tuple] = []
    level3TableNotes: list[tuple] = []

    def _parentIn(childShort, candidates) -> Optional[str]:
        for shortName, g in candidates:
            if _paternityScore(shortName, childShort) >= threshold:
                return g
        return None

    state = ''
    for roleUri, g, defn in ordered:
        state = _secClassify(state, defn)
        short = _shortName(defn)
        parentGroup = None
        if state == 'Notes':
            if re.match(r'.*Accounting.*', defn) and not level1PolicyNote:
                level1PolicyNote.append((short, g))
            else:
                level1OtherNotes.append((short, g))
        elif state == 'Policies':
            level2PolicyNotes.append((short, g))
            if level1PolicyNote:
                parentGroup = level1PolicyNote[0][1]
        elif state == 'Tables':
            level3TableNotes.append((short, g))
            parentGroup = _parentIn(short, level1PolicyNote + level1OtherNotes)
        elif state == 'Details':
            parentGroup = _parentIn(short, level3TableNotes + level2PolicyNotes + level1OtherNotes)
        tb.add(parentGroup or tb.category(state), g)
    return tb.groupTree(_SEC_ORDER), tb.extraGroups, tb.extraLabels


# ---- IFRS strategy ----------------------------------------------------------------------

_IFRS_CAT_LABELS = {
    "General": "General Information", "Statements": "Primary Financial Statements",
    "Notes": "Notes", "Other": "Other",
}
_IFRS_ORDER = ["General", "Statements", "Notes", "Other"]
_ifrsNumRe = re.compile(r'\[(\d{6})\]')


def _ifrsNum(defn: str) -> Optional[int]:
    m = _ifrsNumRe.search(defn)
    return int(m.group(1)) if m else None


def _ifrsCategory(num: Optional[int]) -> str:
    if num is None:
        return "Other"
    if num < 200000:
        return "General"
    if num < 800000:
        return "Statements"
    return "Notes"


def _ifrsGroupTree(modelXbrl, modelName, roleGroups):
    tb = _TreeBuilder(modelName, _IFRS_CAT_LABELS)
    triples = [(roleUri, g, _roleDefinition(modelXbrl, roleUri)) for roleUri, g in roleGroups]
    # numbered roles in [NNNNNN] order; un-numbered (typically filer extension roles) after.
    triples.sort(key=lambda t: (_ifrsNum(t[2]) is None, _ifrsNum(t[2]) or 0, t[0]))
    for roleUri, g, defn in triples:
        tb.add(tb.category(_ifrsCategory(_ifrsNum(defn))), g)
    return tb.groupTree(_IFRS_ORDER), tb.extraGroups, tb.extraLabels


# ---- public entry -----------------------------------------------------------------------

def inferGroupTree(modelXbrl, modelName: str, roleGroups: list[tuple[str, str]]):
    """Infer a group tree for the emitted compiled model.

    ``modelName``  -- the model's QName string; the root source of top-level relationships.
    ``roleGroups`` -- ``[(roleUri, groupName), ...]`` for the per-role groups already emitted.

    Returns ``(groupTree | None, extraGroups, extraLabels)``: the group tree dict (a
    ``groupTree`` singleton), any synthesised category group objects, and their labels.
    Returns ``(None, [], [])`` when no jurisdiction strategy applies."""
    strategy = _detectStrategy(modelXbrl)
    if strategy is None or not roleGroups:
        return None, [], []
    builder = _secGroupTree if strategy == "SEC" else _ifrsGroupTree
    tree, extraGroups, extraLabels = builder(modelXbrl, modelName, roleGroups)
    if tree is None:
        return None, [], []
    return tree, extraGroups, extraLabels
