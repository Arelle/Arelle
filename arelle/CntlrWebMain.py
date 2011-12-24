'''
Created on Oct 3, 2010

Use this module to start Arelle in web server mode

(TBD, plan is to be based on Mark V XBRL Gateway.)

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle.webserver.bottle import route, get, post, request, response, run, static_file
import os, io
from arelle import Version, XmlUtil

def startWebserver(_cntlr, options):
    global imagesDir, cntlr, optionsNames
    cntlr = _cntlr
    imagesDir = cntlr.imagesDir
    optionsNames = [option for option in dir(options) if not option.startswith('_')]
    host, sep, port = options.webserver.partition(":")
    run(host=host, port=port)
    
@get('/rest/login')
def login_form():
    return _('''<html><body><form method="POST"><table>
                <tr><td>Name:</td><td><input name="name" type="text" /></td></tr>
                <tr><td>Password:</td><td><input name="password" type="password" /></td></tr>
                <tr><td>&nbsp;</td><td><input type="submit" value="Submit" /></td></tr>
                </table></form></body></html>''')
    
@post('/rest/login')
def login_submit():
    name     = request.forms.get('name')
    password = request.forms.get('password')
    if checkLogin(name, password):
        return _("<p>You are logged in as user: {0}</p>").format(name)
    else:
        return _("<p>Login failed</p>")
    
def checkLogin(_user, _password):
    global user
    user = _user
    return True

@get('/rest/logout')
def logout():
    global user
    user = None
    return _("<p>You are logged out.</p>")

@route('/favicon.ico')
def arelleIcon():
    return static_file("arelle.ico", root=imagesDir)

@route('/images/<imgFile>')
def image(imgFile):
    return static_file(imgFile, root=imagesDir)

validationOptions = {
    "efm": "validateEFM",
    "gfm": "gfmName",
    "utr": "utrValidate",
    "import": "importFilenames"
                     }

class Options():
    def __init__(self):
        for option in optionsNames:
            setattr(self, option, None)
            
@route('/rest/xbrl/<file:path>/validation/xbrl')
@route('/rest/xbrl/validation')
def validation(file=None):
    flavor = request.query.flavor or 'standard'
    media = request.query.media or 'text'
    errors = []
    if flavor != 'standard' and not flavor.startswith('edgar') and not flavor.startswith('sec'):
        errors.append(_("Flavor {0} is not supported").format(flavor)) 
    if media not in ('xml', 'xhtml', 'text'):
        errors.append(_("Media {0} is not supported").format(media))
    if errors:
        errors.insert(0, _("URL: ") + file)
        return "<br/>".join(errors)
    options = Options() # need named parameters to simulate options
    for key, value in request.query.items():
        if key == "file":
            setattr(options, "filename", value)
        elif key == "flavor":
            if value.startswith("sec") or value.startswith("edgar"):
                setattr(options, "validateEFM", True)
        elif key == "media":
            pass
        elif key in validationOptions:
            setattr(options, validationOptions[key], value)
        elif not value: # convert plain str parameter present to True parameter
            setattr(options, key, True)
    if file:
        setattr(options, "filename", file)
    setattr(options, "validate", True)
    cntlr.run(options)
    if media == "xml":
        response.content_type = 'text/xml; charset=UTF-8'
        return cntlr.logHandler.getXml()
    else:
        response.content_type = 'text/html; charset=UTF-8'
        return htmlBody(cntlr.logHandler.getText().replace("&","&amp;").replace("<","&lt;").replace("\n","<br/>"))

@route('/rest/xbrl/diff')
def diff():
    if not request.query.fromDTS or not request.query.toDTS or not request.query.report:
        return _("From DTS, to DTS, and report must be specified")
    options = Options()
    setattr(options, "filename", request.query.fromDTS)
    setattr(options, "diffFilename", request.query.toDTS)
    setattr(options, "versReportFilename", request.query.report)
    setattr(options, "versReportInMemory", True)
    modelXbrlVersReport = cntlr.run(options)
    fh = io.StringIO()
    XmlUtil.writexml(fh, modelXbrlVersReport.modelDocument.xmlDocument, encoding="utf-8")
    reportContents = fh.getvalue()
    fh.close()
    return reportContents

    
@route('/help')
def help():
    return htmlBody(_('''<table>
<tr><th colspan="2">Arelle web API</th></tr>
<tr><td>/help</td><td>This web page.</td></tr>
<tr><td>/about</td><td>About web page, copyrights, etc.</td></tr>
<tr><th colspan="2">Validation</th></tr>
<tr><td>/rest/xbrl/&#x200B;{file}/&#x200B;validation/&#x200B;xbrl</td><td>Validate document at {file}.  {file} may be
local or web url, and may have "/" characters replaced by ";" characters (but that is not
necessary).</td></tr>
<tr><td style="text-align=right;">Example:</td><td><code>/rest/&#x200B;xbrl/&#x200B;c:/a/b/c.xbrl/&#x200B;validation/&#x200B;xbrl?&#x200B;media=xml</code>: Validate entry instance
document at c:/a/b/c.xbrl (on local drive) and return structured xml results.</td></tr>
<tr><td>/rest/xbrl/&#x200B;validation</td><td>(Alternative syntax) Validate document, file is provided as a parameter (see below).</td></tr>
<tr><td style="text-align=right;">Example:</td><td><code>/rest/&#x200B;xbrl/&#x200B;validation&#x200B;?file=c:/a/b/c.xbrl&amp;&#x200B;media=xml</code>: Validate entry instance
document at c:/a/b/c.xbrl (on local drive) and return structured xml results.</td></tr>
<tr><td></td><td>Parameters are optional after "?" character, and are separated by "&amp;" characters, 
as follows:</td></tr>
<tr><td style="text-indent: 1em;">flavor</td><td><code>standard</code>: XBRL 2.1 and XDT validation. (default)
<br/>{<code>sec</code>*|<code>edgar</code>*}: SEC Edgar Filer Manual validation.</td></tr> 
<tr><td style="text-indent: 1em;">media</td><td><code>html</code>: Html text results. (default)
<br/><code>xml</code>: XML structured results.</td></tr> 
<tr><td style="text-indent: 1em;">file</td><td>Alternate way to specify file name or url by a parameter.</td></tr> 
<tr><td style="text-indent: 1em;">import</td><td>A list of files to import to the DTS, such as additional formula 
or label linkbases.  Multiple file names are separated by a '|' character.</td></tr> 
<tr><td style="text-indent: 1em;">calcDecimals</td><td>Specify calculation linkbase validation inferring decimals.</td></tr> 
<tr><td style="text-indent: 1em;">calcPrecision</td><td>Specify calculation linkbase validation inferring precision.</td></tr> 
<tr><td style="text-indent: 1em;">efm</td><td>Select Edgar Filer Manual (U.S. SEC) disclosure system validation. (Alternative to flavor parameter.)</td></tr> 
<tr><td style="text-indent: 1em;">gfm</td><td>Specify a Global Filer Manual disclosure system name and select disclosure system validation.  Value of parameter is name of gfm validation.</td></tr> 
<tr><td style="text-indent: 1em;">utr</td><td>Select validation with respect to Unit Type Registry.</td></tr> 
<tr><td style="text-indent: 1em;">formulaAsserResultCounts</td><td>Report formula assertion counts.</td></tr> 
<tr><td style="text-indent: 1em;">formulaVarSetExprResult</td><td>Trace variable set formula value, assertion test results.</td></tr> 
<tr><td style="text-indent: 1em;">formulaVarFilterWinnowing</td><td>Trace variable set filter winnowing.</td></tr> 
<tr><td style="text-indent: 1em;">{other}</td><td>Other detailed formula trace parameters:<br/>
formulaParamExprResult, formulaParamInputValue, formulaCallExprSource, formulaCallExprCode, formulaCallExprEval,
formulaCallExprResult, formulaVarSetExprEval, formulaFormulaRules, formulaVarsOrder,
formulaVarExpressionSource, formulaVarExpressionCode, formulaVarExpressionEvaluation, formulaVarExpressionResult, and formulaVarFiltersResult.
<tr><th colspan="2">Versioning Report (diff of two DTSes)</th></tr>
<tr><td>/rest/xbrl/&#x200B;diff</td><td>Diff two DTSes, producing an XBRL versioning report relative to report directory.</td></tr>
<tr><td></td><td>Parameters are requred "?" character, and are separated by "&amp;" characters, 
as follows:</td></tr>
<tr><td style="text-indent: 1em;">fromDTS</td><td>File name or url of from DTS.</td></tr> 
<tr><td style="text-indent: 1em;">toDTS</td><td>File name or url of to DTS.</td></tr> 
<tr><td style="text-indent: 1em;">report</td><td>File name or url of to report (to for relative path construction).  The report is not written out, but its contents are returned by the web request to be saved by the requestor.</td></tr> 
<tr><td style="text-align=right;">Example:</td><td><code>/rest/&#x200B;diff?&#x200B;fromDTS=c:/a/prev/old.xsd&amp;&#x200B;toDTS=c:/a/next/new.xsd&amp;&#x200B;report=c:/a/report/report.xml</code>: Diff two DTSes and produce versioning report.</td></tr>
</table>'''))

@route('/about')
def about():
    return htmlBody(_('''<table width="700p">
<tr><th colspan="2">About arelle</th></tr>
<tr><td rowspan="12" style="vertical-align:top;"><img src="/images/arelle32.gif"/></td><td>arelle&reg; version: %s. An open source XBRL platform</td></tr>
<tr><td>&copy; 2010-2011 Mark V Systems Limited.  All rights reserved.</td></tr>
<tr><td>Web site: <a href="http://www.arelle.org">http://www.arelle.org</a>.  
E-mail support: <a href="mailto:support@arelle.org">support@arelle.org</a>.</td></tr>
<tr><td>Licensed under the Apache License, Version 2.0 (the \"License\"); you may not use this file 
except in compliance with the License.  You may obtain a copy of the License at
<a href="http://www.apache.org/licenses/LICENSE-2.0">http://&#x200B;www.apache.org/&#x200B;licenses/&#x200B;LICENSE-2.0</a>.
Unless required by applicable law or agreed to in writing, software distributed under the License 
is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  
See the License for the specific language governing permissions and limitations under the License.</td></tr>
<tr><td>Includes:</td><tr>
<tr><td style="text-indent: 2.0em;">Python&reg; &copy; 2001-2010 Python Software Foundation</td></tr>
<tr><td style="text-indent: 2.0em;">PyParsing &copy; 2003-2010 Paul T. McGuire</td></tr>
<tr><td style="text-indent: 2.0em;">lxml &copy; 2004 Infrae, ElementTree &copy; 1999-2004 by Fredrik Lundh</td></tr>
<tr><td style="text-indent: 2.0em;">xlrd &copy; 2005-2009 Stephen J. Machin, Lingfo Pty Ltd, \u00a9 2001 D. Giffin, &copy; 2000 A. Khan</td></tr>
<tr><td style="text-indent: 2.0em;">xlwt &copy; 2007 Stephen J. Machin, Lingfo Pty Ltd, &copy; 2005 R. V. Kiseliov</td></tr>
<tr><td style="text-indent: 2.0em;">Bottle &copy; 2011 Marcel Hellkamp</td></tr>
</table>''') % Version.version)

def htmlBody(body):
    return '''
<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <STYLE type="text/css">table {font-family:Arial,sans-serif;vertical-align:top;white-space:normal;}
            p,table {font-size:10pt;}
            th {{background:#eee;}}
            td {vertical-align:top;}
            .tableHdr{border-top:.5pt solid windowtext;border-right:none;border-bottom:none;border-left:.5pt solid windowtext;}
            .cell{border-top:1.0pt solid windowtext;border-right:.5pt solid windowtext;border-bottom:.5pt solid windowtext;border-left:.5pt solid windowtext;}
            .blockedCell{border-top:1.0pt solid windowtext;border-right:.5pt solid windowtext;border-bottom:.5pt solid windowtext;border-left:.5pt solid windowtext;background:#eee;}
        </STYLE>
    </head>
    <body>
    %s
    </body>
</html>
''' % body
#            <table border="1" cellpadding="4" cellspacing="0" style="">
