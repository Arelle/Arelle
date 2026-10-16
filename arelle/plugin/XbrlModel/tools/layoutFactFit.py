# Copyright Exbee Ltd 2026
# License Apache 2
"""
layoutFactFit.py -- place a module's facts in the cells of its gridLayout data tables

Purpose
-------
A reference for the fact-to-cell rule that the layout viewers implement, and a check of a
generated layout against real facts (``eiopaInstanceFacts.py`` attaches them).

The rule, for a ``gridLayout`` data table:

* A cell's dimensions are the union of its x axis item's, its y axis item's, the selected z
  axis item's, and those of any ``tablePoints`` entry at its grid coordinates.
* An x or y ``axisGroup`` with no ``axisNetwork`` is a key column (or row) of an open table:
  each row holds, in that column, a member of the group's dimension, taken from the facts.
  The table's rows are the distinct combinations of key values among the facts.
* A z ``axisGroup`` is a dimension the reader selects a member of (from its ``axisNetwork``,
  or with none, from the facts), so every fact is in the table for its own member.
* A fact is in a cell when it has every one of the cell's dimensions with the same value, its
  key dimensions equal the row's key values, and it has no other dimension except
  ``xbrl:period``, ``xbrl:entity``, ``xbrl:unit`` and ``xbrl:language``.

The report counts, per table, the facts whose concept appears in the table and how many found
a cell.  For the rest it counts the dimensions that kept them out: ``extra`` (the fact has a
dimension no cell has), ``missing`` (a cell dimension the fact lacks), ``value`` (a
dimension whose value no cell uses).  Those point at what the generator dropped.

Usage
-----
::

    python3 layoutFactFit.py <module-with-facts.json> [<table name> ...]
"""
import json
import sys
from collections import Counter, defaultdict

CORE_DIMENSIONS = {"xbrl:period", "xbrl:entity", "xbrl:unit", "xbrl:language"}


def axisItems(axis):
    return ((axis or {}).get("gridAxis") or {}).get("axisItems") or []


def keyDimensions(axis):
    """Dimensions of the axis groups without a network: an open table's key columns."""
    return [g["dimensionName"] for g in ((axis or {}).get("gridAxis") or {}).get("axisGroups") or []
            if g.get("dimensionName") and not g.get("axisNetwork")]


def tableCells(table):
    """Yield (zAxisId, xAxisId, yAxisId, cellDimensions) for each cell of a gridLayout table.

    An axis with no axis items contributes one empty item, so a table with no y items (an
    open table, whose rows come from the facts) still has one cell per column."""
    keyAxisIds = {aid for axis in (table.get("xAxis"), table.get("yAxis"))
                  for g in ((axis or {}).get("gridAxis") or {}).get("axisGroups") or [] for aid in g.get("axisIds", ())}
    zs = axisItems(table.get("zAxis")) or [{}]
    xs = [i for i in axisItems(table.get("xAxis")) if i.get("axisId") not in keyAxisIds] or [{}]
    ys = [i for i in axisItems(table.get("yAxis")) if i.get("axisId") not in keyAxisIds] or [{}]
    allXs, allYs = axisItems(table.get("xAxis")), axisItems(table.get("yAxis"))
    for z in zs:
        for y in ys:
            for x in xs:
                dims = {}
                for item in (z, x, y):
                    dims.update(item.get("dimensions") or {})
                for point in table.get("tablePoints") or ():
                    coords = point.get("gridCoordinates") or {}
                    # tablePoints are 1-based positions on each axis
                    if "xAxis" in coords and str(coords["xAxis"]) != str(allXs.index(x) + 1 if x in allXs else 0):
                        continue
                    if "yAxis" in coords and str(coords["yAxis"]) != str(allYs.index(y) + 1 if y in allYs else 0):
                        continue
                    dims.update(point.get("dimensions") or {})
                yield z.get("axisId"), x.get("axisId"), y.get("axisId"), dims


def fitTable(table, facts):
    cells = list(tableCells(table))
    keyDims = keyDimensions(table.get("xAxis")) + keyDimensions(table.get("yAxis"))
    zGroupDims = [g["dimensionName"] for g in ((table.get("zAxis") or {}).get("gridAxis") or {}).get("axisGroups") or ()]
    tableConcepts = {c[3].get("xbrl:concept") for c in cells} - {None}
    cellValues = defaultdict(set)
    for *_, dims in cells:
        for d, v in dims.items():
            cellValues[d].add(v)
    placed, rows, multi = {}, set(), 0
    why = Counter()
    candidates = [f for f in facts if f["factDimensions"].get("xbrl:concept") in tableConcepts]
    for fact in candidates:
        fd = fact["factDimensions"]
        hits = [c for c in cells
                if all(fd.get(d) == v for d, v in c[3].items())
                and all(d in c[3] or d in CORE_DIMENSIONS or d in keyDims or d in zGroupDims for d in fd)]
        if hits:
            placed[fact["name"]] = hits[0][:3]
            rows.add(tuple(fd.get(d) for d in keyDims))
            multi += len(hits) > 1
            continue
        for d in fd:
            if d not in cellValues and d not in CORE_DIMENSIONS and d not in keyDims and d not in zGroupDims:
                why[f"extra {d}"] += 1
            elif d in cellValues and fd[d] not in cellValues[d]:
                why[f"value {d}={fd[d]}"] += 1
        for d in cellValues:
            if d not in fd and all(d in c[3] for c in cells):
                why[f"missing {d}"] += 1
    return {"cells": len(cells), "facts": len(candidates), "placed": len(placed),
            "openRows": len(rows) if keyDims else None, "multiCell": multi, "why": why}


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__.split("Usage\n-----\n::\n")[1].strip())
    with open(argv[1], encoding="utf-8") as fh:
        model = json.load(fh)["xbrlModel"]
    facts = model.get("facts") or []
    only = set(argv[2:])
    for layout in model.get("layouts") or ():
        for table in layout.get("dataTables") or ():
            if table.get("tableType") != "gridLayout" or (only and table["name"] not in only):
                continue
            r = fitTable(table, facts)
            rows = f", {r['openRows']} open-table rows" if r["openRows"] is not None else ""
            print(f"{table['name']}: {r['placed']} of {r['facts']} facts in {r['cells']} cells{rows}"
                  + (f", {r['multiCell']} in more than one cell" if r["multiCell"] else ""))
            for reason, n in r["why"].most_common(8):
                print(f"    {n:5d} {reason}")


if __name__ == "__main__":
    main(sys.argv)
