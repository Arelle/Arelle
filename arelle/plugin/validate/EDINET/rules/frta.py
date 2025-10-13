"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from arelle import XbrlConst, ModelDocument
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
    EDINET.EC5710W: [FRTA.2.1.10] All extension taxonomy concepts must have a standard label.
    """
    errors = []
    for concept in val.modelXbrl.qnameConcepts.values():
        if pluginData.isStandardTaxonomyUrl(concept.modelDocument.uri, val.modelXbrl):
            continue
        if not concept.label(XbrlConst.standardLabel, fallbackToQname=False):
            errors.append(concept)
    if len(errors) > 0:
        yield Validation.warning(
            codes='EDINET.EC5710W.FRTA.2.1.10',
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


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_frta_4_2_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5710W: [FRTA.4.2.2] Taxonomy schemas must be defined in XML documents in which the XML Schema 'schema'
                                 element appears once only as the root element.
    """
    for modelDocument in val.modelXbrl.urlDocs.values():
        if pluginData.isStandardTaxonomyUrl(modelDocument.uri, val.modelXbrl):
            continue
        # check for nested Schema declarations which are not allowed.
        schemaElts = {elt for elt in modelDocument.xmlRootElement.iterdescendants(XbrlConst.qnXsdSchema.clarkNotation)}
        if len(schemaElts) > 0:
            yield Validation.warning(
                codes='EDINET.EC5710W.FRTA.4.2.2',
                msg=_("The root of a taxonomy schema file MUST be the XMLSchema element."),
                modelObject=modelDocument,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_frta_4_2_4(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5710W: [FRTA.4.2.4] Taxonomy schemas must declare elementFormDefault to be 'qualified',
                                 attributeFormDefault must have the value 'unqualified', and the 'form' attribute
                                  must not appear on element and attribute declarations.
    """
    for modelDocument in val.modelXbrl.urlDocs.values():
        if pluginData.isStandardTaxonomyUrl(modelDocument.uri, val.modelXbrl) or not modelDocument.type == ModelDocument.Type.SCHEMA:
            continue
        rootElt = modelDocument.xmlRootElement
        if rootElt.get('elementFormDefault') != 'qualified' or rootElt.get('attributeFormDefault') != 'unqualified':
            yield Validation.warning(
                codes='EDINET.EC5710W.FRTA.4.2.4',
                msg=_("The XMLSchema root in taxonomy schema files must have the 'elementFormDefault' attribute set as "
                      "'qualified' and the 'attributeFormDefault' attribute set as 'unqualified'"),
                modelObject=modelDocument,
            )
        formUsages = []
        for elt in rootElt.iterdescendants([XbrlConst.qnXsdElement.clarkNotation, XbrlConst.qnXsdAttribute.clarkNotation]):
            if elt.get('form') is not None:
                formUsages.append(elt)
        if len(formUsages) > 0:
            yield Validation.warning(
                codes='EDINET.EC5710W.FRTA.4.2.4',
                msg=_("The 'form' attribute is not allowed on 'xsd:element' or 'xsd:attribute' declarations in a schema file"),
                modelObject=formUsages,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_frta_4_2_7(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5710W: [FRTA.4.2.7] A label linkbase should only contain labels defined in a single language.
    """
    for modelDocument in val.modelXbrl.urlDocs.values():
        if pluginData.isStandardTaxonomyUrl(modelDocument.uri, val.modelXbrl) or not modelDocument.type == ModelDocument.Type.LINKBASE:
            continue
        usedLangs = {
            elt.get(XbrlConst.qnXmlLang.clarkNotation)
            for elt in modelDocument.xmlRootElement.iterdescendants(XbrlConst.qnLinkLabel.clarkNotation)
        }
        if len(usedLangs) > 1:
            yield Validation.warning(
                codes='EDINET.EC5710W.FRTA.4.2.7',
                msg=_("A label linkbase should only contain labels defined in a single language. This linkbase uses the following languages: %(langs)s"),
                langs=usedLangs,
                modelObject=modelDocument,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_frta_4_2_11(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5710W: [FRTA.4.2.11] Every schema in a DTS must define a non-empty targetNamespace attribute value
    """
    for modelDocument in val.modelXbrl.urlDocs.values():
        if pluginData.isStandardTaxonomyUrl(modelDocument.uri, val.modelXbrl) or not modelDocument.type == ModelDocument.Type.SCHEMA:
            continue
        rootElt = modelDocument.xmlRootElement
        if rootElt.get('targetNamespace') is None or rootElt.get('targetNamespace') == "":
            yield Validation.warning(
                codes='EDINET.EC5710W.FRTA.4.2.11',
                msg=_("Every schema in a DTS must define a non-empty targetNamespace attribute value."),
                modelObject=modelDocument,
            )
