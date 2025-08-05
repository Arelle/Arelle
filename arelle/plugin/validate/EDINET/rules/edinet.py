"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any, Iterable, cast

from arelle import XbrlConst, ValidateDuplicateFacts
from arelle.LinkbaseType import LinkbaseType
from arelle.ValidateDuplicateFacts import DuplicateType
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
def rule_EC1057E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC1057E: The submission date on the cover page has not been filled in.
    Ensure that there is a nonnil value disclosed for FilingDateCoverPage
    Note: This rule is only applicable to the public documents.
    """
    dei = pluginData.getDocumentTypes(val.modelXbrl)
    if len(dei) > 0:
        if not (pluginData.hasRequiredValidFact(val.modelXbrl, pluginData.jpcrpEsrFilingDateCoverPageQn)
                or pluginData.hasRequiredValidFact(val.modelXbrl, pluginData.jpcrpFilingDateCoverPageQn)
                or pluginData.hasRequiredValidFact(val.modelXbrl, pluginData.jpspsFilingDateCoverPageQn)):
            yield Validation.error(
                codes='EDINET.EC1057E',
                msg=_("The [Submission Date] on the cover page has not been filled in."),
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC5002E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5002E: A unit other than number of shares (xbrli:shares) has been set for the
    Number of Shares (xbrli:sharesItemType) item '{xxx}yyy'.
    Please check the units and enter the correct information.

    Similar to "xbrl.4.8.2:sharesFactUnit-notSharesMeasure" and "xbrl.4.8.2:sharesFactUnit-notSingleMeasure"
    TODO: Consolidate this rule with the above two rules if possible.
    """
    errorFacts = []
    for fact in val.modelXbrl.facts:
        concept = fact.concept
        if concept is None or not concept.isShares:
            continue
        unit = fact.unit
        measures = unit.measures
        if (
                not measures or
                len(measures[0]) != 1 or
                len(measures[1]) != 0 or
                measures[0][0] != XbrlConst.qnXbrliShares
        ):
            errorFacts.append(fact)
    for fact in errorFacts:
        yield Validation.error(
            codes='EDINET.EC5002E',
            msg=_("A unit other than number of shares (xbrli:shares) has been set for "
                  "the Number of Shares (xbrli:sharesItemType) item '%(qname)s'. "
                  "Please check the units and enter the correct information."),
            qname=fact.qname.clarkNotation,
            modelObject=fact,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8024E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8024E: Instance values of the same element, context, and unit may not
    have different values or different decimals attributes.
    Correct the element with the relevant context ID. For elements in an inline XBRL file that have
    duplicate elements, context IDs, and unit IDs, set the same values for the value and
    decimals attribute.
    """
    duplicateFactSets = ValidateDuplicateFacts.getDuplicateFactSetsWithType(val.modelXbrl.facts, DuplicateType.INCOMPLETE)
    for duplicateFactSet in duplicateFactSets:
        fact = duplicateFactSet.facts[0]
        yield Validation.error(
            codes='EDINET.EC8024E',
            msg=_("Instance values of the same element, context, and unit may not "
                  "have different values or different decimals attributes. <element=%(concept)s> "
                  "<contextID=%(context)s> <unit=%(unit)s>. Correct the element with the relevant "
                  "context ID. For elements in an inline XBRL file that have duplicate "
                  "elements, context IDs, and unit IDs, set the same values for the value and "
                  "decimals attribute."),
            concept=fact.qname,
            context=fact.contextID,
            unit=fact.unitID,
            modelObject=duplicateFactSet.facts,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8027W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8027W: For presentation links and definition links, there must be
    only one root element.
    File name: xxx <Extended link role = yyy>
    Please correct the extended link role of the relevant file. Please set only one
    root element of the extended link role in the presentation link and definition link.
    """
    linkbaseTypes = (LinkbaseType.PRESENTATION, LinkbaseType.DEFINITION)
    roleTypes = [
        roleType
        for roleTypes in val.modelXbrl.roleTypes.values()
        for roleType in roleTypes
    ]
    for roleType in roleTypes:
        for linkbaseType in linkbaseTypes:
            if linkbaseType.getLinkQn() not in roleType.usedOns:
                continue
            arcroles = linkbaseType.getArcroles()
            relSet = val.modelXbrl.relationshipSet(tuple(arcroles), roleType.roleURI)
            relSetFrom = relSet.loadModelRelationshipsFrom()
            rootConcepts = relSet.rootConcepts
            if len(rootConcepts) < 2:
                continue
            rels = [
                rel
                for rootConcept in rootConcepts
                for rel in relSetFrom[rootConcept]
            ]
            yield Validation.warning(
                codes='EDINET.EC8027W',
                msg=_("For presentation links and definition links, there must be only one root element. "
                      "File name: %(filename)s <Extended link role = %(roleUri)s> "
                      "Please correct the extended link role of the relevant file. Please set only one "
                      "root element of the extended link role in the presentation link and definition link."),
                filename=rels[0].modelDocument.basename,
                roleUri=roleType.roleURI,
                modelObject=rels,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8062W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8062W: The sum of all liabilities and equity must equal the sum of all assets.
    """
    deduplicatedFacts = pluginData.getDeduplicatedFacts(val.modelXbrl)

    factsByContextId = defaultdict(list)
    for fact in deduplicatedFacts:
        if fact.qname not in (pluginData.assetsIfrsQn, pluginData.liabilitiesAndEquityIfrsQn):
            continue
        if fact.contextID is None or not pluginData.contextIdPattern.fullmatch(fact.contextID):
            continue
        factsByContextId[fact.contextID].append(fact)

    for facts in factsByContextId.values():
        assetSum = Decimal(0)
        liabilitiesAndEquitySum = Decimal(0)
        for fact in facts:
            if isinstance(fact.xValue, float):
                value = Decimal(fact.xValue)
            else:
                value = cast(Decimal, fact.xValue)
            if fact.qname == pluginData.assetsIfrsQn:
                assetSum += value
            elif fact.qname == pluginData.liabilitiesAndEquityIfrsQn:
                liabilitiesAndEquitySum += value
        if assetSum != liabilitiesAndEquitySum:
            yield Validation.warning(
                codes='EDINET.EC8062W',
                msg=_("The consolidated statement of financial position is not reconciled. "
                      "The sum of all liabilities and equity must equal the sum of all assets. "
                      "Please correct the debit (%(liabilitiesAndEquitySum)s) and credit (%(assetSum)s) "
                      "values so that they match."),
                liabilitiesAndEquitySum=f"{liabilitiesAndEquitySum:,}",
                assetSum=f"{assetSum:,}",
                modelObject=facts,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8075W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8075W: The percentage of female executives has not been tagged in detail. Ensure that there is
    a nonnil value disclosed for jpcrp_cor:RatioOfFemaleDirectorsAndOtherOfficers.
    """
    if pluginData.isCorporateForm(val.modelXbrl):
        if not pluginData.hasRequiredValidFact(val.modelXbrl, pluginData.ratioOfFemaleDirectorsAndOtherOfficersQn):
            yield Validation.warning(
                codes='EDINET.EC8075W',
                msg=_("The percentage of female executives has not been tagged in detail."),
                )
