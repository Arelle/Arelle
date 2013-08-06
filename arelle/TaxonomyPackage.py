'''
Separated on Jul 28, 2013 from DialogOpenArchive.py

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import sys
from lxml import etree
if sys.version[0] >= '3':
    from urllib.parse import urljoin
else:
    from urllib2.urlparse import urljoin
from arelle import Locale

def parseTxmyPkg(mainWin, metadataFile):
    unNamedCounter = 1
    currentLang = Locale.getLanguageCode()

    tree = etree.parse(metadataFile)

    remappings = dict((m.get("prefix"),m.get("replaceWith"))
                      for m in tree.iter(tag="{http://www.corefiling.com/xbrl/taxonomypackage/v1}remapping"))

    result = {}

    for entryPointSpec in tree.iter(tag="{http://www.corefiling.com/xbrl/taxonomypackage/v1}entryPoint"):
        name = None
        
        # find closest match name node given xml:lang match to current language or no xml:lang
        for nameNode in entryPointSpec.iter(tag="{http://www.corefiling.com/xbrl/taxonomypackage/v1}name"):
            xmlLang = nameNode.get('{http://www.w3.org/XML/1998/namespace}lang')
            if name is None or not xmlLang or currentLang == xmlLang:
                name = nameNode.text
                if currentLang == xmlLang: # most prefer one with the current locale's language
                    break

        if not name:
            name = _("<unnamed {0}>").format(unNamedCounter)
            unNamedCounter += 1

        epDocCount = 0
        for epDoc in entryPointSpec.iterchildren("{http://www.corefiling.com/xbrl/taxonomypackage/v1}entryPointDocument"):
            if epDocCount:
                mainWin.addToLog(_("WARNING: skipping multiple-document entry point (not supported)"))
                continue
            epDocCount += 1
            epUrl = epDoc.get('href')
            base = epDoc.get('{http://www.w3.org/XML/1998/namespace}base') # cope with xml:base
            if base:
                resolvedUrl = urljoin(base, epUrl)
            else:
                resolvedUrl = epUrl
    
            #perform prefix remappings
            remappedUrl = resolvedUrl
            for prefix, replace in remappings.items():
                remappedUrl = remappedUrl.replace(prefix, replace, 1)
            result[name] = (remappedUrl, resolvedUrl)

    return (result, remappings)
