from dataclasses import dataclass
from types import SimpleNamespace

import arelle.ModelFormulaObject
from arelle.ModelValue import qname
from arelle.formula import FormulaEvaluator
from arelle.formula.FormulaEvaluator import VariableBinding, trialFilterFacts


@dataclass
class DummyBoundFact:
    context: str


@dataclass
class DummyContext:
    qnameDims: dict


class DummyItemFact:
    def __init__(self, name: str, dims: dict) -> None:
        self.name = name
        self.isItem = True
        self.context = DummyContext(dims)


class DummyFilter:
    def aspectsCovered(self, var_binding) -> set:
        return set()


def _handled_filter_rel(dim) -> tuple:
    return (
        SimpleNamespace(
            toModelObject=DummyFilter(),
            isCovered=False,
        ),
        dim,
    )


def _group_filter_var_set(no_compl_dims: tuple = (), compl_dims: tuple = ()) -> SimpleNamespace:
    return SimpleNamespace(
        filterInfo=True,
        noComplHandledFilterRels=[_handled_filter_rel(dim) for dim in no_compl_dims],
        complHandledFilterRels=[_handled_filter_rel(dim) for dim in compl_dims],
        unHandledFilterRels=[],
    )


def test_fact_variable_evaluation_results_yield_fallback_after_facts_exist() -> None:
    vb = VariableBinding.__new__(VariableBinding)
    vb.isFactVar = True
    vb.isBindAsSequence = False
    vb.facts = [DummyBoundFact("c1")]
    vb.values = ["fallback"]
    vb.yieldedFact = None
    vb.yieldedFactContext = None
    vb.yieldedEvaluation = None
    vb.isFallback = False

    results = list(vb.evaluationResults)

    assert results == [vb.facts[0], vb.values]


def test_fact_variable_evaluation_results_yield_fallback_when_sequence_binding_has_no_matches(monkeypatch) -> None:
    vb = VariableBinding.__new__(VariableBinding)
    vb.isFactVar = True
    vb.isBindAsSequence = True
    vb.facts = [DummyBoundFact("c1")]
    vb.values = ["fallback"]
    vb.aspectsDefined = set()
    vb.aspectsCovered = set()
    vb.xpCtx = SimpleNamespace()
    vb.matchesSubPartitions = lambda partition, aspects: iter(())
    vb.yieldedFact = None
    vb.yieldedFactContext = None
    vb.yieldedEvaluation = None
    vb.isFallback = False

    monkeypatch.setattr(FormulaEvaluator, "factsPartitions", lambda xpCtx, facts, aspects: [facts])

    results = list(vb.evaluationResults)

    assert results == [vb.values]


def test_fact_variable_evaluation_results_yield_fallback_for_sequence_binding_with_matches(monkeypatch) -> None:
    fact = DummyBoundFact("c1")
    vb = VariableBinding.__new__(VariableBinding)
    vb.isFactVar = True
    vb.isBindAsSequence = True
    vb.facts = [fact]
    vb.values = ["fallback"]
    vb.aspectsDefined = set()
    vb.aspectsCovered = set()
    vb.xpCtx = SimpleNamespace()
    vb.matchesSubPartitions = lambda partition, aspects: iter(((fact,),))
    vb.yieldedFact = None
    vb.yieldedFactContext = None
    vb.yieldedEvaluation = None
    vb.isFallback = False

    monkeypatch.setattr(FormulaEvaluator, "factsPartitions", lambda xpCtx, facts, aspects: [facts])

    results = list(vb.evaluationResults)

    assert results == [(fact,), vb.values]


def test_trial_filter_facts_requires_all_non_complement_dimensions() -> None:
    dim_a = qname("{http://example.com}a")
    dim_b = qname("{http://example.com}b")
    fact_with_both = DummyItemFact("both", {dim_a: object(), dim_b: object()})
    fact_with_one = DummyItemFact("one", {dim_a: object()})

    result = trialFilterFacts(
        xpCtx=SimpleNamespace(),
        vb=SimpleNamespace(aspectsCovered=set()),
        facts={fact_with_both, fact_with_one},
        filterRelationships=[],
        filterType="group",
        varSet=_group_filter_var_set(no_compl_dims=(dim_a, dim_b)),
    )

    assert result == {fact_with_both}


def test_trial_filter_facts_requires_all_complement_dimensions_to_be_absent() -> None:
    dim_a = qname("{http://example.com}a")
    dim_b = qname("{http://example.com}b")
    fact_with_none = DummyItemFact("none", {})
    fact_with_one = DummyItemFact("one", {dim_a: object()})

    result = trialFilterFacts(
        xpCtx=SimpleNamespace(),
        vb=SimpleNamespace(aspectsCovered=set()),
        facts={fact_with_none, fact_with_one},
        filterRelationships=[],
        filterType="group",
        varSet=_group_filter_var_set(compl_dims=(dim_a, dim_b)),
    )

    assert result == {fact_with_none}
