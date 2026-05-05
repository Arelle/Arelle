"""
FormulaContext.py - Execution context for the XBRL Query and Rules Language.

Two context levels:

FormulaGlobalContext
    Created once per formula run.  Holds the rule set, the compiled OIM model,
    and caches for constants and fact-query results.

FormulaRuleContext
    Created once per rule iteration.  Holds variable bindings ($varName) and
    the current alignment key.  Chained to the global context.

See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from arelle.ModelValue import QName

from .FormulaValue import FormulaValue, AlignmentKey, NONE_VALUE
from .FormulaRuleSet import FormulaRuleSet

if TYPE_CHECKING:
    from arelle.plugin.XbrlModel.XbrlModel import XbrlCompiledModel


# ---------------------------------------------------------------------------
# Global context
# ---------------------------------------------------------------------------

class FormulaGlobalContext:
    """
    Holds all state shared across the evaluation of an entire rule set.

    Attributes
    ----------
    ruleSet:
        The compiled FormulaRuleSet being evaluated.
    txmyMdl:
        The XbrlCompiledModel (OIM taxonomy + report).
    cntlr:
        Arelle controller (for logging).
    options:
        Command-line options namespace (may be None).
    namespaces:
        Prefix → URI map (merged from model + rule set declarations).
    constants:
        Evaluated constant values keyed by name.
    factCache:
        Cache of concept QName → list[XbrlFact] to avoid repeated model scans.
    results:
        Collected output/assertion messages ready for Arelle logging.
    """

    def __init__(
        self,
        ruleSet: FormulaRuleSet,
        txmyMdl: "XbrlCompiledModel",
        cntlr=None,
        options=None,
    ):
        self.ruleSet    = ruleSet
        self.txmyMdl    = txmyMdl
        self.cntlr      = cntlr
        self.options    = options

        # Namespace prefix map: start from rule set, override with model if available
        self.namespaces: Dict[str, str] = dict(ruleSet.namespaces)
        if hasattr(txmyMdl, "namespaces"):
            self.namespaces.update(txmyMdl.namespaces)

        self.constants: Dict[str, FormulaValue] = {}
        self.factCache: Dict[QName, List] = {}    # QName → list[XbrlFact]
        self.results: List[Dict[str, Any]] = []

        # VectorSearch alignment availability flag
        self._vectorSearchReady: Optional[bool] = None

    @property
    def vectorSearchReady(self) -> bool:
        """True once the VectorSearch embedding index has been built."""
        if self._vectorSearchReady is None:
            self._vectorSearchReady = (
                hasattr(self.txmyMdl, "_xbrlEmbedder")
                and self.txmyMdl._xbrlEmbedder is not None
            )
        return self._vectorSearchReady

    def factsForConcept(self, conceptQn: QName) -> List:
        """
        Return all XbrlFact objects whose concept dimension equals conceptQn.
        Results are cached per QName.
        """
        if conceptQn not in self.factCache:
            from arelle.plugin.XbrlModel.XbrlReport import XbrlFact
            from arelle.XmlValidate import VALID
            from arelle.ModelValue import qname as mkQn

            conceptDimQn = mkQn("https://xbrl.org/2021", "concept")
            matching = [
                obj for obj in self.txmyMdl.filterNamedObjects(XbrlFact)
                if (getattr(obj, "_xValid", VALID) >= VALID
                    and obj.factDimensions.get(conceptDimQn) == conceptQn)
            ]
            self.factCache[conceptQn] = matching
        return self.factCache[conceptQn]

    def resolveQName(self, prefix: str, localName: str) -> QName:
        """
        Build a QName from prefix + localName using the current namespace map.
        A prefix of '*' is treated as 'match any namespace' (returns a bare
        local-name QName with empty namespace — callers must handle wildcard).
        """
        from arelle.ModelValue import qname as mkQn
        if prefix == "*" or prefix == "":
            # Wildcard: attempt to find any concept with this localName
            return mkQn("", localName)
        uri = self.namespaces.get(prefix)
        if uri is None:
            raise KeyError(f"Unknown namespace prefix {prefix!r}")
        return mkQn(uri, localName)

    def log(self, level: str, code: str, msg: str, **kwargs) -> None:
        """Route a message to the Arelle controller or stdout."""
        if self.cntlr:
            self.cntlr.addToLog(msg, messageCode=code, level=level, **kwargs)
        else:
            print(f"[{level}] {code}: {msg}")

    def addResult(self, ruleName: str, ruleType: str, severity: str,
                  message: str, alignment: Optional[AlignmentKey] = None,
                  factObj=None) -> None:
        self.results.append({
            "ruleName": ruleName,
            "ruleType": ruleType,
            "severity": severity,
            "message":  message,
            "alignment": alignment,
            "fact":      factObj,
        })
        level = severity.upper() if severity.lower() != "ok" else "INFO"
        code  = f"formula:{ruleType}:{ruleName}"
        self.log(level, code, message)


# ---------------------------------------------------------------------------
# Rule context (per iteration of a single rule)
# ---------------------------------------------------------------------------

class FormulaRuleContext:
    """
    Holds state for a single rule iteration.

    Each iteration corresponds to one combination of aligned facts bound to
    the fact-query variables in the rule body.

    Attributes
    ----------
    globalCtx:
        The parent FormulaGlobalContext.
    variables:
        Name → FormulaValue bindings for $variables and #tags in this iteration.
    alignment:
        The merged alignment key for all facts bound in this iteration.
    ruleValue:
        The most-recently computed top-level expression value (exposed as
        $rule-value inside message templates).
    """

    def __init__(self, globalCtx: FormulaGlobalContext):
        self.globalCtx   = globalCtx
        self.variables:  Dict[str, FormulaValue] = {}
        self.alignment:  Optional[AlignmentKey] = None
        self.ruleValue:  Optional[FormulaValue] = None

    # Delegation helpers
    @property
    def txmyMdl(self):
        return self.globalCtx.txmyMdl

    @property
    def namespaces(self):
        return self.globalCtx.namespaces

    def bindVariable(self, name: str, value: FormulaValue) -> None:
        self.variables[name] = value

    def lookupVariable(self, name: str) -> FormulaValue:
        # Check local variables first, then global constants
        if name in self.variables:
            return self.variables[name]
        if name in self.globalCtx.constants:
            return self.globalCtx.constants[name]
        # Built-in $rule-value
        if name == "rule-value" and self.ruleValue is not None:
            return self.ruleValue
        return NONE_VALUE

    def childContext(self) -> "FormulaRuleContext":
        """Return a new child context that inherits current variable bindings."""
        child = FormulaRuleContext(self.globalCtx)
        child.variables = dict(self.variables)
        child.alignment = self.alignment
        return child
