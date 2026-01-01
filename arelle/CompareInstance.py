"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from arelle.ModelDtsObject import ModelResource
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.ModelXbrl import ModelXbrl, load
from arelle.PluginManager import pluginClassMethods
from arelle.XmlUtil import collapseWhitespace
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.ModelManager import ModelManager

_: TypeGetText


def _factFootnotes(fact: ModelFact, footnotesRelSet: ModelRelationshipSet) -> dict[str, str]:
    footnotes = {}
    footnoteRels = footnotesRelSet.fromModelObject(fact)
    if footnoteRels:
        # most process rels in same order between two instances, use labels to sort
        for i, footnoteRel in enumerate(sorted(footnoteRels,
                                               key=lambda r: (r.fromLabel,r.toLabel))):
            modelObject = footnoteRel.toModelObject
            if isinstance(modelObject, ModelResource):
                xml = collapseWhitespace(modelObject.viewText().strip())
                footnotes["Footnote {}".format(i+1)] = xml #re.sub(r'\s+', ' ', collapseWhitespace(modelObject.stringValue))
            elif isinstance(modelObject, ModelFact):
                footnotes["Footnoted fact {}".format(i+1)] = \
                    "{} context: {} value: {}".format(
                        modelObject.qname,
                        modelObject.contextID,
                        collapseWhitespace(modelObject.value))
    return footnotes


def _compareInstance(originalInstance: ModelXbrl, expectedInstance: ModelXbrl, targetInstance: ModelXbrl, matchById: bool) -> None:
    if targetInstance is None:
        originalInstance.error("compareInstance:targetInstanceNotLoaded",
                        _("Target instance for comparison was not loaded: %(file)s"),
                        modelXbrl=originalInstance,
                        file=originalInstance.uri)
        return
    if expectedInstance.modelDocument is None:
        originalInstance.error("compareInstance:expectedResultNotLoaded",
                        _("Expected result instance not loaded: %(file)s"),
                        modelXbrl=originalInstance,
                        file=originalInstance.uri)
        return
    for pluginXbrlMethod in pluginClassMethods("CompareInstance.Loaded"):
        pluginXbrlMethod(expectedInstance, targetInstance)
    if len(expectedInstance.facts) != len(targetInstance.facts):
        targetInstance.error("compareInstance:resultFactCounts",
                                    _("Found %(countFacts)s facts, expected %(expectedFacts)s facts"),
                                    modelXbrl=originalInstance, countFacts=len(targetInstance.facts),
                                    expectedFacts=len(expectedInstance.facts))
        return
    compareFootnotesRelSet = ModelRelationshipSet(targetInstance, "XBRL-footnotes")  # type: ignore[no-untyped-call]
    expectedFootnotesRelSet = ModelRelationshipSet(expectedInstance, "XBRL-footnotes")  # type: ignore[no-untyped-call]
    for expectedInstanceFact in expectedInstance.facts:
        unmatchedFactsStack: list[ModelFact] = []
        compareFact = targetInstance.matchFact(expectedInstanceFact, unmatchedFactsStack, deemP0inf=True, matchId=matchById, matchLang=False)
        if compareFact is None:
            if unmatchedFactsStack: # get missing nested tuple fact, if possible
                missingFact = unmatchedFactsStack[-1]
            else:
                missingFact = expectedInstanceFact
            # is it possible to show value mismatches?
            expectedFacts = targetInstance.factsByQname.get(missingFact.qname)
            if expectedFacts and len(expectedFacts) == 1:
                targetInstance.error("compareInstance:expectedFactMissing",
                                            _("Output missing expected fact %(fact)s, extracted value \"%(value1)s\", expected value  \"%(value2)s\""),
                                            modelXbrl=missingFact, fact=missingFact.qname, value1=missingFact.xValue, value2=next(iter(expectedFacts)).xValue)
            else:
                targetInstance.error("compareInstance:expectedFactMissing",
                                            _("Output missing expected fact %(fact)s"),
                                            modelXbrl=missingFact, fact=missingFact.qname)
        else: # compare footnotes
            expectedInstanceFactFootnotes = _factFootnotes(expectedInstanceFact, expectedFootnotesRelSet)
            compareFactFootnotes = _factFootnotes(compareFact, compareFootnotesRelSet)
            if (len(expectedInstanceFactFootnotes) != len(compareFactFootnotes) or
                    set(expectedInstanceFactFootnotes.values()) != set(compareFactFootnotes.values())):
                targetInstance.error("compareInstance:expectedFactFootnoteDifference",
                                            _("Output expected fact %(fact)s expected footnotes %(footnotes1)s produced footnotes %(footnotes2)s"),
                                            modelXbrl=(compareFact,expectedInstanceFact),
                                            fact=expectedInstanceFact.qname,
                                            footnotes1=sorted(expectedInstanceFactFootnotes.items()),
                                            footnotes2=sorted(compareFactFootnotes.items()))


def compareInstance(
        modelManager: ModelManager,
        originalInstance: ModelXbrl,
        targetInstance: ModelXbrl,
        expectedInstanceUri: str,
        errorCaptureLevel: int,
        matchById: bool
) -> list[str | None]:
    expectedInstance = load(modelManager,
                            expectedInstanceUri,
                            _("loading expected result XBRL instance"),
                            errorCaptureLevel=errorCaptureLevel)
    _compareInstance(originalInstance, expectedInstance, targetInstance, matchById)
    expectedInstance.close()
    errors = targetInstance.errors
    return errors
