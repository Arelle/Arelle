'''
Created on Oct 3, 2010

Use this module to start Arelle in web server mode

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle.webserver.bottle import route, get, post, request, response, run, static_file
import os, io
from arelle import Version, XmlUtil
from arelle.FileSource import FileNamedStringIO

def startWebserver(_cntlr, options):
    """Called once from main program in CmtlrCmdLine to initiate web server on specified local port.
       
    :param options: OptionParser options from parse_args of main argv arguments (the argument *webserver* provides hostname and port), port being used to startup the webserver on localhost.
    :type options: optparse.Values
    """
    global imagesDir, cntlr, optionsNames
    cntlr = _cntlr
    imagesDir = cntlr.imagesDir
    optionsNames = [option for option in dir(options) if not option.startswith('_')]
    host, sep, port = options.webserver.partition(":")
    run(host=host, port=port)
    
@get('/rest/login')
def login_form():
    """Request for a login form (get to */rest/login*).  Corresponds to login from other providers of XBRL validation services, but 
    this version of Arelle does not perform accounting or charges for validation requests, so the login is ignored.
    
    :returns: str -- HTML login form to enter and submit via method=POST these fields: name, password
    """
    return _('''<html><body><form method="POST"><table>
                <tr><td>Name:</td><td><input name="name" type="text" /></td></tr>
                <tr><td>Password:</td><td><input name="password" type="password" /></td></tr>
                <tr><td>&nbsp;</td><td><input type="submit" value="Submit" /></td></tr>
                </table></form></body></html>''')
    
@post('/rest/login')
def login_submit():
    """Login of fields from login form (post to */rest/login*).  Saves user ID for future use.
    
    :param name: User ID
    :param password: Password
    """
    name     = request.forms.get('name')
    password = request.forms.get('password')
    if checkLogin(name, password):
        return _("<p>You are logged in as user: {0}</p>").format(name)
    else:
        return _("<p>Login failed</p>")
    
def checkLogin(_user, _password):
    """Save user ID for future use.  Password not currently processed.
    
    :returns: bool -- True (for now, future user may interact with authentication and accounting services.)
    """
    global user
    user = _user
    return True

@get('/rest/logout')
def logout():
    """Request to log out (get */rest/logout*).  Removes any proior user ID from session.
    
    :returns: html -- Message that user has logged out
    """
    global user
    user = None
    return _("<p>You are logged out.</p>")

@route('/favicon.ico')
def arelleIcon():
    """Request for icon for URL display (get */favicon.ico*).
    
    :returns: ico -- Icon file for browsers
    """
    return static_file("arelle.ico", root=imagesDir)

@route('/images/<imgFile>')
def image(imgFile):
    """Request for an image file for URL display (get */images/<imgFile>*).
    
    :returns: image file -- Requested image file from images directory of application for browsers
    """
    return static_file(imgFile, root=imagesDir)

validationOptions = {
    "efm": "validateEFM",
    "ifrs": "gfmName=ifrs",
    "hmrc": "gfmName=hmrc",
    "sbr-nl": "gfmName=sbr-nl",
    "utr": "utrValidate",
    "infoset": "infosetValidate",
    "import": "importFiles"
                     }

class Options():
    """Class to emulate options needed by CntlrCmdLine.run"""
    def __init__(self):
        for option in optionsNames:
            setattr(self, option, None)
            
supportedViews = {'DTS', 'concepts', 'pre', 'cal', 'dim', 'facts', 'factTable', 'formulae'}
GETorPOST = ('GET', 'POST')

@route('/rest/xbrl/<file:path>/open', method=GETorPOST)
@route('/rest/xbrl/<file:path>/close', method=GETorPOST)
@route('/rest/xbrl/<file:path>/validation/xbrl', method=GETorPOST)
@route('/rest/xbrl/<file:path>/DTS', method=GETorPOST)
@route('/rest/xbrl/<file:path>/concepts', method=GETorPOST)
@route('/rest/xbrl/<file:path>/pre', method=GETorPOST)
@route('/rest/xbrl/<file:path>/cal', method=GETorPOST)
@route('/rest/xbrl/<file:path>/dim', method=GETorPOST)
@route('/rest/xbrl/<file:path>/facts', method=GETorPOST)
@route('/rest/xbrl/<file:path>/factTable', method=GETorPOST)
@route('/rest/xbrl/<file:path>/formulae', method=GETorPOST)
@route('/rest/xbrl/validation', method=GETorPOST)
@route('/rest/xbrl/view', method=GETorPOST)
@route('/rest/xbrl/open', method=GETorPOST)
@route('/rest/xbrl/close', method=GETorPOST)
def validation(file=None):
    """REST request to validate, by *get* or *post*, to URL patterns including */rest/xbrl/<file:path>/{open|close|validation|DTS...}*,
    and */rest/xbrl/{view|open|close}*.
    Sets up CntrlCmdLine options for request, performed by runOptionsAndGetResult using CntlrCmdLine.run with get or post arguments.
    
    :returns: html, xhtml, xml, json, text -- Return per media type argument and request arguments
    """
    errors = []
    flavor = request.query.flavor or 'standard'
    media = request.query.media or 'html'
    requestPathParts = request.urlparts[2].split('/')
    isValidation = 'validation' == requestPathParts[-1] or 'validation' == requestPathParts[-2]
    view = request.query.view
    if request.method == 'POST':
        sourceZipStream = request.body
        mimeType = request.get_header("Content-Type")
        if mimeType not in ('application/zip', 'application/x-zip', 'application/x-zip-compressed', 'multipart/x-zip'):
            errors.append(_("POST must provide a zip file, Content-Type '{0}' not recognized as a zip file.").format(mimeType))
    else:
        sourceZipStream = None
    if not view:
        if requestPathParts[-1] in supportedViews:
            view = requestPathParts[-1]
    if isValidation:
        if view:
            errors.append(_("Only validation or one view can be specified in one requested."))
        if media not in ('xml', 'xhtml', 'html', 'json', 'text'):
            errors.append(_("Media '{0}' is not supported for validation (please select xhtml, html, xml, json or text)").format(media))
    elif view:
        if media not in ('xml', 'xhtml', 'html', 'csv', 'json'):
            errors.append(_("Media '{0}' is not supported for view (please select xhtml, html, xml, csv, or json)").format(media))
    elif requestPathParts[-1] not in ("open", "close"):                
        errors.append(_("Neither validation nor view requested, nothing to do."))
    if flavor != 'standard' and not flavor.startswith('edgar') and not flavor.startswith('sec'):
        errors.append(_("Flavor '{0}' is not supported").format(flavor)) 
    if view and view not in supportedViews:
        errors.append(_("View '{0}' is not supported").format(view))
    if errors:
        errors.insert(0, _("URL: ") + file)
        return errorReport(errors, media)
    options = Options() # need named parameters to simulate options
    for key, value in request.query.items():
        if key == "file":
            setattr(options, "entrypointFile", value)
        elif key == "flavor":
            if value.startswith("sec") or value.startswith("edgar"):
                setattr(options, "validateEFM", True)
        elif key in("media", "view"):
            pass
        elif key in validationOptions:
            optionKey, sep, optionValue = validationOptions[key].partition('=')
            setattr(options, optionKey, optionValue or value)
        elif not value: # convert plain str parameter present to True parameter
            setattr(options, key, True)
        else:
            setattr(options, key, value)
    if file:
        setattr(options, "entrypointFile", file.replace(';','/'))
    requestPathParts = set(request.urlparts[2].split('/'))
    viewFile = None
    if isValidation:
        setattr(options, "validate", True)
    elif view:
        viewFile = FileNamedStringIO(media)
        setattr(options, view + "File", viewFile)
    return runOptionsAndGetResult(options, media, viewFile, sourceZipStream)
    
def runOptionsAndGetResult(options, media, viewFile, sourceZipStream=None):
    """Execute request according to options, for result in media, with *post*ed file in sourceZipStream, if any.
    
    :returns: html, xml, csv, text -- Return per media type argument and request arguments
    """
    successful = cntlr.run(options, sourceZipStream)
    if media == "xml":
        response.content_type = 'text/xml; charset=UTF-8'
    elif media == "csv":
        response.content_type = 'text/csv; charset=UTF-8'
    elif media == "json":
        response.content_type = 'application/json; charset=UTF-8'
    elif media == "text":
        response.content_type = 'text/plain; charset=UTF-8'
    else:
        response.content_type = 'text/html; charset=UTF-8'
    if successful and viewFile:
        # defeat re-encoding
        result = viewFile.getvalue().replace("&nbsp;","\u00A0").replace("&shy;","\u00AD").replace("&amp;","&")
        viewFile.close()
    elif media == "xml":
        result = cntlr.logHandler.getXml()
    elif media == "json":
        result = cntlr.logHandler.getJson()
    elif media == "text":
        result = cntlr.logHandler.getText()
    else:
        result = htmlBody(tableRows(cntlr.logHandler.getLines(), header=_("Messages")))
    return result

@route('/rest/xbrl/diff')
def diff():
    """Execute versioning diff request for *get* request to */rest/xbrl/diff*.
    
    :returns: xml -- Versioning report.
    """
    if not request.query.fromDTS or not request.query.toDTS or not request.query.report:
        return _("From DTS, to DTS, and report must be specified")
    options = Options()
    setattr(options, "entrypointFile", request.query.fromDTS)
    setattr(options, "diffFile", request.query.toDTS)
    fh = FileNamedStringIO(request.query.report)
    setattr(options, "versReportFile", fh)
    cntlr.run(options)
    reportContents = fh.getvalue()
    fh.close()
    response.content_type = 'text/xml; charset=UTF-8'
    return reportContents

@route('/rest/configure')
def configure():
    """Set up features for *get* requests to */rest/configure*, e.g., proxy or plug-ins.
    
    :returns: html -- Status of configuration request (e.g., proxy or plug-ins).
    """
    if not request.query.proxy and not request.query.plugins:
        return _("proxy or plugins must be specified")
    options = Options()
    if request.query.proxy:
        setattr(options, "proxy", request.query.proxy)
    if request.query.plugins:
        setattr(options, "plugins", request.query.plugins)
    cntlr.run(options)
    response.content_type = 'text/html; charset=UTF-8'
    return htmlBody(tableRows(cntlr.logHandler.getLines(), header=_("Configuration Request")))

@route('/rest/stopWebServer')
def stopWebServer():
    """Stop the web server by *get* requests to */rest/stopWebServer*.
    
    (This is not working on Windows.)
    """
    request.app.close()
    request.app.reset()
    raise KeyboardInterrupt()
    
@route('/quickbooks/server.asmx', method='POST')
def quickbooksServer():
    """Interface to QuickBooks server responding to  *post* requests to */quickbooks/server.asmx*.
    
    (Part of QuickBooks protocol, see module CntlrQuickBooks.)
    """
    from arelle import CntlrQuickBooks
    response.content_type = 'text/xml; charset=UTF-8'
    return CntlrQuickBooks.server(cntlr, request.body, request.urlparts)


@route('/rest/quickbooks/<qbReport>/xbrl-gl/<file:path>')
@route('/rest/quickbooks/<qbReport>/xbrl-gl/<file:path>/view')
@route('/rest/quickbooks/<qbReport>/xbrl-gl/view')
def quickbooksGLrequest(qbReport=None, file=None):
    """Initiate request to QuickBooks server for *get* requests to */rest/quickbooks/<qbReport>/xbrl-gl/...*.
    
    :returns: html, xml, csv, text -- Return per media type argument and request arguments
    """
    from arelle.CntlrQuickBooks import supportedQbReports, qbRequest 
    from arelle.ModelValue import dateTime
    errors = []
    requestPathParts = request.urlparts[2].split('/')
    viewRequested = "view" == requestPathParts[-1]
    media = request.query.media or 'html'
    fromDate = request.query.fromDate
    toDate = request.query.toDate
    if qbReport not in supportedQbReports:
        errors.append(_("QuickBooks report '{0}' is not supported (please select from: {1})").format(
                          qbReport, ', '.join(supportedQbReports)))
    if media not in ('xml', 'xhtml', 'html'):
        errors.append(_("Media '{0}' is not supported for xbrl-gl (please select xhtml, html or xml)").format(media))
    if not fromDate or dateTime(fromDate) is None:
        errors.append(_("FromDate '{0}' missing or not valid").format(fromDate))
    if not toDate or dateTime(toDate) is None:
        errors.append(_("ToDate '{0}' missing or not valid").format(toDate))
    if errors:
        return errorReport(errors, media)
    ticket = qbRequest(qbReport, fromDate, toDate, file)
    result = htmlBody(tableRows([_("Request queued for QuickBooks...")], header=_("Quickbooks Request")), script='''
<script type="text/javascript">
<!-- 
var timer = setInterval("autoRefresh()", 1000 * 10);
function autoRefresh(){{location.href = "/rest/quickbooks/response?ticket={0}&media={1}&view={2}";}}
//--> 
</script>
'''.format(ticket, media, viewRequested))
    return result

    
@route('/rest/quickbooks/response')
def quickbooksGLresponse():
    """Poll for QuickBooks protocol responses for *get* requests to */rest/quickbooks/response*.
    
    :returns: html, xml, csv, text -- Return per media type argument and request arguments, if response is ready, otherwise javascript to requery this *get* request periodicially.
    """
    from arelle import CntlrQuickBooks
    ticket = request.query.ticket
    media = request.query.media
    viewRequested = request.query.view
    status = CntlrQuickBooks.qbRequestStatus.get(ticket)
    if not status:
        return htmlBody(tableRows([_("QuickBooks ticket not found, request canceled.")], header=_("Quickbooks Request")))
    if status.startswith("ConnectionErrorMessage: "):
        CntlrQuickBooks.qbRequestStatus.pop(ticket, None)
        return errorReport([status[24:]], media)
    if status != "Done" or ticket not in CntlrQuickBooks.xbrlInstances:
        return htmlBody(tableRows([_("{0}, Waiting 20 seconds...").format(status)], 
                                  header=_("Quickbooks Request")), 
                                  script='''
<script type="text/javascript">
<!-- 
var timer = setInterval("autoRefresh()", 1000 * 20);
function autoRefresh(){{clearInterval(timer);self.location.reload(true);}}
//--> 
</script>
''')
    CntlrQuickBooks.qbRequestStatus.pop(ticket)
    
    instanceUuid = CntlrQuickBooks.xbrlInstances[ticket]
    CntlrQuickBooks.xbrlInstances.pop(ticket)
    options = Options()
    setattr(options, "entrypointFile", instanceUuid)
    viewFile = FileNamedStringIO(media)
    setattr(options, "factsFile", viewFile)
    return runOptionsAndGetResult(options, media, viewFile)

@route('/quickbooks/server.html')
def quickbooksWebPage():
    return htmlBody(_('''<table width="700p">
<tr><th colspan="2">Arelle QuickBooks Global Ledger Interface</th></tr>
<tr><td>checkbox</td><td>Trial Balance.</td></tr>
<tr><td>close button</td><td>Done</td></tr>
</table>'''))

@route('/quickbooks/localhost.crt')
@route('/localhost.crt')
def localhostCertificate():
    """Interface to QuickBooks server responding to  *get* requests for a host certificate */quickbooks/localhost.crt* or */localhost.crt*.
    
    (Supports QuickBooks protocol.)
    
    :returns: self-signed certificate
    """
    return '''
-----BEGIN CERTIFICATE-----
MIIDljCCAn4CAQAwDQYJKoZIhvcNAQEEBQAwgZAxCzAJBgNVBAYTAlVTMRMwEQYD
VQQIEwpDYWxpZm9ybmlhMQ8wDQYDVQQHEwZFbmNpbm8xEzARBgNVBAoTCmFyZWxs
ZS5vcmcxDzANBgNVBAsTBmFyZWxsZTESMBAGA1UEAxMJbG9jYWxob3N0MSEwHwYJ
KoZIhvcNAQkBFhJzdXBwb3J0QGFyZWxsZS5vcmcwHhcNMTIwMTIwMDg0NjM1WhcN
MTQxMDE1MDg0NjM1WjCBkDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCkNhbGlmb3Ju
aWExDzANBgNVBAcTBkVuY2lubzETMBEGA1UEChMKYXJlbGxlLm9yZzEPMA0GA1UE
CxMGYXJlbGxlMRIwEAYDVQQDEwlsb2NhbGhvc3QxITAfBgkqhkiG9w0BCQEWEnN1
cHBvcnRAYXJlbGxlLm9yZzCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEB
AMJEq9zT4cdA2BII4TG4OJSlUP22xXqNAJdZZeB5rTIX4ePwIZ8KfFh/XWQ1/q5I
c/rkZ5TyC+SbEmQa/unvv1CypMAWWMfuguU6adOsxt+zFFMJndlE1lr3A2SBjHbD
vBGzGJJTivBzDPBIQ0SGcf32usOeotmE2PA11c5en8/IsRXm9+TA/W1xL60mfphW
9PIaJ+WF9rRROjKXVdQZTRFsNRs/Ag8o3jWEyWYCwR97+XkorYsAJs2TE/4zV+8f
8wKuhOrsy9KYFZz2piVWaEC0hbtDwX1CqN+1oDHq2bYqLygUSD/LbgK1lxM3ciVy
ewracPVHBErPlcJFxiOxAw0CAwEAATANBgkqhkiG9w0BAQQFAAOCAQEAM2np3UVY
6g14oeV0Z32Gn04+r6FV2D2bobxCVLIQDsWGEv1OkjVBJTu0bLsZQuNVZHEn5a+2
I0+MGME3HK1rx1c8MrAsr5u7ZLMNj7cjjtFWAUp9GugJyOmGK136o4/j1umtBojB
iVPvHsAvwZuommfME+AaBE/aJjPy5I3bSu8x65o1fuJPycrSeLAnLd/shCiZ31xF
QnJ9IaIU1HOusplC13A0tKhmRMGNz9v+Vqdj7J/kpdTH7FNMulrJTv/0ezTPjaOB
QhpLdqly7hWJ23blbQQv4ILT2CiPDotJslcKDT7GzvPoDu6rIs2MpsB/4RDYejYU
+3cu//C8LvhjkQ==
-----END CERTIFICATE-----
'''
    
@route('/help')
def help():
    """Help web page for *get* requests to */help*.
    
    :returns: html - Table of CntlrWebMain web API
    """
    return htmlBody(_('''<table>
<tr><th colspan="2">Arelle web API</th></tr>
<tr><td>/help</td><td>This web page.</td></tr>
<tr><td>/about</td><td>About web page, copyrights, etc.</td></tr>

<tr><th colspan="2">Validation</th></tr>
<tr><td>/rest/xbrl/{file}/validation/xbrl</td><td>Validate document at {file}.</td></tr>
<tr><td>\u00A0</td><td>For a browser request or http GET request, {file} may be local or web url, and may have "/" characters replaced by ";" characters (but that is not
necessary).</td></tr>
<tr><td style="text-align=right;">Example:</td><td><code>/rest/xbrl/c:/a/b/c.xbrl/validation/xbrl?media=xml</code>: Validate entry instance
document at c:/a/b/c.xbrl (on local drive) and return structured xml results.</td></tr>
<tr><td>\u00A0</td><td>For an http POST of a zip file (mime type application/zip), {file} is the relative file path inside the zip file.</td></tr>
<tr><td>/rest/xbrl/validation</td><td>(Alternative syntax) Validate document, file is provided as a parameter (see below).</td></tr>
<tr><td style="text-align=right;">Example:</td><td><code>/rest/xbrl/validation?file=c:/a/b/c.xbrl&amp;media=xml</code>: Validate entry instance
document at c:/a/b/c.xbrl (on local drive) and return structured xml results.</td></tr>
<tr><td></td><td>Parameters are optional after "?" character, and are separated by "&amp;" characters, 
as follows:</td></tr>
<tr><td style="text-indent: 1em;">flavor</td><td><code>standard</code>: XBRL 2.1 and XDT validation. (default)
<br/>{<code>sec</code>*|<code>edgar</code>*}: SEC Edgar Filer Manual validation.</td></tr> 
<tr><td style="text-indent: 1em;">media</td><td><code>html</code> or <code>xhtml</code>: Html text results. (default)
<br/><code>xml</code>: XML structured results.
<br/><code>json</code>: JSON results.
<br/><code>text</code>: Plain text results (no markup).</td></tr> 
<tr><td style="text-indent: 1em;">file</td><td>Alternate way to specify file name or url by a parameter.</td></tr> 
<tr><td style="text-indent: 1em;">import</td><td>A list of files to import to the DTS, such as additional formula 
or label linkbases.  Multiple file names are separated by a '|' character.</td></tr> 
<tr><td style="text-indent: 1em;">labelLang</td><td>Label language to override system settings, e.g., <code>&labelLang=ja</code>.</td></tr> 
<tr><td style="text-indent: 1em;">labelRole</td><td>Label role instead of standard label, e.g., <code>&labelRole=http://www.xbrl.org/2003/role/verboseLabel</code>.  To use the concept QName instead of a label, specify <code>&labelRole=XBRL-concept-name</code>.</td></tr> 
<tr><td style="text-indent: 1em;">uiLang</td><td>User interface language to override system settings, e.g., <code>&uiLang=fr</code>.  Changes setting for current session (but not saved setting).</td></tr> 
<tr><td style="text-indent: 1em;">calcDecimals</td><td>Specify calculation linkbase validation inferring decimals.</td></tr> 
<tr><td style="text-indent: 1em;">calcPrecision</td><td>Specify calculation linkbase validation inferring precision.</td></tr> 
<tr><td style="text-indent: 1em;">efm</td><td>Select Edgar Filer Manual (U.S. SEC) disclosure system validation. (Alternative to flavor parameter.)</td></tr> 
<tr><td style="text-indent: 1em;">ifrs</td><td>Specify IFRS Global Filer Manual validation.</td></tr>
<tr><td style="text-indent: 1em;">hmrc</td><td>Specify HMRC validation.</td></tr>
<tr><td style="text-indent: 1em;">sbr-nl</td><td>Specify SBR-NL taxonomy validation.</td></tr>
<tr><td style="text-indent: 1em;">utr</td><td>Select validation with respect to Unit Type Registry.</td></tr> 
<tr><td style="text-indent: 1em;">infoset</td><td>Select validation with respect to testcase infoset.</td></tr> 
<tr><td style="text-indent: 1em;">parameters</td><td>Specify parameters for validation or formula (comma separated name=value[,name2=value2]).</td></tr> 
<tr><td style="text-indent: 1em;">formulaAsserResultCounts</td><td>Report formula assertion counts.</td></tr> 
<tr><td style="text-indent: 1em;">formulaVarSetExprResult</td><td>Trace variable set formula value, assertion test results.</td></tr> 
<tr><td style="text-indent: 1em;">formulaVarSetTiming</td><td>Trace variable set execution times.</td></tr> 
<tr><td style="text-indent: 1em;">formulaVarFilterWinnowing</td><td>Trace variable set filter winnowing.</td></tr> 
<tr><td style="text-indent: 1em;">{other}</td><td>Other detailed formula trace parameters:<br/>
formulaParamExprResult, formulaParamInputValue, formulaCallExprSource, formulaCallExprCode, formulaCallExprEval,
formulaCallExprResult, formulaVarSetExprEval, formulaFormulaRules, formulaVarsOrder,
formulaVarExpressionSource, formulaVarExpressionCode, formulaVarExpressionEvaluation, formulaVarExpressionResult, and formulaVarFiltersResult.
</td></tr>
<tr><td style="text-indent: 1em;">abortOnMajorError</td><td>Abort process on major error, such as when load is unable to find an entry or discovered file.</td></tr> 
<tr><td style="text-indent: 1em;">collectProfileStats</td><td>Collect profile statistics, such as timing of validation activities and formulae.</td></tr> 

<tr><th colspan="2">Versioning Report (diff of two DTSes)</th></tr>
<tr><td>/rest/xbrl/diff</td><td>Diff two DTSes, producing an XBRL versioning report relative to report directory.</td></tr>
<tr><td></td><td>Parameters are requred "?" character, and are separated by "&amp;" characters, 
as follows:</td></tr>
<tr><td style="text-indent: 1em;">fromDTS</td><td>File name or url of from DTS.</td></tr> 
<tr><td style="text-indent: 1em;">toDTS</td><td>File name or url of to DTS.</td></tr> 
<tr><td style="text-indent: 1em;">report</td><td>File name or url of to report (to for relative path construction).  The report is not written out, but its contents are returned by the web request to be saved by the requestor.</td></tr> 
<tr><td style="text-align=right;">Example:</td><td><code>/rest/diff?fromDTS=c:/a/prev/old.xsd&amp;toDTS=c:/a/next/new.xsd&amp;report=c:/a/report/report.xml</code>: Diff two DTSes and produce versioning report.</td></tr>

<tr><th colspan="2">Views</th></tr>
<tr><td>/rest/xbrl/{file}/{view}</td><td>View document at {file}.</td></tr>
<tr><td>\u00A0</td><td>{file} may be local or web url, and may have "/" characters replaced by ";" characters (but that is not necessary).</td></tr>
<tr><td>\u00A0</td><td>{view} may be <code>DTS</code>, <code>concepts</code>, <code>pre</code>, <code>cal</code>, <code>dim</code>, <code>facts</code>, <code>factTable</code>, or <code>formulae</code>.</td></tr>
<tr><td style="text-align=right;">Example:</td><td><code>/rest/xbrl/c:/a/b/c.xbrl/dim?media=html</code>: View dimensions of 
document at c:/a/b/c.xbrl (on local drive) and return html result.</td></tr>
<tr><td>/rest/xbrl/view</td><td>(Alternative syntax) View document, file and view are provided as parameters (see below).</td></tr>
<tr><td style="text-align=right;">Example:</td><td><code>/rest/xbrl/view?file=c:/a/b/c.xbrl&amp;view=dim&amp;media=xml</code>: Validate entry instance
document at c:/a/b/c.xbrl (on local drive) and return structured xml results.</td></tr>
<tr><td></td><td>Parameters are optional after "?" character, and are separated by "&amp;" characters, 
as follows:</td></tr>
<tr><td style="text-indent: 1em;">media</td><td><code>html</code> or <code>xhtml</code>: Html text results. (default)
<br/><code>xml</code>: XML structured results.
<br/><code>csv</code>: CSV text results (no markup).
<br/><code>json</code>: JSON text results.</td></tr> 
<tr><td style="text-indent: 1em;">file</td><td>Alternate way to specify file name or url by a parameter.</td></tr> 
<tr><td style="text-indent: 1em;">view</td><td>Alternate way to specify view by a parameter.</td></tr> 
<tr><td style="text-indent: 1em;">import</td><td>A list of files to import to the DTS, such as additional formula 
or label linkbases.  Multiple file names are separated by a '|' character.</td></tr> 
<tr><td style="text-indent: 1em;">factListCols</td><td>A list of column names for facts list.  Multiple names are separated by a space or comma characters.
Example:  <code>factListCols=Label,unitRef,Dec,Value,EntityScheme,EntityIdentifier,Period,Dimensions</code></td></tr> 

<tr><th colspan="2">Excel interface</th></tr>
<tr><td>GUI operation:</td><td>Select data tab.<br/>Click Get External Data From Web.<br/>
New Web Query dialog, enter rest URI to Address (example, for instance with indicated fact columns: 
<code>http://localhost:8080/rest/xbrl/C:/Users/John Doe/Documents/eu/instance.xbrl/facts?media=xhtml&factListCols=Label,unitRef,Dec,Value,EntityScheme,EntityIdentifier,Period,Dimensions</code><br/>
Before clicking Go, click Options, on Options dialog select Full HTML Formatting, then Ok to Options dialog.<br/>
Click Go.<br/>
Click arrow to select table.<br/>
Click Import button.<br/>
Review insertion cell, click ok on Import Data dialog.</td></tr>
<tr><td>VBA macro:</td><td>
<code>With ActiveSheet.QueryTables.Add(Connection:= _<br/>
   "URL;http://localhost:8080/rest/xbrl/C:/Users/John Doe/Documents/eu/instance.xbrl/facts?media=xhtml&factListCols=Label,unitRef,Dec,Value,EntityScheme,EntityIdentifier,Period,Dimensions" _<br/>
   , Destination:=Range("$A$1"))<br/>
   .Name = "facts"<br/>
   .FieldNames = True<br/>
   .RowNumbers = False<br/>
   .FillAdjacentFormulas = False<br/>
   .PreserveFormatting = False<br/>
   .RefreshOnFileOpen = False<br/>
   .BackgroundQuery = True<br/>
   .RefreshStyle = xlInsertDeleteCells<br/>
   .SavePassword = False<br/>
   .SaveData = True<br/>
   .AdjustColumnWidth = True<br/>
   .RefreshPeriod = 0<br/>
   .WebSelectionType = xlAllTables<br/>
   .WebFormatting = xlWebFormattingAll<br/>
   .WebPreFormattedTextToColumns = True<br/>
   .WebConsecutiveDelimitersAsOne = True<br/>
   .WebSingleBlockTextImport = False<br/>
   .WebDisableDateRecognition = False<br/>
   .WebDisableRedirections = False<br/>
   .Refresh BackgroundQuery:=False<br/>
End With</code></td></tr>

<tr><th colspan="2">QuickBooks interface</th></tr>
<tr><td>Setup:</td><td>Install QuickBooks Web Connector by <a href="http://marketplace.intuit.com/webconnector/" target="installWBWC">clicking here</a>.<br/>
Click on QuickBooks.qwc in the Program Files Arelle directory, to install web connector for Arelle.  (It specifies localhost:8080 in it.)<br/>
Open your QuickBooks and desired company<br/>
From start menu, programs, QuickBooks, start Web Connector (QBWC).  Web connector may want a password, use any string, such as "abcd", as it's not checked at this time.<br/>
Start Arelle web server (if it wasn't already running)<br/>
To request xbrl-gl, select report type (generalLedger, journal, or trialBalance) and specify file name for xbrl-gl output instance.<br/>
QBWC polls once a minute, if impatient, in the QBWC window, click its Arelle checkbox and press the update button.<br/>
(If you get the error [8004041A] from Quickbooks, enable the company file for Arelle access in
Quickbooks: Edit->Preferences...->Integrated Applications->Company Preferences->click allow web access for ArelleWebService)<br/>
</td></tr> 
<tr><td style="text-align=right;">Example:</td><td><code>http://localhost:8080/rest/quickbooks/generalLedger/xbrl-gl/C:/mystuff/xbrlGeneralLedger.xbrl/view?fromDate=2011-01-01&toDate=2011-12-31</code> 
(You may omit <code>/view</code>.)</td></tr>
<tr><td></td><td>Parameters follow "?" character, and are separated by "&amp;" characters, 
as follows:</td></tr>
<tr><td style="text-indent: 1em;">media</td><td><code>html</code> or <code>xhtml</code>: Html text results. (default)
<br/><code>xml</code>: XML structured results.
<br/><code>json</code>: JSON results.
<br/><code>text</code>: Plain text results (no markup).</td></tr> 
<tr><td style="text-indent: 1em;">fromDate, toDate</td><td>From &amp to dates for GL transactions</td></tr>

<tr><th colspan="2">Configure settings</th></tr>
<tr><td>/rest/configure</td><td>Configure settings:</td></tr>
<tr><td></td><td>Parameters are required following "?" character, and are separated by "&amp;" characters, 
as follows:</td></tr>
<tr><td style="text-indent: 1em;">proxy</td><td>Show or modify and re-save proxy settings:<br/>
Enter 'show' to view current setting, 'system' to configure to use system proxy setting, 'none' to configure for no proxy, or 'http://[user[:password]@]host[:port]' (e.g., http://192.168.1.253, http://example.com:8080, http://joe:secret@example.com:8080)." ))
</td></tr>
<tr><td style="text-indent: 1em;">plugins</td><td>Show or modify and re-save plug-ins configuration:<br/>
Enter 'show' to view plug-ins configuration, , or '|' separated modules: 
+url to add plug-in by its url or filename, ~name to reload a plug-in by its name, -name to remove a plug-in by its name, 
 (e.g., '+http://arelle.org/files/hello_web.py', '+C:\Program Files\Arelle\examples\plugin\hello_dolly.py' to load,
~Hello Dolly to reload, -Hello Dolly to remove)
</td></tr>
</table>'''))

@route('/about')
def about():
    """About web page for *get* requests to */about*.
    
    :returns: html - About web page
    """
    return htmlBody(_('''<table width="700p">
<tr><th colspan="2">About arelle</th></tr>
<tr><td rowspan="12" style="vertical-align:top;"><img src="/images/arelle32.gif"/></td><td>arelle&reg; version: %s %s. An open source XBRL platform</td></tr>
<tr><td>&copy; 2010-2011 Mark V Systems Limited.  All rights reserved.</td></tr>
<tr><td>Web site: <a href="http://www.arelle.org">http://www.arelle.org</a>.  
E-mail support: <a href="mailto:support@arelle.org">support@arelle.org</a>.</td></tr>
<tr><td>Licensed under the Apache License, Version 2.0 (the \"License\"); you may not use this file 
except in compliance with the License.  You may obtain a copy of the License at
<a href="http://www.apache.org/licenses/LICENSE-2.0">http://www.apache.org/licenses/LICENSE-2.0</a>.
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
</table>''') % (cntlr.__version__, Version.version) )

@route('/')
def indexPage():
    """Index (default) web page for *get* requests to */*.
    
    :returns: html - Web page of choices to navigate to */help* or */about*.
    """
    return htmlBody(_('''<table width="700p">
<tr><th colspan="2">Arelle Web Services</th></tr>
<tr><td>/help</td><td>Help web page, web services API.</td></tr>
<tr><td>/about</td><td>About web page, copyrights, license, included software.</td></tr>
</table>'''))


def htmlBody(body, script=""):
    """Wraps body html string in a css-styled html web page
    
    :param body: Contents for the *<body>* element
    :type body: html str
    :param script: Script to insert in generated html web page (such as a timed reload script)
    :type script: javascript str
    :returns: html - Web page of choices to navigate to */help* or */about*.
    """
    return '''
<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
%s    <head>
        <STYLE type="text/css">
            body, table, p {font-family:Arial,sans-serif;font-size:10pt;}
            table {vertical-align:top;white-space:normal;}
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
''' % (script, body)

def tableRows(lines, header=None):
    """Wraps lines of text into a one-column table (for display of text results of operations, such as processing messages and status, to web browser).
    Replaces any *&* with *&amp;* and *<* with *&lt;*.
    
    :param lines: Sequence (list or tuple) of line strings.
    :type lines: [str]
    :param header: Optional header text for top row of table.
    :type header: str
    :returns: html - <table> html string.
    """
    return '<table cellspacing="0" cellpadding="4">%s\n</table>' % (
            ("<tr><th>%s</th></tr>" % header if header else "") + 
            "\n".join("<tr><td>%s</td></tr>" % line.replace("&","&amp;").replace("<","&lt;") for line in lines))

def errorReport(errors, media="html"):
    """Wraps lines of error text into specified media type for return of result to a request.
    
    :param errors: Sequence (list or tuple) of error strings.
    :type errors: [str]
    :param media: Type of result requestd.
    :type media: str
    :returns: html - <table> html string.
    """
    if media == "text":
        response.content_type = 'text/plain; charset=UTF-8'
        return '\n'.join(errors)
    else:
        response.content_type = 'text/html; charset=UTF-8'
        return htmlBody(tableRows(errors, header=_("Messages")))
