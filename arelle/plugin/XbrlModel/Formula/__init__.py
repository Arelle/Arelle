"""
__init__.py - Arelle plugin entry point for the XBRL Query and Rules Language.

This module registers the formula plugin with Arelle and exposes the standard
Arelle plugin hooks:

  cmdLineOptionExtender  — add  --formula-ruleset  and related CLI options
  validateFinished       — run formula rules after model validation
  testcaseVariationRead  — support for XBRL test suite

See COPYRIGHT.md for copyright information.

Usage (command line)
--------------------
arelleCmdLine.py  --plugins XbrlModel/Formula \
    --formula-ruleset path/to/rules.xule \
    [--formula-ruleset path/to/more-rules/]   # may repeat \
    instance.json

Usage (Arelle GUI)
------------------
Enable the XbrlModel/Formula plugin in the plugins dialog, then provide
the formula ruleset path via Tools → Formula Parameters.

"""
from __future__ import annotations

import os
from typing import Any, List, Optional


# ---------------------------------------------------------------------------
# Arelle plugin hook: command-line options
# ---------------------------------------------------------------------------

def cmdLineOptionExtender(parser, *args, **kwargs):
    """Add formula-specific CLI options."""
    parser.add_option(
        "--formula-ruleset",
        action="append",
        dest="formulaRulesets",
        default=[],
        help="Path to a .xule formula file or directory of .xule files to run. "
             "May be specified multiple times.",
    )
    parser.add_option(
        "--formula-align-threshold",
        action="store",
        type="float",
        dest="formulaAlignThreshold",
        default=0.999,
        help="Cosine similarity threshold for GPU-based fact alignment "
             "(default 0.999, meaning nearly exact dimensional match).",
    )
    parser.add_option(
        "--formula-embed-dim",
        action="store",
        type="int",
        dest="formulaEmbedDim",
        default=64,
        help="Embedding dimension used by VectorSearch for fact alignment "
             "(default 64).",
    )
    parser.add_option(
        "--formula-output-file",
        action="store",
        dest="formulaOutputFile",
        default=None,
        help="Write formula results to this JSON file in addition to Arelle logging.",
    )


# ---------------------------------------------------------------------------
# Arelle plugin hook: after validation
# ---------------------------------------------------------------------------

def validateFinished(val, *args, **kwargs):
    """
    Called by Arelle after model validation completes.

    Loads the formula rule set, builds the VectorSearch index if not already
    present on the model, then runs all formula rules.
    """
    modelXbrl = val.modelXbrl
    options   = getattr(val, "options", None)
    cntlr     = getattr(val, "cntlr", None) or getattr(modelXbrl, "modelManager", None)

    rulesetPaths: List[str] = getattr(options, "formulaRulesets", [])
    if not rulesetPaths:
        return   # nothing to do

    # Obtain the OIM compiled model from the Arelle model
    try:
        from arelle.plugin.XbrlModel import castToXbrlCompiledModel
        txmyMdl = castToXbrlCompiledModel(modelXbrl)
    except Exception as exc:
        _log(cntlr, "WARNING", "formula:modelCast",
             f"Cannot obtain XbrlCompiledModel for formula evaluation: {exc}")
        return

    # Ensure VectorSearch index is built (lazy, cached on model)
    _ensureVectorSearch(txmyMdl, options, cntlr)

    # Load rule sets
    try:
        from .FormulaRuleSet import loadRuleSet
        ruleSet = loadRuleSet(rulesetPaths, cntlr=cntlr)
    except Exception as exc:
        _log(cntlr, "ERROR", "formula:load", f"Failed to load formula rule set: {exc}")
        return

    if not list(ruleSet.allRules):
        _log(cntlr, "INFO", "formula:noRules", "Formula rule set loaded but contains no rules.")
        return

    # Execute
    from .FormulaContext import FormulaGlobalContext
    from .FormulaInterpreter import evaluateRuleSet

    globalCtx = FormulaGlobalContext(ruleSet, txmyMdl, cntlr=cntlr, options=options)
    try:
        evaluateRuleSet(globalCtx)
    except Exception as exc:
        _log(cntlr, "ERROR", "formula:eval", f"Formula evaluation failed: {exc}")
        return

    # Optional: write results to a JSON file
    outputFile = getattr(options, "formulaOutputFile", None)
    if outputFile and globalCtx.results:
        _writeResults(globalCtx.results, outputFile, cntlr)


# ---------------------------------------------------------------------------
# Arelle plugin hook: test-suite variation support
# ---------------------------------------------------------------------------

def testcaseVariationRead(modelTestcase, rulesetFiles, *args, **kwargs):
    """
    Called by the Arelle test suite runner when processing formula test cases.
    Registers the rule set files with the testcase variation.
    """
    if rulesetFiles:
        modelTestcase.formulaRulesets = list(rulesetFiles)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensureVectorSearch(txmyMdl, options, cntlr) -> None:
    """Build the VectorSearch embedding index if not already present."""
    if getattr(txmyMdl, "_xbrlEmbedder", None) is not None:
        return   # already built

    try:
        from arelle.plugin.XbrlModel.VectorSearch import buildXbrlVectors
        embedDim = getattr(options, "formulaEmbedDim", 64) or 64
        embedder, _vocab, _ivocab, store = buildXbrlVectors(txmyMdl, embedDim=embedDim)
        txmyMdl._xbrlEmbedder = embedder
        txmyMdl._xbrlVectorStore = store
        _log(cntlr, "INFO", "formula:vectorSearch",
             f"VectorSearch index built: {len(store.factObjsList)} facts, "
             f"embed_dim={embedDim}")
    except ImportError:
        _log(cntlr, "INFO", "formula:vectorSearch",
             "torch not available — formula alignment will use exact key matching.")
    except Exception as exc:
        _log(cntlr, "WARNING", "formula:vectorSearch",
             f"VectorSearch index build failed (exact fallback will be used): {exc}")


def _writeResults(results: list, path: str, cntlr) -> None:
    """Serialise formula results to a JSON file."""
    import json
    try:
        serialisable = []
        for r in results:
            serialisable.append({
                "ruleName":  r["ruleName"],
                "ruleType":  r["ruleType"],
                "severity":  r["severity"],
                "message":   r["message"],
            })
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(serialisable, fh, indent=2)
        _log(cntlr, "INFO", "formula:output", f"Formula results written to {path!r}")
    except Exception as exc:
        _log(cntlr, "WARNING", "formula:output", f"Failed to write formula results: {exc}")


def _log(cntlr, level: str, code: str, msg: str) -> None:
    if cntlr is not None:
        cntlr.addToLog(msg, messageCode=code, level=level)
    else:
        print(f"[{level}] {code}: {msg}")


# ---------------------------------------------------------------------------
# Arelle plugin registration boilerplate
# ---------------------------------------------------------------------------

__pluginInfo__ = {
    "name":         "XbrlModel/Formula",
    "version":      "1.0.0",
    "description":  "XBRL Query and Rules Language (Xule) for the OIM XbrlModel",
    "license":      "See COPYRIGHT.md",
    "author":       "Herm Fischer",
    "import":       [],
    "CntlrCmdLine.Options": cmdLineOptionExtender,
    "Validate.Finally":     validateFinished,
    "TestcaseVariation.Read": testcaseVariationRead,
}
