"""Generate sec-transform-types.json from SEC's formal transformation registry.

Sources (both in the EDGAR plugin, which is where SEC publishes them):
  transformationRegistry/schema/inlinexbrl-sec-transformation.xsd  -> input dataTypes
  transformationRegistry/registry/ixt-sec-*.xml                    -> transform signatures
                                                                      + documentation
Nothing here is hand-written, so re-running it tracks the registry.
"""
import json, os, re, sys
from collections import OrderedDict
from lxml import etree

REG = "/Users/hermf/Documents/projects/Arelle/ArelleProject/edgrReorg/bin/arelle/plugin/EDGAR/transform/transformationRegistry"
XS = "http://www.w3.org/2001/XMLSchema"
FN = "http://xbrl.org/2008/function"
XHTML = "http://www.w3.org/1999/xhtml"

# ---- input dataTypes from the SEC schema -------------------------------------
dataTypes = OrderedDict()
tree = etree.parse(os.path.join(REG, "schema", "inlinexbrl-sec-transformation.xsd"))
for st in tree.iter("{%s}simpleType" % XS):
    name = st.get("name")
    if not name:
        continue
    restriction = st.find("{%s}restriction" % XS)
    dt = OrderedDict((("name", "ixt-sec:" + name),
                      ("baseType", restriction.get("base") if restriction is not None else "xs:string")))
    patterns = [p.get("value") for p in st.iter("{%s}pattern" % XS) if p.get("value")]
    enums = [e.get("value") for e in st.iter("{%s}enumeration" % XS) if e.get("value") is not None]
    if patterns:
        dt["patterns"] = patterns
    if enums:
        dt["enumeration"] = enums
    dataTypes[dt["name"]] = dt

# ---- transforms + documentation from the registry entries --------------------
def text(elt):
    if elt is None:
        return None
    s = " ".join(" ".join(elt.itertext()).split())
    return s or None

transforms, labels = [], []
for fname in sorted(os.listdir(os.path.join(REG, "registry"))):
    if not fname.startswith("ixt-sec-") or not fname.endswith(".xml"):
        continue
    doc = etree.parse(os.path.join(REG, "registry", fname))
    sig = doc.find("//{%s}signature" % FN)
    if sig is None:
        continue
    name = sig.get("name")
    inp = sig.find("{%s}input" % FN)
    out = sig.find("{%s}output" % FN)
    t = OrderedDict((("name", name),))
    if inp is not None and inp.get("type"):
        t["inputDataType"] = inp.get("type")
    if out is not None and out.get("type"):
        t["outputDataType"] = out.get("type")
    transforms.append(t)
    summary = text(doc.find("//{%s}summary" % FN))
    documentation = text(doc.find("//{%s}documentation" % FN))
    value = " ".join(x for x in (summary, documentation) if x)
    if value:
        labels.append(OrderedDict((("forObject", name), ("language", "en"),
                                   ("labelType", "xbrl:documentation"), ("value", value))))

# keep only the input dataTypes the transforms actually reference
referenced = {t.get("inputDataType") for t in transforms} | {t.get("outputDataType") for t in transforms}
dataTypes = [dt for n, dt in dataTypes.items() if n in referenced]

print("transforms:", len(transforms), " dataTypes:", len(dataTypes), " labels:", len(labels))
print("names:", sorted(t["name"].split(":")[1] for t in transforms))
json.dump({"transforms": transforms, "dataTypes": dataTypes, "labels": labels},
          open(sys.argv[1], "w"), indent=1, ensure_ascii=False)
