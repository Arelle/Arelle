'''
See COPYRIGHT.md for copyright information.
'''
import os
from arelle import XmlUtil
from arelle.ModelDocument import ModelDocument, Type

class ModelRssObject(ModelDocument):
    """
    .. class:: ModelRssObject(type=ModelDocument.Type.RSSFEED, uri=None, filepath=None, xmlDocument=None)

    ModelRssObject is a specialization of ModelDocument for RSS Feeds.

    (for parameters and inherited attributes, please see ModelDocument)
    """
    def __init__(self, modelXbrl,
                 type=Type.RSSFEED,
                 uri=None, filepath=None, xmlDocument=None):
        super(ModelRssObject, self).__init__(modelXbrl, type, uri, filepath, xmlDocument)
        self.rssItems = []

    def rssFeedDiscover(self, rootElement):
        """Initiates discovery of RSS feed
        """
        # add self to namespaced document
        self.xmlRootElement = rootElement
        for itemElt in XmlUtil.descendants(rootElement, None, "item"):
            self.rssItems.append(itemElt)
