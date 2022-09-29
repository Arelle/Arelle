'''
EdgarRendererAllReports.py is a supplemental plugin to EdgarRenderer

Its purpose is to generate an Rall.htm file of all reports with no menus.

It supplements EdgarRenderer plugin code, running after regular EdgarRenderer.Filing.* methods.

To assure that this plugin runs after EdgarRenderer's event, please specify it after
EdgarRenderer in the list of plugins to load:

e.g., --plugins 'validate/EFM|EdgarRenderer|EdgarRendererAllReports.py|transforms/SEC.py'
if running from command line, or
      &plugins=validate/EFM|EdgarRenderer|EdgarRendererAllReports.py|transforms/SEC.py
if running by web service REST API

This plugin changes the default reportFormat to Xml only, avoiding generation of R1.htm,
if that's not wanted, please comment that out below.  It does require the xml files (so if
you also want individual Html R files, reportXslt should be chanted below to HtmlAndXml).

The resources folder must have InstanceReportTable.xslt (which is just InstanceReport.xslt
modified to not have an instance html header on the table body in xsl:template match="/").

See COPYRIGHT.md for copyright information.
'''
import os
from arelle.Version import authorLabel, copyrightLabel
from lxml import etree
from lxml.etree import tostring as treeToString

def edgarRendererFilingStartSupplement(cntlr, options, entrypointFiles, filing, *args, **kwargs):
    edgarRenderer = filing.edgarRenderer
    edgarRenderer.reportFormat = 'Html' # override report format to force only xml file output
    edgarRenderer.reportXslt = os.path.join(edgarRenderer.resourcesFolder,'InstanceReportTable.xslt')
    edgarRenderer.summaryXslt = '' # no FilingSummary.htm

def edgarRendererFilingEndSupplement(cntlr, options, filesource, filing, *args, **kwargs):
    edgarRenderer = filing.edgarRenderer

    # obtain R files from
    url = "FilingSummary.xml"
    # note that reportZip operations are on filing.reportZip as EdgarRenderer has finished
    # if needing to re-use EdgarRenderer.reportZip, set it again to filing.reportZip
    if filing.reportZip and url in filing.reportZip.namelist():
        filing.setReportZipStreamMode('r') # switch stream to read mode
        fileLikeObj = filing.reportZip.open(url)
    elif edgarRenderer.reportsFolder and os.path.exists(os.path.join(edgarRenderer.reportsFolder, url)):
        fileLikeObj = os.path.join(edgarRenderer.reportsFolder, url)
    else:
        return
    edgarRenderer.logDebug("Generate all-reports htm file")
    rAll = [b'''
        <html>
          <head>
            <title>View Filing Data</title>
            <link rel="stylesheet" type="text/css" href="report.css"/>
            <script type="text/javascript" src="Show.js">/* Do Not Remove This Comment */</script>
            <script type="text/javascript">
                            function toggleNextSibling (e) {
                            if (e.nextSibling.style.display=='none') {
                            e.nextSibling.style.display='block';
                            } else { e.nextSibling.style.display='none'; }
                            }</script>
          </head>
          <body>
          ''']
    filingSummaryTree = etree.parse(fileLikeObj)
    for htmlFileName in filingSummaryTree.iter(tag="HtmlFileName"):
        rFile = htmlFileName.text.strip()
        edgarRenderer.logDebug("Appending report file {}".format(rFile))
        if filing.reportZip and rFile in filing.reportZip.namelist():
            with filing.reportZip.open(rFile) as f:
                rAll.append(f.read())
        elif edgarRenderer.reportsFolder and os.path.exists(os.path.join(edgarRenderer.reportsFolder, rFile)):
            rFilePath = os.path.join(edgarRenderer.reportsFolder, rFile)
            with open(rFilePath, mode='rb') as f:
                rAll.append(f.read())
            os.remove(rFilePath)
        else:
            continue
    rAll.append(b'''
          </body>
        </html>
        ''')
    allHtmFile = "Rall.htm"
    if filing.reportZip:
        filing.setReportZipStreamMode('a') # switch stream to append mode (was read mode above)
        filing.reportZip.writestr(allHtmFile, b"".join(rAll))
    else:
        with open(os.path.join(edgarRenderer.reportsFolder, allHtmFile), mode='wb') as f:
            f.write(b"".join(rAll))
    edgarRenderer.renderedFiles.add(allHtmFile)
    edgarRenderer.logDebug("Write {} complete".format(allHtmFile))



__pluginInfo__ = {
    'name': 'Edgar Renderer All Reports supplement',
    'version': '0.9',
    'description': "This plug-in adds an \"Rall.htm\" result to the EdgarRenderer report directory or output zip",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    # note that this mount point must load after EdgarRenderer's same-named mount point
    'EdgarRenderer.Filing.Start': edgarRendererFilingStartSupplement,
    'EdgarRenderer.Filing.End': edgarRendererFilingEndSupplement,
    'EdgarRenderer.Gui.Start': edgarRendererFilingStartSupplement,
    'EdgarRenderer.Gui.End': edgarRendererFilingEndSupplement
}
