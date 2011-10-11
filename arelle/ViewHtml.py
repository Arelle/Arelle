'''
Created on Sep 13, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import io
from lxml import etree

class View:
    def __init__(self, modelXbrl, outfile, tabTitle, lang=None):
        self.modelXbrl = modelXbrl
        self.outfile = outfile
        self.lang = lang
        if modelXbrl:
            if not lang: 
                self.lang = modelXbrl.modelManager.defaultLang
        html = io.StringIO(
'''
<html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <STYLE type="text/css"> 
            table {font-family:Arial,sans-serif;vertical-align:middle;white-space:normal;}
            th {background:#eee;}
            td {} 
            .tableHdr{border-top:.5pt solid windowtext;border-right:none;border-bottom:none;border-left:.5pt solid windowtext;}
            .zAxisHdr{border-top:.5pt solid windowtext;border-right:.5pt solid windowtext;border-bottom:none;border-left:.5pt solid windowtext;}
            .xAxisSpanLeg,.yAxisSpanLeg,.yAxisSpanArm{border-top:none;border-right:none;border-bottom:none;border-left:.5pt solid windowtext;}
            .xAxisHdrValue{border-top:.5pt solid windowtext;border-right:none;border-bottom:none;border-left:1.0pt solid windowtext;}
            .xAxisHdr{border-top:.5pt solid windowtext;border-right:none;border-bottom:none;border-left:.5pt solid windowtext;} 
            .yAxisHdrWithLeg{vertical-align:middle;border-top:.5pt solid windowtext;border-right:none;border-bottom:none;border-left:.5pt solid windowtext;}
            .yAxisHdrWithChildrenFirst{border-top:none;border-right:none;border-bottom:.5pt solid windowtext;border-left:.5pt solid windowtext;}
            .yAxisHdrAbstract{border-top:.5pt solid windowtext;border-right:none;border-bottom:none;border-left:.5pt solid windowtext;}
            .yAxisHdrAbstractChildrenFirst{border-top:none;border-right:none;border-bottom:.5pt solid windowtext;border-left:.5pt solid windowtext;}
            .yAxisHdr{border-top:.5pt solid windowtext;border-right:none;border-bottom:none;border-left:.5pt solid windowtext;}
            .cell{border-top:1.0pt solid windowtext;border-right:.5pt solid windowtext;border-bottom:.5pt solid windowtext;border-left:.5pt solid windowtext;}
            .blockedCell{border-top:1.0pt solid windowtext;border-right:.5pt solid windowtext;border-bottom:.5pt solid windowtext;border-left:.5pt solid windowtext;background:#eee;}
        </STYLE>
    </head>
    <body>
        <table border="1" cellspacing="0" cellpadding="4" style="font-size:8pt;">
        </table>
    </body>
</html>
'''
            )
        self.htmlDoc = etree.parse(html)
        html.close()
        for elt in self.htmlDoc.iter(tag='table'):
            self.tableElt = elt
            break
        
    def write(self):
        try:
            from arelle import XmlUtil
            with open(self.outfile, "w") as fh:
                XmlUtil.writexml(fh, self.htmlDoc, encoding="utf-8")
            self.modelXbrl.info("info", _("Saved output html to %(file)s"), file=self.outfile)
        except (IOError, EnvironmentError) as err:
            self.modelXbrl.exception("arelle:htmlIOError", _("Failed to save output html to %(file)s: \s%(error)s"), file=self.outfile, error=err)
        
    def close(self):
        self.modelXbrl = None
        self.htmlDoc = None

