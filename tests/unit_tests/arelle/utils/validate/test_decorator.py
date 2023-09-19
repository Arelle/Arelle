from __future__ import annotations

import importlib
import importlib.util
import inspect
import pkgutil
from collections.abc import Generator
from types import ModuleType

from arelle.examples.plugin import validate as exampleValidationPlugins
from arelle.plugin import validate as validationPlugins
from arelle.utils.validate.Decorator import getValidationAttributes

KNOWN_IMPORT_FAILURES = frozenset([
    "arelle.plugin.validate.XFsyntax.xf",
])


def test_decoratorApplied():
    """
    For functions defined in validation plugins verify that:
    1. function names with "rule" prefix have @validation decorator applied.
    2. names of functions with @validation decorator applied begin with "rule" prefix.
    """
    rulesMissingDecorator = []
    misnamedRuleFunctions = []
    for module in (exampleValidationPlugins, validationPlugins):
        for mod in moduleWalk(module, set(KNOWN_IMPORT_FAILURES)):
            for funcName, func in inspect.getmembers(
                mod, inspect.isfunction
            ):
                matchesRuleNamingPattern = funcName.startswith("rule")
                validationDecoratorApplied = getValidationAttributes(func) is not None
                modName = f"{func.__module__}.{funcName}"
                if matchesRuleNamingPattern and not validationDecoratorApplied:
                    rulesMissingDecorator.append(modName)
                elif validationDecoratorApplied and not matchesRuleNamingPattern:
                    misnamedRuleFunctions.append(modName)
    assert not rulesMissingDecorator, 'Function names in validation plugin begin with "rule" validation prefix, but are missing @validation decorator.'
    assert not misnamedRuleFunctions, 'Functions in validation plugin with @validation decorator, but do not begin with "rule" function prefix.'


def moduleWalk(
    mod: ModuleType,
    subModsToSkip: set[str],
) -> Generator[ModuleType, None, None]:
    if inspect.ismodule(mod):
        yield mod

        path = getattr(mod, "__path__", None)
        pkg = getattr(mod, "__package__", None)
        if path is not None and pkg is not None:
            for _, modname, _ in pkgutil.iter_modules(path):
                subModName = f"{pkg}.{modname}"
                if subModsToSkip is not None and subModName in subModsToSkip:
                    continue
                subMod = importlib.import_module(subModName)
                for m in moduleWalk(subMod, subModsToSkip):
                    yield m
