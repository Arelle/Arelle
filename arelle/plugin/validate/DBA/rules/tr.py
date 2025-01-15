"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import datetime
import decimal
import itertools
from collections import defaultdict
from collections.abc import Iterable
from typing import Any, cast

from arelle.typing import TypeGetText
from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.XmlValidateConst import VALID
from . import errorOnMultipleFacts
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


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
