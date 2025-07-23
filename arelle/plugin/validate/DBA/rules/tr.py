"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from arelle import ModelDocument, ModelValue
from arelle.typing import TypeGetText
from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.DetectScriptsInXhtml import containsScriptMarkers
from arelle.utils.validate.Validation import Validation
from arelle.XbrlConst import xhtml, xml
from arelle.XmlValidateConst import VALID
from . import lookup_namespaced_facts, errorOnForbiddenImage
from ..PluginValidationDataExtension import PluginValidationDataExtension
from ..ValidationPluginExtension import NAMESPACE_GSD
from ..DisclosureSystems import MULTI_TARGET_DISCLOSURE_SYSTEMS, STAND_ALONE_DISCLOSURE_SYSTEMS

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tr01(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TR01: All GSD facts must have context with the same entity and period as gsd:IdentificationNumberCvrOfReportingEntity
    """
    cvr_facts = val.modelXbrl.factsByQname.get(pluginData.identificationNumberCvrOfReportingEntityQn, set())
    if len(cvr_facts) > 0:
        cvr_fact = next(iter(cvr_facts))
        gsd_facts = lookup_namespaced_facts(val.modelXbrl, NAMESPACE_GSD)
        facts_in_error = []
        for fact in gsd_facts:
            if not (
                fact.context.isEntityIdentifierEqualTo(cvr_fact.context) and
                fact.context.isPeriodEqualTo(cvr_fact.context)
            ):
                facts_in_error.append(fact)
        if len(facts_in_error) > 0:
            yield Validation.error(
                codes='DBA.TR01',
                msg=_("Facts tagged with gsd-namespaced concepts must have a context with the same entity and period as IdentificationNumberCvrOfReportingEntity"),
                modelObject=facts_in_error
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
)
def rule_tr02(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TR02: gsd:IdentificationNumberCvrOfReportingEntity must have the absolute URI 'http://www.dcca.dk/cvr' as
    context entity identifier scheme
    """
    cvr_facts = val.modelXbrl.factsByQname.get(pluginData.identificationNumberCvrOfReportingEntityQn, set())
    if len(cvr_facts) > 0:
        cvr_fact = next(iter(cvr_facts))
        if cvr_fact.context.entityIdentifier[0] != 'http://www.dcca.dk/cvr':
            yield Validation.error(
                codes='DBA.TR02',
                msg=_("IdentificationNumberCvrOfReportingEntity must have the absolute URI 'http://www.dcca.dk/cvr' as context entity identifier scheme"),
                modelObject=cvr_fact
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
)
def rule_tr03(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TR03: gsd:IdentificationNumberCvrOfReportingEntity must have the CVR number specified in gsd:IdentificationNumberCvrOfReportingEntity
    as the context entity identifier.
    """
    cvr_facts = val.modelXbrl.factsByQname.get(pluginData.identificationNumberCvrOfReportingEntityQn, set())
    if len(cvr_facts) > 0:
        cvr_fact = next(iter(cvr_facts))
        if cvr_fact.xValid >= VALID and cvr_fact.xValue != cvr_fact.context.entityIdentifier[1]:
            yield Validation.error(
                codes='DBA.TR03',
                msg=_("IdentificationNumberCvrOfReportingEntity must have the CVR number({}) specified in "
                      "IdentificationNumberCvrOfReportingEntity as the context entity identifier({}).").format(
                    cvr_fact.xValue,
                    cvr_fact.context.entityIdentifier[1]
                ),
                modelObject=cvr_fact
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
)
def rule_tr05(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TR05: gsd:ReportingPeriodStartDate must specify the same date as period startDate in the context of
    gsd:IdentificationNumberCvrOfReportingEntity
    """
    cvr_facts = val.modelXbrl.factsByQname.get(pluginData.identificationNumberCvrOfReportingEntityQn, set())
    start_date_facts = val.modelXbrl.factsByQname.get(pluginData.reportingPeriodStartDateQn, set())
    filtered_start_date_facts = {f for f in start_date_facts if not f.context.scenDimValues}
    if len(cvr_facts) > 0 and len(filtered_start_date_facts) > 0:
        cvr_fact = next(iter(cvr_facts))
        if cvr_fact.context.startDatetime is not None:
            start_date_fact = next(iter(filtered_start_date_facts))
            if start_date_fact.xValid >= VALID and start_date_fact.xValue != cvr_fact.context.startDatetime:
                yield Validation.error(
                    codes='DBA.TR05',
                    msg=_("ReportingPeriodStartDate must specify the same date({}) as period startDate({}) in the context "
                          "of IdentificationNumberCvrOfReportingEntity").format(
                        start_date_fact.xValue,
                        cvr_fact.context.startDatetime.date()
                    ),
                    modelObject=[start_date_fact, cvr_fact]
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
)
def rule_tr06(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TR06: gsd:ReportingPeriodEndDate must specify the same date as period endDate in the context of
    gsd:IdentificationNumberCvrOfReportingEntity
    """
    cvr_facts = val.modelXbrl.factsByQname.get(pluginData.identificationNumberCvrOfReportingEntityQn, set())
    end_date_facts = val.modelXbrl.factsByQname.get(pluginData.reportingPeriodEndDateQn, set())
    filtered_end_date_fact = {f for f in end_date_facts if not f.context.scenDimValues}
    if len(cvr_facts) > 0 and len(filtered_end_date_fact) > 0:
        cvr_fact = next(iter(cvr_facts))
        end_date_fact = next(iter(filtered_end_date_fact))
        if (end_date_fact.xValid >= VALID and
                isinstance(end_date_fact.xValue, ModelValue.DateTime) and
                end_date_fact.xValue.date() != cvr_fact.context.endDate):
            yield Validation.error(
                codes='DBA.TR06',
                msg=_("ReportingPeriodEndDate must specify the same date({}) as period endDate({}) in the context of "
                      "IdentificationNumberCvrOfReportingEntity").format(
                    end_date_fact.xValue.date(),
                    cvr_fact.context.endDate
                ),
                modelObject=[end_date_fact, cvr_fact]
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tr09(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TR09: All contexts must have the same identifier scheme and value
    """
    entity_identifier_values = {context.entityIdentifier for context in val.modelXbrl.contexts.values()}
    if len(entity_identifier_values) > 1:
        yield Validation.error(
            'DBA.TR09',
            _('All contexts must have the same identifier scheme and value')
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY
)
def rule_tr12(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TR12: InlineXBRL documents may not contain executable code.
    """
    modelXbrl = val.modelXbrl
    for doc in modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INLINEXBRL:
            for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements:
                for elt in ixdsHtmlRootElt.iter():
                    if containsScriptMarkers(elt) is not None:
                        yield Validation.error(
                            codes='DBA.TR12',
                            msg=_('InlineXBRL documents may not contain executable code.'),
                            modelObject=elt,
                        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tr11(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TR11: InlineXBRL must not contain references to external images. Only Base64 encoded content is accepted.
    """
    imagesToCheck = set()
    _xhtmlNs = "{{{}}}".format(xhtml)
    _xhtmlNsLen = len(_xhtmlNs)
    modelXbrl = val.modelXbrl
    modelDocument = modelXbrl.modelDocument
    if modelDocument is not None and modelDocument.type in (ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET):
        for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements:
            for elt in ixdsHtmlRootElt.iter(f'{_xhtmlNs}img'):
                imagesToCheck.add(elt.get("src","").strip())
    if len(imagesToCheck) > 0:
        yield from errorOnForbiddenImage(
            images = imagesToCheck,
            code="DBA.TR11",
            message=("InlineXBRL must not contain references to external images. Additionaly only Base64 encoded content is accepted."),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=MULTI_TARGET_DISCLOSURE_SYSTEMS,
)
def rule_tr15(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TR15: If the context identifier scheme is http://standards.iso.org/iso/17442, all context identifiers must be equal to the value of the field gsd:LegalEntityIdentifierOfReportingEntity.
    """
    leiFacts = val.modelXbrl.factsByQname.get(pluginData.legalEntityIdentifierOfReportingEntityQn, set())
    if len(leiFacts) > 0:
        leiFact = next(iter(leiFacts))
        if leiFact is not None and leiFact.context is not None and leiFact.context.entityIdentifier[0] == 'http://standards.iso.org/iso/17442' and leiFact.xValid >= VALID and leiFact.context.entityIdentifier[1] != leiFact.xValue:
                 yield Validation.error(
                    codes='DBA.TR15',
                    msg=_("If the context identifier scheme is http://standards.iso.org/iso/17442, all context identifiers must be equal to the value of the field gsd:LegalEntityIdentifierOfReportingEntity."),
                    modelObject=leiFact
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=MULTI_TARGET_DISCLOSURE_SYSTEMS,
)
def rule_tr16(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TR16: Inline XBRL must contain xml:lang in the root of the inlineXBRL document
    """
    modelXbrl = val.modelXbrl
    for doc in modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INLINEXBRL:
            lang = doc.xmlRootElement.get('{http://www.w3.org/XML/1998/namespace}lang')
            if not lang:
                yield Validation.error(
                    codes='DBA.TR16',
                    msg=_('Inline XBRL must contain xml:lang in the root of the InlineXBRL document'),
                    modelObject=doc,
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=MULTI_TARGET_DISCLOSURE_SYSTEMS,
)
def rule_tr17(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TR17: Inline XBRL must NOT contain the HTML <base> element or the xml:base attribute
    """
    _xhtmlNs = "{{{}}}".format(xhtml)
    _xmlNs = "{{{}}}".format(xml)
    htmlBases = []
    xmlBases = []
    modelXbrl = val.modelXbrl

    for doc in modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INLINEXBRL:
            for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements:
                for elt in ixdsHtmlRootElt.iter():
                    if elt.tag == _xhtmlNs + "base":
                        htmlBases.append(elt)
                    elif elt.get(_xmlNs + "base") is not None:
                        xmlBases.append(elt)
    if len(htmlBases) > 0:
        yield Validation.error(
            codes='DBA.TR17',
            msg=_('The HTML <base> element MUST NOT be used in the Inline XBRL document.'),
            modelObject=htmlBases,
        )
    if len(xmlBases) > 0:
            yield Validation.error(
                codes='DBA.TR17',
                msg=_('The xml:base attribute MUST NOT be used in the Inline XBRL document'),
                modelObject=xmlBases,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tr19(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TR19: Duplicate facts must not have different content. "Duplicate" is defined by the following criteria:
    - same concept name
    - same period
    - same dimensions (including same identifier in typed dimension)
    - same language (xml:lang)
    - same unit
    """
    duplicates = defaultdict(list)
    for fact in val.modelXbrl.facts:
        fact_hash = str(fact.conceptContextUnitHash) + str(fact.xmlLang)
        duplicates[fact_hash].append(fact)
    for duplicate_facts_group in duplicates.values():
        duplicate_fact_values = {fact.xValue for fact in duplicate_facts_group}
        if len(duplicate_fact_values) > 1:
            yield Validation.error(
                'DBA.TR19',
                _('Duplicate facts must not have different values. The values reported for these facts are: {}').format(
                    duplicate_fact_values
                ),
                modelObject=duplicate_facts_group
            )
