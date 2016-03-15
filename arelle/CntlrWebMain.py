'''
Created on Oct 3, 2010

Use this module to start Arelle in web server mode

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle.webserver.bottle import Bottle, request, response, static_file
from arelle.Cntlr import LogFormatter
import os, io, sys, time, threading, uuid
from arelle import Version
from arelle.FileSource import FileNamedStringIO
_os_pid = os.getpid()

def startWebserver(_cntlr, options):
    """Called once from main program in CmtlrCmdLine to initiate web server on specified local port.
    To test WebServer run from source in IIS, use an entry like this: c:\python33\python.exe c:\\users\\myname\\mySourceFolder\\arelleCmdLine.py %s
       
    :param options: OptionParser options from parse_args of main argv arguments (the argument *webserver* provides hostname and port), port being used to startup the webserver on localhost.
    :type options: optparse.Values
    """
    global imagesDir, cntlr, optionsPrototype
    cntlr = _cntlr
    imagesDir = cntlr.imagesDir
    optionValuesTypes = _STR_NUM_TYPES + (type(None),)
    optionsPrototype = dict((option,value if isinstance(value,_STR_NUM_TYPES) else None)
                            for option in dir(options)
                            for value in (getattr(options, option),)
                            if isinstance(value,optionValuesTypes) and not option.startswith('_'))
    host, sep, portServer = options.webserver.partition(":")
    port, sep, server = portServer.partition(":")
    # start a Bottle application
    app = Bottle()
    
    GETorPOST = ('GET', 'POST')
    GET = 'GET'
    POST = 'POST'

    # install REST API interfaces
    # if necessary to support CGI hosted servers below root, add <prefix:path> as first part of routes
    # and corresponding arguments to the handler methods
    app.route('/rest/login', GET, login_form)
    app.route('/rest/login', POST, login_submit)
    app.route('/rest/logout', GET, logout)
    app.route('/favicon.ico', GET, arelleIcon)
    app.route('/rest/xbrl/<file:path>/open', GETorPOST, validation)
    app.route('/rest/xbrl/<file:path>/close', GETorPOST, validation)
    app.route('/rest/xbrl/<file:path>/validation/xbrl', GETorPOST, validation)
    app.route('/rest/xbrl/<file:path>/DTS', GETorPOST, validation)
    app.route('/rest/xbrl/<file:path>/concepts', GETorPOST, validation)
    app.route('/rest/xbrl/<file:path>/pre', GETorPOST, validation)
    app.route('/rest/xbrl/<file:path>/cal', GETorPOST, validation)
    app.route('/rest/xbrl/<file:path>/dim', GETorPOST, validation)
    app.route('/rest/xbrl/<file:path>/facts', GETorPOST, validation)
    app.route('/rest/xbrl/<file:path>/factTable', GETorPOST, validation)
    app.route('/rest/xbrl/<file:path>/roleTypes', GETorPOST, validation)
    app.route('/rest/xbrl/<file:path>/arcroleTypes', GETorPOST, validation)
    app.route('/rest/xbrl/<file:path>/formulae', GETorPOST, validation)
    app.route('/rest/xbrl/validation', GETorPOST, validation)
    app.route('/rest/xbrl/view', GETorPOST, validation)
    app.route('/rest/xbrl/open', GETorPOST, validation)
    app.route('/rest/xbrl/close', GETorPOST, validation)
    app.route('/images/<imgFile>', GET, image)
    app.route('/rest/xbrl/diff', GET, diff)
    app.route('/rest/configure', GET, configure)
    app.route('/rest/stopWebServer', GET, stopWebServer)
    app.route('/quickbooks/server.asmx', POST, quickbooksServer)
    app.route('/rest/quickbooks/<qbReport>/xbrl-gl/<file:path>', GET, quickbooksGLrequest)
    app.route('/rest/quickbooks/<qbReport>/xbrl-gl/<file:path>/view', GET, quickbooksGLrequest)
    app.route('/rest/quickbooks/<qbReport>/xbrl-gl/view', GET, quickbooksGLrequest)
    app.route('/rest/quickbooks/response', GET, quickbooksGLresponse)
    app.route('/quickbooks/server.html', GET, quickbooksWebPage)
    app.route('/quickbooks/localhost.crt', GET, localhostCertificate)
    app.route('/localhost.crt', GET, localhostCertificate)
    app.route('/help', GET, helpREST)
    app.route('/about', GET, about)
    app.route('/', GET, indexPageREST)
    if server == "cgi":
        # catch a non-REST interface by cgi Interface (may be a cgi app exe module, etc)
        app.route('<cgiAppPath:path>', GETorPOST, cgiInterface)
    if server == "wsgi":
        return app
    elif server == "cgi":
        if sys.stdin is None:
            sys.stdin = open(os.devnull, 'r')
        app.run(server=server)
        sys.exit(0)
    elif server:
        app.run(host=host, port=port or 80, server=server)
    else:
        app.run(host=host, port=port or 80)
        
def cgiInterface(cgiAppPath):
    # route request according to content
    #with open(r"c:\temp\tracecgi.log", "at", encoding="utf-8") as fh:
    #    fh.write("trace 2 arg={}\n".format(cgiAppPath))
    if not request.query:  # no parameters, index page
        return indexPageCGI()
    elif 'about' in request.query:
        return about(cgiAppPath + "?image=arelle32.gif")
    elif 'help' in request.query:
        return helpREST()
    elif 'image' in request.query:
        return image(request.query.image)
    else:
        return indexPageCGI()
            
    
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

def logout():
    """Request to log out (get */rest/logout*).  Removes any proior user ID from session.
    
    :returns: html -- Message that user has logged out
    """
    global user
    user = None
    return _("<p>You are logged out.</p>")

def arelleIcon():
    """Request for icon for URL display (get */favicon.ico*).
    
    :returns: ico -- Icon file for browsers
    """
    return static_file("arelle.ico", root=imagesDir, mimetype='image/vnd.microsoft.icon')

def image(imgFile):
    """Request for an image file for URL display (get */images/<imgFile>*).
    
    :returns: image file -- Requested image file from images directory of application for browsers
    """
    return static_file(imgFile, root=imagesDir)

validationOptions = {
    # these options have no value (after + in query)
    "efm": ("validateEFM", True),
    "efm-pragmatic": ("disclosureSystemName", "efm-pragmatic"),
    "efm-strict": ("disclosureSystemName", "efm-strict"),
    "disclosure-system": ("disclosureSystemName", None),
    "ifrs": ("gfmName", "ifrs"),
    "hmrc": ("gfmName", "hmrc"),
    "sbr-nl": ("gfmName", "sbr-nl"),
    "utr": ("utrValidate", True),
    "infoset": ("infosetValidate", True),
    # these parameters pass through the value after + in query
    "import": ("importFiles", None),
                     }

validationKeyVarName = {
    # these key names store their value in the named var that differs from key name
    "disclosureSystem": "disclosureSystemName",
    "roleTypes": "roleTypesFile",
    "arcroleTypes": "arcroleTypesFile"
    }

class Options():
    """Class to emulate options needed by CntlrCmdLine.run"""
    def __init__(self):
        for option, defaultValue in optionsPrototype.items():
            setattr(self, option, defaultValue)
            
supportedViews = {'DTS', 'concepts', 'pre', 'cal', 'dim', 'facts', 'factTable', 'formulae', 'roleTypes', 'arcroleTypes'}

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
    viewArcrole = request.query.viewArcrole
    if request.method == 'POST':
        mimeType = request.get_header("Content-Type")
        if mimeType.startswith("multipart/form-data"):
            _upload = request.files.get("upload")
            if not _upload or not _upload.filename.endswith(".zip"):
                errors.append(_("POST file upload must be a zip file"))
                sourceZipStream = None
            else:
                sourceZipStream = _upload.file
        elif mimeType not in ('application/zip', 'application/x-zip', 'application/x-zip-compressed', 'multipart/x-zip'):
            errors.append(_("POST must provide a zip file, Content-Type '{0}' not recognized as a zip file.").format(mimeType))
        sourceZipStream = request.body
    else:
        sourceZipStream = None
    if not view and not viewArcrole:
        if requestPathParts[-1] in supportedViews:
            view = requestPathParts[-1]
    if isValidation:
        if view or viewArcrole:
            errors.append(_("Only validation or one view can be specified in one requested."))
        if media not in ('xml', 'xhtml', 'html', 'json', 'text') and not (sourceZipStream and media == 'zip'):
            errors.append(_("Media '{0}' is not supported for validation (please select xhtml, html, xml, json or text)").format(media))
    elif view or viewArcrole:
        if media not in ('xml', 'xhtml', 'html', 'csv', 'json'):
            errors.append(_("Media '{0}' is not supported for view (please select xhtml, html, xml, csv, or json)").format(media))
    elif requestPathParts[-1] not in ("open", "close"):                
        errors.append(_("Neither validation nor view requested, nothing to do."))
    if (flavor not in ('standard', 'standard-except-formula', 'formula-compile-only', 'formula-compile-and-run')
        and not flavor.startswith('edgar') and not flavor.startswith('sec')):
        errors.append(_("Flavor '{0}' is not supported").format(flavor)) 
    if view and view not in supportedViews:
        errors.append(_("View '{0}' is not supported").format(view))
    if errors:
        errors.insert(0, _("URL: ") + (file or request.query.file or '(no file)'))
        return errorReport(errors, media)
    options = Options() # need named parameters to simulate options
    isFormulaOnly = False
    for key, value in request.query.items():
        if key == "file":
            setattr(options, "entrypointFile", value)
        elif key == "flavor":
            if value.startswith("sec") or value.startswith("edgar"):
                setattr(options, "validateEFM", True)
            elif value == "formula-compile-only":
                isFormulaOnly = True
                setattr(options, "formulaAction", "validate")
            elif value == "formula-compile-and-run":
                isFormulaOnly = True
                setattr(options, "formulaAction", "run")
            elif value == "standard-except-formula":
                setattr(options, "formulaAction", "none")
        elif key in("media", "view", "viewArcrole"):
            pass
        elif key in validationOptions:
            optionKey, optionValue = validationOptions[key]
            setattr(options, optionKey, optionValue if optionValue is not None else value)
        elif key in validationKeyVarName:
            setattr(options, validationKeyVarName[key], value or True)
        elif not value: # convert plain str parameter present to True parameter
            setattr(options, key, True)
        else:
            setattr(options, key, value)
    if file:
        setattr(options, "entrypointFile", file.replace(';','/'))
    requestPathParts = set(request.urlparts[2].split('/'))
    viewFile = None
    if isValidation:
        if not isFormulaOnly:
            setattr(options, "validate", True)
    elif view:
        viewFile = FileNamedStringIO(media)
        setattr(options, view + "File", viewFile)
    elif viewArcrole:
        viewFile = FileNamedStringIO(media)
        setattr(options, "viewArcrole", viewArcrole)
        setattr(options, "viewFile", viewFile)
    return runOptionsAndGetResult(options, media, viewFile, sourceZipStream)
    
def runOptionsAndGetResult(options, media, viewFile, sourceZipStream=None):
    """Execute request according to options, for result in media, with *post*ed file in sourceZipStream, if any.
    
    :returns: html, xml, csv, text -- Return per media type argument and request arguments
    """
    if media == "zip" and not viewFile:
        responseZipStream = io.BytesIO()
    else:
        responseZipStream = None
    successful = cntlr.run(options, sourceZipStream, responseZipStream)
    if media == "xml":
        response.content_type = 'text/xml; charset=UTF-8'
    elif media == "csv":
        response.content_type = 'text/csv; charset=UTF-8'
    elif media == "json":
        response.content_type = 'application/json; charset=UTF-8'
    elif media == "text":
        response.content_type = 'text/plain; charset=UTF-8'
    elif media == "zip":
        response.content_type = 'application/zip; charset=UTF-8'
    else:
        response.content_type = 'text/html; charset=UTF-8'
    if successful and viewFile:
        # defeat re-encoding
        result = viewFile.getvalue().replace("&nbsp;","\u00A0").replace("&shy;","\u00AD").replace("&amp;","&")
        viewFile.close()
    elif media == "zip":
        responseZipStream.seek(0)
        result = responseZipStream.read()
        responseZipStream.close()
        cntlr.logHandler.clearLogBuffer() # zip response file may contain non-cleared log entries
    elif media == "xml":
        result = cntlr.logHandler.getXml()
    elif media == "json":
        result = cntlr.logHandler.getJson()
    elif media == "text":
        _logFormat = request.query.logFormat
        if _logFormat:
            _stdLogFormatter = cntlr.logHandler.formatter
            cntlr.logHandler.formatter = LogFormatter(_logFormat)
        result = cntlr.logHandler.getText()
        if _logFormat:
            cntlr.logHandler.formatter = _stdLogFormatter
            del _stdLogFormatter # dereference
    else:
        result = htmlBody(tableRows(cntlr.logHandler.getLines(), header=_("Messages")))
    return result

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

def configure():
    """Set up features for *get* requests to */rest/configure*, e.g., proxy or plug-ins.
    
    :returns: html -- Status of configuration request (e.g., proxy or plug-ins).
    """
    if not request.query.proxy and not request.query.plugins and not request.query.packages and 'environment' not in request.query:
        return _("proxy, plugins, packages or environment must be specified")
    options = Options()
    if request.query.proxy:
        setattr(options, "proxy", request.query.proxy)
    if request.query.plugins:
        setattr(options, "plugins", request.query.plugins)
    if request.query.packages:
        setattr(options, "packages", request.query.packages)
    if 'environment' in request.query:
        setattr(options, "showEnvironment", True)
    cntlr.run(options)
    response.content_type = 'text/html; charset=UTF-8'
    return htmlBody(tableRows(cntlr.logHandler.getLines(), header=_("Configuration Request")))

def stopWebServer():
    """Stop the web server by *get* requests to */rest/stopWebServer*.
    
    """
    def stopSoon(delaySeconds):
        time.sleep(delaySeconds)
        import signal
        os.kill(_os_pid, signal.SIGTERM)
    thread = threading.Thread(target=lambda: stopSoon(2.5))
    thread.daemon = True
    thread.start()
    response.content_type = 'text/html; charset=UTF-8'
    return htmlBody(tableRows((time.strftime("Received at %Y-%m-%d %H:%M:%S"),
                               "Good bye...",), 
                              header=_("Stop Request")))
    
    
def quickbooksServer():
    """Interface to QuickBooks server responding to  *post* requests to */quickbooks/server.asmx*.
    
    (Part of QuickBooks protocol, see module CntlrQuickBooks.)
    """
    from arelle import CntlrQuickBooks
    response.content_type = 'text/xml; charset=UTF-8'
    return CntlrQuickBooks.server(cntlr, request.body, request.urlparts)


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

def quickbooksWebPage():
    return htmlBody(_('''<table width="700p">
<tr><th colspan="2">Arelle QuickBooks Global Ledger Interface</th></tr>
<tr><td>checkbox</td><td>Trial Balance.</td></tr>
<tr><td>close button</td><td>Done</td></tr>
</table>'''))

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
    
def helpREST():
    """Help web page for *get* requests to */help*.
    
    :returns: html - Table of CntlrWebMain web API
    """
    return htmlBody(_('''<table>
<tr><th colspan="2">Arelle web API</th></tr>
<tr><td>/help</td><td>This web page.</td></tr>
<tr><td>/about</td><td>About web page, copyrights, etc.</td></tr>

<tr><th colspan="2">Validation</th></tr>
<tr><td>/rest/xbrl/{file}/validation/xbrl</td><td>Validate document at {file}.</td></tr>
''') +
(_('''
<tr><td>\u00A0</td><td>For an http POST of a zip file (mime type application/zip), {file} is the relative file path inside the zip file.</td></tr>
<tr><td>\u00A0</td><td>For an http GET request, {file} may be a web url, and may have "/" characters replaced by ";" characters 
(but that is not necessary).</td></tr>
<tr><td style="text-align=right;">Example:</td><td><code>/rest/xbrl/c.xbrl/validation/xbrl?media=xml</code>: Validate entry instance
document in the POSTed zip archived file c.xbrl and return structured xml results.</td></tr>
<tr><td>/rest/xbrl/validation</td><td>(Alternative syntax) Validate document, file is provided as a parameter (see below).</td></tr>
<tr><td style="text-align=right;">Example:</td><td><code>/rest/xbrl/validation?file=c.xbrl&amp;media=xml</code>: Validate entry instance
document c.xbrl (in POSTed zip) and return structured xml results.</td></tr>
''')
if cntlr.isGAE else
_('''
<tr><td>\u00A0</td><td>For a browser request or http GET request, {file} may be local or web url, and may have "/" characters replaced by ";" characters 
(but that is not necessary).</td></tr>
<tr><td style="text-align=right;">Example:</td><td><code>/rest/xbrl/c:/a/b/c.xbrl/validation/xbrl?media=xml</code>: Validate entry instance
document at c:/a/b/c.xbrl (on local drive) and return structured xml results.</td></tr>
<tr><td>\u00A0</td><td>For an http POST of a zip file (mime type application/zip), {file} is the relative file path inside the zip file.</td></tr>
<tr><td>/rest/xbrl/validation</td><td>(Alternative syntax) Validate document, file is provided as a parameter (see below).</td></tr>
<tr><td style="text-align=right;">Example:</td><td><code>/rest/xbrl/validation?file=c:/a/b/c.xbrl&amp;media=xml</code>: Validate entry instance
document at c:/a/b/c.xbrl (on local drive) and return structured xml results.</td></tr>
''')) +
_('''
<tr><td></td><td>Parameters are optional after "?" character, and are separated by "&amp;" characters, 
as follows:</td></tr>
<tr><td style="text-indent: 1em;">flavor</td><td><code>standard</code>: XBRL 2.1 and XDT validation.  (If formulas are present they will also be compiled and run.)  (default)
<br/>{<code>sec</code>*|<code>edgar</code>*}: SEC Edgar Filer Manual validation.   (If formulas are present they will also be compiled and run.)
<br/><code>standard-except-formula</code>: XBRL 2.1 and XDT validation.  (If formulas are present they will be ignored.)
<br/><code>formula-compile-only</code>: Formulas will be compiled but not run.  (No XBRL 2.1, XDT, or disclosure system validation.)
<br/><code>formula-compile-and-run</code>: Formulas will be compiled and run.  (No XBRL 2.1, XDT, or disclosure system validation.)</td></tr> 
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
<tr><td style="text-indent: 1em;">efm-*</td><td>Select Edgar Filer Manual (U.S. SEC) disclosure system validation. (Alternative to flavor parameter.):<br/> 
<code>efm-pragmatic</code>: SEC-required rules, currently-allowed years<br/>
<code>efm-strict</code>: SEC-semantic additional rules, currently-allowed years<br/>
<code>efm-pragmatic-all-years</code>: SEC-required rules, all years<br/>
<code>efm-strict-all-years</code>: SEC-semantic additional rules, all years</td></tr>
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
formulaVarExpressionSource, formulaVarExpressionCode, formulaVarExpressionEvaluation, formulaVarExpressionResult, formulaVarFiltersResult, and formulaRunIDs.
</td></tr>
<tr><td style="text-indent: 1em;">abortOnMajorError</td><td>Abort process on major error, such as when load is unable to find an entry or discovered file.</td></tr> 
<tr><td style="text-indent: 1em;">collectProfileStats</td><td>Collect profile statistics, such as timing of validation activities and formulae.</td></tr> 
<tr><td style="text-indent: 1em;">plugins</td><td>Activate plug-ins, specify  '|' separated .py modules (relative to plug-in directory).</td></tr>
<tr><td style="text-indent: 1em;">packages</td><td>Activate taxonomy packages, specify  '|' separated .zip packages (absolute URLs or file paths).</td></tr>

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
<tr><td>\u00A0</td><td>{view} may be <code>DTS</code>, <code>concepts</code>, <code>pre</code>, <code>cal</code>, <code>dim</code>, <code>facts</code>, <code>factTable</code>, <code>formulae</code>, <code>roleTypes</code>, or <code>arcroleTypes</code>.</td></tr>
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
<tr><td style="text-indent: 1em;">viewArcrole</td><td>Alternate way to specify view by indicating arcrole desired.</td></tr> 
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

<tr><th colspan="2">Management</th></tr>
<tr><td>/rest/configure</td><td>Configure settings:</td></tr>
<tr><td></td><td>Parameters are required following "?" character, and are separated by "&amp;" characters, 
as follows:</td></tr>
<tr><td style="text-indent: 1em;">proxy</td><td>Show or modify and re-save proxy settings:<br/>
Enter 'show' to view current setting, 'system' to configure to use system proxy setting, 'none' to configure for no proxy, or 'http://[user[:password]@]host[:port]' (e.g., http://192.168.1.253, http://example.com:8080, http://joe:secret@example.com:8080)." ))
</td></tr>
<tr><td style="text-indent: 1em;">plugins</td><td>Show or modify and re-save plug-ins configuration:<br/>
Enter 'show' to view plug-ins configuration, , or '|' separated modules: 
+url to add plug-in by its url or filename (relative to plug-in directory else absolute), ~name to reload a plug-in by its name, -name to remove a plug-in by its name, 
 (e.g., '+http://arelle.org/files/hello_web.py', '+C:\Program Files\Arelle\examples\plugin\hello_dolly.py' to load,
~Hello Dolly to reload, -Hello Dolly to remove).  (Note that plug-ins are transient on Google App Engine, specify with &amp;plugins to other rest commands.) 
</td></tr>
<tr><td style="text-indent: 1em;">packages</td><td>Show or modify and re-save taxonomy packages configuration:<br/>
Enter 'show' to view packages configuration, , or '|' separated package URLs: 
+url to add package by its full url or filename, ~name to reload a package by its name, -name to remove a package by its name. 
(Note that packages are transient on Google App Engine, specify with &amp;packages to other rest commands.) 
</td></tr>
<tr><td style="text-indent: 1em;">environment</td><td>Show host environment (config and cache directories).</td></tr>
''') +
(_('''
<tr><td>/rest/stopWebServer</td><td>Shut down (terminate process after 2.5 seconds delay).</td></tr>
''') if cntlr.isGAE else '') +
'</table>')

def about(arelleImgFile=None):
    from lxml import etree
    """About web page for *get* requests to */about*.
    
    :returns: html - About web page
    """
    return htmlBody(_('''<table width="700p">
<tr><th colspan="2">About arelle</th></tr>
<tr><td rowspan="12" style="vertical-align:top;"><img src="%s"/></td><td>arelle&reg; version: %s %sbit %s. An open source XBRL platform</td></tr>
<tr><td>&copy; 2010-2015 Mark V Systems Limited.  All rights reserved.</td></tr>
<tr><td>Web site: <a href="http://www.arelle.org">http://www.arelle.org</a>.  
E-mail support: <a href="mailto:support@arelle.org">support@arelle.org</a>.</td></tr>
<tr><td>Licensed under the Apache License, Version 2.0 (the \"License\"); you may not use this file 
except in compliance with the License.  You may obtain a copy of the License at
<a href="http://www.apache.org/licenses/LICENSE-2.0">http://www.apache.org/licenses/LICENSE-2.0</a>.
Unless required by applicable law or agreed to in writing, software distributed under the License 
is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  
See the License for the specific language governing permissions and limitations under the License.</td></tr>
<tr><td>Includes:</td><tr>
<tr><td style="text-indent: 2.0em;">Python&reg; %s.%s.%s &copy; 2001-2010 Python Software Foundation</td></tr>
<tr><td style="text-indent: 2.0em;">PyParsing &copy; 2003-2010 Paul T. McGuire</td></tr>
<tr><td style="text-indent: 2.0em;">lxml %s.%s.%s &copy; 2004 Infrae, ElementTree &copy; 1999-2004 by Fredrik Lundh</td></tr>
<tr><td style="text-indent: 2.0em;">Bottle &copy; 2011 Marcel Hellkamp</td></tr>
</table>''') % (arelleImgFile or '/images/arelle32.gif',
                cntlr.__version__, 
                cntlr.systemWordSize, 
                Version.version,
                sys.version_info[0],sys.version_info[1],sys.version_info[2], 
                etree.LXML_VERSION[0],etree.LXML_VERSION[1],etree.LXML_VERSION[2]) )

def indexPageREST():
    """Index (default) web page for *get* requests to */*.
    
    :returns: html - Web page of choices to navigate to */help* or */about*.
    """
    return htmlBody(_('''<table width="700p">
<tr><th colspan="2">Arelle Web Services</th></tr>
<tr><td>/help</td><td>Help web page, web services API.</td></tr>
<tr><td>/about</td><td>About web page, copyrights, license, included software.</td></tr>
</table>'''))

def indexPageCGI():
    """Default web page response for *get* CGI request with no parameters.
    
    :returns: html - Web page of choices to navigate to *?help* or *?about*.
    """
    return htmlBody(_('''<table width="700p">
<tr><th colspan="2">Arelle CGI Services</th></tr>
<tr><td>?help</td><td>Help web page, CGI services.</td></tr>
<tr><td>?about</td><td>About web page, copyrights, license, included software.</td></tr>
<tr><td>REST API</td><td>The Arelle REST API is supported through CGI if the entire CGI path is wildcard-mapped to the arelleCmdLine executable.</td></tr>
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
    
def multipartResponse(parts):
    # call with ( (filename, contentType, content), ...)
    boundary='----multipart-boundary-%s----' % (uuid.uuid1(),)
    response.content_type = 'multipart/mixed; boundary=%s' % (boundary,)
    buf = []
    
    for filename, contentType, content in parts:
        buf.append("\r\n" + boundary + "\r\n")
        buf.append('Content-Disposition: attachment; filename="{0}";\r\n'.format(filename))
        buf.append('Content-Type: {0};\r\n'.format(contentType))
        buf.append('Content-Length: {0}\r\n'.format(len(content)))
        buf.append('\r\n')
        buf.append(content)
    buf.append("\r\n" + boundary + "\r\n")
    s = ''.join(buf)
    response.content_length = len(s)
    return s
