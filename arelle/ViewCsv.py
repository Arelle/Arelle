'''
Created on Oct 9, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import csv

class View:
    def __init__(self, modelXbrl, outfile, tabTitle, lang=None):
        self.modelXbrl = modelXbrl
        self.csvFile = open(outfile, "w", newline='')
        self.csvWriter = csv.writer(self.csvFile, dialect="excel")
        self.lang = lang
        if modelXbrl:
            if not lang: 
                self.lang = modelXbrl.modelManager.defaultLang
        
    def write(self,columns):
        self.csvWriter.writerow(columns)
        
    def close(self):
        self.csvFile.close()
        self.modelXbrl = None

