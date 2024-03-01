"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import codecs
from collections import defaultdict
from pathlib import Path
from typing import Any, BinaryIO, Iterable, cast

import regex
from lxml import etree

from arelle import ModelDocument, XbrlConst, XmlUtil
from arelle.FileSource import openXmlFileStream
from arelle.ModelObject import ModelObject, ModelComment
from arelle.ModelValue import qname
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import (
    DISCLOSURE_SYSTEM_NT16,
    DISCLOSURE_SYSTEM_NT17,
    DISCLOSURE_SYSTEM_NT18,
)
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


ALLOWED_NAMED_CHARACTER_REFS = frozenset({'lt', 'gt', 'amp', 'apos', 'quot'})
BOM_BYTES = sorted({
    codecs.BOM,
    codecs.BOM_BE,
    codecs.BOM_LE,
    codecs.BOM_UTF8,
    codecs.BOM_UTF16,
    codecs.BOM_UTF16_LE,
    codecs.BOM_UTF16_BE,
    codecs.BOM_UTF32,
    codecs.BOM_UTF32_LE,
    codecs.BOM_UTF32_BE,
    codecs.BOM32_LE,
    codecs.BOM32_BE,
    codecs.BOM64_BE,
    codecs.BOM64_LE,
}, key=lambda x: len(x), reverse=True)
UNICODE_CHARACTER_DECIMAL_RANGES = (
    (0x0000, 0x007F),  # Basic Latin
    (0x0080, 0x00FF),  # Latin-1 Supplement
    (0x20A0, 0x20CF),  # Currency Symbols
)
UNICODE_CHARACTER_RANGES_PATTERN = regex.compile(
    r"[^" +
    ''.join(fr"\u{min:04x}-\u{max:04x}" for min, max in UNICODE_CHARACTER_DECIMAL_RANGES) +
    "]")
XHTML_ALLOWED_STYLES = {
    'font-family',
    'font-size',
    'color'
}
XHTML_LIST_ITEM_TYPES = {
    'ol': frozenset({'1', 'a', 'A', 'i', 'I'}),
    'ul': frozenset({None, '', 'circle', 'square'}),
}


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18,
    ],
)
def rule_fr_nl_1_02(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-1.02: Characters MUST be from the Unicode ranges Basic Latin, Latin Supplement and Currency Symbols
    Only Unicode characters (version 9.0.0) from the ranges Basic Latin, Latin Supplement, Currency Symbols.
    (32, 127), 0020 - 007F: Basic Latin
    (160, 255), 00A0 - 00FF: Latin-1 Supplement
    (8352, 8399), 20A0 - 20CF: Currency Symbols
    """
    modelXbrl = val.modelXbrl
    errorObjects: list[ModelObject] = []
    foundChars = set()
    for doc in modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            for elt in doc.xmlRootElement.iter():
                if isinstance(elt, ModelComment):
                    texts = [getattr(elt, 'text')]
                else:
                    texts = [elt.elementAttributesStr, elt.textValue]
                matched = False
                for text in texts:
                    for match in regex.finditer(UNICODE_CHARACTER_RANGES_PATTERN, text):
                        matched = True
                        foundChars.add(match.group())
                if matched:
                    errorObjects.append(elt)
    if len(errorObjects) > 0:
        yield Validation.error(
            codes='NL.FR-NL-1.02',
            msg=_('Characters MUST be from the Unicode ranges Basic Latin, Latin Supplement and Currency Symbols '
                  '(ranges %(ranges)s). '
                  'Found disallowed characters: %(foundChars)s'),
            foundChars=sorted(foundChars),
            ranges=', '.join(f'{hex(min)}-{hex(max)}' for min, max in UNICODE_CHARACTER_DECIMAL_RANGES),
            modelObject=errorObjects,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18
    ],
)
def rule_fr_nl_1_03(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-1.03: A DOCTYPE declaration MUST NOT be used in the filing instance document
    """
    for doc in val.modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            if doc.xmlDocument.docinfo.doctype:
                yield Validation.error(
                    codes='NL.FR-NL-1.03',
                    msg=_('A DOCTYPE declaration MUST NOT be used in the filing instance document'),
                    modelObject=val.modelXbrl.modelDocument
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18,
    ],
)
def rule_fr_nl_1_04(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-1.04: Disallowed character references MUST NOT be used. The use of character references (e.g. &#1080;)
    is not allowed unless it concerns numeric character references within the allowed set of characters and except
    for the entity references listed here: &lt; &gt; &amp; &apos; &quot;
    """
    pattern = regex.compile(r"""
          & \#     (?<dec>[0-9]+)         ;
        | & \#[Xx] (?<hex>[0-9A-Fa-f]+)   ;
        | &        (?<named>[0-9A-Za-z]+) ;
    """, regex.VERBOSE)
    modelXbrl = val.modelXbrl
    foundChars = set()
    sourceFileLines = []
    for doc in modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            with modelXbrl.fileSource.file(doc.filepath)[0] as file:
                for i, line in enumerate(file):
                    for match in regex.finditer(pattern, line):
                        decimalValue = None
                        if (numericMatch := match.group('hex')) is not None:
                            decimalValue = int(numericMatch, 16)
                        if (numericMatch := match.group('dec')) is not None:
                            decimalValue = int(numericMatch)
                        if decimalValue is not None:
                            if any(min <= decimalValue <= max
                                   for min, max in UNICODE_CHARACTER_DECIMAL_RANGES):
                                continue  # numeric references in certain ranges are allowed
                        if (namedMatch := match.group('named')) is not None:
                            if namedMatch in ALLOWED_NAMED_CHARACTER_REFS:
                                continue  # certain named references are allowed
                        foundChars.add(match.group())
                        sourceFileLines.append((doc.filepath, i + 1))
    if len(sourceFileLines) > 0:
        yield Validation.error(
            codes='NL.FR-NL-1.04',
            msg=_('Disallowed character references MUST NOT be used. Only numeric character references within certain ranges '
                  '(%(ranges)s) and certain named references (%(allowedNames)s) are allowed. '
                  'Found disallowed characters: %(foundChars)s'),
            allowedNames=', '.join(sorted(f'"&{name};"' for name in ALLOWED_NAMED_CHARACTER_REFS)),
            foundChars=sorted(foundChars),
            ranges=', '.join(f'{hex(min)}-{hex(max)}' for min, max in UNICODE_CHARACTER_DECIMAL_RANGES),
            sourceFileLines=sourceFileLines
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18
    ],
)
def rule_fr_nl_1_05(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-1.05: The character encoding UTF-8 MUST be used in the filing instance document
    """
    for doc in val.modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            if 'UTF-8' != doc.documentEncoding.upper():
                yield Validation.error(
                    codes='NL.FR-NL-1.05',
                    msg=_('The XML character encoding \'UTF-8\' MUST be used in the filing instance document'),
                    modelObject=val.modelXbrl.modelDocument
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18,
    ],
)
def rule_fr_nl_1_06(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-1.06: The file name of an XBRL instance document MUST NOT contain characters with different meanings on different platforms.
    Only characters [0-9], [az], [AZ], [-] and [_] (File names not including the extension and separator [.]).
    """
    pattern = regex.compile(r"^[0-9a-zA-Z_-]*$")
    modelXbrl = val.modelXbrl
    for doc in modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            stem = Path(doc.basename).stem
            match = pattern.match(stem)
            if not match:
                yield Validation.error(
                    codes='NL.FR-NL-1.06',
                    msg=_('The file name of an XBRL instance document MUST NOT contain characters with different meanings on different platforms. ' +
                          'Only A-Z, a-z, 0-9, "-", and "_" may be used (excluding file extension with period).'),
                    fileName=doc.basename,
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18,
    ],
)
def rule_fr_nl_1_01(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-1.01: A BOM character MUST NOT be used.
    """
    modelXbrl = val.modelXbrl
    for doc in modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            with cast(BinaryIO, modelXbrl.fileSource.file(doc.filepath, binary=True)[0]) as file:
                initialBytes = file.read(4)
                for bom in BOM_BYTES:
                    if initialBytes.startswith(bom):
                        yield Validation.error(
                            codes='NL.FR-NL-1.01',
                            msg=_('A BOM (byte order mark) character MUST NOT be used in an XBRL instance document. Found %(bom)s.'),
                            bom=bom,
                            fileName=doc.basename,
                        )
                        return


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18,
    ],
)
def rule_fr_nl_2_03(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-2.03: The language of a report MUST be included in the 'xml:lang' attribute of the 'xbrli:xbrl' root element
    """
    modelXbrl = val.modelXbrl
    for doc in modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            lang = doc.xmlRootElement.get('{http://www.w3.org/XML/1998/namespace}lang')
            if not lang:
                yield Validation.error(
                    codes='NL.FR-NL-2.03',
                    msg=_('The language of a report MUST be included in the "xml:lang" attribute of the "xbrli:xbrl" root element.'),
                    modelObject=doc,
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18
    ],
)
def rule_fr_nl_2_04(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-2.04: The 'link:schemaRef' element MUST NOT appear more than once
    """
    schema_ref_model_objects = []
    for doc in val.modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            for refDoc, docRef in doc.referencesDocument.items():
                if docRef.referringModelObject.localName == "schemaRef":
                    schema_ref_model_objects.append(docRef.referringModelObject)
    if len(schema_ref_model_objects) > 1:
        yield Validation.error(
            codes='NL.FR-NL-2.04',
            msg=_('The \'link:schemaRef\' element must not appear more than once.'),
            modelObject=schema_ref_model_objects
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18
    ],
)
def rule_fr_nl_2_05(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-2.05: The 'link:linkbaseRef' element MUST NOT occur
    """
    linkbase_ref_model_objects = []
    for doc in val.modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            for refDoc, docRef in doc.referencesDocument.items():
                if docRef.referringModelObject.localName == "linkbaseRef":
                    linkbase_ref_model_objects.append(docRef.referringModelObject)
    if len(linkbase_ref_model_objects) > 0:
        yield Validation.error(
            codes='NL.FR-NL-2.05',
            msg=_('The \'link:linkbaseRef\' element must not occur.'),
            modelObject=linkbase_ref_model_objects
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18,
    ],
)
def rule_fr_nl_2_06(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-2.06: A CDATA end sequence ("]]>") MAY NOT be used.
    A CDATA section, specifically the end sequence, will cause the SOAP processing to fail since the instance document is itself
    wrapped in a CDATA section.

    The original wording of the rule stipulates that a CDATA "section" not be included, but prohibiting the CDATA end sequence
    specifically is a more accurate enforcement of the rule's intent.
    """
    pattern = regex.compile(r"]]>")
    modelXbrl = val.modelXbrl
    sourceFileLines = []
    for doc in modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            # By default, etree parsing replaces CDATA sections with their text content,
            # effectively removing the CDATA start/end sequences. Even when a parser has
            # strip_cdata=False, the sequences will not appear depending on how the text
            # content is retrieved. (`text` or `itertext` will not, `etree.tostring` will)
            # Info about lxml and CDATA: https://lxml.de/api.html#cdata
            # Because of this ambiguity, and to mirror the context that this validation
            # is designed for (CDATA within a SOAP request), it's preferable to check
            # the text as close as possible to its original form.
            with modelXbrl.fileSource.file(doc.filepath)[0] as file:
                for i, line in enumerate(file):
                    for __ in regex.finditer(pattern, line):
                        sourceFileLines.append((doc.filepath, i + 1))
    if len(sourceFileLines) > 0:
        yield Validation.error(
            codes='NL.FR-NL-2.06',
            msg=_('A CDATA end sequence ("]]>") MAY NOT be used in an XBRL instance document.'),
            sourceFileLines=sourceFileLines,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18
    ],
)
def rule_fr_nl_2_07(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-2.07: The attribute 'xsi:nil' MUST NOT be used
    """
    for fact in val.modelXbrl.facts:
        if fact.get("{http://www.w3.org/2001/XMLSchema-instance}nil") is not None:
            yield Validation.error(
                codes='NL.FR-NL-2.07',
                msg=_('The attribute \'xsi:nil\' must not be used.'),
                modelObject=fact
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18
    ],
)
def rule_fr_nl_3_01(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-3.01: Date elements in an 'xbrli:period' element MUST be included without time

    Based on section 3.2.7.1 of the XML Schema (https://www.w3.org/TR/xmlschema-2),
    'T' is a separator indicating that time-of-day follows the date
    """
    for context in val.modelXbrl.contexts.values():
        elt_start = XmlUtil.child(context.period, XbrlConst.xbrli, "startDate")
        elt_end = XmlUtil.child(context.period, XbrlConst.xbrli, "endDate")
        if ((elt_start is not None and 'T' in getattr(elt_start, 'text')) or
                (elt_end is not None and 'T' in getattr(elt_end, 'text'))):
            yield Validation.error(
                codes='NL.FR-NL-3.01',
                msg=_('Date elements in an \'xbrli:period\' element must be included without time'),
                modelObject=context
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18
    ],
)
def rule_fr_nl_3_02(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-3.02: The element 'xbrli:forever' MUST NOT be used
    """
    for context in val.modelXbrl.contexts.values():
        if context.isForeverPeriod:
            yield Validation.error(
                codes='NL.FR-NL-3.02',
                msg=_('The element \'xbrli:forever\' must not be used'),
                modelObject=context
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18
    ],
)
def rule_fr_nl_3_03(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-3.03: An XBRL instance document MUST NOT contain unused contexts
    """
    unused_contexts = list(set(val.modelXbrl.contexts.values()) - set(val.modelXbrl.contextsInUse))
    unused_contexts.sort(key=lambda x: x.id)
    for context in unused_contexts:
        yield Validation.error(
            codes='NL.FR-NL-3.03',
            msg=_('Unused context must not exist in XBRL instance document'),
            modelObject=context
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18
    ],
)
def rule_fr_nl_3_04(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-3.04: An XBRL instance document MUST NOT contain duplicate 'xbrli:context' elements
    """
    duplicates = defaultdict(list)
    for context in val.modelXbrl.contexts.values():
        duplicates[context.contextDimAwareHash].append(context)
    for duplicate_contexts in duplicates.values():
        if len(duplicate_contexts) > 1:
            yield Validation.error(
                codes='NL.FR-NL-3.04',
                msg=_('An XBRL instance document MUST NOT contain duplicate \'context\' elements'),
                modelObject=duplicate_contexts
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18
    ],
)
def rule_fr_nl_4_01(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-4.01: An XBRL instance document MUST NOT contain duplicate 'xbrli:unit' elements
    """
    duplicates = defaultdict(list)
    for unit in val.modelXbrl.units.values():
        duplicates[unit.hash].append(unit)
    for duplicate_units in duplicates.values():
        if len(duplicate_units) > 1:
            yield Validation.error(
                codes='NL.FR-NL-4.01',
                msg=_('An XBRL instance document MUST NOT contain duplicate \'xbrli:unit\' elements'),
                modelObject=duplicate_units
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18
    ],
)
def rule_fr_nl_4_02(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-4.02: An XBRL instance document MUST NOT contain unused 'xbrli:unit' elements
    """
    unused_units_set = set(val.modelXbrl.units.values()) - {fact.unit for fact in val.modelXbrl.facts if fact.unit is not None}
    unused_units = list(unused_units_set)
    unused_units.sort(key=lambda x: x.hash)
    for unit in unused_units:
        yield Validation.error(
            codes='NL.FR-NL-4.02',
            msg=_('Unused unit must not exist in the XBRL instance document'),
            modelObject=unit
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18
    ],
)
def rule_fr_nl_5_01(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-5.01: An XBRL instance document MUST NOT contain duplicate facts

    Duplicate facts are evaluated on concept, context and unit. Lang does not matter because of FR.KVK-2.02,
    which states that an instance document can only have one lang. Value also doesn't matter because the filing
    manual makes no distinction between consistent or inconsistent duplicate facts.
    """
    duplicates = defaultdict(list)
    for fact in val.modelXbrl.facts:
        duplicates[fact.conceptContextUnitHash].append(fact)
    for duplicate_facts in duplicates.values():
        if len(duplicate_facts) > 1:
            yield Validation.error(
                codes='NL.FR-NL-5.01',
                msg=_('An XBRL instance document must not contain duplicate facts'),
                modelObject=duplicate_facts
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18
    ],
)
def rule_fr_nl_5_03(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-5.03: An XBRL instance document MUST NOT contain empty item concepts
    """
    for fact in val.modelXbrl.facts:
        if fact.concept.instanceOfType(XbrlConst.qnXbrliStringItemType) and not fact.xValue:
            yield Validation.error(
                codes='NL.FR-NL-5.03',
                msg=_('An XBRL instance document MUST NOT contain empty item concepts.'),
                modelObject=fact
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18
    ],
)
def rule_fr_nl_5_06(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-5.06: The 'precision' attribute MUST NOT be used
    """
    for fact in val.modelXbrl.facts:
        if fact.get("precision") is not None:
            yield Validation.error(
                codes='NL.FR-NL-5.06',
                msg=_('The \'precision\' attribute must not be used.'),
                modelObject=fact
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18
    ],
)
def rule_fr_nl_5_11(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-5.11: Formatting using a limited set of 'escaped XHTML' elements MAY ONLY be included in
    fact values of facts tagged with concepts of type 'formattedExplanationItemType'.
    Only certain tags are allowed (see manual). "ul" and "ol" tags have a restriction on the "type" attribute".
    Any valid tag may have a style attribute, but only certain style properties may be used. (font-family, font-size, color)
    The manual specifies general readabilty in styling, but that is not practically enforced here.
    - No font smaller than "3" (font size can be altered in many ways that depend on browser support)
    - No white text on white background (many potential "color" values are not easily readable)
    """
    cntlr = val.modelXbrl.modelManager.cntlr
    filepath = Path(cntlr.configDir) / pluginData.textFormattingSchemaPath
    with openXmlFileStream(cntlr, filepath.as_posix(), stripDeclaration=True)[0] as file:
        text = file.read()
    schema_root = etree.XML(text)
    schema = etree.XMLSchema(schema_root)
    parser = etree.XMLParser(schema=schema)

    invalidTypeFacts = []
    typeQname = pluginData.formattedExplanationItemTypeQn
    for fact in val.modelXbrl.facts:
        validType = fact.concept.instanceOfType(typeQname)
        wrappedContent = pluginData.textFormattingWrapper.format(fact.textValue)
        try:
            tree = etree.fromstring(wrappedContent, parser)
        except etree.XMLSyntaxError as exc:
            if validType:
                yield Validation.warning(
                    codes='NL.FR-NL-5.11',
                    msg=_('Encountered XHTML syntax error while parsing "%(typeQname)s" fact value: %(error)s'),
                    typeQname=typeQname,
                    error=exc.msg,
                    modelObject=fact
                )
            continue

        #  If child elements are found and this fact is of an invalid type, trigger an error
        if len(tree) > 0 and not validType:
            invalidTypeFacts.append(fact)
            break

        invalidListItemTypes = set()
        invalidStyles = set()
        for elt in tree.iter():
            styleAttr = elt.get('style', '')
            styles = [x.split(':') for x in styleAttr.split(';')]
            for styleValues in styles:
                if len(styleValues) > 1:
                    styleProperty = styleValues[0].strip()
                    if styleProperty not in XHTML_ALLOWED_STYLES:
                        invalidStyles.add(styleProperty)
            tag = qname(elt.tag).localName
            parent = elt.getparent()
            if tag == 'li' and parent is not None:
                parentTag = qname(parent.tag).localName
                if parentTag in XHTML_LIST_ITEM_TYPES:
                    typeAttr = elt.get('type')
                    if typeAttr not in XHTML_LIST_ITEM_TYPES[parentTag]:
                        invalidListItemTypes.add(f'{parentTag}.li type="{typeAttr}"')
                        continue
        # Generate tag/styling errors per-fact so helpful information about fact contents can be reported
        if len(invalidListItemTypes) > 0:
            yield Validation.error(
                codes='NL.FR-NL-5.11',
                msg=_('Only a limited set of list item ("li") type values are allowed, depending on parent ("ul" or "ol"). '
                      'Found invalid type values: %(invalidListItemTypes)s'),
                invalidListItemTypes=sorted(invalidListItemTypes),
                modelObject=fact
            )
        if len(invalidStyles) > 0:
            yield Validation.error(
                codes='NL.FR-NL-5.11',
                msg=_('Only a limited set of style properties (%(allowedStyles)s) are allowed in escaped XHTML. '
                      'Found invalid style properties: %(invalidStyles)s'),
                allowedStyles=', '.join(sorted(XHTML_ALLOWED_STYLES)),
                invalidStyles=sorted(invalidStyles),
                modelObject=fact
            )
    if len(invalidTypeFacts) > 0:
        yield Validation.warning(
            codes='NL.FR-NL-5.11',
            msg=_('Formatting using "escaped XHTML" elements MAY ONLY be included in '
                  'fact values of facts tagged with concepts of type "%(typeQname)s"'),
            typeQname=typeQname,
            modelObject=invalidTypeFacts,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18
    ],
)
def rule_fr_nl_6_01(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-NL-6.01: Footnotes MUST NOT appear in an XBRL instance document
    """
    for doc in val.modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            for elt in doc.xmlRootElement.iter():
                if elt is not None and hasattr(elt, 'qname') and elt.qname == XbrlConst.qnLinkFootnote:
                    yield Validation.error(
                        codes='NL.FR-NL-6.01',
                        msg=_('Footnotes must not appear in an XBRL instance document.'),
                        modelObject=elt
                    )
