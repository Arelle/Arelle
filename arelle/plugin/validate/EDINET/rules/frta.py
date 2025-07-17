"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from arelle import XbrlConst
from arelle.ModelDtsObject import ModelResource, ModelConcept
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import (DISCLOSURE_SYSTEM_EDINET)
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_frta_2_1_9(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5710W: [FRTA.2.1.9] All documentation of a concept must be contained
    in XBRL linkbases. Do not use the xsd:documentation element in an element definition.
    """
    errors = []
    for modelDocument in val.modelXbrl.urlDocs.values():
        if pluginData.isStandardTaxonomyUrl(modelDocument.uri, val.modelXbrl):
            continue
        rootElt = modelDocument.xmlRootElement
        for elt in rootElt.iterdescendants(XbrlConst.qnXsdDocumentation.clarkNotation):
            errors.append(elt)
    if len(errors) > 0:
        yield Validation.warning(
            codes='EDINET.EC5710W.FRTA.2.1.9',
            msg=_("All documentation of a concept must be contained in XBRL linkbases. "
                  "Taxonomy element declarations should not use the XML Schema documentation element."),
            modelObject=errors,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_frta_2_1_10(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET: [FRTA.2.1.10] All extension taxonomy concepts must have a standard label.
    """
    errors = []
    for concept in val.modelXbrl.qnameConcepts.values():
        if pluginData.isStandardTaxonomyUrl(concept.modelDocument.uri, val.modelXbrl):
            continue
        if not concept.label(XbrlConst.standardLabel, fallbackToQname=False):
            errors.append(concept)
    if len(errors) > 0:
        yield Validation.warning(
            codes='EDINET.FRTA.2.1.10',  # Not associated with EC5710W code.
            msg=_("All extension taxonomy concepts must have a standard label. "
                  "A standard label is not specified for a concept in an "
                  "extension taxonomy. When adding a concept to an extension taxonomy, "
                  "please provide Japanese and English labels in the standard, verbose, and "
                  "documentation roles."),
            modelObject=errors,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_frta_2_1_11(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5710W: [FRTA.2.1.11] All concepts within a taxonomy schema should have a
    unique label for the standard or verbose role in each language used.
    """
    labelsRelationshipSet = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    labelGroupsByLang: dict[str, dict[str, dict[str, set[ModelConcept]]]] = (
        defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    )
    relevantRoles = frozenset({
        XbrlConst.standardLabel,
        XbrlConst.verboseLabel
    })
    for concept, modelLabelRels in labelsRelationshipSet.fromModelObjects().items():
        if pluginData.isStandardTaxonomyUrl(concept.modelDocument.uri, val.modelXbrl):
            continue
        for modelLabelRel in modelLabelRels:
            modelLabel = modelLabelRel.toModelObject
            if not isinstance(modelLabel, ModelResource):
                continue
            if modelLabel.role not in relevantRoles:
                continue
            if not modelLabel.modelDocument.inDTS:
                continue
            if not modelLabel.xmlLang:
                continue
            labelGroupsByLang[modelLabel.xmlLang][modelLabel.role][modelLabel.textValue].add(concept)
    for lang, labelGroupsByRole in labelGroupsByLang.items():
        duplicateLabelsByRole = defaultdict(list)
        conceptsWithVerboseLabel = {
            concept: False
            for concept in val.modelXbrl.qnameConcepts.values()
            if not pluginData.isStandardTaxonomyUrl(concept.modelDocument.uri, val.modelXbrl)
        }
        for role, labelGroupsByValue in labelGroupsByRole.items():
            for value, concepts in labelGroupsByValue.items():
                if role == XbrlConst.verboseLabel:
                    for concept in concepts:
                        conceptsWithVerboseLabel[concept] = True
                if len(concepts) < 2:
                    continue
                duplicateLabelsByRole[role].append((value, concepts))
        if len(duplicateLabelsByRole[XbrlConst.standardLabel]) == 0:
            # There are no duplicate standard labels, so we don't need to check verbose labels
            continue
        conceptsWithoutVerboseLabel = {concept for concept, value in conceptsWithVerboseLabel.items() if not value}
        if len(duplicateLabelsByRole[XbrlConst.verboseLabel]) == 0 and len(conceptsWithoutVerboseLabel) == 0:
            # All concepts have a verbose label, and there are no duplicate verbose labels,
            return
        for role, duplicateLabels in duplicateLabelsByRole.items():
            for value, concepts in duplicateLabels:
                yield Validation.warning(
                    codes='EDINET.EC5710W.FRTA.2.1.11',
                    msg=_("All concepts within a taxonomy schema should have a unique label for the "
                          "standard or verbose role in each language used. "
                          "The %(role)s label contains a duplicate label ('%(value)s') in the same "
                          "language ('%(lang)s'). Define either the standard label or the verbose label "
                          "so that they are unique in the same language."),
                    role='standard' if role == XbrlConst.standardLabel else 'verbose',
                    value=value,
                    lang=lang,
                    modelObject=concepts,
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_frta_3_1_10(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5710W: [FRTA.3.1.10] Role types defined in the extension taxonomy must have a definition.
    """
    errors = []
    for uri, roleTypes in val.modelXbrl.roleTypes.items():
        for roleType in roleTypes:
            if pluginData.isStandardTaxonomyUrl(roleType.document.uri, val.modelXbrl):
                continue
            if not roleType.definition:
                errors.append(roleType)
    if len(errors) > 0:
        yield Validation.warning(
            codes='EDINET.EC5710W.FRTA.3.1.10',
            msg=_("Role types defined in the extension taxonomy must have a definition."),
            modelObject=errors,
        )
