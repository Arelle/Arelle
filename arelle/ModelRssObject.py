'''
Created on Nov 11, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os
from arelle import XmlUtil
from arelle.ModelDocument import ModelDocument, Type

class ModelRssObject(ModelDocument):
    def __init__(self, modelXbrl, 
                 type=Type.RSSFEED, 
                 uri=None, filepath=None, xmlDocument=None):
        super().__init__(modelXbrl, type, uri, filepath, xmlDocument)
        self.rssItems = []
        
    def rssFeedDiscover(self, rootElement):
        # add self to namespaced document
        self.xmlRootElement = rootElement
        for itemElt in XmlUtil.descendants(rootElement, None, "item"):
            self.rssItems.append(itemElt)
            
