#!/usr/bin/env python
#
# this script generates a testcase variations file for entry point checking
#

import os, fnmatch, xml.dom.minidom, datetime

def main():
    # the top directory where to generate the test case (and relative file names in the variations)
    topDirectory = "C:\\temp\\editaxonomy20110314"
    testcaseName = "EDInet test cases"
    ownerName = "Hugh Wallis"
    ownerEmail = "hughwallis@xbrl.org"
    
    entryRelativeFilePaths = []
    for root, dirs, files in os.walk(topDirectory):
        for fileName in files:
            if fnmatch.fnmatch(fileName, '*.xsd'):
                fullFilePath = os.path.join(root, fileName)
                entryRelativeFilePaths.append( os.path.relpath(fullFilePath, topDirectory) )

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!-- Copyright 2011 XBRL International.  All Rights Reserved. -->',
        '<?xml-stylesheet type="text/xsl" href="http://www.xbrl.org/Specification/formula/REC-2009-06-22/conformance/infrastructure/test.xsl"?>',
        '<testcase name="{0}" date="{1}" '.format(testcaseName,datetime.date.today()),
        ' xmlns="http://xbrl.org/2008/conformance"',
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        ' xsi:schemaLocation="http://xbrl.org/2008/conformance http://www.xbrl.org/Specification/formula/REC-2009-06-22/conformance/infrastructure/test.xsd">',
        '  <creator>',
        '  <name>{0}</name>'.format(ownerName),
        '  <email>{0}</email>'.format(ownerEmail),
        '  </creator>',
        '  <name>{0}</name>'.format(ownerEmail),
        '  <description>{0}</description>'.format(testcaseName),
        ]
    
    num = 1
    for entryFile in entryRelativeFilePaths:
        fileName = os.path.basename(entryFile)
        lines.append("  <variation name='{0}' id='V-{1}'>".format(fileName, num))
        num += 1
        lines.append("    <description>{0}</description>".format(fileName))
        lines.append("    <data>")
        lines.append("       <xsd readMeFirst='true'>{0}</xsd>".format(entryFile.replace("\\","/")))
        lines.append("    </data>")
        lines.append("    <result expected='valid'/>")
        lines.append("  </variation>")
        
    lines.append('</testcase>')
        
    with open( os.path.join(topDirectory, "testcase.xml"), "w") as fh:
        fh.write('\n'.join(lines))

if __name__ == "__main__":
    main()
