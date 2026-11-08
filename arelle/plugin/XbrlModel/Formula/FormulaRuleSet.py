"""
FormulaRuleSet.py - Load, compile, and cache formula rule sets for the
XBRL Query and Rules Language interpreter.

A rule set is a collection of `output` and `assert` rules parsed from one or
more `.xule` files.  Once compiled, the rule set is cached so that the same
file is not reparsed on every validation run.

See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import hashlib
import pickle
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Rule data classes (produced by FormulaParser, consumed by FormulaInterpreter)
# ---------------------------------------------------------------------------

@dataclass
class NamespaceDecl:
    prefix: str
    uri: str


@dataclass
class ConstantDecl:
    name: str           # without the '$'
    expr: Any           # AST node


@dataclass
class OutputRule:
    """Produces a value or message (no pass/fail)."""
    name: str
    expr: Any           # AST node for the body expression
    messageExpr: Optional[Any] = None   # AST node for the message string, if present
    severity: str = "info"
    severityExpr: Optional[Any] = None  # AST node for the severity clause
    suffixExpr: Optional[Any] = None    # AST node for the rule-suffix string


@dataclass
class AssertRule:
    """Reports a result when its condition is true (`unsatisfied`, the default),
    or, declared `satisfied`, when it is false."""
    name: str
    expr: Any           # AST node for the boolean condition
    messageExpr: Optional[Any] = None
    severity: str = "error"
    severityExpr: Optional[Any] = None  # AST node for the severity clause
    suffixExpr: Optional[Any] = None    # AST node for the rule-suffix string
    # `assert Name satisfied` reports when the expression is false; the default,
    # `unsatisfied`, reports when it is true (tavi-formula.md, "Assert block").
    reportWhenSatisfied: bool = False


# ---------------------------------------------------------------------------
# RuleSet container
# ---------------------------------------------------------------------------

@dataclass
class FormulaRuleSet:
    """
    Container for a compiled collection of formula rules.

    Attributes
    ----------
    namespaces:
        Prefix → URI mapping from all `namespace` declarations in the source.
    constants:
        Ordered list of constant declarations (must be evaluated in order).
    outputRules:
        Named output rules.
    assertRules:
        Named assertion rules.
    sourceFiles:
        Original source file paths, used to detect staleness for caching.
    """
    namespaces: Dict[str, str] = field(default_factory=dict)
    constants: List[ConstantDecl] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)   # name -> FormulaParameters.ParameterDecl
    outputRules: Dict[str, OutputRule] = field(default_factory=dict)
    assertRules: Dict[str, AssertRule] = field(default_factory=dict)
    sourceFiles: List[str] = field(default_factory=list)

    def mergeFrom(self, other: "FormulaRuleSet") -> None:
        """Merge another rule set into this one (used when loading multiple files)."""
        self.namespaces.update(other.namespaces)
        self.constants.extend(other.constants)
        for name, decl in other.parameters.items():
            if name in self.parameters:
                raise ValueError(f"taviqe:duplicateParameterName: parameter ${name} is declared "
                                 f"in more than one rule set file")
            self.parameters[name] = decl
        self.outputRules.update(other.outputRules)
        self.assertRules.update(other.assertRules)
        self.sourceFiles.extend(other.sourceFiles)

    @property
    def allRules(self):
        """Iterate over all rules (output then assert) in insertion order."""
        yield from self.outputRules.values()
        yield from self.assertRules.values()


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

_ruleSetCache: Dict[str, "FormulaRuleSet"] = {}


def _fileHash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# Parsing is slow (pyparsing explores many alternatives per token: a rule file of
# a few hundred generated rows takes seconds to minutes), and rule files change
# far less often than they are run. A parsed file is therefore kept between runs,
# keyed by its path and content and by the source of the modules that define the
# parse, so that editing either a rule file or the grammar invalidates it.
_PARSE_MODULES = ("FormulaParser.py", "FormulaRuleSet.py", "FormulaParameters.py")
_parserVersion: Optional[str] = None


def _parserVersionKey() -> str:
    global _parserVersion
    if _parserVersion is None:
        h = hashlib.sha256()
        here = os.path.dirname(os.path.abspath(__file__))
        for name in _PARSE_MODULES:
            with open(os.path.join(here, name), "rb") as fh:
                h.update(fh.read())
        _parserVersion = h.hexdigest()
    return _parserVersion


def _parseCacheDir(cntlr) -> Optional[str]:
    """Where parsed rule files are kept: the Arelle user cache, when there is a controller."""
    for c in (cntlr, getattr(cntlr, "cntlr", None)):   # a controller, or a model manager
        userAppDir = getattr(c, "userAppDir", None)
        if userAppDir:
            return os.path.join(userAppDir, "cache", "formula-parse")
    return None


def _parseFileCached(path: str, cacheDir: Optional[str]) -> "FormulaRuleSet":
    """Parse one rule file, or load it as parsed by an earlier run."""
    from .FormulaParser import parseFormulaFile
    if cacheDir is None:
        return parseFormulaFile(path)
    key = hashlib.sha256(f"{os.path.abspath(path)}|{_fileHash(path)}|{_parserVersionKey()}"
                         .encode("utf-8")).hexdigest()
    cacheFile = os.path.join(cacheDir, key + ".pickle")
    try:
        with open(cacheFile, "rb") as fh:
            return pickle.load(fh)
    except (OSError, EOFError, pickle.UnpicklingError, AttributeError, ImportError):
        pass                                   # absent or unreadable: parse it again
    ruleSet = parseFormulaFile(path)
    try:
        os.makedirs(cacheDir, exist_ok=True)
        tmpFile = f"{cacheFile}.{os.getpid()}.tmp"
        with open(tmpFile, "wb") as fh:
            pickle.dump(ruleSet, fh, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmpFile, cacheFile)        # never leave a half-written entry
    except OSError:
        pass                                   # a cache that cannot be written is not an error
    return ruleSet


def loadRuleSet(paths: List[str], cntlr=None) -> "FormulaRuleSet":
    """
    Load and compile a rule set from one or more `.xule` source files or
    directories.  Results are cached by source content hash.

    Parameters
    ----------
    paths:
        List of file or directory paths.  Directories are searched recursively
        for `*.xule` files.
    cntlr:
        Optional Arelle controller, used for logging parse warnings and progress.

    Returns
    -------
    FormulaRuleSet
        The merged and compiled rule set ready for interpretation.
    """
    cacheDir = _parseCacheDir(cntlr)

    # Expand directories to individual .xule files
    xuleFiles: List[str] = []
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for fname in sorted(files):
                    if fname.endswith(".xule"):
                        xuleFiles.append(os.path.join(root, fname))
        elif os.path.isfile(p):
            xuleFiles.append(p)

    # Build a compound cache key from all file hashes
    cacheKey = "|".join(f"{f}:{_fileHash(f)}" for f in sorted(xuleFiles))
    if cacheKey in _ruleSetCache:
        return _ruleSetCache[cacheKey]

    merged = FormulaRuleSet(sourceFiles=list(xuleFiles))
    totalStartTime = time.perf_counter()

    for i, xuleFile in enumerate(xuleFiles, 1):
        try:
            startTime = time.perf_counter()
            ruleSet = _parseFileCached(xuleFile, cacheDir)
            elapsedSecs = time.perf_counter() - startTime
            mergeTime = time.perf_counter()
            merged.mergeFrom(ruleSet)
            mergeSecs = time.perf_counter() - mergeTime
            msg = f"Formula parse {i}/{len(xuleFiles)}: {os.path.basename(xuleFile)} loaded {len(ruleSet.outputRules)} outputs in {elapsedSecs:.2f}s (merge {mergeSecs:.3f}s)"
            if cntlr:
                cntlr.addToLog(msg, messageCode="formula:parseProgress", level="DEBUG")
            else:
                print(f"[INFO] {msg}")
        except Exception as exc:
            msg = f"FormulaRuleSet: failed to parse {xuleFile!r}: {exc}"
            if cntlr:
                cntlr.addToLog(msg, messageCode="formula:parseError", level="ERROR")
            else:
                print(msg)

    totalSecs = time.perf_counter() - totalStartTime
    _ruleSetCache[cacheKey] = merged
    msg = f"Formula rule set loaded: {len(merged.outputRules)} outputs, {len(merged.assertRules)} asserts from {len(xuleFiles)} files in {totalSecs:.2f}s"
    if cntlr:
        cntlr.addToLog(msg, messageCode="formula:parseComplete", level="DEBUG")
    else:
        print(f"[INFO] {msg}")
    return merged


def clearCache() -> None:
    """Clear the in-process rule set cache (useful in tests)."""
    _ruleSetCache.clear()
