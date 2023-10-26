"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from abc import ABC
from enum import Enum
from typing import Any, TYPE_CHECKING

from arelle.RuntimeOptions import RuntimeOptions

if TYPE_CHECKING:
    import io
    from optparse import OptionParser
    from tkinter import Menu

    from arelle.Cntlr import Cntlr
    from arelle.CntlrCmdLine import CntlrCmdLine
    from arelle.CntlrWinMain import CntlrWinMain
    from arelle.DisclosureSystem import DisclosureSystem
    from arelle.FileSource import FileSource
    from arelle.ModelDocument import LoadingException, ModelDocument
    from arelle.ModelManager import ModelManager
    from arelle.ModelXbrl import ModelXbrl
    from arelle.ValidateXbrl import ValidateXbrl
    from arelle.formula.XPathContext import XPathContext
    from arelle.webserver.bottle import Bottle


class ValidationHook(Enum):
    """
    These hooks are called at different stages of validation, but all provide a common interface (ValidateXbrl is the first param).
    """

    XBRL_START = "Validate.XBRL.Start"
    XBRL_FINALLY = "Validate.XBRL.Finally"
    XBRL_DTS_DOCUMENT = "Validate.XBRL.DTS.document"
    FINALLY = "Validate.Finally"


class PluginHooks(ABC):
    @staticmethod
    def cntlrCmdLineOptions(
        parser: OptionParser,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Plugin hook: `CntlrCmdLine.Options`

        This hook is used to add plugin specific options to the command line.

        Example:
        ```python
        parser.add_option(
            "--my-option",
            dest="myOption",
            help="My custom option",
        )
        ```

        :param parser: the parser class to add options to.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        raise NotImplementedError

    @staticmethod
    def cntlrCmdLineUtilityRun(
        cntlr: Cntlr,
        options: RuntimeOptions,
        *args: Any,
        **kwargs: Any
    ) -> None:
        """
        Plugin hook: `CntlrCmdLine.Utility.Run`

        This hook is triggered after command line options have been parsed.
        It can be used to handle values for parameters configured in `cntlrCmdLineOptions`.

        Example:
        ```python
        if options.myOption:
            myOptionEnabled = True
        ```

        :param cntlr: The [Cntlr](#arelle.Cntlr.Cntlr) being initialized.
        :param options: Parsed options object.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        raise NotImplementedError

    @staticmethod
    def cntlrInit(
        cntlr: Cntlr,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Plugin hook: `Cntlr.Init`

        This hook is called while the [Cntlr](#arelle.Cntlr.Cntlr) is being initialized and after logging has been setup.

        :param cntlr: The [Cntlr](#arelle.Cntlr.Cntlr) being initialized.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        raise NotImplementedError

    @staticmethod
    def cntlrWebMainStartWebServer(
        app: Bottle,
        cntlr: CntlrCmdLine,
        host: str,
        port: str,
        server: str,
        *args: Any,
        **kwargs: Any,
    ) -> str | None:
        """
        Plugin hook: `CntlrWebMain.StartWebServer`

        This hook is for adding routes to the webserver.

        Only routes from a single plugin will be applied.

        Example:
        ```python
        app.route('/rest/my-test', "GET", my_test)
        app.route('/rest/my-run/<file:path>', ("GET", "POST"), my_run)
        ```

        :param app: The [Bottle](#arelle.webserver.bottle.Bottle) server.
        :param cntlr: The [controller](#arelle.CntlrCmdLine.CntlrCmdLine) for the server.
        :param host: The webserver host.
        :param port: The webserver port.
        :param server: The webserver path.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: `None`, a string of `skip-routes` or `skip-run`.
            Example:
            ```python
            # Block default Arelle routes.
            return "skip-routes"

            # Block default webserver startup.
            return "skip-run"

            # Block default Arelle routes and webserver startup.
            return "skip-routes|skip-run"

            # Normal routes will be combined with plugin routes and app started.
            return None
            ```
        """
        raise NotImplementedError

    @staticmethod
    def cntlrWinMainMenuHelp(
        cntlr: CntlrWinMain,
        menu: Menu,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Plugin hook: `CntlrWinMain.Menu.Help`

        Hook for adding items to the Arelle GUI help menu.

        Example:
        ```python
        menu.add_command(label="Plugin documentation URL", command=self.openHelpDocumentation)
        ```

        :param cntlr: The [CntlrWinMain](#arelle.CntlrWinMain.CntlrWinMain) instance that the request is coming from.
        :param menu: The tkinter help menu to extend.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        raise NotImplementedError

    @staticmethod
    def cntlrWinMainMenuTools(
        cntlr: CntlrWinMain,
        menu: Menu,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Plugin hook: `CntlrWinMain.Menu.Tools`

        Hook for adding items to the Arelle GUI tools menu.

        Example:
        ```python
        menu.add_command(label="Plugin Option", command=self.doSomething)
        ```

        :param cntlr: The [CntlrWinMain](#arelle.CntlrWinMain.CntlrWinMain) instance that the request is coming from.
        :param menu: The tkinter tools menu to extend.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        raise NotImplementedError

    @staticmethod
    def cntlrWinMainMenuValidation(
        cntlr: CntlrWinMain,
        menu: Menu,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Plugin hook: `CntlrWinMain.Menu.Validation`

        Hook for adding items to the Arelle GUI validation menu.

        Example:
        ```python
        menu.add_command(label="Plugin validation option", command=self.validationOptions)
        ```

        :param cntlr: The [CntlrWinMain](#arelle.CntlrWinMain.CntlrWinMain) instance that the request is coming from.
        :param menu: The tkinter validation menu to extend.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        raise NotImplementedError

    @staticmethod
    def cntlrWinMainMenuView(
        cntlr: CntlrWinMain,
        menu: Menu,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Plugin hook: `CntlrWinMain.Menu.View`

        Hook for adding items to the Arelle GUI view menu.

        Example:
        ```python
        menu.add_command(label="My Plugin Option", command=self.doSomething)
        ```

        :param cntlr: The [CntlrWinMain](#arelle.CntlrWinMain.CntlrWinMain) instance that the request is coming from.
        :param menu: The tkinter view menu to extend.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        raise NotImplementedError

    @staticmethod
    def disclosureSystemConfigURL(
        disclosureSystem: DisclosureSystem,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """
        Plugin hook: `DisclosureSystem.ConfigURL`

        For validation plugins this provides a path to the disclosure system config file.
        See arelle/config/disclosuresystems.xml for examples.

        :param disclosureSystem: The [DisclosureSystem](#arelle.DisclosureSystem.DisclosureSystem)
               instance that the config will be applied to.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: A relative path to a disclosure system XML config file.
            Example:
            ```python
            return str(Path(__file__).parent / "resources" / "config.xml")
            ```
        """
        raise NotImplementedError

    @staticmethod
    def disclosureSystemTypes(
        disclosureSystem: DisclosureSystem,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[tuple[str, str], ...]:
        """
        Plugin hook: `DisclosureSystem.Types`

        For validation plugins this should return a tuple of tuples containing:
        1. a validation type (matching a validation type from a disclosure system config.
        2. a test type property that's applied to the [DisclosureSystem](#arelle.DisclosureSystem.DisclosureSystem).
           It will be set to `True` if the disclosure system for the validation type above is
           selected and `false` otherwise.

        :param disclosureSystem: The [DisclosureSystem](#arelle.DisclosureSystem.DisclosureSystem)
               instance that the types will be applied to.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: A tuple of two item tuples containing a validation type and test property.
            Example:
            ```python
            return (("ESEF", "ESEFplugin"),)
            ```
        """
        raise NotImplementedError

    @staticmethod
    def fileSourceExists(
        cntlr: Cntlr,
        filepath: str,
        *args: Any,
        **kwargs: Any,
    ) -> bool | None:
        """
        Plugin hook: `FileSource.Exists`

        This hook can be used to override [FileSource](#arelle.FileSource.FileSource) existence checks.
        For instance for a plugin that encrypts files, creating a copy with a different file extension,
        and the filepath should be transformed accordingly.

        :param cntlr: The [controller](#arelle.Cntlr.Cntlr) the current request is running from.
        :param filepath: The path which Arelle is checking for the existence of a file.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None or boolean value indicating if the file exists.
            Example:
            ```python
            # Defer to other plugins and/or default behavior.
            return None
            # Indicate file exists.
            return True
            # Indicate file does not exist.
            return False
            ```
        """
        raise NotImplementedError

    @staticmethod
    def fileSourceFile(
        cntlr: Cntlr,
        filepath: str,
        binary: bool,
        stripDeclaration: bool,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[io.BytesIO | None] | tuple[io.TextIOWrapper, str]:
        """
        Plugin hook: `FileSource.File`

        fileResult = pluginMethod(self.cntlr, filepath, binary, stripDeclaration)

        This hook can be used to override [FileSource](#arelle.FileSource.FileSource) file open operations.

        :param cntlr: The [controller](#arelle.Cntlr.Cntlr) the current request is running from.
        :param filepath: The path of the file to open.
        :param binary: Indicates if the file should be opened as binary.
        :param stripDeclaration: Indicates if XML declaration should be stripped.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: tuple of text IO and encoding, or binary io and None
            Example:
            ```python
            # Binary IO
            return (io.BytesIO(b),)
            # Text IO
            return return (io.TextIOWrapper(io.BytesIO(b), encoding="utf-8"), "utf-8")
            ```
        """
        raise NotImplementedError

    @staticmethod
    def modelDocumentIsPullLoadable(
        modelXbrl: ModelXbrl,
        mappedUri: str,
        normalizedUri: str,
        filepath: str,
        isEntry: bool,
        namespace: str,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """
        Plugin hook: `ModelDocument.IsPullLoadable`

        Plugin hook to signal files which can be opened by the plugin that otherwise would not be supported by Arelle.
        For instance a plugin that enables opening and loading data from json files.

        :param modelXbrl: The [ModelXbrl](#arelle.ModelXbrl.ModelXbrl) being constructed.
        :param mappedUri: The path of the document. May be the same as the `normalizedUri` or a path to a file in a taxonomy package.
        :param normalizedUri: The normalized path of the document. This can be a URL or local file system path.
        :param filepath: The path of the document. May be the same as the `normalizedUri` or a path to a file in the local cache.
        :param isEntry: Boolean value indicating if the document is an entrypoint.
        :param namespace: The target namespace if the document has one.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: `True` if the plugin can load the file or `False` if not.
            Example:
            ```python
            return Path(filepath).suffix == ".json"
            ```
        """
        raise NotImplementedError

    @staticmethod
    def modelDocumentPullLoader(
        modelXbrl: ModelXbrl,
        normalizedUri: str,
        filepath: str,
        isEntry: bool,
        namespace: str | None,
        *args: Any,
        **kwargs: Any,
    ) -> ModelDocument | LoadingException | None:
        """
        Plugin hook: `ModelDocument.PullLoader`

        This plugin hook can be used to override [ModelDocument](#arelle.ModelDocument.ModelDocument) construction.

        For instance for a plugin that enables opening and loading data from Excel files.

        This hook can also be used to log an initial error and/or return a
        [LoadingException](#arelle.ModelDocument.LoadingException)
        if the XBRL report doesn't match a naming requirement.

        :param modelXbrl: The [ModelXbrl](#arelle.ModelXbrl.ModelXbrl) being constructed.
        :param normalizedUri: The normalized path of the document. This can be a URL or local file system path.
        :param filepath: The path of the document. May be the same as the `normalizedUri` or a path to a file in the local cache.
        :param isEntry: Boolean value indicating if the document is an entrypoint.
        :param namespace: The target namespace if the document has one.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: A [ModelDocument](#arelle.ModelDocument.ModelDocument), a
                 [LoadingException](#arelle.ModelDocument.LoadingException], or `None`.
            Example:
            ```python
            # Defer to other plugins and/or default behavior.
            return None

            # Override ModelDocument construction from plugin.
            return ModelDocument(...)

            # Signal that document can't be constructed.
            return LoadingException("Invalid document")
            ```
        """
        raise NotImplementedError

    @staticmethod
    def modelManagerLoad(
        manager: ModelManager,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
    ) -> ModelXbrl | None:
        """
        Plugin hook: `ModelManager.Load`

        Hook to override default [ModelXbrl](#arelle.ModelXbrl.ModelXbrl) loading.
        Return `None` to defer to other plugins of default loading.

        :param manager: The [ModelManager](#arelle.ModelManager.ModelManager) the request is coming from.
        :param fileSource: The [FileSource](#arelle.FileSource.FileSource) to load.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: Either a [ModelXbrl](#arelle.ModelXbrl.ModelXbrl) instance or `None` to defer to default loading.
        """
        raise NotImplementedError

    @staticmethod
    def modelXbrlInit(
        modelXbrl: ModelXbrl,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Plugin hook: `ModelXbrl.Init`

        This plugin hook is called as the last step of the [ModelXbrl](#arelle.ModelXbrl.ModelXbrl)
        constructor which is prior to [ModelDocument](#arelle.ModelDocument.ModelDocument) loading.

        :param modelXbrl: The [XBRL model](#arelle.ModelXbrl.ModelXbrl) being constructed.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        raise NotImplementedError

    @staticmethod
    def modelXbrlLoadComplete(
        modelXbrl: ModelXbrl,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Plugin hook: `ModelXbrl.LoadComplete`

        This plugin hook is called after the [ModelXbrl](#arelle.ModelXbrl.ModelXbrl) and
        [ModelDocument](#arelle.ModelDocument.ModelDocument) loading is complete.

        :param modelXbrl: The constructed [ModelXbrl](#arelle.ModelXbrl.ModelXbrl).
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        raise NotImplementedError

    @staticmethod
    def validateFinally(
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Plugin hook: `Validate.Finally`

        This plugin hook is called after formula processing and other XBRL validation.
        This hook is useful for logging errors or warnings based on other errors or warnings that were triggered.

        Example:
        ```python
        if "XYZ.01.01" in val.modelXbrl.errors and "XYZ.21.02" not in val.modelXbrl.errors:
            modelXbrl.error("XYZ.52.04", "Incompatible data reported.")
        ```

        :param val: The [ValidateXBRL](#arelle.ValidateXbrl.ValidateXbrl) instance.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        raise NotImplementedError

    @staticmethod
    def validateFormulaCompiled(
        modelXbrl: ModelXbrl,
        xpathContext: XPathContext,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Plugin hook: `ValidateFormula.Compiled`

        Hook executed after formula rules are compiled, but before they're executed.

        :param modelXbrl: The [ModelXbrl](#arelle.ModelXbrl.ModelXbrl).
        :param xpathContext: The formula evaluation [XPathContext](#arelle.formula.XPathContext.XPathContext).
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        raise NotImplementedError

    @staticmethod
    def validateFormulaFinished(
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Plugin hook: `ValidateFormula.Finished`

        Hook executed after formula evaluation.

        :param val: The [ValidateXBRL](#arelle.ValidateXbrl.ValidateXbrl) instance.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        raise NotImplementedError

    @staticmethod
    def validateXbrlDtsDocument(
        val: ValidateXbrl,
        modelDocument: ModelDocument,
        isFilingDocument: bool,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Plugin hook: `Validate.XBRL.DTS.document`

        Validation hook for implementing DTS validation rules.
        Useful for implementing validation rules related to extension taxonomies.

        Example:
        ```python
        if (
            modelDocument.type == ModelDocument.Type.SCHEMA
            and modelDocument.targetNamespace is not None
            and len(modelDocument.targetNamespace) > 100
        ):
            val.modelXbrl.error(
                codes="XYZ.1.9.13",
                msg="TargetNamespace is too long.",
            )
        ```

        :param val: The [ValidateXBRL](#arelle.ValidateXbrl.ValidateXbrl) instance.
        :param modelDocument: The [ModelDocument](#arelle.ModelDocument.ModelDocument) to validate.
        :param isFilingDocument: Indicates if document is part of filing or external reference.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        raise NotImplementedError

    @staticmethod
    def validateXbrlFinally(
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Plugin hook: `Validate.XBRL.Finally`

        Hook for executing validation rules after other XBRL validations, but prior to formula processing.

        Example:
        ```python
        if "Cash" not in val.modelXbrl.factsByLocalName:
            val.modelXbrl.error(codes="01.01", msg="Cash must be reported.")
        if "Assets" not in val.modelXbrl.factsByLocalName:
            val.modelXbrl.warning(codes=("01.02", "13.04"), msg="Assets should be reported.")
        ```

        :param val: The [ValidateXBRL](#arelle.ValidateXbrl.ValidateXbrl) instance.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        raise NotImplementedError

    @staticmethod
    def validateXbrlStart(
        val: ValidateXbrl,
        parameters: dict[Any, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Plugin hook: `Validate.XBRL.Start`

        Hook for executing validation rules prior to other XBRL validations.

        Example:
        ```python
        if "Cash" not in val.modelXbrl.factsByLocalName:
            val.modelXbrl.error(codes="01.01", msg="Cash must be reported.")
        if "Assets" not in val.modelXbrl.factsByLocalName:
            val.modelXbrl.warning(codes=("01.02", "13.04"), msg="Assets should be reported.")
        ```

        :param val: The [ValidateXBRL](#arelle.ValidateXbrl.ValidateXbrl) instance.
        :param parameters: dictionary of validation parameters.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        raise NotImplementedError

    @staticmethod
    def modelTestcaseVariationReportPackageIxdsOptions(
        val: ValidateXbrl,
        rptPkgIxdsOptions: dict[str, bool],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Plugin hook: `ModelTestcaseVariation.ReportPackageIxdsOptions`

        Hook for other plugins to specify IXDS testcase variation options which will be passed to the inlineXbrlDocumentSet plugin.

        Example:
        ```python
        rptPkgIxdsOptions["lookOutsideReportsDirectory"] = True
        rptPkgIxdsOptions["combineIntoSingleIxds"] = True
        ```

        :param val: The [ValidateXBRL](#arelle.ValidateXbrl.ValidateXbrl) instance.
        :param rptPkgIxdsOptions: the dict to set IXDS options on.
        :param args: Argument capture to ensure new parameters don't break plugin hook.
        :param kwargs: Argument capture to ensure new named parameters don't break plugin hook.
        :return: None
        """
        raise NotImplementedError
