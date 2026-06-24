"""
See COPYRIGHT.md for copyright information.
"""
import re
from typing import Any

from collections.abc import Iterable

from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..ESEF_2021.ValidateXbrlFinally import validateXbrlFinally as validateXbrlFinally2021
from ..ESEF_Current.ValidateXbrlFinally import validateXbrlFinally as validateXbrlFinallyCurrent
from ..PluginValidationDataExtension import PluginValidationDataExtension
from ..Util import getDisclosureSystemYear, shouldRunEsefValidationRules

_: TypeGetText

ixErrorPattern = re.compile(r"ix11[.]|xmlSchema[:]|(?!xbrl.5.2.5.2|xbrl.5.2.6.2)xbrl[.]|xbrld[ti]e[:]|utre[:]")
dupIdErrorPattern = re.compile(r"xml.3.3.1:idMustBeUnique|ix11.14.1.2:uniqueIxId")


@validation(
    hook=ValidationHook.FINALLY,
)
def rule_finally(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    Performs final ESEF validation checks after all other validation has completed.

    Skips validation for unconsolidated reports or when ESEF rules are not applicable.
    """
    if not shouldRunEsefValidationRules(val):
        return
    if val.unconsolidated:
        return
    modelXbrl = val.modelXbrl
    modelDocument = getattr(modelXbrl, "modelDocument")
    if (modelDocument is None or not modelXbrl.facts) and "ESEF.RTS.Art.6.a.noInlineXbrlTags" not in modelXbrl.errors:
        yield Validation.error(
            "ESEF.RTS.Art.6.a.noInlineXbrlTags",
            _("RTS on ESEF requires inline XBRL, no facts were reported."),
            modelObject=modelXbrl
        )
        return # never loaded properly

    disclosureSystemYear = getDisclosureSystemYear(modelXbrl)
    if disclosureSystemYear >= 2025:
        numDupIdErrors = sum(dupIdErrorPattern.match(e) is not None for e in modelXbrl.errors if isinstance(e,str))
        if numDupIdErrors:
            yield Validation.warning(
                "ESEF.2.2.8.duplicatedIdAttribute",
                  _("ID attributes should be unique, %(numDupIdErrors)s such errors were reported."),
                  modelObject=modelXbrl,
                numDupIdErrors=numDupIdErrors
            )

    numXbrlErrors = sum(ixErrorPattern.match(e) is not None for e in modelXbrl.errors if isinstance(e,str))
    if numXbrlErrors:
        yield Validation.error(
            "ESEF.RTS.Annex.III.Par.1.invalidInlineXBRL",
            _("RTS on ESEF requires valid XBRL instances, %(numXbrlErrors)s errors were reported."),
            modelObject=modelXbrl,
            numXbrlErrors=numXbrlErrors
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_xbrl_finally(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    Dispatches validations to the appropriate year-specific implementation.

    Skips validation when ESEF rules are not applicable.
    """
    if not shouldRunEsefValidationRules(val):
        return
    disclosureSystemYear = getDisclosureSystemYear(val.modelXbrl)
    if disclosureSystemYear == 2021:
        validateXbrlFinally2021(val, *args, **kwargs)
    else:
        validateXbrlFinallyCurrent(val, *args, **kwargs)
    yield from iter([])
