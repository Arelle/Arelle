"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any, Iterable

from arelle.LinkbaseType import LinkbaseType
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import (DISCLOSURE_SYSTEM_EDINET)
from ..ManifestInstance import ManifestTocItem
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


def _validateTocItem(modelXbrl: ModelXbrl, tocItem: ManifestTocItem, instanceId: str) -> Iterable[Validation]:
    for childTocItem in tocItem.childItems:
        yield from _validateTocItem(modelXbrl, childTocItem, instanceId)
    relSet = modelXbrl.relationshipSet(tuple(LinkbaseType.PRESENTATION.getArcroles()), tocItem.extrole)
    if len(relSet.fromModelObjects()) == 0:
        yield Validation.error(
            codes="EDINET.EC5800E.FATAL_ERROR_TOC_TREE_NOT_DEFINED",
            msg=_("A table of contents item specified an extended link role "
                  "that does not exist in the presentation linkbase. "),
            modelObject=tocItem.element,
        )
    for conceptQname in {tocItem.parent, tocItem.start, tocItem.end}:
        if conceptQname is None:
            continue
        concept = modelXbrl.qnameConcepts.get(conceptQname)
        if concept is None or not relSet.contains(concept):
            yield Validation.error(
                codes="EDINET.EC5800E.ERROR_ELEMENT_NOT_DEFINED_IN_EXTENDED_LINK_ROLE",
                msg=_("A table of contents item specified an extended link role "
                      "that does not contain the element specified by the parent "
                      "attribute of the insert element or the start or end "
                      "attribute of the item element. Check the extended link "
                      "role and correct it."),
                modelObject=tocItem.element,
            )
    if tocItem.end is not None:
        if tocItem.start is None or \
                not relSet.isRelated(tocItem.start, "child", tocItem.end):
            yield Validation.error(
                codes="EDINET.EC5800E.ERROR_ENDING_ELEMENT_NOT_DEFINED_UNDER_STARTING_ELEMENT",
                msg=_("A table of contents item specified an end element that "
                      "is not a descendant of the start element within the "
                      "specified extended link role. Please check and correct "
                      "the table of contents items."),
                modelObject=tocItem.element,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC5800E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5800E.FATAL_ERROR_TOC_TREE_NOT_DEFINED:
    A table of contents item specified an extended link role that does not
    exist in the presentation linkbase.
    EDINET.EC5800E.ERROR_ELEMENT_NOT_DEFINED_IN_EXTENDED_LINK_ROLE:
    A table of contents item specified an extended link role that does not
    contain the element specified by the parent attribute of the insert
    element or the start or end attribute of the item element. Check the
    extended link role and correct it.
    EDINET.EC5800E.ERROR_ENDING_ELEMENT_NOT_DEFINED_UNDER_STARTING_ELEMENT:
    A table of contents item specified an end element that is not a descendant
    of the start element within the specified extended link role. Please check
    and correct the table of contents items.
    """
    instance = pluginData.getManifestInstance(val.modelXbrl)
    if instance is None:
        return
    for tocItem in instance.tocItems:
        yield from _validateTocItem(val.modelXbrl, tocItem, instance.id)
