'''
Verify the error codes used in the OIM-taxonomy conformance test index
(xbrl-model-tests.xml) against the specs that DEFINE those codes, and report any
code that is used by a test but not defined by its owning spec.

Run after regenerating the index with oimTxmyTestIndex.py.

Where each error prefix is defined (authoritative local sources):
  oimte:  / oime:   -> oim-taxonomy/oim-taxonomy.md          (plain text mention)
  oimce:            -> oim-common/oim-common.xml              (<error id="localName">)
  calc11e:          -> oim-taxonomy/spec-taxonomies/calc11e.json  (member "name" values)

For any undefined code the report also checks whether the SAME localName is
defined under a different prefix (a prefix-mismatch, e.g. an oimte:* calculation
code that is really calc11e:*).

Codes in the index come from two places: references in the error taxonomies
(oimte/oime/oimce.json forObjects) and, for otherwise-unreferenced tests, the
test file's documentInfo/description (see oimTxmyTestIndex.py). So an "undefined"
finding is usually a wrong prefix or a missing spec definition in a description.
'''
import os, re, json
from collections import defaultdict

SPECS = "/Users/hermf/Documents/projects/XBRL.org/oim/specifications"
TEST_INDEX = os.path.join(SPECS, "oim-taxonomy/conformance/xbrl-model-tests.xml")
TAXONOMY_MD = os.path.join(SPECS, "oim-taxonomy/oim-taxonomy.md")
OIM_COMMON_XML = os.path.join(SPECS, "oim-common/oim-common.xml")
CALC11E_JSON = os.path.join(SPECS, "oim-taxonomy/spec-taxonomies/calc11e.json")

# --- collect code -> {test file ids} from the generated test index ---
variationRe = re.compile(r'<variation id="([^"]+)">.*?<result>(.*?)</result>', re.S)
errorRe = re.compile(r'<error>([^<]+)</error>')
codeFiles = defaultdict(set)
xml = open(TEST_INDEX).read()
for m in variationRe.finditer(xml):
    vid, result = m.group(1), m.group(2)
    for code in errorRe.findall(result):
        if code.startswith("tbd"):
            continue
        codeFiles[code].add(vid)

# --- defined-code sources ---
taxonomyText = open(TAXONOMY_MD).read()
oimceIds = set(re.findall(r'<error id="([^"]+)"', open(OIM_COMMON_XML).read()))
calc = json.load(open(CALC11E_JSON))
calc11eLocalNames = {m["name"].split(":", 1)[1]
                     for m in calc["xbrlModel"].get("members", ()) if m.get("name")}

def isDefined(code):
    prefix, localName = code.split(":", 1)
    if prefix in ("oimte", "oime"):
        return code in taxonomyText
    if prefix == "oimce":
        return localName in oimceIds or code in taxonomyText
    if prefix == "calc11e":
        return localName in calc11eLocalNames
    return True  # non-OIM prefixes (e.g. arelle:) not checked here

def definedElsewhere(localName):
    '''Return a hint if this localName is defined under a different prefix.'''
    hints = []
    if localName in calc11eLocalNames:
        hints.append(f"calc11e:{localName}")
    if localName in oimceIds:
        hints.append(f"oimce:{localName}")
    if re.search(r'[a-z0-9]+:' + re.escape(localName), taxonomyText):
        hints.append(f"(some prefix):{localName} in oim-taxonomy.md")
    return hints

# --- report ---
undefinedByPrefix = defaultdict(list)
for code in sorted(codeFiles):
    if code.split(":", 1)[0] in ("oimte", "oime", "oimce", "calc11e") and not isDefined(code):
        undefinedByPrefix[code.split(":", 1)[0]].append(code)

print(f"Checked {TEST_INDEX}")
total = 0
for prefix in ("oimte", "oime", "oimce", "calc11e"):
    used = sorted(c for c in codeFiles if c.startswith(prefix + ":"))
    undef = undefinedByPrefix.get(prefix, [])
    total += len(undef)
    print(f"\n{prefix}: {len(used)} used, {len(undef)} undefined by spec")
    for code in undef:
        localName = code.split(":", 1)[1]
        hints = definedElsewhere(localName)
        hintStr = f"  [defined as: {', '.join(hints)}]" if hints else "  [not defined under any prefix]"
        print(f"   {code}{hintStr}")
        for f in sorted(codeFiles[code]):
            print(f"       {f}")

print(f"\nTOTAL undefined OIM/calc codes: {total}")
