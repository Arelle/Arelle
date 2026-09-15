from __future__ import annotations

from unittest.mock import MagicMock, patch

from arelle import Validate as ValidateModule
from arelle.ModelRssObject import ModelRssObject
from arelle.Validate import Validate


def _feedValidator(rssItems: list[MagicMock]) -> Validate:
    feedModelXbrl = MagicMock()
    feedModelXbrl.modelDocument = MagicMock(spec=ModelRssObject)
    feedModelXbrl.modelDocument.rssItems = rssItems
    feedModelXbrl.modelManager.cntlr.plugins.hooks.return_value = []
    validator = Validate.__new__(Validate)
    validator.modelXbrl = feedModelXbrl
    validator.useFileSource = MagicMock(isArchive=False)
    validator.instValidator = MagicMock()
    return validator


def _rssItem(url: str, doNotProcess: bool = False) -> MagicMock:
    return MagicMock(skipRssItem=False, status=None, doNotProcessRSSitem=doNotProcess, zippedUrl=url)


def _loadedModelXbrl() -> MagicMock:
    modelXbrl = MagicMock(supplementalModelXbrls=())
    modelXbrl.modelManager.cntlr.plugins.hooks.return_value = []
    return modelXbrl


def test_validateRssFeed_closes_each_item_through_model_manager() -> None:
    loaded = [_loadedModelXbrl(), _loadedModelXbrl()]
    validator = _feedValidator([_rssItem("https://example.com/a.zip"), _rssItem("https://example.com/b.zip")])
    with (
        patch.object(ValidateModule, "openFileSource", return_value=MagicMock(selection="entry.htm")),
        patch.object(ValidateModule, "modelXbrlLoad", side_effect=loaded),
    ):
        validator.validateRssFeed()
    closed = [c.args[0] for c in validator.modelXbrl.modelManager.close.call_args_list]
    assert closed == loaded  # each item's own modelXbrl, never the feed's (close() without one)


def test_validateRssFeed_closes_skipped_item_through_model_manager() -> None:
    loaded = [_loadedModelXbrl()]
    validator = _feedValidator([_rssItem("https://example.com/a.zip", doNotProcess=True)])
    with (
        patch.object(ValidateModule, "openFileSource", return_value=MagicMock(selection="entry.htm")),
        patch.object(ValidateModule, "modelXbrlLoad", side_effect=loaded),
    ):
        validator.validateRssFeed()
    validator.instValidator.validate.assert_not_called()
    validator.modelXbrl.modelManager.close.assert_called_once_with(loaded[0])


def test_validateRssFeed_closes_item_after_validation_exception() -> None:
    loaded = [_loadedModelXbrl()]
    validator = _feedValidator([_rssItem("https://example.com/a.zip")])
    validator.instValidator.validate.side_effect = RuntimeError("validation failed")
    with (
        patch.object(ValidateModule, "openFileSource", return_value=MagicMock(selection="entry.htm")),
        patch.object(ValidateModule, "modelXbrlLoad", side_effect=loaded),
    ):
        validator.validateRssFeed()
    validator.modelXbrl.error.assert_called_once()
    validator.modelXbrl.modelManager.close.assert_called_once_with(loaded[0])
