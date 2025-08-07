"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import os
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Union, cast

from arelle import UrlUtil, ModelObject, XmlUtil, ModelValue
from arelle.Locale import format_string
from arelle.ModelObject import ObjectPropertyViewWrapper
from arelle.PluginManager import pluginClassMethods
from arelle.PythonUtil import flattenSequence

if TYPE_CHECKING:
    from arelle.ModelManager import ModelManager
    from arelle.typing import EmptyTuple

LoggableValue = Union[str, dict[Any, Any], list[Any], set[Any], tuple[Any, ...]]
EMPTY_TUPLE: EmptyTuple = ()


class ErrorManager:
    _errorCaptureLevel: int
    _errors: list[str | None]
    _logCount: dict[str, int] = {}
    _logHasRelevelerPlugin: bool
    _logRefFileRelUris: defaultdict[Any, dict[str, str]]
    _modelManager: ModelManager

    def __init__(self, modelManager: ModelManager, errorCaptureLevel: int):
        self._errorCaptureLevel = errorCaptureLevel
        self._errors = []
        self._logCount = {}
        self._logHasRelevelerPlugin: bool = any(True for m in pluginClassMethods("Logging.Severity.Releveler"))
        self._logRefFileRelUris = defaultdict(dict)
        self._modelManager = modelManager

    @property
    def errors(self) -> list[str | None]:
        return self._errors

    @property
    def logCount(self) -> dict[str, int]:
        return self._logCount

    def effectiveMessageCode(self, messageCodes: tuple[Any] | str) -> str | None:
        """
        If codes includes EFM, GFM, HMRC, or SBR-coded error then the code chosen (if a sequence)
        corresponds to whether EFM, GFM, HMRC, or SBR validation is in effect.
        """
        effectiveMessageCode = None
        _validationType = self.modelManager.disclosureSystem.validationType
        _exclusiveTypesPattern = self.modelManager.disclosureSystem.exclusiveTypesPattern

        for argCode in messageCodes if isinstance(messageCodes,tuple) else (messageCodes,):
            if (isinstance(argCode, ModelValue.QName) or
                    (_validationType and argCode and argCode.startswith(_validationType)) or
                    (not _exclusiveTypesPattern or _exclusiveTypesPattern.match(argCode or "") == None)):
                effectiveMessageCode = argCode
                break
        return effectiveMessageCode

    def clear(self) -> None:
        self._errors.clear()
        self._logCount.clear()

    def logArguments(self, messageCode: str, msg: str, codedArgs: dict[str, str]) -> Any:
        # Prepares arguments for logger function as per info() below.

        def propValues(properties: Any) -> Any:
            # deref objects in properties
            return [(p[0], str(p[1])) if len(p) == 2 else (p[0], str(p[1]), propValues(p[2]))
                    for p in properties if 2 <= len(p) <= 3]
        # determine message and extra arguments
        fmtArgs: dict[str, LoggableValue] = {}
        extras: dict[str, Any] = {"messageCode":messageCode}
        modelObjectArgs: tuple[Any, ...] | list[Any] = ()

        for argName, argValue in codedArgs.items():
            if argName in ("modelObject", "modelXbrl", "modelDocument"):
                try:
                    entryUrl = self.modelDocument.uri  # type: ignore[union-attr]
                except AttributeError:
                    try:
                        entryUrl = self.entryLoadingUrl
                    except AttributeError:
                        entryUrl = self.fileSource.url
                refs: list[dict[str, Any]] = []
                modelObjectArgs_complex = argValue if isinstance(argValue, (tuple,list,set)) else (argValue,)
                modelObjectArgs = flattenSequence(modelObjectArgs_complex)
                for arg in modelObjectArgs:
                    if arg is not None:
                        if isinstance(arg, str):
                            objectUrl = arg
                        else:
                            try:
                                objectUrl = arg.modelDocument.displayUri
                            except AttributeError:
                                try:
                                    objectUrl = arg.displayUri
                                except AttributeError:
                                    try:
                                        objectUrl = self.modelDocument.displayUri  # type: ignore[union-attr]
                                    except AttributeError:
                                        objectUrl = getattr(self, "entryLoadingUrl", "")
                        try:
                            if objectUrl.endswith("/_IXDS"):
                                file = objectUrl[:-6] # inline document set or report package
                            elif objectUrl in self.logRefFileRelUris.get(entryUrl, EMPTY_TUPLE):
                                file = self.logRefFileRelUris[entryUrl][objectUrl]
                            else:
                                file = UrlUtil.relativeUri(entryUrl, objectUrl)
                                self.logRefFileRelUris[entryUrl][objectUrl] = file
                        except:
                            file = ""
                        ref: dict[str, Any] = {}
                        if isinstance(arg,(ModelObject, ObjectPropertyViewWrapper)):
                            _arg:ModelObject = arg.modelObject if isinstance(arg, ObjectPropertyViewWrapper) else arg
                            if len(modelObjectArgs) > 1 and getattr(arg,"tag",None) == "instance":
                                continue # skip IXDS top level element
                            ref["href"] = file + "#" + cast(str, XmlUtil.elementFragmentIdentifier(_arg))
                            ref["sourceLine"] = _arg.sourceline
                            ref["objectId"] = _arg.objectId()
                            if self.logRefObjectProperties:
                                try:
                                    ref["properties"] = propValues(arg.propertyView)
                                except AttributeError:
                                    pass # is a default properties entry appropriate or needed?
                            if self.logRefHasPluginProperties:
                                refProperties: Any = ref.get("properties", {})
                                for pluginXbrlMethod in pluginClassMethods("Logging.Ref.Properties"):
                                    pluginXbrlMethod(arg, refProperties, codedArgs)
                                if refProperties:
                                    ref["properties"] = refProperties
                        else:
                            ref["href"] = file
                            try:
                                ref["sourceLine"] = arg.sourceline
                            except AttributeError:
                                pass # arg may not have sourceline, ignore if so
                        if self.logRefHasPluginAttrs:
                            refAttributes: dict[str, str] = {}
                            for pluginXbrlMethod in pluginClassMethods("Logging.Ref.Attributes"):
                                pluginXbrlMethod(arg, refAttributes, codedArgs)
                            if refAttributes:
                                ref["customAttributes"] = refAttributes
                        refs.append(ref)
                extras["refs"] = refs
            elif argName == "sourceFileLine":
                # sourceFileLines is pairs of file and line numbers, e.g., ((file,line),(file2,line2),...)
                ref = {}
                if isinstance(argValue, (tuple,list)):
                    ref["href"] = str(argValue[0])
                    if len(argValue) > 1 and argValue[1]:
                        ref["sourceLine"] = str(argValue[1])
                else:
                    ref["href"] = str(argValue)
                extras["refs"] = [ref]
            elif argName == "sourceFileLines":
                # sourceFileLines is tuple/list of pairs of file and line numbers, e.g., ((file,line),(file2,line2),...)
                sf_refs: list[dict[str, str]] = []
                argvalues: tuple[Any, ...] | list[Any] = argValue if isinstance(argValue, (tuple, list)) else (argValue,)
                for arg in argvalues:
                    ref = {}
                    if isinstance(arg, (tuple, list)):
                        arg_: tuple[Any, ...] | list[Any] = arg
                        ref["href"] = str(arg_[0])
                        if len(arg_) > 1 and arg_[1]:
                            ref["sourceLine"] = str(arg_[1])
                    else:
                        ref["href"] = str(arg)
                    sf_refs.append(ref)
                extras["refs"] = sf_refs
            elif argName == "sourceLine":
                if isinstance(argValue, int):    # must be sortable with int's in logger
                    extras["sourceLine"] = argValue
            elif argName not in ("exc_info", "messageCodes"):
                fmtArgs[argName] = self.loggableValue(argValue) # dereference anything not loggable

        if "refs" not in extras:
            try:
                file = os.path.basename(cast('ModelDocumentClass', self.modelDocument).displayUri)
            except AttributeError:
                try:
                    file = os.path.basename(self.entryLoadingUrl)
                except:
                    file = ""
            extras["refs"] = [{"href": file}]
        for pluginXbrlMethod in pluginClassMethods("Logging.Message.Parameters"):
            # plug in can rewrite msg string or return msg if not altering msg
            msg = pluginXbrlMethod(messageCode, msg, modelObjectArgs, fmtArgs) or msg
        return (messageCode,
                (msg, fmtArgs) if fmtArgs else (msg,),
                extras)

    def loggableValue(self, argValue: Any) -> LoggableValue:  # must be dereferenced and not related to object lifetimes
        if argValue is None:
            return "(none)"
        if isinstance(argValue, bool):
            return str(argValue).lower()  # show lower case true/false xml values
        if isinstance(argValue, int):
            # need locale-dependent formatting
            return format_string(self.modelManager.locale, '%i', argValue)
        if isinstance(argValue, (float, Decimal)):
            # need locale-dependent formatting
            return format_string(self.modelManager.locale, '%f', argValue)
        if isinstance(argValue, tuple):
            return tuple(self.loggableValue(x) for x in argValue)
        if isinstance(argValue, list):
            return [self.loggableValue(x) for x in argValue]
        if isinstance(argValue, set):
            return {self.loggableValue(x) for x in argValue}
        if isinstance(argValue, dict):
            return dict((self.loggableValue(k), self.loggableValue(v)) for k, v in argValue.items())
        return str(argValue)
