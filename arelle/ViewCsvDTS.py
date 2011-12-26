#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
Created on Oct 5, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os
from arelle import ViewCsv

def viewDTS(modelXbrl, csvfile):
    view = ViewDTS(modelXbrl, csvfile)
    modelXbrl.modelManager.showStatus(_("viewing DTS"))
    view.viewDtsElement(modelXbrl.modelDocument, [], [])
    view.close()
    
class ViewDTS(ViewCsv.View):
    def __init__(self, modelXbrl, csvfile):
        super().__init__(modelXbrl, csvfile, "DTS")
                
    def viewDtsElement(self, modelDocument, indent, visited):
        visited.append(modelDocument)
        self.write(indent + ["{0} - {1}".format(
                    os.path.basename(modelDocument.uri),
                    modelDocument.gettype())])
        for referencedDocument in modelDocument.referencesDocument.keys():
            if visited.count(referencedDocument) == 0:
                self.viewDtsElement(referencedDocument, indent + [None], visited)
        visited.remove(modelDocument)
                
