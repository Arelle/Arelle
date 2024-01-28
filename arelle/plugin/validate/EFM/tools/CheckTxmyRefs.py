'''
Created by staff of the U.S. Securities and Exchange Commission.
Data and content created by government employees within the scope of their employment are not subject
to domestic copyright protection. 17 U.S.C. 105.

To run
   arelleCmdLine --plugin validate/EFM/tools/CheckTxmyRefs --disclosureSystem efm-pragmatic --report-file ../myReportFile.csv

   if no --report-file the log entryies are printed to standard output stream

pass 1: for each edgartaxonomy family, for each version,
        load each href
        check that it's in the standard taxonomies dict inferred from edgartaxonomies
        check that each referenced URL from the href is also an href in edgartaxonomies
        check that any ref and doc LBs in same cache dir are in TaxonomyAddonManager files

pass 2: for each file found in an local-root directory by entries in fishInDirsForMissing
        for pattern (such as fishing for files -sub-)
        check if the file is loadable and if so if there are referenced files not in edgartaxonomies

'''
import os, regex as re
from collections import defaultdict
from lxml import etree
from arelle.Version import authorLabel, copyrightLabel

fishInDirsForMissing = {
    "stx": {
        "url-root": "https://xbrl.sec.gov",
        # "local-root": r"C:/gns/w/git-osd/stx/xbrl.sec.gov",
        "local-root": r"C:/gns/w/git-group2/sec-arelle/xbrl_taxonomies/xbrl_taxonomies/resources/System/cache/https/xbrl.sec.gov",
        "entrypoint-pattern": r"https?://xbrl.sec.gov/[^/]+/2023[^/]*/[^/]+(-sub-)[^.]+\.xsd"
        }
    # not sure what we load for US-GAAP and IFRS to determine needed ref and doc linkbases
    }


def utilityRun(cntlr, options, *args, **kwargs):
    logLines = []
    def log(line):
        if options.reportFile:
            logLines.append(line)
        else:
            print(line)
    disclosureSystem = cntlr.modelManager.disclosureSystem
    edTxmyTree = etree.parse(disclosureSystem.standardTaxonomiesUrl)
    edTxmyFamilies = defaultdict(dict) # by Family, Version, set of Hrefs
    edTxmyHrefs = set()
    for locElt in edTxmyTree.iter("Loc"):
        family = locElt.find("Family").text
        version = locElt.find("Version").text
        href = locElt.find("Href").text
        txmyFamily = edTxmyFamilies[family]
        txmyFamily.setdefault(version, set()).add(href)
        edTxmyHrefs.add(href)

    txmyAddOnTree = etree.parse(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "EdgarRenderer", "resources", "TaxonomyAddonManager.xml"))
    txmyAddons = defaultdict(dict)
    for txmyElt in txmyAddOnTree.iter("TaxonomyAddon"):
        txmyAddon = txmyAddons[txmyElt.find("Taxonomy").text]
        defsElt = txmyElt.find("DefinitionFiles")
        if defsElt is not None:
            for elt in defsElt.iter("string"):
                txmyAddon.setdefault("doc", set()).add(elt.text)
        refsElt = txmyElt.find("ReferenceFiles")
        if refsElt is not None:
            for elt in refsElt.iter("string"):
                txmyAddon.setdefault("ref", set()).add(elt.text)

    # check each edgartaxonomy family
    for txmyFamily in edTxmyFamilies:
        for familyVer in edTxmyFamilies[txmyFamily]:
            for hRef in edTxmyFamilies[txmyFamily][familyVer]:
                # check if it loads
                modelXbrl = cntlr.modelManager.load(hRef)
                if modelXbrl is not None:
                    log(f"family {txmyFamily} ver {familyVer} href {hRef} loaded")
                    if not hRef in disclosureSystem.standardTaxonomiesDict:
                        log(f"family {txmyFamily} ver {familyVer} href {hRef} not in edgartaxonomies")
                    for refUrl in modelXbrl.urlDocs:
                        if refUrl not in edTxmyHrefs and refUrl != hRef:
                            log(f"ref taxonomy also missing from edgartaxonomies: ref {refUrl}, loaded from {hRef}")
                    if not re.match(r".*([-_](lab|ref|pre|cal|def|sub)(-\n\n\n\n)?\.xsd)", hRef):
                        cachePath = os.path.dirname(cntlr.webCache.getfilename(hRef))
                        docRefs = defaultdict(set)
                        for root, dir, files in os.walk(cachePath):
                            for file in files:
                                m = re.match(r".*(doc|ref)\.(xsd|xml)", file)
                                if m:
                                    docRefs[m.group(1)].add(file)
                        addOn = txmyAddons.get(os.path.basename(hRef))
                        if addOn:
                            if docRefs != addOn:
                                for _type in ("doc", "ref"):
                                    missing = ", ".join(set(docRefs.get(_type, {}.values())) - set(addOn.get(_type, {}.values())))
                                    extra = ", ".join(set(addOn.get(_type, {}.values())) - set(docRefs.get(_type, {}.values())))
                                    log(f"family {txmyFamily} ver {familyVer} href {hRef}, addon extra {_type}s: {extra}, addon missing {_type}s: {missing}")
                        elif "-sub-" not in hRef and not hRef.endswith(".xml"):
                            log(f"family {txmyFamily} ver {familyVer} href {hRef} not in TaxonomyAddons")
                else:
                    log(f"family {txmyFamily} ver {familyVer} href {hRef} DID NOT LOAD")
    missingHrefs = set(disclosureSystem.standardTaxonomiesDict) - edTxmyHrefs
    extraHrefs = edTxmyHrefs - set(disclosureSystem.standardTaxonomiesDict)
    if missingHrefs:
        log(f"disclosure system missing {', '.join(sorted(missingHrefs))}")
    if extraHrefs:
        log(f"disclosure system missing {', '.join(sorted(extraHrefs))}")
    # fish in unzipped archive for file patterns
    for repo in fishInDirsForMissing:
        fileRoot = fishInDirsForMissing[repo]["local-root"]
        urlRoot = fishInDirsForMissing[repo]["url-root"]
        urlPattern = re.compile(fishInDirsForMissing[repo]["entrypoint-pattern"])
        for root, dir, files in os.walk(fileRoot):
            for file in files:
                fullFilePath = os.path.join(root, file)
                relativePath = fullFilePath[len(fileRoot)+1:]
                hRef = os.path.join(urlRoot, relativePath)
                if urlPattern.match(hRef):
                    if hRef not in edTxmyHrefs:
                        # check if it loads
                        modelXbrl = cntlr.modelManager.load(hRef)
                        if modelXbrl is not None:
                            log(f"missing from edgartaxonomies: href {hRef}, loaded")
                            for refUrl in modelXbrl.urlDocs:
                                if refUrl not in edTxmyHrefs and refUrl != hRef:
                                    log(f"ref taxonomy also missing from edgartaxonomies: ref {refUrl}, loaded from {hRef}")
                            if not re.match(r".*([-_](lab|ref|pre|cal|def|sub)(-\n\n\n\n)?\.xsd)", hRef):
                                cachePath = os.path.dirname(cntlr.webCache.getfilename(hRef))
                                docRefs = defaultdict(set)
                                for root, dir, files in os.walk(cachePath):
                                    for file in files:
                                        m = re.match(r".*(doc|ref)\.(xsd|xml)", file)
                                        if m:
                                            docRefs[m.group(1)].add(file)
                                addOn = txmyAddons.get(os.path.basename(hRef))
                                if not addOn:
                                    log(f"ref {hRef} not in TaxonomyAddons")
                                else:
                                    if docRefs != addOn:
                                        for _type in ("doc", "ref"):
                                            missing = ", ".join(set(docRefs.get(_type, {}.values())) - set(addOn.get(_type, {}.values())))
                                            extra = ", ".join(set(addOn.get(_type, {}.values())) - set(docRefs.get(_type, {}.values())))
                                            log(f"family {txmyFamily} ver {familyVer} href {hRef}, addon extra {_type}s: {extra}, addon missing {_type}s: {missing}")
                        else:
                            log(f"missing from edgartaxonomies: {hRef} DID NOT LOAD")
    if options.reportFile:
        with open(options.reportFile, "w", encoding="utf-8") as fh:
            fh.write("\n".join(logLines))

def commandLineOptionExtender(parser, *args, **kwargs):
    # extend command line options to store to database
    parser.add_option("--report-file",
                      action="store",
                      dest="reportFile",
                      help=_("Report file on taxonomy refs."))

def dislosureSystemTypes(disclosureSystem, *args, **kwargs):
    # return ((disclosure system name, variable name), ...)
    return (("EFM", "EFMplugin"),)

def disclosureSystemConfigURL(disclosureSystem, *args, **kwargs):
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.xml")


__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Check Taxonomy Refs',
    'version': '1.0',
    'description': '''
Check edgartaxonomies.xml and taxonomyAddonManager.xml
for completeness against supported year entry points.''',
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrCmdLine.Options': commandLineOptionExtender,
    'CntlrCmdLine.Utility.Run': utilityRun,
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
}
