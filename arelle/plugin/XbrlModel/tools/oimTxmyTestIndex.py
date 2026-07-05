'''
Create XII style test index file for DQC conf tests

Procedure:

from https://xbrl.us/data-quality/certification/process/



'''
import os, csv, regex as re, json
from openpyxl import load_workbook
from collections import defaultdict

DIR = "/Users/hermf/Documents/projects/XBRL.org/oim/specifications/oim-taxonomy"
TESTINDEX = "xbrl-model-tests.xml"
TESTCASE = os.path.join(DIR, "conformance", TESTINDEX)
# Only .json test-case files are variations; skip supporting files (.html/.md/.xml)
# and the build manifest that also live in the conformance directory.
NON_TESTCASE_FILES = {"manifest.json"}
testcaseFiles = {f for f in os.listdir(os.path.join(DIR, "conformance"))
                 if f.endswith(".json") and f not in NON_TESTCASE_FILES}
origCount = len(testcaseFiles)
fileErrs = defaultdict(list)
for oimErrFile in ("oimte.json", "oime.json", "oimce.json"):
    with open(os.path.join(DIR, "spec-taxonomies", oimErrFile), "r") as fp:
        errorsTxmy = json.load(fp)
    for refObj in errorsTxmy["xbrlModel"]["references"]:
      for propObj in refObj.get("properties", ()):
          if propObj["property"] == "xbrl:conformanceTestFileName":
              for errName in refObj.get("forObjects", ()):
                  fileErrs[propObj["value"]].append((errName, 
                                                    any(propObj2["property"] == "xbrl:conformanceStatus" and "Fail" in propObj2["value"]
                                                        for propObj2 in refObj.get("properties", ()))))
# Error-code namespace prefixes that may be named in a test's documentInfo/description.
ERROR_CODE_PREFIXES = ("oimte", "oime", "oimce", "calc11e")
errCodeRe = re.compile(r"\b(" + "|".join(ERROR_CODE_PREFIXES) + r"):([A-Za-z][\w-]*)")

# Description leads (case-insensitive) that indicate a valid / permitted case, i.e.
# no error is expected. "EXAMPLE" and "ALLOWED" describe permitted constructs the
# same way "VALID" does.
VALID_LEAD_KEYWORDS = ("VALID", "EXAMPLE", "ALLOWED")

def resultFromDescription(f):
    """Derive the expected result for an unreferenced test case from its own
    documentInfo/description.

    Returns:
      ("valid", [])           - description leads with VALID -> no error expected
      ("error", [codes...])   - description leads with ERROR -> expected error QNames
                                (codes may be empty when none are named)
      None                    - description missing / unreadable / no VALID|ERROR lead;
                                caller falls back to the filename heuristic.

    Only ERROR-lead descriptions contribute error codes: VALID descriptions often
    name a code as the feature under test, which must NOT be treated as an expected
    error."""
    try:
        with open(os.path.join(DIR, "conformance", f), "r") as fp:
            doc = json.load(fp)
    except (OSError, ValueError):
        return None
    docInfo = doc.get("documentInfo") if isinstance(doc, dict) else None
    desc = docInfo.get("description") if isinstance(docInfo, dict) else None
    if not isinstance(desc, str):
        return None
    lead = desc.lstrip().upper()
    if lead.startswith(VALID_LEAD_KEYWORDS):
        return ("valid", [])
    if lead.startswith("ERROR"):
        codes, seen = [], set()
        for prefix, localName in errCodeRe.findall(desc):
            code = f"{prefix}:{localName}"
            if code not in seen:
                seen.add(code)
                codes.append(code)
        return ("error", codes)
    return None

# add unreferenced test cases: prefer the file's own description, falling back to
# the "-Valid" filename heuristic (with a tbd placeholder) when it is inconclusive.
unrefErrs = []
varNbr = 1
for f in sorted(set(testcaseFiles) - set(fileErrs.keys())):
    verdict = resultFromDescription(f)
    if verdict is None:
        verdict = ("valid", []) if "-Valid" in f else ("error", [])
    kind, codes = verdict
    if kind == "valid":
        unrefErrs.append((f, ()))
    elif codes:
        unrefErrs.append((f, tuple((code, True) for code in codes)))
    else:  # error expected but no code named -> keep a tbd placeholder
        unrefErrs.append((f, (("tbd{0:03}".format(varNbr), True),)))
        varNbr += 1

fw = open(TESTCASE, "w")
fw.write(
"""<?xml version="1.0" encoding="UTF-8"?>
<?xml-stylesheet type="text/xsl" href="../../infrastructure/test.xsl"?>
<testcase
    xmlns="http://xbrl.org/2008/conformance"
    xmlns:oimte="https://xbrl.org/2026/oimtaxonomy/error"
    xmlns:oime="http://www.xbrl.org/2021/oim/error"
    xmlns:oimce="https://xbrl.org/2021/oim-common/error"
>
  <creator>
    <name>Herm Fischer</name>
    <email>herm@exbee.dev</email>s
  </creator>
  <number>XBRL Model</number>
  <name>XBRL Model Certification Tests</name>
  <description>
    XBRL Model Certification Tests
  </description>
""")
varNbr = 1
for f, errs in (sorted(fileErrs.items()) + unrefErrs):
    results = "".join([(f"\n      <error>{e}</error>" if isErr else "")
                       for (e, isErr) in errs])
    fw.write(
"""  <variation id="{0}">
    <description>File {1}</description>
    <data>
      <instance readMeFirst="true">{1}</instance>
    </data>
    <result>{2}
    </result>
  </variation>
""".format(f[:-5], f, results)
     )
    varNbr += 1
    testcaseFiles.discard(f)
fw.write(
"""</testcase>
""")
fw.close()
print(f"Original testcase files count {origCount}, unreferenced count {len(testcaseFiles)}")
print(f"Testcase files not referenced: {sorted(testcaseFiles)}")

