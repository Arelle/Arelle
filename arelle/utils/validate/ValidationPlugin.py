"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from types import ModuleType
from typing import Any

from arelle.Cntlr import Cntlr
from arelle.DisclosureSystem import DisclosureSystem
from arelle.FileSource import FileSource
from arelle.ModelDocument import LoadingException, ModelDocument
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.PluginData import PluginData
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import (
    ValidationAttributes,
    ValidationFunction,
    getValidationAttributes,
)


class ValidationPlugin:
    def __init__(
        self,
        name: str,
        disclosureSystemConfigUrl: Path,
        validationTypes: list[str],
        validationRuleModules: list[ModuleType],
    ) -> None:
        """
        Base validation plugin class. Can be initialized directly, or extended if you require additional plugin hooks.
        This class is intended to be used in conjunction with the [@validation](#arelle.utils.validate.Decorator.validation) decorator.

        If you need to cache or store data between rules, you should implement a dataclass that extends [PluginData](#arelle.utils.PluginData.PluginData)
        and override the [newPluginData](#newPluginData) method to return your dataclass.

        :param disclosureSystemConfigUrl: A path to the plugin disclosure system xml config file.
        :param validationTypes: A list of validation types for the plugin. These should correspond to the validation types
               in your disclosure system xml file.
        :param validationRulesModule: The rules module which will be searched recursively for rule functions decorated with @validation.
        """
        self.name = name
        self._disclosureSystemConfigURL = disclosureSystemConfigUrl
        self._validationTypes = tuple(validationTypes)
        if not validationRuleModules:
            raise ValueError("At least one rules module must be provided.")
        self._validationModules = validationRuleModules
        self._validationsDiscovered = False
        self._rulesByDisclosureSystemByHook: dict[
            ValidationHook, dict[str, list[ValidationFunction]]
        ] = {}
        self._excludedDisclosureSystemsByRulesByHook: dict[
            ValidationHook, dict[ValidationFunction, set[str]]
        ] = {}

    def newPluginData(self, cntlr: Cntlr, validateXbrl: ValidateXbrl | None) -> PluginData:
        """
        Returns a dataclass intended to be overriden by plugins to facilitate caching and passing data between rule functions.
        The default implementation doesn't provide any fields other than the plugin name.

        :return: An instance of PluginData.
        """
        return PluginData(self.name)

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

    def validateComplete(
            self,
            cntlr: Cntlr,
            fileSource: FileSource,
            *args: Any,
            **kwargs: Any,
    ) -> None:
        """
        Executes validation functions in the rules module that was provided to the constructor of this class.
        Each function decorated with [@validation](#arelle.utils.validate.Decorator.validation) will be run if:
        1. the decorator was used with the validation complete hook: `@validation(hook=ValidationHook.COMPLETE)`

        :param cntlr: The [Cntlr](#arelle.Cntlr.Cntlr) instance.
        :param fileSource: The [FileSource](#arelle.FileSource.FileSource) involved in loading the entrypoint files.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        self._executeCntlrValidations(ValidationHook.COMPLETE, cntlr, fileSource, *args, **kwargs)

    def validateFileSource(
        self,
        cntlr: Cntlr,
        fileSource: FileSource,
        entrypoints: list[dict[str, Any]] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Executes validation functions in the rules module that was provided to the constructor of this class.
        Each function decorated with [@validation](#arelle.utils.validate.Decorator.validation) will be run if:
        1. the decorator was used with the FileSource validation hook: `@validation(hook=ValidationHook.FILESOURCE)`

        :param cntlr: The [Cntlr](#arelle.Cntlr.Cntlr) instance.
        :param fileSource: The [FileSource](#arelle.FileSource.FileSource) involved in loading the entrypoint files.
        :param entrypoints: A list of entrypoint configurations.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        self._executeCntlrValidations(ValidationHook.FILESOURCE, cntlr, fileSource, entrypoints, *args, **kwargs)

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
        self._executeModelValidations(ValidationHook.XBRL_START, val, parameters, *args, **kwargs)

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
        self._executeModelValidations(ValidationHook.XBRL_FINALLY, val, *args, **kwargs)

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
        self._executeModelValidations(ValidationHook.XBRL_DTS_DOCUMENT, val, modelDocument, isFilingDocument, *args, **kwargs)

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
        self._executeModelValidations(ValidationHook.FINALLY, val, *args, **kwargs)

    def _executeCntlrValidations(
            self,
            pluginHook: ValidationHook,
            cntlr: Cntlr,
            fileSource: FileSource | None = None,
            entrypoints: list[dict[str, Any]] | None = None,
            *args: Any,
            **kwargs: Any,
    ) -> None:
        pluginData = self.newPluginData(
            cntlr=cntlr,
            validateXbrl=None
        )
        for rule in self._getValidations(cntlr.modelManager.disclosureSystem, pluginHook):
            validations = rule(pluginData, cntlr, fileSource, entrypoints, *args, **kwargs)
            if validations is not None:
                for val in validations:
                    cntlr.error(level=val.level.name, codes=val.codes, msg=val.msg, **val.args)

    def _executeModelValidations(
        self,
        pluginHook: ValidationHook,
        validateXbrl: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if self.disclosureSystemFromPluginSelected(validateXbrl):
            pluginData = validateXbrl.getPluginData(self.name)
            if pluginData is None:
                pluginData = self.newPluginData(
                    cntlr=validateXbrl.modelXbrl.modelManager.cntlr,
                    validateXbrl=validateXbrl
                )
                validateXbrl.setPluginData(pluginData)
            for rule in self._getValidations(validateXbrl.disclosureSystem, pluginHook):
                validations = rule(pluginData, validateXbrl, *args, **kwargs)
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
        rulesFunctionDiscovered = False
        for mod in self._validationModules:
            for _, func in inspect.getmembers(mod, inspect.isfunction):
                attributes = getValidationAttributes(func)
                if attributes is not None:
                    rulesFunctionDiscovered = True
                    self._storeValidationFunction(func, attributes)
        if not rulesFunctionDiscovered:
            raise RuntimeError(f"No @validation rules found for '{self.name}' validation plugin.")
        self._validationsDiscovered = True

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
