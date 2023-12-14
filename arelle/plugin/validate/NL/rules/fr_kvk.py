"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any, cast, Iterable

from arelle import ModelDocument, XbrlConst
from arelle.ModelDtsObject import ModelResource
from arelle.ModelInstanceObject import ModelInlineFootnote
from arelle.ValidateXbrl import ValidateXbrl
from arelle.ModelObject import ModelObject
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from lxml.etree import _Element
from ..DisclosureSystems import (
    DISCLOSURE_SYSTEM_NT16,
    DISCLOSURE_SYSTEM_NT17,
)
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


ACCEPTED_LANGUAGES = ('de', 'en', 'fr', 'nl')
ACCEPTED_DECIMAL_VALUES = ('INF', '-9', '-6', '-3', '0', '2')


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
    ],
)
def rule_fr_kvk_1_01(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-KVK-1.01: An XBRL instance document MUST have the file extension .xbrl
    """
    modelXbrl = val.modelXbrl
    for doc in modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            if not doc.basename.endswith('.xbrl'):
                yield Validation.error(
                    codes='NL.FR-KVK-1.01',
                    msg=_('An XBRL instance document MUST have the file extension .xbrl: %(fileName)s'),
                    modelObject=doc,
                    fileName=doc.basename,
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
    ],
)
def rule_fr_kvk_2_01(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-KVK-2.01: The XBRL instance root node MUST contain attribute "xml:lang" with value "nl", "en", "de" or "fr"
    """
    modelXbrl = val.modelXbrl
    for doc in modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            lang = doc.xmlRootElement.get('{http://www.w3.org/XML/1998/namespace}lang')
            if lang not in ACCEPTED_LANGUAGES:
                yield Validation.error(
                    codes='NL.FR-KVK-2.01',
                    msg=_('The XBRL instance root node MUST contain attribute "xml:lang" with one of the following values: %(acceptedLangs)s. Provided: %(lang)s'),
                    modelObject=doc,
                    acceptedLangs=", ".join(ACCEPTED_LANGUAGES),
                    lang=lang,
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
    ],
)
def rule_fr_kvk_2_02(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-KVK-2.02: The attribute 'xml:lang' MUST contain the same value within an XBRL instance document
    """
    modelXbrl = val.modelXbrl
    lang = None
    for doc in modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            lang = doc.xmlRootElement.get('{http://www.w3.org/XML/1998/namespace}lang')
    for fact in modelXbrl.facts:
        if fact.xmlLang and fact.xmlLang != lang:
            yield Validation.error(
                codes='NL.FR-KVK-2.02',
                msg=_('The attribute \'xml:lang\' can be reported on different elements within an XBRL instance document.'
                      'The attribute \'xml:lang\' must always contain the same value within an XBRL instance document. '
                      'It is not allowed to report different values here. Document language: %(documentLang)s  Element language: %(additionalLang)s'),
                modelObject=fact,
                additionalLang=fact.xmlLang,
                documentLang=lang,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
    ],
)
def rule_fr_kvk_2_03(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-KVK-2.03: The attribute 'href' of the 'link:schemaRef' element MUST refer to the
    full web location of the published entrypoint from the annual reporting taxonomy
    """
    modelXbrl = val.modelXbrl
    for doc in modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            for refDoc, docRef in doc.referencesDocument.items():
                if "href" not in docRef.referenceTypes:
                    continue
                if docRef.referringModelObject.localName != "schemaRef":
                    continue
                href = refDoc.uri
                if href not in pluginData.entrypoints:
                    yield Validation.error(
                        codes='NL.FR-KVK-2.03',
                        msg=_('The attribute "href" of the "link:schemaRef" element MUST refer to the '
                              'full web location of the published entrypoint from the annual reporting taxonomy. '
                              'Provided: %(href)s. See valid entry points at %(entryPointRoot)s'),
                        modelObject=doc,
                        href=href,
                        entryPointRoot=pluginData.entrypointRoot,
                    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
    ],
)
def rule_fr_kvk_5_01(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-KVK-5.01: The attribute 'decimals' to monetary values MUST be filled with allowed values.
    """
    modelXbrl = val.modelXbrl
    for fact in modelXbrl.facts:
        if not fact.concept.isMonetary:
            continue
        decimals = fact.decimals
        if decimals not in ACCEPTED_DECIMAL_VALUES:
            yield Validation.error(
                codes='NL.FR-KVK-5.01',
                msg=_('The attribute "decimals" on monetary values MUST be filled with allowed values: %(acceptedValues)s. Provided: %(decimals)s'),
                modelObject=fact,
                acceptedValues=ACCEPTED_DECIMAL_VALUES,
                decimals=decimals,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
    ],
)
def rule_fr_kvk_5_02(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-KVK-5.02: The attribute 'decimals' for non-monetary numeric facts MUST be filled with 'INF'.
    """
    modelXbrl = val.modelXbrl
    for fact in modelXbrl.facts:
        if not fact.concept.isNumeric or fact.concept.isMonetary:
            continue
        decimals = fact.decimals
        if decimals != 'INF':
            yield Validation.error(
                codes='NL.FR-KVK-5.02',
                msg=_('The attribute "decimals" for non-monetary numeric facts MUST be filled with "INF". Provided: %(decimals)s'),
                modelObject=fact,
                decimals=decimals,
            )
