'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

from typing import TYPE_CHECKING

from lxml import etree

from arelle import XmlUtil
from arelle.ModelDocument import ModelDocument, Type
from arelle.ModelObject import ModelObject


if TYPE_CHECKING:
    from arelle.ModelXbrl import ModelXbrl
    from arelle.PrototypeDtsObject import PrototypeObject


class ModelRssObject(ModelDocument):
    """
    .. class:: ModelRssObject(type=ModelDocument.Type.RSSFEED, uri=None, filepath=None, xmlDocument=None)

    ModelRssObject is a specialization of ModelDocument for RSS Feeds.

    (for parameters and inherited attributes, please see ModelDocument)
    """

    rssItems: list[ModelObject | PrototypeObject]

    def __init__(
        self,
        modelXbrl: ModelXbrl,
        type: int = Type.RSSFEED,
        uri: str | None = None,
        filepath: str | None = None,
        xmlDocument: etree._ElementTree[etree._Element] | None = None,
    ) -> None:
        super(ModelRssObject, self).__init__(modelXbrl, type, uri, filepath, xmlDocument)  # type: ignore[arg-type]
        self.rssItems = []

    def rssFeedDiscover(self, rootElement: ModelObject) -> None:
        """Initiates discovery of RSS feed
        """
        # add self to namespaced document
        self.xmlRootElement = rootElement
        for itemElt in XmlUtil.descendants(rootElement, None, "item"):
            self.rssItems.append(itemElt)
