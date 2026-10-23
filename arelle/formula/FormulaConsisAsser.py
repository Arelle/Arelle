"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from math import fabs
from typing import TYPE_CHECKING

from arelle import XbrlConst
from arelle.ModelFormulaObject import ModelConsistencyAssertion
from arelle.typing import TypeGetText
from arelle.ValidateXbrlCalcs import inferredPrecision, roundValue
from arelle.XbrlUtil import S_EQUAL2, xEqual

if TYPE_CHECKING:
    from arelle.formula.XPathContext import XPathContext
    from arelle.ModelFormulaObject import ModelVariableSet
    from arelle.ModelInstanceObject import ModelFact

_: TypeGetText


def evaluate(xpCtx: XPathContext, varSet: ModelVariableSet, derivedFact: ModelFact | None) -> None:
    # there may be multiple consis assertions parenting any formula
    for consisAsserRel in xpCtx.modelXbrl.relationshipSet(XbrlConst.consistencyAssertionFormula).toModelObject(varSet):
        consisAsser = consisAsserRel.fromModelObject
        assert isinstance(consisAsser, ModelConsistencyAssertion)
        hasProportionalAcceptanceRadius = consisAsser.hasProportionalAcceptanceRadius
        hasAbsoluteAcceptanceRadius = consisAsser.hasAbsoluteAcceptanceRadius
        if derivedFact is None:
            continue
        isNumeric = derivedFact.isNumeric
        if isNumeric and not derivedFact.isNil:
            derivedFactInferredPrecision = inferredPrecision(derivedFact)
            if (
                derivedFactInferredPrecision == 0
                and not hasProportionalAcceptanceRadius
                and not hasAbsoluteAcceptanceRadius
            ):
                if xpCtx.formulaOptions.traceVariableSetExpressionResult:
                    xpCtx.modelXbrl.info(
                        "formula:trace",
                        _("Consistency assertion %(id)s formula %(xlinkLabel)s fact %(derivedFact)s has zero precision and no radius is defined, skipping consistency assertion"),
                        modelObject=consisAsser,
                        id=consisAsser.id,
                        xlinkLabel=varSet.xlinkLabel,
                        derivedFact=derivedFact,
                    )
                continue

        # check xbrl validity of new fact

        # find source facts which match derived fact
        aspectMatchedInputFacts = []
        isStrict = consisAsser.isStrict
        for inputFact in xpCtx.modelXbrl.facts:
            if (
                not inputFact.isNil
                and inputFact.qname == derivedFact.qname
                and inputFact.context.isEqualTo(  # type: ignore[union-attr]
                    derivedFact.context, dimensionalAspectModel=(varSet.aspectModel == "dimensional")
                )
                and (not isNumeric or inputFact.unit.isEqualTo(derivedFact.unit))  # type: ignore[union-attr]
            ):
                aspectMatchedInputFacts.append(inputFact)

        if len(aspectMatchedInputFacts) == 0:
            if isStrict:
                if derivedFact.isNil:
                    isSatisfied: bool | None = True
                else:
                    isSatisfied = False
            else:
                if xpCtx.formulaOptions.traceVariableSetExpressionResult:
                    xpCtx.modelXbrl.info(
                        "formula:trace",
                        _("Consistency assertion %(id)s formula %(xlinkLabel)s no input facts matched to %(derivedFact)s, skipping consistency assertion"),
                        modelObject=consisAsser,
                        id=consisAsser.id,
                        xlinkLabel=varSet.xlinkLabel,
                        derivedFact=derivedFact,
                    )
                continue
        elif derivedFact.isNil:
            isSatisfied = False
        else:
            isSatisfied = True

        paramQnamesAdded = []
        for paramRel in consisAsser.orderedVariableRelationships:  # type: ignore[attr-defined]
            paramQname = paramRel.variableQname
            paramVar = paramRel.toModelObject
            paramValue = xpCtx.inScopeVars.get(paramVar.parameterQname)
            paramAlreadyInVars = paramQname in xpCtx.inScopeVars
            if not paramAlreadyInVars:
                paramQnamesAdded.append(paramQname)
                xpCtx.inScopeVars[paramQname] = paramValue  # type: ignore[assignment]
        acceptance = None
        for fact in aspectMatchedInputFacts:
            if isSatisfied != True:
                break
            if fact.isNil:
                if not derivedFact.isNil:
                    isSatisfied = False
            elif isNumeric:
                factInferredPrecision = inferredPrecision(fact)
                if (
                    factInferredPrecision == 0
                    and not hasProportionalAcceptanceRadius
                    and not hasAbsoluteAcceptanceRadius
                ):
                    if xpCtx.formulaOptions.traceVariableSetExpressionResult:
                        xpCtx.modelXbrl.info(
                            "formula:trace",
                            _("Consistency assertion %(id)s formula %(xlinkLabel)s input fact matched to %(derivedFact)s has zero precision and no radius, skipping consistency assertion"),
                            modelObject=consisAsser,
                            id=consisAsser.id,
                            xlinkLabel=varSet.xlinkLabel,
                            derivedFact=derivedFact,
                        )
                        isSatisfied = None
                        break
                if hasProportionalAcceptanceRadius or hasAbsoluteAcceptanceRadius:
                    acceptance = consisAsser.evalRadius(xpCtx, derivedFact.vEqValue)
                    if acceptance is not None:
                        if hasProportionalAcceptanceRadius:
                            acceptance *= derivedFact.vEqValue
                        isSatisfied = fabs(derivedFact.vEqValue - fact.vEqValue) <= fabs(acceptance)  # type: ignore[operator]
                    else:
                        isSatisfied = None  # no radius
                else:
                    p = min(derivedFactInferredPrecision, factInferredPrecision)
                    if p == 0 or roundValue(derivedFact.value, precision=p) != roundValue(fact.value, precision=p):
                        isSatisfied = False
            else:
                if not xEqual(fact, derivedFact, equalMode=S_EQUAL2):
                    isSatisfied = False
        if isSatisfied is not None:  # None means no evaluation
            if xpCtx.formulaOptions.traceVariableSetExpressionResult:
                xpCtx.modelXbrl.info(
                    "formula:trace",
                    _("Consistency assertion %(id)s result %(result)s"),
                    modelObject=consisAsser,
                    id=consisAsser.id,
                    result=isSatisfied,
                )
            message = consisAsser.message(isSatisfied)
            if message is not None:
                xpCtx.inScopeVars[XbrlConst.qnCaAspectMatchedFacts] = aspectMatchedInputFacts  # type: ignore[assignment]
                xpCtx.inScopeVars[XbrlConst.qnCaAcceptanceRadius] = acceptance  # type: ignore[assignment]
                xpCtx.inScopeVars[XbrlConst.qnCaAbsoluteAcceptanceRadiusExpression] = consisAsser.get("absoluteAcceptanceRadius")  # type: ignore[assignment]
                xpCtx.inScopeVars[XbrlConst.qnCaProportionalAcceptanceRadiusExpression] = consisAsser.get("proportionalAcceptanceRadius")  # type: ignore[assignment]
                xpCtx.modelXbrl.info(
                    "message:" + consisAsser.id,  # type: ignore[operator]
                    message.evaluate(xpCtx),  # type: ignore[union-attr]
                    modelObject=message,
                    messageCodes=("message:{variableSetID|xlinkLabel}"),
                )
                xpCtx.inScopeVars.pop(XbrlConst.qnCaAspectMatchedFacts)
                xpCtx.inScopeVars.pop(XbrlConst.qnCaAcceptanceRadius)
                xpCtx.inScopeVars.pop(XbrlConst.qnCaAbsoluteAcceptanceRadiusExpression)
                xpCtx.inScopeVars.pop(XbrlConst.qnCaProportionalAcceptanceRadiusExpression)
            if isSatisfied:
                consisAsser.countSatisfied += 1  # type: ignore[attr-defined]
            else:
                consisAsser.countNotSatisfied += 1  # type: ignore[attr-defined]
        for paramQname in paramQnamesAdded:
            xpCtx.inScopeVars.pop(paramQname)
