"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import codecs
from pathlib import Path
from typing import Any, Iterable, cast

import regex

from arelle import ModelDocument, XbrlConst
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
    foundChars = set()
    sourceFileLines = []
    for doc in modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            with modelXbrl.fileSource.file(doc.filepath)[0] as file:
                for i, line in enumerate(file):
                    for match in regex.finditer(UNICODE_CHARACTER_RANGES_PATTERN, line):
                        foundChars.add(match.group())
                        sourceFileLines.append((doc.filepath, i + 1))
    if len(sourceFileLines) > 0:
        yield Validation.error(
            codes='NL.FR-NL-1.02',
            msg=_('Characters MUST be from the Unicode ranges Basic Latin, Latin Supplement and Currency Symbols '
                  '(ranges %(ranges)s). '
                  'Found disallowed characters: %(foundChars)s'),
            foundChars=sorted(foundChars),
            ranges=', '.join(f'{hex(min)}-{hex(max)}' for min, max in UNICODE_CHARACTER_DECIMAL_RANGES),
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
            if 'UTF-8' != doc.xmlDocument.docinfo.encoding:
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
            with modelXbrl.fileSource.file(doc.filepath, binary=True)[0] as file:
                firstLine = cast(bytes, file.readline())
                for bom in BOM_BYTES:
                    if firstLine.startswith(bom):
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
                if elt is not None and elt.qname == XbrlConst.qnLinkFootnote:
                    yield Validation.error(
                        codes='NL.FR-NL-6.01',
                        msg=_('Footnotes must not appear in an XBRL instance document.'),
                        modelObject=elt
                    )
