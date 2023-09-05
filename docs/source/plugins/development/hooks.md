# Plugin Hooks

:::{index} Plugin Hooks
:::

The following method hooks can be configured for your plugin via `pluginInfo`.

> **Note:** This documentation is a work in progress.
> Feel free to contribute documentation for any hooks missing documentation below.
> Please follow the existing documentation format, for example: [FileSource.Exists](#filesource-exists).

## Main Controller Processes
### `Cntlr.Init`
### `CntlrCmdLine.Filing.End`
### `CntlrCmdLine.Filing.Start`
### `CntlrCmdLine.Filing.Validate`
### `CntlrCmdLine.Options`
### `CntlrCmdLine.Utility.Run`
### `CntlrCmdLine.Xbrl.Loaded`
### `CntlrCmdLine.Xbrl.Run`

## Web Server
### `CntlrWebMain.StartWebServer`

## GUI
### `CntlrWinMain.Menu.Help`
### `CntlrWinMain.Menu.Tools`
### `CntlrWinMain.Menu.Validation`
### `CntlrWinMain.Menu.View`
### `CntlrWinMain.Toolbar`
### `CntlrWinMain.Xbrl.Loaded`
### `CntlrWinMain.Xbrl.Open`
### `DialogRssWatch.FileChoices`
### `DialogRssWatch.ValidateChoices`

## Disclosure System
### `DisclosureSystem.ConfigURL`
### `DisclosureSystem.Types`

## Edgar Renderer
### `EdgarRenderer.Filing.End`
### `EdgarRenderer.Filing.Start`
### `EdgarRenderer.Xbrl.Run`

## File System
(filesource-exists)=
### `FileSource.Exists`
This handle can be used to override `FileSource` existence checks. 

Example: A plugin that encrypts files, creating a copy with a different file extension, and the filepath should be transformed accordingly.
* **Arguments**
  * `cntlr: Cntlr` The controller the current request is running from.
  * `filepath: str` The path which Arelle is checking for the existence of a file.
* **Returns** `bool | None`
  * `None` to defer to other plugins and/or default behavior.
  * `True` to indicate file exists.
  * `False` to indicate file does not exist.

### `FileSource.File`

## Inline Documents
### `InlineDocumentSet.CreateTargetInstance`
### `InlineDocumentSet.Discovery`
### `InlineDocumentSet.SavesTargetInstance`
### `InlineDocumentSet.Url.Separator`

## Logging
### `Logging.Message.Parameters`
### `Logging.Ref.Attributes`
### `Logging.Ref.Properties`
### `Logging.Severity.Releveler`

## Testcases
### `ModelTestcaseVariation.ArchiveIxds`
### `ModelTestcaseVariation.ExpectedCount`
### `ModelTestcaseVariation.ExpectedResult`
### `ModelTestcaseVariation.ExpectedSeverity`
### `ModelTestcaseVariation.ReadMeFirstUris`
### `ModelTestcaseVariation.ReportPackageIxds`
### `ModelTestcaseVariation.ReportPackageIxdsOptions`
### `ModelTestcaseVariation.ResultXbrlInstanceUri`
### `TestcaseVariation.ExpectedInstance.Loaded`
### `TestcaseVariation.Validated`
### `TestcaseVariation.Xbrl.Loaded`
### `TestcaseVariation.Xbrl.Validated`
### `Testcases.Start`

## Security
### `Security.Crypt.FileSource.Exists`
### `Security.Crypt.FileSource.File`
### `Security.Crypt.Filing.Start`
### `Security.Crypt.Init`
### `Security.Crypt.IsActive`
### `Security.Crypt.Write`

## Streaming
### `Streaming.BlockStreaming`
### `Streaming.Facts`
### `Streaming.Finish`
### `Streaming.Start`
### `Streaming.ValidateFacts`
### `Streaming.ValidateFinish`

## Validation
### `Validate.EFM.Fact`
### `Validate.EFM.Finally`
### `Validate.EFM.Start`
### `Validate.Finally`
### `Validate.Infoset`
### `Validate.RssItem`
### `Validate.SBRNL.DTS.document`
### `Validate.TableInfoset`
### `Validate.XBRL.DTS.document`
### `Validate.XBRL.Fact`
### `Validate.XBRL.Finally`
### `Validate.XBRL.Start`
### `ValidateFormula.Compiled`
### `ValidateFormula.Finished`

## XBRLDB
### `xbrlDB.Open.Ext.ExistingFilingPk`
### `xbrlDB.Open.Ext.ExistingReportPk`
### `xbrlDB.Open.Ext.ExtFiling`
### `xbrlDB.Open.Ext.ExtReport`
### `xbrlDB.Open.Ext.ExtReportUpdate`
### `xbrlDB.Open.Ext.ExtSubmission`
### `xbrlDB.Open.Ext.InitializeBatch`
### `xbrlDB.Open.Ext.Metadata`
### `xbrlDB.Open.Ext.TableDDLFiles`

## Miscellaneous
### `Formula.CustomFunctions`
### `FtJson.IsFtJsonDocument`
### `Import.Packaged.Entry{#}`
### `Import.Unpackaged.Entry{#}`
### `LoadFromOim.DocumentSetup`
### `ModelDocument.CustomCloser`
### `ModelDocument.CustomLoader`
### `ModelDocument.DiscoverIxdsDts`
### `ModelDocument.Discover`
### `ModelDocument.IdentifyType`
### `ModelDocument.IsPullLoadable`
### `ModelDocument.IsValidated`
### `ModelDocument.PullLoader`
### `ModelDocument.SelectIxdsTarget`
### `ModelManager.LoadCustomTransforms`
### `ModelManager.Load`
### `ModelXbrl.Init`
### `ModelXbrl.LoadComplete`
### `ModelXbrl.RoleTypeName`
### `Proxy.HTTPAuthenticate`
### `Proxy.HTTPNtlmAuthHandler`
### `RssItem.Xbrl.Loaded`
### `RssWatch.DoWatchAction`
### `RssWatch.HasWatchAction`
### `SakaCalendar.ToGregorian`
