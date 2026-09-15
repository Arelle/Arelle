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


def _rssItem(url: str) -> MagicMock:
    return MagicMock(skipRssItem=False, status=None, doNotProcessRSSitem=False, zippedUrl=url)


def _loadedModelXbrl(name: str, events: list[str]) -> MagicMock:
    modelXbrl = MagicMock(supplementalModelXbrls=())
    modelXbrl.modelManager.cntlr.plugins.hooks.return_value = []
    modelXbrl.close.side_effect = lambda: events.append(f"close {name}")
    return modelXbrl


def test_validateRssFeed_collects_garbage_after_each_item() -> None:
    events: list[str] = []
    loaded = [_loadedModelXbrl("a", events), _loadedModelXbrl("b", events)]
    validator = _feedValidator([_rssItem("https://example.com/a.zip"), _rssItem("https://example.com/b.zip")])
    with (
        patch.object(ValidateModule, "openFileSource", return_value=MagicMock(selection="entry.htm")),
        patch.object(ValidateModule, "modelXbrlLoad", side_effect=loaded),
        patch.object(ValidateModule.gc, "collect", side_effect=lambda: events.append("collect")),
    ):
        validator.validateRssFeed()
    assert events == ["close a", "collect", "close b", "collect"]


def test_validateRssFeed_collects_garbage_after_item_exception() -> None:
    validator = _feedValidator([_rssItem("https://example.com/a.zip")])
    with (
        patch.object(ValidateModule, "openFileSource", return_value=MagicMock(selection="entry.htm")),
        patch.object(ValidateModule, "modelXbrlLoad", side_effect=OSError("unloadable")),
        patch.object(ValidateModule.gc, "collect") as collect,
    ):
        validator.validateRssFeed()
    validator.modelXbrl.error.assert_called_once()
    collect.assert_called_once_with()
