"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections.abc import Generator
from pathlib import Path
from types import ModuleType
from typing import Any

from arelle.DisclosureSystem import DisclosureSystem
from arelle.ModelDocument import LoadingException, ModelDocument
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import (
    ValidationAttributes,
    ValidationFunction,
    getValidationAttributes,
)


class ValidationPlugin:
    def __init__(
        self,
        disclosureSystemConfigUrl: Path,
        validationTypes: list[str],
        validationRulesModule: ModuleType,
    ) -> None:
        """
        Base validation plugin class. Can be initialized directly, or extended if you require additional plugin hooks.
        This class is intended to be used in conjunction with the [@validation](#arelle.utils.validate.Decorator.validation) decorator.

        :param disclosureSystemConfigUrl: A path to the plugin disclosure system xml config file.
        :param validationTypes: A list of validation types for the plugin. These should correspond to the validation types
               in your disclosure system xml file.
        :param validationRulesModule: The rules module which will be searched recursively for rule functions decorated with @validation.
        """
        self._disclosureSystemConfigURL = disclosureSystemConfigUrl
        self._validationTypes = tuple(validationTypes)
        self._validationsModules = validationRulesModule
        self._validationsDiscovered = False
        self._rulesByDisclosureSystemByHook: dict[
            ValidationHook, dict[str, list[ValidationFunction]]
        ] = {}
        self._excludedDisclosureSystemsByRulesByHook: dict[
            ValidationHook, dict[ValidationFunction, set[str]]
        ] = {}
        self.pluginCache: dict[str, Any] = {}

    @property
    def validationTypes(self) -> tuple[str, ...]:
        return self._validationTypes

    @property
    def disclosureSystemConfigURL(self) -> str:
        return str(self._disclosureSystemConfigURL)

    @property
    def disclosureSystemTypes(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (validationType, f"pluginValidationType{validationType}")
            for validationType in self.validationTypes
        )

    def modelDocumentPullLoader(
        self,
        modelXbrl: ModelXbrl,
        normalizedUri: str,
        filepath: str,
        isEntry: bool,
        namespace: str | None,
        *args: Any,
        **kwargs: Any,
    ) -> ModelDocument | LoadingException | None:
        raise NotImplementedError

    def modelXbrlLoadComplete(
        self,
        modelXbrl: ModelXbrl,
        *args: Any,
        **kwargs: Any,
    ) -> ModelDocument | LoadingException | None:
        raise NotImplementedError

    def validateXbrlStart(
        self,
        val: ValidateXbrl,
        parameters: dict[Any, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Executes validation functions in the rules module that was provided to the constructor of this class.
        Each function decorated with [@validation](#arelle.utils.validate.Decorator.validation) will be run if:
        1. the decorator was used with the xbrl start hook: `@validation(hook=ValidationHook.XBRL_START)`
        2. the user selected disclosure system is in line with the combination of disclosure systems provided to the decorator.

        :param val: The [ValidateXBRL](#arelle.ValidateXbrl.ValidateXbrl) instance.
        :param parameters: dictionary of validation parameters.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        self._executeValidations(ValidationHook.XBRL_START, val, parameters, *args, **kwargs)

    def validateXbrlFinally(
        self,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Executes validation functions in the rules module that was provided to the constructor of this class.
        Each function decorated with [@validation](#arelle.utils.validate.Decorator.validation) will be run if:
        1. the decorator was used with the xbrl finally hook: `@validation(hook=ValidationHook.XBRL_FINALLY)`
        2. the user selected disclosure system is in line with the combination of disclosure systems provided to the decorator.

        :param val: The [ValidateXBRL](#arelle.ValidateXbrl.ValidateXbrl) instance.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        self._executeValidations(ValidationHook.XBRL_FINALLY, val, *args, **kwargs)

    def validateXbrlDtsDocument(
        self,
        val: ValidateXbrl,
        modelDocument: ModelDocument,
        isFilingDocument: bool,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Executes validation functions in the rules module that was provided to the constructor of this class.
        Each function decorated with [@validation](#arelle.utils.validate.Decorator.validation) will be run if:
        1. the decorator was used with the xbrl dts document hook: `@validation(hook=ValidationHook.XBRL_DTS_DOCUMENT)`
        2. the user selected disclosure system is in line with the combination of disclosure systems provided to the decorator.

        :param val: The [ValidateXBRL](#arelle.ValidateXbrl.ValidateXbrl) instance.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        self._executeValidations(ValidationHook.XBRL_DTS_DOCUMENT, val, modelDocument, isFilingDocument, *args, **kwargs)

    def validateFinally(
        self,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Executes validation functions in the rules module that was provided to the constructor of this class.
        Each function decorated with [@validation](#arelle.utils.validate.Decorator.validation) will be run if:
        1. the decorator was used with the validate finally hook: `@validation(hook=ValidationHook.FINALLY)`
        2. the user selected disclosure system is in line with the combination of disclosure systems provided to the decorator.

        :param val: The [ValidateXBRL](#arelle.ValidateXbrl.ValidateXbrl) instance.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        self._executeValidations(ValidationHook.FINALLY, val, *args, **kwargs)

    def _executeValidations(
        self,
        pluginHook: ValidationHook,
        validateXbrl: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if self.disclosureSystemFromPluginSelected(validateXbrl):
            for rule in self._getValidations(validateXbrl.disclosureSystem, pluginHook):
                validations = rule(self.pluginCache, validateXbrl, *args, **kwargs)
                if validations is not None:
                    modelXbrl = validateXbrl.modelXbrl
                    for val in validations:
                        modelXbrl.log(level=val.level.name, codes=val.codes, msg=val.msg, **val.args)

    def disclosureSystemFromPluginSelected(
        self,
        model: ValidateXbrl | ModelXbrl,
    ) -> bool:
        if isinstance(model, ValidateXbrl):
            disclosureSystem = model.disclosureSystem
        elif isinstance(model, ModelXbrl):
            disclosureSystem = model.modelManager.disclosureSystem
        else:
            raise ValueError(f"Expected param to be either ValidateXbrl or ModelXbrl, received {type(model)}.")
        return any(
            getattr(disclosureSystem, testProperty, False)
            for _, testProperty in self.disclosureSystemTypes
        )

    def _getValidations(
        self,
        disclosureSystem: DisclosureSystem,
        pluginHook: ValidationHook,
    ) -> list[ValidationFunction]:
        if disclosureSystem.name is None:
            raise RuntimeError("Disclosure system not configured.")
        if not self._validationsDiscovered:
            self._discoverValidations()
        nonExcludedRules = [
            func
            for func, excluded in self._excludedDisclosureSystemsByRulesByHook.get(pluginHook, {}).items()
            if disclosureSystem.name not in excluded
        ]
        includedRules = self._rulesByDisclosureSystemByHook.get(pluginHook, {}).get(disclosureSystem.name, [])
        return nonExcludedRules + includedRules

    def _discoverValidations(self) -> None:
        modules = self._moduleWalk(self._validationsModules)
        for mod in modules:
            for _, func in inspect.getmembers(mod, inspect.isfunction):
                attributes = getValidationAttributes(func)
                if attributes is not None:
                    self._storeValidationFunction(func, attributes)
        self._validationsDiscovered = True

    def _moduleWalk(self, mod: ModuleType) -> Generator[ModuleType, None, None]:
        if inspect.ismodule(mod):
            yield mod

            path = getattr(mod, "__path__", None)
            pkg = getattr(mod, "__package__", None)
            if path is not None and pkg is not None:
                for _, modname, _ in pkgutil.iter_modules(path):
                    subMod = importlib.import_module(f"{pkg}.{modname}")
                    for m in self._moduleWalk(subMod):
                        yield m

    def _storeValidationFunction(
        self,
        func: ValidationFunction,
        attributes: ValidationAttributes,
    ) -> None:
        hook = attributes.hook
        disclosureSystems = attributes.disclosureSystems
        if disclosureSystems is None:
            excludedDisclosureSystemsByRules = self._excludedDisclosureSystemsByRulesByHook.setdefault(hook, {})
            excludedDisclosureSystems = excludedDisclosureSystemsByRules.setdefault(func, set())
            excludedDisclosureSystems.update(attributes.excludeDisclosureSystems)
        else:
            rulesByDisclosureSystem = self._rulesByDisclosureSystemByHook.setdefault(hook, {})
            for disclosureSystem in disclosureSystems:
                rulesByDisclosureSystem.setdefault(disclosureSystem, []).append(func)
