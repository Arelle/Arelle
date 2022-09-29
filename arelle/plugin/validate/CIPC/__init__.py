'''
Filer Guidelines: http://www.cipc.co.za/files/8615/1333/0514/25082017_Guidelines_for_Filing__AFSs_in_XBRL_by_Client_Companies_Technical_Aspects_v1-7_HVMZ.pdf

Taxonomy Architecture: http://www.cipc.co.za/files/1715/1325/5802/CIPC_XBRL_Taxonomy_Framework_Architecture_-_2017-12-15.pdf

Taxonomy package expected to be installed: http://xbrl.cipc.co.za/cipc_2017-12-15.zip

See COPYRIGHT.md for copyright information.
'''
import os, re
from lxml.etree import _ElementTree, _Comment, _ProcessingInstruction
from arelle import ModelDocument, XbrlConst
from arelle.ModelDtsObject import ModelResource
from arelle.ModelInstanceObject import ModelFact, ModelInlineFact, ModelInlineFootnote
from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname
from arelle.Version import authorLabel, copyrightLabel
from arelle.XbrlConst import ixbrlAll, xhtml
from .Const import cpicModules # , mandatoryElements

cipcBlockedInlineHtmlElements = {
    'object', 'script'}

namePattern = re.compile(r"^(.*) - ((18|19|20)\d{2}-[0-9]+-(06|07|08|09|10|12|20|21|22|23|24|25|26|30|31)) - (20[1-9]\d)$")
reportingModulePattern = re.compile(r"http://xbrl.cipc.co.za/taxonomy/.*/\w*(ca_fas|full_ifrs|ifrs_for_smes)\w*[_-]20[12][0-9]-[0-9]{2}-[0-9]{2}.xsd")

def dislosureSystemTypes(disclosureSystem, *args, **kwargs):
    # return ((disclosure system name, variable name), ...)
    return (("CIPC", "CIPCplugin"),)

def disclosureSystemConfigURL(disclosureSystem, *args, **kwargs):
    return os.path.join(os.path.dirname(__file__), "config.xml")

def validateXbrlStart(val, parameters=None, *args, **kwargs):
    val.validateCIPCplugin = val.validateDisclosureSystem and getattr(val.disclosureSystem, "CIPCplugin", False)
    if not (val.validateCIPCplugin):
        return


def validateXbrlFinally(val, *args, **kwargs):
    if not (val.validateCIPCplugin):
        return

    _xhtmlNs = "{{{}}}".format(xhtml)
    _xhtmlNsLen = len(_xhtmlNs)
    modelXbrl = val.modelXbrl
    modelDocument = modelXbrl.modelDocument
    if not modelDocument:
        return # never loaded properly

    _statusMsg = _("validating {0} filing rules").format(val.disclosureSystem.name)
    modelXbrl.profileActivity()
    modelXbrl.modelManager.showStatus(_statusMsg)


    if modelDocument.type == ModelDocument.Type.INSTANCE:
        modelXbrl.error("cipc:instanceMustBeInlineXBRL",
                        _("CIPC expects inline XBRL instances."),
                        modelObject=modelXbrl)
    if modelDocument.type in (ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INSTANCE):
        footnotesRelationshipSet = modelXbrl.relationshipSet("XBRL-footnotes")
        orphanedFootnotes = set()
        nonEnglishFootnotes = set()
        foonoteRoleErrors = set()
        transformRegistryErrors = set()
        def checkFootnote(elt, text):
            if text: # non-empty footnote must be linked to a fact if not empty
                if not any(isinstance(rel.fromModelObject, ModelFact)
                           for rel in footnotesRelationshipSet.toModelObject(elt)):
                    orphanedFootnotes.add(elt)
            if not elt.xmlLang.startswith("en"):
                nonEnglishFootnotes.add(elt)
            if elt.role != XbrlConst.footnote or not all(
                rel.arcrole == XbrlConst.factFootnote and rel.linkrole == XbrlConst.defaultLinkRole
                for rel in footnotesRelationshipSet.toModelObject(elt)):
                footnoteRoleErrors.add(elt)

        if modelDocument.type == ModelDocument.Type.INLINEXBRL:
            _baseName, _baseExt = os.path.splitext(modelDocument.basename)
            if _baseExt not in (".xhtml",) or not namePattern.match(_baseName):
                modelXbrl.warning("cipc:fileNameMalformed",
                    _("FileName should have the pattern \"Co. name - regYr-regNbr-coCode - finYr.xhtml\": %(fileName)s"),
                    modelObject=modelXbrl, fileName=modelDocument.basename)
            rootElt = modelDocument.xmlRootElement
            if rootElt.tag not in ("{http://www.w3.org/1999/xhtml}html", "{http://www.w3.org/1999/xhtml}xhtml"):
                modelXbrl.error("cipc:htmlRootElement",
                    _("InlineXBRL root element <%(element)s> MUST be html and have the xhtml namespace."),
                    modelObject=rootElt, element=rootElt.tag)
            for elt in rootElt.iter():
                eltTag = elt.tag
                if isinstance(elt, ModelObject) and elt.namespaceURI == xhtml:
                    eltTag = elt.localName
                elif isinstance(elt, (_ElementTree, _Comment, _ProcessingInstruction)):
                    continue # comment or other non-parsed element
                else:
                    eltTag = elt.tag
                    if eltTag.startswith(_xhtmlNs):
                        eltTag = eltTag[_xhtmlNsLen:]
                    if eltTag in cipcBlockedInlineHtmlElements:
                        modelXbrl.error("cipc:disallowedHtmlElement",
                            _("Html element is disallowed: %(element)s"),
                            modelObject=elt, element=eltTag)
                    if eltTag == "title" and not namePattern.match(elt.text):
                        modelXbrl.error("cipc:titleElementMalformed",
                            _("Title element required to have the pattern \"Co. name - regYr-regNbr-coCode - finYr\": %(title)s"),
                            modelObject=elt, title=elt.text)
                    for attrTag, attrValue in elt.items():
                        if ((attrTag == "href" and eltTag == "a") or
                            (attrTag == "src" and eltTag == "img")):
                            if "javascript:" in attrValue:
                                modelXbrl.error("cipc:disallowedScript",
                                    _("Element %(element)s has javascript in '%(attribute)s'"),
                                    modelObject=elt, attribute=attrTag, element=eltTag)
                if isinstance(elt, ModelInlineFootnote):
                    checkFootnote(elt, elt.value)
                elif isinstance(elt, ModelResource) and elt.qname == XbrlConst.qnLinkFootnote:
                    checkFootnote(elt, elt.value)
                elif isinstance(elt, ModelInlineFact):
                    if elt.format is not None and elt.format.namespaceURI != 'http://www.xbrl.org/inlineXBRL/transformation/2015-02-26':
                        transformRegistryErrors.add(elt)
        elif modelDocument.type == ModelDocument.Type.INSTANCE:
            for elt in modelDocument.xmlRootElement.iter():
                if elt.qname == XbrlConst.qnLinkFootnote: # for now assume no private elements extend link:footnote
                    checkFootnote(elt, elt.stringValue)


        # identify type of filer (FAS, Full IFES, IFRS for SMES)
        reportingModules = [reportingModulePattern.match(referencedDoc.uri).group(1)
                            for referencedDoc in modelDocument.referencesDocument.keys()
                            if referencedDoc.type == ModelDocument.Type.SCHEMA
                            if reportingModulePattern.match(referencedDoc.uri)]

        if len(reportingModules) != 1 or reportingModules[0] not in cpicModules:
            modelXbrl.error("cipc:reportingModuleAmbiguous",
                _("Reporting module must specify namespace for FAS, IFRS-FULL or IFRS-SMES"),
                modelObject=elt)
            reportingModule = None
        else:
            reportingModule = cpicModules[reportingModules[0]]

        # build namespace maps
        nsMap = {}
        for ns in modelXbrl.namespaceDocs.keys():
            if ns.endswith("/ca"):
                nsMap["cipc-ca"] = ns
            elif ns.endswith("/ca/enum"):
                nsMap["cipc-ca-enum"] = ns
            elif ns.endswith("/ifrs-full"):
                nsMap["ifrs-full"] = ns
            elif ns.endswith("/ifrs-smes"):
                nsMap["ifrs-smes"] = ns

        ''' checked by CIPC formula
        # build mandatory and footnoteIfNil tables by ns qname in use
        mandatory = set()
        for prefixedName in mandatoryElements[reportingModule]["mandatory"]:
            prefix, _sep, name = prefixedName.rpartition(":")
            mandatory.add(qname(nsMap.get(prefix),name))

        footnoteIfNil = set()
        for prefixedName in mandatoryElements[reportingModule]["footnoteIfNil"]:
            prefix, _sep, name = prefixedName.rpartition(":")
            footnoteIfNil.add(qname(nsMap.get(prefix),name))

        reportedMandatory = set()
        reportedFootnoteIfNil = set()
        factsMandatoryNilWithoutFootnote = set()
        footnotesRelationshipSet = modelXbrl.relationshipSet(XbrlConst.factFootnote, XbrlConst.defaultLinkRole)

        for qn, facts in modelXbrl.factsByQname.items():
            if qn in mandatory:
                reportedMandatory.add(qn)
            elif qn in footnoteIfNil:
                for fact in facts:
                    reportedFootnoteIfNil.add(qn)
                    if fact.isNil and not any(footnote.role == XbrlConst.footnote and
                                              footnote.xmlLang.startswith("en") and
                                              footnote.stringValue.strip()
                                              for footnoteRel in footnotesRelationshipSet.fromModelObject(fact)
                                              for footnote in (footnoteRel.toModelObject,)):
                        factsMandatoryNilWithoutFootnote.add(fact)

        missingElements = (mandatory - reportedMandatory) # | (reportedFootnoteIfNil - reportedFootnoteIfNil)
        if missingElements:
            modelXbrl.error("cpic:missingRequiredElements",
                            _("Required elements missing from document: %(elements)s."),
                            modelObject=modelXbrl, elements=", ".join(sorted(str(qn) for qn in missingElements)))

        if factsMandatoryNilWithoutFootnote:
            modelXbrl.error("cpic:missingExplanatoryFootnote",
                            _("Required nil facts missing explanatory footnote: %(elements)s."),
                            modelObject=factsMandatoryNilWithoutFootnote,
                            elements=", ".join(sorted(str(fact.qname) for fact in factsMandatoryNilWithoutFootnote)))
        '''

        if transformRegistryErrors:
            modelXbrl.warning("cpic:transformRegistry",
                              _("Transformation Registry 3 should be for facts: %(elements)s."),
                              modelObject=transformRegistryErrors,
                              elements=", ".join(sorted(str(fact.qname) for fact in transformRegistryErrors)))

        if orphanedFootnotes:
            modelXbrl.error("cipc:orphanedFootnote",
                _("Non-empty footnotes must be connected to fact(s)."),
                modelObject=orphanedFootnotes)

        if nonEnglishFootnotes:
            modelXbrl.error("cipc:nonEnglishFootnote",
                _("Footnotes must use English language."),
                modelObject=nonEnglishFootnotes)

        if foonoteRoleErrors:
            modelXbrl.error("cipc:footnoteRoleErrors",
                _("Footnotes must the default link, resource and arc roles."),
                modelObject=foonoteRoleErrors)

    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)


__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate CIPC',
    'version': '1.0',
    'description': '''CIPC (South Africa) Validation.''',
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally,
}
