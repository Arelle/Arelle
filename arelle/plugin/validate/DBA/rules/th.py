"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from arelle import ModelDocument
from collections.abc import Iterable
from typing import Any

from arelle.typing import TypeGetText
from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.XmlValidateConst import VALID
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_th01(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TH01: The “schemaRef” must contain “http://archprod.service.eogs.dk/taxonomy/”
    """
    modelXbrl = val.modelXbrl
    for doc in modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INLINEXBRL:
            for refDoc, docRef in doc.referencesDocument.items():
                if docRef.referringModelObject.localName == "schemaRef":
                    href = refDoc.uri
                    if href.startswith(pluginData.schemaRefUri):
                        continue
                    else:
                        yield Validation.error(
                            codes="DBA.TH01",
                            msg=_("The 'link:schemaRef' must contain '{}'. "
                                  "The 'link:schemaRef' as reported is {}.").format(pluginData.schemaRefUri, href),
                            modelObject=doc,
                        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_th05 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TH05: Contexts should not contain segments
    """
    contexts = val.modelXbrl.contexts.values()
    for context in contexts:
        if context.hasSegment:
            yield Validation.error(
                'DBA.TH05',
                _('Contexts should not contain segments.'),
                modelObject=context,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_th06 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TH06: CVR (gsd:IdentificationNumberCvrOfReportingEntity) context period cannot be forever.
    """
    facts = val.modelXbrl.factsByQname.get(pluginData.identificationNumberCvrOfReportingEntityQn, set())
    for fact in facts:
        if fact is not None and fact.context is not None:
            if fact.context.isForeverPeriod:
                yield Validation.error(
                    'DBA.TH06',
                    _('The CVR (gsd:IdentificationNumberCvrOfReportingEntity) context period cannot be forever.'),
                    modelObject=fact,
                )



@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_th10 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TH10: The taxonomy must be identified via a schema ref to an entry point, so the instance MUST NOT contain the following:
    linkbaseRef
    roleRef
    more than one schemaRef
    """
    linkbaseRefModelObjects = []
    roleRefModelObjects = []
    schemaRefModelObjects = []
    for doc in val.modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INLINEXBRL:
            for refDoc, docRef in doc.referencesDocument.items():
                if docRef.referringModelObject.localName == "linkbaseRef":
                    linkbaseRefModelObjects.append(docRef.referringModelObject)
                if docRef.referringModelObject.localName == "schemaRef":
                    schemaRefModelObjects.append(docRef.referringModelObject)
            for htmlElement in doc.modelXbrl.ixdsHtmlElements:
                for inlineElement in htmlElement.iterdescendants(tag=doc.ixNStag + "resources"):
                    roleRefModelObjects.extend(inlineElement.iterchildren("{http://www.xbrl.org/2003/linkbase}roleRef"))
    if len(schemaRefModelObjects) > 1:
            yield Validation.error(
                codes="DBA.TH10",
                msg=_("The 'link:schemaRef' element must only occur once."),
                modelObject=schemaRefModelObjects
            )
    if len(linkbaseRefModelObjects) > 0:
        yield Validation.error(
            codes="DBA.TH10",
            msg=_("The 'link:linkbaseRef' element must not occur."),
            modelObject=linkbaseRefModelObjects
        )
    if len(roleRefModelObjects) > 0:
        yield Validation.error(
            codes="DBA.TH10",
            msg=_("The 'link:roleRef' element must not occur."),
            modelObject=roleRefModelObjects
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_th14 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TH14: gsd:InformationOnTypeOfSubmittedReport MUST NOT use the following enumerations:
        Selskabsselvangivelse
        Erklæring om undtagelse fra aflæggelse årsrapport
        ESG-rapport
        ESG report
    """
    facts = val.modelXbrl.factsByQname.get(pluginData.informationOnTypeOfSubmittedReportQn, set())
    for fact in facts:
        if fact is not None and fact.xValid >= VALID:
            if fact.xValue in pluginData.forbiddenTypeOfSubmittedReportEnumerations:
                yield Validation.error(
                    'DBA.TH14',
                    _('gsd:InformationOnTypeOfSubmittedReport MUST NOT use the following enumerations:'
                      '"Selskabsselvangivelse", "Erklæring om undtagelse fra aflæggelse årsrapport", "ESG-rapport", "ESG report"'
                      'InformationOnTypeOfSubmittedReport is reported as "{}".').format(
                    fact.xValue),
                    modelObject=fact,

                )
