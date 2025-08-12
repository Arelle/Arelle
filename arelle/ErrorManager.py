"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Union, cast

from arelle import UrlUtil, XmlUtil, ModelValue, XbrlConst
from arelle.FileSource import FileSource
from arelle.Locale import format_string
from arelle.ModelObject import ModelObject, ObjectPropertyViewWrapper
from arelle.PluginManager import hasPluginWithHook, pluginClassMethods
from arelle.PythonUtil import flattenSequence

if TYPE_CHECKING:
    from arelle.ModelManager import ModelManager
    from arelle.ModelXbrl import ModelXbrl
    from arelle.typing import EmptyTuple

LoggableValue = Union[str, dict[Any, Any], list[Any], set[Any], tuple[Any, ...]]
EMPTY_TUPLE: EmptyTuple = ()


class ErrorManager:
    logHasRelevelerPlugin: bool | None
    _errorCaptureLevel: int
    _errors: list[str | None]
    _logCount: dict[str, int] = {}
    _logRefFileRelUris: defaultdict[Any, dict[str, str]]
    _modelManager: ModelManager

    def __init__(self, modelManager: ModelManager, errorCaptureLevel: int):
        self._errorCaptureLevel = errorCaptureLevel
        self._errors = []
        self._logCount = {}
        self._logRefFileRelUris = defaultdict(dict)
        self._modelManager = modelManager
        self.logHasRelevelerPlugin = None

    @property
    def errors(self) -> list[str | None]:
        return self._errors

    @property
    def logCount(self) -> dict[str, int]:
        return self._logCount

    def _effectiveMessageCode(self, messageCodes: tuple[Any] | str) -> str | None:
        """
        If codes includes EFM, GFM, HMRC, or SBR-coded error then the code chosen (if a sequence)
        corresponds to whether EFM, GFM, HMRC, or SBR validation is in effect.
        """
        effectiveMessageCode = None
        _validationType = self._modelManager.disclosureSystem.validationType
        _exclusiveTypesPattern = self._modelManager.disclosureSystem.exclusiveTypesPattern

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

    def isLoggingEffectiveFor(self, logger: logging.Logger, **kwargs: Any) -> bool:  # args can be messageCode(s) and level
        assert hasattr(logger, 'messageCodeFilter'), 'messageCodeFilter not set on controller logger.'
        assert hasattr(logger, 'messageLevelFilter'), 'messageLevelFilter not set on controller logger.'
        if "messageCodes" in kwargs or "messageCode" in kwargs:
            if "messageCodes" in kwargs:
                messageCodes = kwargs["messageCodes"]
            else:
                messageCodes = kwargs["messageCode"]
            messageCode = self._effectiveMessageCode(messageCodes)
            codeEffective = (messageCode and
                             (not logger.messageCodeFilter or logger.messageCodeFilter.match(messageCode)))
        else:
            codeEffective = True
        if "level" in kwargs and logger.messageLevelFilter:
            levelEffective = logger.messageLevelFilter.match(kwargs["level"].lower())
        else:
            levelEffective = True
        return bool(codeEffective and levelEffective)

    def log(
            self,
            logger: logging.Logger,
            level: str,
            codes: Any,
            msg: str,
            sourceModelXbrl: ModelXbrl | None = None,
            fileSource: FileSource | None = None,
            entryLoadingUrl: str | None = None,
            logRefObjectProperties: bool = False,
            **args: Any
    ) -> None:
        """Same as error(), but level passed in as argument
        """
        assert hasattr(logger, 'messageCodeFilter'), 'messageCodeFilter not set on controller logger.'
        messageCodeFilter = getattr(logger, 'messageCodeFilter')
        assert hasattr(logger, 'messageLevelFilter'), 'messageLevelFilter not set on controller logger.'
        messageLevelFilter = getattr(logger, 'messageLevelFilter')
        # determine logCode
        messageCode = self._effectiveMessageCode(codes)
        if messageCode == "asrtNoLog":
            self._errors.append(args["assertionResults"])
            return
        if self.logHasRelevelerPlugin is None:
            self.logHasRelevelerPlugin = hasPluginWithHook("Logging.Severity.Releveler")
        if sourceModelXbrl is not None and self.logHasRelevelerPlugin:
            for pluginXbrlMethod in pluginClassMethods("Logging.Severity.Releveler"):
                level, messageCode = pluginXbrlMethod(sourceModelXbrl, level, messageCode, args) # args must be passed as dict because it may contain modelXbrl or messageCode key value
        if (messageCode and
                (not messageCodeFilter or messageCodeFilter.match(messageCode)) and
                (not messageLevelFilter or messageLevelFilter.match(level.lower()))):
            # note that plugin Logging.Message.Parameters may rewrite messageCode which now occurs after filtering on messageCode
            messageCode, logArgs, extras = self._logArguments(
                messageCode,
                msg,
                args,
                sourceModelXbrl=sourceModelXbrl,
                fileSource=fileSource,
                entryLoadingUrl=entryLoadingUrl,
                logRefObjectProperties=logRefObjectProperties,
            )
            numericLevel = logging._checkLevel(level)  #type: ignore[attr-defined]
            self._logCount[numericLevel] = self._logCount.get(numericLevel, 0) + 1
            if numericLevel >= self._errorCaptureLevel:
                try: # if there's a numeric errorCount arg, extend messages codes by count
                    self._errors.extend([messageCode] * int(logArgs[1]["errorCount"]))
                except (IndexError, KeyError, ValueError): # no msgArgs, no errorCount, or not int
                    self._errors.append(messageCode) # assume one error occurence
            """@messageCatalog=[]"""
            logger.log(numericLevel, *logArgs, exc_info=args.get("exc_info"), extra=extras)

    def _logArguments(
            self,
            messageCode: str,
            msg: str,
            codedArgs: dict[str, str],
            sourceModelXbrl: ModelXbrl | None = None,
            fileSource: FileSource | None = None,
            entryLoadingUrl: str | None = None,
            logRefObjectProperties: bool = False,
    ) -> Any:
        # Prepares arguments for logger function as per info() below.

        def propValues(properties: Any) -> Any:
            # deref objects in properties
            return [(p[0], str(p[1])) if len(p) == 2 else (p[0], str(p[1]), propValues(p[2]))
                    for p in properties if 2 <= len(p) <= 3]
        # determine message and extra arguments
        fmtArgs: dict[str, LoggableValue] = {}
        extras: dict[str, Any] = {"messageCode":messageCode}
        modelObjectArgs: tuple[Any, ...] | list[Any] = ()
        sourceModelDocument = getattr(sourceModelXbrl, "modelDocument", None)
        for argName, argValue in codedArgs.items():
            if argName in ("modelObject", "modelXbrl", "modelDocument"):
                if sourceModelDocument is not None:
                    entryUrl = sourceModelDocument.uri
                else:
                    if entryLoadingUrl is not None:
                        entryUrl = entryLoadingUrl
                    else:
                        assert fileSource is not None, 'Expected FileSource to be available for fallback entry URL.'
                        entryUrl = fileSource.url
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
                                        objectUrl = sourceModelDocument.displayUri  # type: ignore[union-attr]
                                    except AttributeError:
                                        objectUrl = entryLoadingUrl or ""
                        try:
                            if objectUrl.endswith("/_IXDS"):
                                file = objectUrl[:-6] # inline document set or report package
                            elif objectUrl in self._logRefFileRelUris.get(entryUrl, EMPTY_TUPLE):
                                file = self._logRefFileRelUris[entryUrl][objectUrl]
                            else:
                                file = UrlUtil.relativeUri(entryUrl, objectUrl)
                                self._logRefFileRelUris[entryUrl][objectUrl] = file
                        except:
                            file = ""
                        ref: dict[str, Any] = {}
                        if isinstance(arg,(ModelObject, ObjectPropertyViewWrapper)):
                            _arg:ModelObject = arg.modelObject if isinstance(arg, ObjectPropertyViewWrapper) else arg
                            if len(modelObjectArgs) > 1 and getattr(arg,"tag",None) == "instance":
                                continue # skip IXDS top level element
                            fragmentIdentifier = "#" + cast(str, XmlUtil.elementFragmentIdentifier(_arg))
                            if not hasattr(_arg, 'modelDocument') and _arg.namespaceURI == XbrlConst.svg and len(refs) > 0:
                                # This is an embedded SVG document without its own file.
                                # Set the href to the containing document element that defined the encoded SVG.
                                # and define a nestedHrefs attribute with the fragment identifier.
                                priorRef = refs[-1]
                                ref["href"] = priorRef["href"]
                                priorNestedHrefs = priorRef.get("customAttributes", {}).get("nestedHrefs", [])
                                ref["customAttributes"] = {
                                    "nestedHrefs": [*priorNestedHrefs, fragmentIdentifier]
                                }
                                if priorArgSourceline := priorRef.get("sourceLine"):
                                    ref["sourceLine"] = priorArgSourceline
                            else:
                                ref["href"] = file + fragmentIdentifier
                                ref["sourceLine"] = _arg.sourceline
                            ref["objectId"] = _arg.objectId()
                            if logRefObjectProperties:
                                try:
                                    ref["properties"] = propValues(arg.propertyView)
                                except AttributeError:
                                    pass # is a default properties entry appropriate or needed?
                            if any(True for m in pluginClassMethods("Logging.Ref.Properties")):
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
                        if any(True for m in pluginClassMethods("Logging.Ref.Attributes")):
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
                fmtArgs[argName] = self._loggableValue(argValue) # dereference anything not loggable

        if "refs" not in extras:
            if sourceModelDocument is not None:
                file = sourceModelDocument.displayUri
            else:
                if entryLoadingUrl is not None:
                    file = os.path.basename(entryLoadingUrl)
                else:
                    file = ""
            extras["refs"] = [{"href": file}]
        for pluginXbrlMethod in pluginClassMethods("Logging.Message.Parameters"):
            # plug in can rewrite msg string or return msg if not altering msg
            msg = pluginXbrlMethod(messageCode, msg, modelObjectArgs, fmtArgs) or msg
        return (messageCode,
                (msg, fmtArgs) if fmtArgs else (msg,),
                extras)

    def _loggableValue(self, argValue: Any) -> LoggableValue:  # must be dereferenced and not related to object lifetimes
        if argValue is None:
            return "(none)"
        if isinstance(argValue, bool):
            return str(argValue).lower()  # show lower case true/false xml values
        if isinstance(argValue, int):
            # need locale-dependent formatting
            return format_string(self._modelManager.locale, '%i', argValue)
        if isinstance(argValue, (float, Decimal)):
            # need locale-dependent formatting
            return format_string(self._modelManager.locale, '%f', argValue)
        if isinstance(argValue, tuple):
            return tuple(self._loggableValue(x) for x in argValue)
        if isinstance(argValue, list):
            return [self._loggableValue(x) for x in argValue]
        if isinstance(argValue, set):
            return {self._loggableValue(x) for x in argValue}
        if isinstance(argValue, dict):
            return dict((self._loggableValue(k), self._loggableValue(v)) for k, v in argValue.items())
        return str(argValue)
