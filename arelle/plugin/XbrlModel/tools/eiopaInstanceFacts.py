# Copyright Exbee Ltd 2026
# License Apache 2
"""
eiopaInstanceFacts.py -- EIOPA XBRL 2.1 sample instance to OIM facts in a generated module's names

Purpose
-------
``tlbTemplate-eiopa.py`` folds every object of the EIOPA DPM into one ``eiopa:`` namespace,
keeping the source prefix in the local name (a module may only define objects in its own
namespace).  EIOPA's published sample instances use the source names.  This script converts
an instance's facts onto the generated names, so they can be attached to a generated module
and shown in its layouts, and so Arelle validation of that module checks the generator: a
fact that fits no generated cube reports ``oimte:noFactSpaceForFact``.

The fold is fixed:

=============================================================  ==================================
instance                                                       generated module
=============================================================  ==================================
concept ``s2md_met:mi686``                                     ``eiopa:s2md_met_mi686``
dimension ``s2c_dim:EA``                                       ``eiopa:s2c_dim_EA``
member ``s2c_VM:x23``                                          ``eiopa:s2c_VM_x23``
enumerated value ``s2c_GA:SI``                                 ``eiopa:s2c_GA_SI``
typed member ``<xbrldi:typedMember dimension="s2c_dim:PX">``   ``"eiopa:s2c_dim_PX": "v"``
=============================================================  ==================================

The instance is parsed as plain XML: the fold is syntactic, so the EIOPA taxonomy (which
is not downloaded) is not needed.  Periods, units and decimals follow the xBRL-XML mapping
as ``LoadFactsCommon`` implements it (an instant date is the end of that day, so
``2026-12-31`` becomes ``2027-01-01T00:00:00``; a lone ``xbrli:pure`` unit is no unit).

Usage
-----
::

    python3 eiopaInstanceFacts.py <instance.xbrl> <out.json> [<module.json>]

Without a module, ``out.json`` is a JSON array of facts.  With a module, ``out.json`` is
that module with ``xbrlModel.facts`` set to the facts whose concept, dimensions and explicit
members the module defines (a single-table module defines only that table's), and with the namespace
prefixes the facts use (entity scheme, unit measures) added to ``documentInfo``.
"""
import json
import re
import sys
from datetime import date, timedelta

from lxml import etree

XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDI = "http://xbrl.org/2006/xbrldi"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
FIND = "http://www.eurofiling.info/xbrl/ext/filing-indicators"
EIOPA_NS_PREFIX = "http://eiopa.europa.eu/xbrl/"  # every EIOPA DPM namespace starts with this
FOLD_PREFIX = "eiopa"

# Entity schemes and unit namespaces get these prefixes in the module (the instance's own
# prefixes are used for anything else).
KNOWN_PREFIXES = {
    "http://standards.iso.org/iso/17442": "lei",
    "http://www.xbrl.org/2003/iso4217": "iso4217",
}
QNAME_VALUE = re.compile(r"^([A-Za-z_][\w.-]*):([A-Za-z_][\w.-]*)$")


def fold(prefix, localName):
    """``s2c_VM`` + ``x23`` -> ``eiopa:s2c_VM_x23``."""
    return f"{FOLD_PREFIX}:{prefix}_{localName}"


def foldQName(text, nsmap):
    """Fold a prefixed name in an EIOPA namespace; return None for anything else."""
    m = QNAME_VALUE.match((text or "").strip())
    if not m:
        return None
    prefix, localName = m.groups()
    ns = nsmap.get(prefix)
    if ns is None or not ns.startswith(EIOPA_NS_PREFIX):
        return None
    return fold(prefix, localName)


def dayAfter(dateStr):
    """End of an XBRL 2.1 date: midnight starting the next day (as LoadFactsCommon.dayAfter)."""
    if "T" in dateStr:
        return dateStr
    y, m, d = (int(p) for p in dateStr.split("-"))
    return (date(y, m, d) + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")


def startOfDay(dateStr):
    return dateStr if "T" in dateStr else dateStr + "T00:00:00"


def oimPeriod(periodElt):
    instant = periodElt.find(f"{{{XBRLI}}}instant")
    if instant is not None:
        return dayAfter(instant.text.strip())
    start = periodElt.find(f"{{{XBRLI}}}startDate")
    end = periodElt.find(f"{{{XBRLI}}}endDate")
    if start is not None and end is not None:
        return f"{startOfDay(start.text.strip())}/{dayAfter(end.text.strip())}"
    return None  # forever: no period dimension


def prefixFor(ns, nsmap, usedPrefixes):
    """Module prefix for a namespace: a known one, else the instance's own."""
    prefix = KNOWN_PREFIXES.get(ns) or next((p for p, u in nsmap.items() if u == ns and p), None) or "ns"
    usedPrefixes[prefix] = ns
    return prefix


def parseContexts(root, usedPrefixes):
    """{contextId: factDimensions without the concept}."""
    contexts = {}
    for ctx in root.iter(f"{{{XBRLI}}}context"):
        dims = {}
        ident = ctx.find(f"{{{XBRLI}}}entity/{{{XBRLI}}}identifier")
        if ident is not None:
            scheme = ident.get("scheme")
            dims["xbrl:entity"] = f"{prefixFor(scheme, ctx.nsmap, usedPrefixes)}:{ident.text.strip()}"
        period = oimPeriod(ctx.find(f"{{{XBRLI}}}period"))
        if period:
            dims["xbrl:period"] = period
        for mem in ctx.iter(f"{{{XBRLDI}}}explicitMember", f"{{{XBRLDI}}}typedMember"):
            dimName = foldQName(mem.get("dimension"), mem.nsmap)
            if dimName is None:
                raise ValueError(f"context {ctx.get('id')}: dimension {mem.get('dimension')} is not an EIOPA name")
            if etree.QName(mem).localname == "explicitMember":
                memName = foldQName(mem.text, mem.nsmap)
                if memName is None:
                    raise ValueError(f"context {ctx.get('id')}: member {mem.text} is not an EIOPA name")
                dims[dimName] = memName
            else:  # the typed value is the text of the typed member's one child element
                dims[dimName] = "".join(mem.itertext()).strip()
        contexts[ctx.get("id")] = dims
    return contexts


def parseUnits(root, usedPrefixes):
    """{unitId: OIM unit string, or None for pure}."""
    def measures(parent):
        names = []
        for m in parent.findall(f"{{{XBRLI}}}measure"):
            prefix, localName = m.text.strip().split(":")
            ns = m.nsmap[prefix]
            if ns == XBRLI and localName == "pure":
                names.append("xbrlr:pure")  # the model's built-in pure unit, as LoadFactsCommon folds it
            else:
                names.append(f"{prefixFor(ns, m.nsmap, usedPrefixes)}:{localName}")
        return sorted(names)

    def emit(names):
        return f"({'*'.join(names)})" if len(names) > 1 else "".join(names)

    units = {}
    for unit in root.iter(f"{{{XBRLI}}}unit"):
        divide = unit.find(f"{{{XBRLI}}}divide")
        if divide is not None:
            num = emit(measures(divide.find(f"{{{XBRLI}}}unitNumerator")))
            den = emit(measures(divide.find(f"{{{XBRLI}}}unitDenominator")))
            units[unit.get("id")] = f"{num}/{den}"
        else:
            names = measures(unit)
            units[unit.get("id")] = None if names == ["xbrlr:pure"] else emit(names)
    return units


def instanceFacts(instancePath):
    """Return (facts, usedPrefixes) for an EIOPA XBRL 2.1 instance."""
    root = etree.parse(instancePath).getroot()
    usedPrefixes = {}
    contexts = parseContexts(root, usedPrefixes)
    units = parseUnits(root, usedPrefixes)
    facts = []
    for elt in root:
        if not isinstance(elt.tag, str) or elt.get("contextRef") is None:
            continue
        qn = etree.QName(elt)
        if qn.namespace == FIND or not qn.namespace.startswith(EIOPA_NS_PREFIX):
            continue
        conceptPrefix = next(p for p, u in elt.nsmap.items() if u == qn.namespace and p)
        dims = {"xbrl:concept": fold(conceptPrefix, qn.localname)}
        dims.update(contexts[elt.get("contextRef")])
        unitRef = elt.get("unitRef")
        if unitRef and units[unitRef]:
            dims["xbrl:unit"] = units[unitRef]
        name = f"{FOLD_PREFIX}:f{len(facts) + 1}"
        factValue = {"name": f"{name}_fv"}  # as LoadXbrlXmlFacts names a fact's value
        fact = {"name": name, "factDimensions": dims, "factValues": [factValue]}
        if elt.get(f"{{{XSI}}}nil") in ("true", "1"):
            fact["properties"] = [{"property": "xbrl:nil", "value": "xbrl:unknownNilReason"}]
        else:
            text = elt.text or ""
            factValue["value"] = foldQName(text, elt.nsmap) or text  # enumerated values are folded too
            decimals = elt.get("decimals")
            if decimals not in (None, "INF"):
                factValue["decimals"] = int(decimals)
        facts.append(fact)
    return facts, usedPrefixes


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__.split("Usage\n-----\n::\n")[1].split("\n\n")[0])
    facts, usedPrefixes = instanceFacts(argv[1])
    if len(argv) > 3:
        with open(argv[3], encoding="utf-8") as fh:
            module = json.load(fh)
        model = module["xbrlModel"]
        concepts = {c["name"] for c in model.get("concepts", ())}
        members = {m["name"] for m in model.get("members", ())}
        # a typed dimension's domain class allows a datatype, not member objects: any value will do
        typedClasses = {c["name"] for c in model.get("domainClasses", ()) if c.get("allowedDomainItem") != "xbrl:memberObject"}
        dimensions = {d["name"]: d.get("domainClass") in typedClasses for d in model.get("dimensions", ())}
        model["facts"] = [f for f in facts if f["factDimensions"]["xbrl:concept"] in concepts
                          and all(d.startswith("xbrl:") or (d in dimensions and (dimensions[d] or v in members))
                                  for d, v in f["factDimensions"].items())]
        namespaces = module["documentInfo"].setdefault("namespaces", {})
        for prefix, ns in usedPrefixes.items():
            namespaces.setdefault(prefix, ns)
        print(f"{len(model['facts'])} of {len(facts)} facts have a concept, dimensions and members of {model.get('name')}")
        out = module
    else:
        print(f"{len(facts)} facts")
        out = facts
    with open(argv[2], "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main(sys.argv)
