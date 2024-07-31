# -*- coding: utf-8 -*-
"""
:mod:`EdgarFtIxGen.FtJsonToOimJson`
~~~~~~~~~~~~~~~~~~~
FtJsonToOimJson was created by staff of the U.S. Securities and Exchange Commission.
Data and content created by government employees within the scope of their employment
are not subject to domestic copyright protection. 17 U.S.C. 105.

This plugin can be run as a main program (with file name argument for FT JSON input) or as a
report setup plugin to LoadFromOIM (in which case it converts the FT JSON into OIM JSON
during the LoadFromOIM process).

"""

import datetime, json, re, os

unitByName = (
        ("iso4217:USD", re.compile("(?!.*[Ee]xpltn).*(Amt|Val|Pric|Valtn|PdFee|PricFsclYr|PricPrrFsclYr|Cdts)$|(?!.*Per).*([vV]al)[A-Z]|(csh|val).*$")),
        ("xbrli:shares", re.compile(".*(NbOf).*$|(amtScties).*$")),
        (None, re.compile(".*Rate.*$")) # pure is omitted
    )

def unitForName(name):
    for unit, namePattern in unitByName:
        if namePattern.match(name):
            return unit
    return None

def prefixForName(name):
    if name in ("entityCentralIndexKey", "entityRegistrantName"):
        return "dei"
    return "ffd"

def getLatestTaxonomyFamily(modelXbrl, name):
    latest_version = None
    if not modelXbrl:
        # keeping this hard coded version just for debugging purposes.
        # This plugin is called via loadFromOIM plugin so it should have
        # a modelXbrl when called.
        class taxonomyFamily:
            def __init__(self, name):
                self.family = name.lower()
                self.namespace = f"http://xbrl.sec.gov/{self.family}/2024"
                self.href = f"https://xbrl.sec.gov/{self.family}/2024/{self.family}-2024.xsd"
        latest_version = taxonomyFamily(name)
    else:
        for family in modelXbrl.modelManager.disclosureSystem.familyHrefs.get(name, []):
            prefix = family.namespace.split("/")[-2]
            if not latest_version and prefix == name.lower():
                latest_version = family
            else:
                if prefix == name.lower() and family.version > latest_version.version:
                    latest_version = family
    return latest_version

def ftJsonToOimJson(modelXbrl, oimObject, *args, **kwargs):
    # is this an FT JSON file?
    if not( isinstance(oimObject, dict) and "documentInfo" not in oimObject and all(
            t in oimObject for t in ("feesSummaryTable", "submissionTable"))):
        return None
    ftJson = oimObject
    CIK = oimObject.get("submissionTable", {}).get("entityCentralIndexKey", "0000000000")
    today = datetime.datetime.today()
    start_date = (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")
    period = f"{start_date}T00:00:00/{end_date}T00:00:00"
    facts = {}
    dei = getLatestTaxonomyFamily(modelXbrl, "DEI")
    ffd = getLatestTaxonomyFamily(modelXbrl, "FFD")
    ftOim = {
        "documentInfo": {
            "documentType": "https://xbrl.org/2021/xbrl-json",
            "features": {},
            "namespaces": {
                "dei": dei.namespace,
                "ffd": ffd.namespace,
                "iso4217": "http://www.xbrl.org/2003/iso4217",
                "scheme": "http://www.sec.gov/CIK",
                "xbrli": "http://www.xbrl.org/2003/instance",
                "xbrl": "https://xbrl.org/2021"
            },
            "taxonomy": [
                ffd.href
            ]
        },
        "facts": facts
    }

    ignoreZeroFlagNamePattern = re.compile(r"ffd:(Rule(011|457[aoursf]|415a6|457[bp]Offset|011a2Offset)Flg|FeesOthrRuleFlg)")

    # relative import of sibling module Util is iffy in cx_frozen builds, read ft-validations directly
    with open(os.path.join(os.path.dirname(__file__),"resources","ft-validations.json"), "r", encoding="utf-8") as fh:
        ftValidations = json.load(fh)
        formFields =  ftValidations['form-fields']
        formCodeMapping = {v: k for k, v in ftValidations['form-mapping'].items()}

    def newFact(name, value, axis=None, tableLine=None):
        unit = unitForName(name)
        if ":" not in name:
            name = f"{prefixForName(name)}:{name[0].upper()}{name[1:]}"
        if isinstance(value, (bool,int,float)):
            if unit == "xbrli:shares" and isinstance(value, float):
                value = int(value)
            value = str(value).lower() # OIM requires all fact values be string in OIM-JSON input
        if value in ("0", "false") and ignoreZeroFlagNamePattern.match(name):
            return # ignore flag
        if name in formFields and value in formCodeMapping:
            value = formCodeMapping[value]
        facts[f"f{len(facts)+1}"] = fact= {
            "value": value,
            "dimensions": {
                "concept": name,
                "entity": f"scheme:{CIK}",
                "period": period
            }
        }
        if unit:
            fact["dimensions"]["unit"] = unit
        if axis:
            fact["dimensions"][axis] = f"{tableLine}"

    for table, axis in (("feesSummaryTable", None),
                        ("offeringTable", "ffd:OfferingAxis"),
                        ("offsetTable", "ffd:OffsetAxis"),
                        ("cmbndPrspctsTable", "ffd:CmbndPrspctsItemAxis"),
                        ("submissionTable", None),
                        ("scties424iTable", "ffd:Scties424iAxis")
                        ):
        tableLine = 1
        lines = ftJson.get(table, [])
        if axis is None and isinstance(lines, dict): # top level object only
            lines = [lines]
        for line in lines:
            for name, value in line.items():
                if not table.startswith(name) and not name.endswith("InnerText") and not name in {"!@%duplicateValues%@!", "tpOfPmt", "nbDaysLate", "cmbndPrspctsItem"} and \
                not (axis=="ffd:Scties424iAxis" and name=="rule457uFlg"): # rule457uFlg is derived for EDGAR on 424i subtypes but not part of taxonomy
                    newFact(name, value, axis, tableLine)
            tableLine += 1

    oimObject.clear()
    oimObject.update(ftOim)
    #with open("/Users/hermf/Documents/mvsl/projects/SEC/FT/LN-samples/457bOffset1Source-test.json", "w", encoding="utf-8") as fh:
    #    fh.write(json.dumps(oimObject, indent=3))

    if modelXbrl is not None:
        modelXbrl.loadedFromFtJson = True
    return ftOim

def isFtJsonDocument(modelXbrl, *args, **kwargs):
    return getattr(modelXbrl, "loadedFromFtJson", False)


# debugging
if __name__ == "__main__":
    with open(r"C:\Users\Lopezfr\Documents\AB\EXFILINGFEES.json", "rt", encoding="utf-8") as fh:
        ftJson = json.load(fh)
    oim = ftJsonToOimJson(None, ftJson)
    with open(r"C:\Users\Lopezfr\Documents\AB\EXFILINGFEESoim.json", "w", encoding="utf-8") as fh:
        fh.write(json.dumps(oim, indent=3))

__pluginInfo__ = {
    'name': 'FT JSON to OIM JSON',
    'version': '1.0',
    'description': "This plug-in converts an FT JSON document into an xBRL-JSON OIM report.",
    'license': 'Apache-2',
    'author': 'SEC Employees',
    'copyright': '(c) Portions by SEC Employees not subject to domestic copyright.',
    'import': ('loadFromOIM', ), # import dependent modules
    # classes of mount points (required)
    'LoadFromOim.DocumentSetup': ftJsonToOimJson,
    'FtJson.IsFtJsonDocument': isFtJsonDocument
}
