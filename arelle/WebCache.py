'''
See COPYRIGHT.md for copyright information.

For SEC EDGAR data access see: https://www.sec.gov/os/accessing-edgar-data
e.g., User-Agent: Sample Company Name AdminContact@<sample company domain>.com

'''
from __future__ import annotations
from typing import TYPE_CHECKING
import os, posixpath, sys, re, time, calendar, io, json, logging, shutil, zlib
from urllib.parse import quote, unquote
from urllib.error import URLError, HTTPError, ContentTooShortError
from http.client import IncompleteRead
from urllib import request as proxyhandlers

import certifi

try:
    import ssl
except ImportError:
    ssl = None
from arelle.FileSource import SERVER_WEB_CACHE, archiveFilenameParts
from arelle.PluginManager import pluginClassMethods
from arelle.UrlUtil import isHttpUrl
from arelle.Version import __version__

if TYPE_CHECKING:
    from arelle.Cntlr import Cntlr

addServerWebCache = None

DIRECTORY_INDEX_FILE = "!~DirectoryIndex~!"
INF = float("inf")
RETRIEVAL_RETRY_COUNT = 5
HTTP_USER_AGENT = 'Mozilla/5.0 (Arelle/{})'.format(__version__)

def proxyDirFmt(httpProxyTuple):
    if isinstance(httpProxyTuple,(tuple,list)) and len(httpProxyTuple) == 5:
        useOsProxy, urlAddr, urlPort, user, password = httpProxyTuple
        if useOsProxy:
            return None
        elif urlAddr:
            if user and password:
                userPart = "{0}:{1}@".format(user, password)
            else:
                userPart = ""
            if urlPort:
                portPart = ":{0}".format(urlPort)
            else:
                portPart = ""
            return {"http": "http://{0}{1}{2}".format(userPart, urlAddr, portPart) }
            #return {"http": "{0}{1}{2}".format(userPart, urlAddr, portPart) }
        else:
            return {}  # block use of any proxy
    else:
        return None # use system proxy

def proxyTuple(url): # system, none, or http:[user[:passowrd]@]host[:port]
    if url == "none":
        return (False, "", "", "", "")
    elif url == "system":
        return (True, "", "", "", "")
    userpwd, sep, hostport = url.rpartition("://")[2].rpartition("@")
    urlAddr, sep, urlPort = hostport.partition(":")
    user, sep, password = userpwd.partition(":")
    return (False, urlAddr, urlPort, user, password)

def lastModifiedTime(headers):
    if headers:
        headerTimeStamp = headers["last-modified"]
        if headerTimeStamp:
            from email.utils import parsedate
            hdrTime = parsedate(headerTimeStamp)
            if hdrTime:
                return time.mktime(hdrTime)
    return None


class WebCache:

    default_timeout = None

    def __init__(
        self, cntlr: Cntlr,
        httpProxyTuple: tuple[bool, str, str, str, str] | None
    ) -> None:

        self.cntlr = cntlr
        #self.proxies = request.getproxies()
        #self.proxies = {'ftp': 'ftp://63.192.17.1:3128', 'http': 'http://63.192.17.1:3128', 'https': 'https://63.192.17.1:3128'}
        self._timeout = None

        self._noCertificateCheck = False
        self._httpUserAgent = HTTP_USER_AGENT # default user agent for product
        self._httpsRedirect = False
        self.resetProxies(httpProxyTuple)

        self.opener.addheaders = [('User-agent', self.httpUserAgent)]

        #self.opener = WebCacheUrlOpener(cntlr, proxyDirFmt(httpProxyTuple)) # self.proxies)

        if cntlr.isGAE:
            self.cacheDir = SERVER_WEB_CACHE # GAE type servers
            self.encodeFileChars = re.compile(r'[:^]')
        elif sys.platform == "darwin" and "/Application Support/" in cntlr.userAppDir:
            self.cacheDir = cntlr.userAppDir.replace("Application Support","Caches")
            self.encodeFileChars = re.compile(r'[:^]')

        else:  #windows and unix
            self.cacheDir = cntlr.userAppDir + os.sep + "cache"
            if sys.platform.startswith("win"):
                self.encodeFileChars = re.compile(r'[<>:"\\|?*^]')
            else:
                self.encodeFileChars = re.compile(r'[:^]')
        self.decodeFileChars = re.compile(r'\^[0-9]{3}')
        self.workOffline: bool = False
        self._logDownloads = False
        self.maxAgeSeconds = 60.0 * 60.0 * 24.0 * 7.0 # seconds before checking again for file
        if cntlr.hasFileSystem:
            self.urlCheckJsonFile = cntlr.userAppDir + os.sep + "cachedUrlCheckTimes.json"
            try:
                with io.open(self.urlCheckJsonFile, 'rt', encoding='utf-8') as f:
                    self.cachedUrlCheckTimes = json.load(f)
            except Exception:
                self.cachedUrlCheckTimes = {}
        else:
            self.cachedUrlCheckTimes = {}
        self.cachedUrlCheckTimesModified = False

    @property
    def timeout(self):
        return self._timeout or WebCache.default_timeout

    @timeout.setter
    def timeout(self, seconds):
        self._timeout = seconds

    @property
    def recheck(self):
        days = self.maxAgeSeconds / (60.0 * 60.0 * 24.0)
        if days == INF:
            return "never"
        elif days >= 30:
            return "monthly"
        elif days >= 7:
            return "weekly"
        elif days >=1:
            return "daily"
        elif self.maxAgeSeconds >= 3600.0:
            return "hourly"
        elif self.maxAgeSeconds >= 900.0: # 15 minutes. just intended for testing
            return "quarter-hourly"
        else:
            return "(invalid)"

    @recheck.setter
    def recheck(self, recheckInterval):
        self.maxAgeSeconds = {"daily": 1.0, "weekly": 7.0, "monthly": 30.0, "never": INF,
                              "hourly": 1.0/24.0, "quarter-hourly": 1.0/96.0 # lower numbers for testing purposes
                              }.get(recheckInterval, 7.0) * (60.0 * 60.0 * 24.0)

    @property
    def logDownloads(self):
        return self._logDownloads

    @logDownloads.setter
    def logDownloads(self, _logDownloads):
        self._logDownloads = _logDownloads

    def saveUrlCheckTimes(self) -> None:
        if self.cachedUrlCheckTimesModified:
            with io.open(self.urlCheckJsonFile, 'wt', encoding='utf-8') as f:
                f.write(json.dumps(self.cachedUrlCheckTimes, ensure_ascii=False, indent=0))
        self.cachedUrlCheckTimesModified = False

    @property
    def noCertificateCheck(self):
        return self._noCertificateCheck

    @noCertificateCheck.setter
    def noCertificateCheck(self, check):
        priorValue = self._noCertificateCheck
        self._noCertificateCheck = check
        if priorValue != check:
            self.resetProxies(self._httpProxyTuple)

    @property
    def httpUserAgent(self):
        return self._httpUserAgent

    @httpUserAgent.setter
    def httpUserAgent(self, userAgent):
        if not userAgent: # None or blank sets to default
            userAgent = HTTP_USER_AGENT
        priorValue = self._httpUserAgent
        self._httpUserAgent = userAgent
        if priorValue != userAgent:
            self.resetProxies(self._httpProxyTuple)

    @property
    def httpsRedirect(self):
        return self._httpsRedirect

    @httpsRedirect.setter
    def httpsRedirect(self, value):
        self._httpsRedirect = value

    def resetProxies(self, httpProxyTuple):
        # for ntlm user and password are required
        self.hasNTLM = False
        self._httpProxyTuple = httpProxyTuple # save for resetting in noCertificateCheck setter
        if isinstance(httpProxyTuple,(tuple,list)) and len(httpProxyTuple) == 5:
            useOsProxy, _urlAddr, _urlPort, user, password = httpProxyTuple
            _proxyDirFmt = proxyDirFmt(httpProxyTuple)
            # only try ntlm if user and password are provided because passman is needed
            if user and not useOsProxy:
                for pluginXbrlMethod in pluginClassMethods("Proxy.HTTPAuthenticate"):
                    pluginXbrlMethod(self.cntlr)
                for pluginXbrlMethod in pluginClassMethods("Proxy.HTTPNtlmAuthHandler"):
                    HTTPNtlmAuthHandler = pluginXbrlMethod()
                    if HTTPNtlmAuthHandler is not None:
                        self.hasNTLM = True
                if not self.hasNTLM: # try for python site-packages ntlm
                    try:
                        from ntlm import HTTPNtlmAuthHandler
                        self.hasNTLM = True
                    except ImportError:
                        pass
            if self.hasNTLM:
                pwrdmgr = proxyhandlers.HTTPPasswordMgrWithDefaultRealm()
                pwrdmgr.add_password(None, _proxyDirFmt["http"], user, password)
                self.proxy_handler = proxyhandlers.ProxyHandler({})
                self.proxy_auth_handler = proxyhandlers.ProxyBasicAuthHandler(pwrdmgr)
                self.http_auth_handler = proxyhandlers.HTTPBasicAuthHandler(pwrdmgr)
                self.ntlm_auth_handler = HTTPNtlmAuthHandler.HTTPNtlmAuthHandler(pwrdmgr)
                proxyHandlers = [self.proxy_handler, self.ntlm_auth_handler, self.proxy_auth_handler, self.http_auth_handler]
        if not self.hasNTLM:
            self.proxy_handler = proxyhandlers.ProxyHandler(proxyDirFmt(httpProxyTuple))
            self.proxy_auth_handler = proxyhandlers.ProxyBasicAuthHandler()
            self.http_auth_handler = proxyhandlers.HTTPBasicAuthHandler()
            proxyHandlers = [self.proxy_handler, self.proxy_auth_handler, self.http_auth_handler]
        if ssl:
            # Attempts to load the default CA certificates from the OS.
            context = ssl.create_default_context()
            # Include certifi certificates (Mozilla’s carefully curated
            # collection) for systems with outdated certs and for platforms
            # that we're unable to load certs from (macOS and some Linux
            # distros.)
            context.load_verify_locations(cafile=certifi.where())
            if self.noCertificateCheck:  # this is required in some Akamai environments, such as sec.gov
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            proxyHandlers.append(proxyhandlers.HTTPSHandler(context=context))
        self.opener = proxyhandlers.build_opener(*proxyHandlers)
        self.opener.addheaders = [
            ('User-Agent', self.httpUserAgent),
            ('Accept-Encoding', 'gzip, deflate')
            ]

        #self.opener.close()
        #self.opener = WebCacheUrlOpener(self.cntlr, proxyDirFmt(httpProxyTuple))


    def normalizeUrl(self, url, base=None):
        if url:
            if url.startswith("file://"): url = url[7:]
            elif url.startswith("file:\\"): url = url[6:]
        if url and not (isHttpUrl(url) or os.path.isabs(url)):
            if base is not None and not isHttpUrl(base) and '%' in url:
                url = unquote(url)
            if base:
                if isHttpUrl(base):
                    scheme, sep, path = base.partition("://")
                    normedPath = scheme + sep + posixpath.normpath(os.path.dirname(path) + "/" + url)
                else:
                    if '%' in base:
                        base = unquote(base)
                    normedPath = os.path.normpath(os.path.join(os.path.dirname(base),url))
            else: # includes base == '' (for forcing relative path)
                normedPath = url
            if normedPath.startswith("file://"): normedPath = normedPath[7:]
            elif normedPath.startswith("file:\\"): normedPath = normedPath[6:]

            # no base, not normalized, must be relative to current working directory
            if base is None and not os.path.isabs(url):
                normedPath = os.path.abspath(normedPath)
        else:
            normedPath = url

        if normedPath:
            if isHttpUrl(normedPath):
                scheme, sep, pathpart = normedPath.partition("://")
                pathpart = pathpart.replace('\\','/')
                endingSep = '/' if pathpart[-1] == '/' else ''  # normpath drops ending directory separator
                return scheme + "://" + posixpath.normpath(pathpart) + endingSep
            normedPath = os.path.normpath(normedPath)
            if normedPath.startswith(self.cacheDir):
                normedPath = self.cacheFilepathToUrl(normedPath)
        return normedPath

    def encodeForFilename(self, pathpart):
        return self.encodeFileChars.sub(lambda m: '^{0:03}'.format(ord(m.group(0))), pathpart)

    def urlToCacheFilepath(self, url):
        scheme, sep, path = url.partition("://")
        filepath = [self.cacheDir, scheme]
        pathparts = path.split('/')
        user, sep, server = pathparts[0].partition("@")
        if not sep:
            server = user
            user = None
        host, sep, port = server.partition(':')
        filepath.append(self.encodeForFilename(host))
        if port:
            filepath.append("^port" + port)
        if user:
            filepath.append("^user" + self.encodeForFilename(user) ) # user may have : or other illegal chars
        filepath.extend(self.encodeForFilename(pathpart) for pathpart in pathparts[1:])
        if url.endswith("/"):  # default index file
            filepath.append(DIRECTORY_INDEX_FILE)
        return os.sep.join(filepath)

    def cacheFilepathToUrl(self, cacheFilepath):
        urlparts = cacheFilepath[len(self.cacheDir)+1:].split(os.sep)
        urlparts[0] += ':/'  # add separator between http and file parts, less one '/'
        if len(urlparts) > 2:
            if urlparts[2].startswith("^port"):
                urlparts[1] += ":" + urlparts[2][5:]  # the port number
                del urlparts[2]
            if urlparts[2].startswith("^user"):
                urlparts[1] = urlparts[2][5:] + "@" + urlparts[1]  # the user part
                del urlparts[2]
        if urlparts[-1] == DIRECTORY_INDEX_FILE:
            urlparts[-1] = ""  # restore default index file syntax
        return '/'.join(self.decodeFileChars  # remove cacheDir part
                        .sub(lambda c: chr( int(c.group(0)[1:]) ), # remove ^nnn encoding
                         urlpart) for urlpart in urlparts)

    def getfilename(
            self, url: str | None, base: str | None = None,
            reload: bool = False, checkModifiedTime: bool = False,
            normalize: bool = False, filenameOnly: bool = False) -> str | None:
        if url is None:
            return url
        if base is not None or normalize:
            url = self.normalizeUrl(url, base)
        urlScheme, schemeSep, urlSchemeSpecificPart = url.partition("://")
        if schemeSep and urlScheme in ("http", "https"):
            # is this a mapped archive file contents?
            _archiveFileNameParts = archiveFilenameParts(url)
            if _archiveFileNameParts:
                _archiveFilename = self.getfilename(_archiveFileNameParts[0], reload=reload, checkModifiedTime=checkModifiedTime)
                if _archiveFilename:
                    return os.path.join(_archiveFilename, _archiveFileNameParts[1])
                return None
            # form cache file name (substituting _ for any illegal file characters)
            filepath = self.urlToCacheFilepath(url)
            if self.httpsRedirect:
                if not os.path.exists(filepath):
                    # if enabled, check for missing files in their inverse http/https cache directory
                    redirect = None
                    if url.startswith('http://'):
                        redirect = self.urlToCacheFilepath('https' + url[4:])
                    elif url.startswith('https://'):
                        redirect = self.urlToCacheFilepath('http' + url[5:])
                    if redirect and os.path.exists(redirect):
                        filepath = redirect
            if self.cacheDir == SERVER_WEB_CACHE:
                # server web-cached files are downloaded when opening to prevent excessive memcache api calls
                return filepath
            # quotedUrl has scheme-specific-part quoted except for parameter separators
            quotedUrl = urlScheme + schemeSep + quote(urlSchemeSpecificPart, '/?=&')
            # handle default directory requests
            if filepath.endswith("/"):
                filepath += DIRECTORY_INDEX_FILE
            if os.sep == '\\':
                filepath = filepath.replace('/', '\\')
            if self.workOffline or filenameOnly:
                return filepath
            filepathtmp = filepath + ".tmp"
            fileExt = os.path.splitext(filepath)[1]
            timeNow = time.time()
            timeNowStr = time.strftime('%Y-%m-%dT%H:%M:%S UTC', time.gmtime(timeNow))
            retrievingDueToRecheckInterval = False
            if not reload and os.path.exists(filepath):
                if url in self.cachedUrlCheckTimes and not checkModifiedTime:
                    cachedTime = calendar.timegm(time.strptime(self.cachedUrlCheckTimes[url], '%Y-%m-%dT%H:%M:%S UTC'))
                else:
                    cachedTime = 0
                if timeNow - cachedTime > self.maxAgeSeconds:
                    # weekly check if newer file exists
                    newerOnWeb = False
                    try: # no provision here for proxy authentication!!!
                        remoteFileTime = lastModifiedTime( self.getheaders(quotedUrl) )
                        if remoteFileTime and remoteFileTime > os.path.getmtime(filepath):
                            newerOnWeb = True
                    except:
                        pass # for now, forget about authentication here
                    if not newerOnWeb:
                        # update ctime by copying file and return old file
                        self.cachedUrlCheckTimes[url] = timeNowStr
                        self.cachedUrlCheckTimesModified = True
                        return filepath
                    retrievingDueToRecheckInterval = True
                else:
                    return filepath
            filedir = os.path.dirname(filepath)
            if not os.path.exists(filedir):
                os.makedirs(filedir)
            # Retrieve over HTTP and cache, using rename to avoid collisions
            # self.modelManager.addToLog('web caching: {0}'.format(url))

            # download to a temporary name so it is not left readable corrupted if download fails
            retryCount = 5
            while retryCount > 0:
                try:
                    self.progressUrl = url
                    savedfile, headers, initialBytes = self.retrieve(
                    #savedfile, headers = self.opener.retrieve(
                                      quotedUrl,
                                      filename=filepathtmp,
                                      reporthook=self.reportProgress)

                    # check if this is a real file or a wifi or web logon screen
                    if fileExt in {".xsd", ".xml", ".xbrl"}:
                        if b"<html" in initialBytes:
                            if retrievingDueToRecheckInterval:
                                return self.internetRecheckFailedRecovery(filepath, url,
                                                                          "file contents appear to be an html logon request",
                                                                          timeNowStr)
                            response = None  # found possible logon request
                            if self.cntlr.hasGui:
                                response = self.cntlr.internet_logon(url, quotedUrl,
                                                                     _("Unexpected HTML in {0}").format(url),
                                                                     _("Is this a logon page? If so, click 'yes', else click 'no' if it is the expected XBRL content, or 'cancel' to abort retrieval: \n\n{0}")
                                                                     .format(initialBytes[:1500]))
                            if response == "retry":
                                retryCount -= 1
                                continue
                            elif response != "no":
                                self.cntlr.addToLog(_("Web file appears to be an html logon request, not retrieved: %(URL)s \nContents: \n%(contents)s"),
                                                    messageCode="webCache:invalidRetrieval",
                                                    messageArgs={"URL": url, "contents": initialBytes},
                                                    level=logging.ERROR)
                                return None

                    retryCount = 0
                except (ContentTooShortError, IncompleteRead) as err:
                    if retrievingDueToRecheckInterval:
                        return self.internetRecheckFailedRecovery(filepath, url, err, timeNowStr)
                    if retryCount > 1:
                        self.cntlr.addToLog(_("%(error)s \nunsuccessful retrieval of %(URL)s \n%(retryCount)s retries remaining"),
                                            messageCode="webCache:retryingOperation",
                                            messageArgs={"error": err, "URL": url, "retryCount": retryCount},
                                            level=logging.ERROR)
                        retryCount -= 1
                        continue
                    self.cntlr.addToLog(_("%(error)s \nretrieving %(URL)s"),
                                        messageCode="webCache:contentTooShortError",
                                        messageArgs={"URL": url, "error": err},
                                        level=logging.ERROR)
                    if os.path.exists(filepathtmp):
                        os.remove(filepathtmp)
                    return None
                    # handle file is bad
                except (HTTPError, URLError) as err:
                    try:
                        tryWebAuthentication = False
                        if isinstance(err, HTTPError) and err.code == 401:
                            tryWebAuthentication = True
                            if 'www-authenticate' in err.hdrs:
                                match = re.match('[ \t]*([^ \t]+)[ \t]+realm="([^"]*)"', err.hdrs['www-authenticate'])
                                if match:
                                    scheme, realm = match.groups()
                                    if scheme.lower() == 'basic':
                                        host = os.path.dirname(quotedUrl)
                                        userPwd = self.cntlr.internet_user_password(host, realm)
                                        if isinstance(userPwd,(tuple,list)):
                                            self.http_auth_handler.add_password(realm=realm,uri=host,user=userPwd[0],passwd=userPwd[1])
                                            retryCount -= 1
                                            continue
                                    self.cntlr.addToLog(_("'%(scheme)s' www-authentication for realm '%(realm)s' is required to access %(URL)s\n%(error)s"),
                                                        messageCode="webCache:unsupportedWWWAuthentication",
                                                        messageArgs={"scheme": scheme, "realm": realm, "URL": url, "error": err},
                                                        level=logging.ERROR)
                        elif isinstance(err, HTTPError) and err.code == 407:
                            tryWebAuthentication = True
                            if 'proxy-authenticate' in err.hdrs:
                                match = re.match('[ \t]*([^ \t]+)[ \t]+realm="([^"]*)"', err.hdrs['proxy-authenticate'])
                                if match:
                                    scheme, realm = match.groups()
                                    host = self.proxy_handler.proxies.get('http')
                                    if scheme.lower() == 'basic':
                                        userPwd = self.cntlr.internet_user_password(host, realm)
                                        if isinstance(userPwd,(tuple,list)):
                                            self.proxy_auth_handler.add_password(realm=realm,uri=host,user=userPwd[0],passwd=userPwd[1])
                                            retryCount -= 1
                                            continue
                                    self.cntlr.addToLog(_("'%(scheme)s' proxy-authentication for realm '%(realm)s' is required to access %(URL)s\n%(error)s"),
                                                        messageCode="webCache:unsupportedProxyAuthentication",
                                                        messageArgs={"scheme": scheme, "realm": realm, "URL": url, "error": err},
                                                        level=logging.ERROR)
                        if retrievingDueToRecheckInterval:
                            return self.internetRecheckFailedRecovery(filepath, url, err, timeNowStr)
                        if tryWebAuthentication:
                            # check if single signon is requested (on first retry)
                            if retryCount == RETRIEVAL_RETRY_COUNT:
                                for pluginXbrlMethod in pluginClassMethods("Proxy.HTTPAuthenticate"):
                                    if pluginXbrlMethod(self.cntlr): # true if succeessful single sign on
                                        retryCount -= 1
                                        break
                                if retryCount < RETRIEVAL_RETRY_COUNT:
                                    continue # succeeded
                            # may be a web login authentication request
                            response = None  # found possible logon request
                            if self.cntlr.hasGui:
                                response = self.cntlr.internet_logon(url, quotedUrl,
                                                                     _("HTTP {0} authentication request").format(err.code),
                                                                     _("Is browser-based internet access authentication possible? If so, click 'yes', or 'cancel' to abort retrieval: \n\n{0}")
                                                                     .format(url))
                            if response == "retry":
                                retryCount -= 1
                                continue
                            elif response != "no":
                                self.cntlr.addToLog(_("Web file HTTP 401 (authentication required) response, not retrieved: %(URL)s"),
                                                    messageCode="webCache:authenticationRequired",
                                                    messageArgs={"URL": url},
                                                    level=logging.ERROR)
                                return None

                    except AttributeError:
                        pass
                    if retrievingDueToRecheckInterval:
                        return self.internetRecheckFailedRecovery(filepath, url, err, timeNowStr)
                    self.cntlr.addToLog(_("%(error)s \nretrieving %(URL)s"),
                                        messageCode="webCache:retrievalError",
                                        messageArgs={"error": err.reason if hasattr(err, "reason") else err,
                                                     "URL": url},
                                        level=logging.ERROR)
                    return None

                except Exception as err:
                    if retryCount > 1:
                        self.cntlr.addToLog(_("%(error)s \nunsuccessful retrieval of %(URL)s \n%(retryCount)s retries remaining"),
                                            messageCode="webCache:retryingOperation",
                                            messageArgs={"error": err, "URL": url, "retryCount": retryCount},
                                            level=logging.ERROR)
                        retryCount -= 1
                        continue
                    if retrievingDueToRecheckInterval:
                        return self.internetRecheckFailedRecovery(filepath, url, err, timeNowStr)
                    if self.cntlr.hasGui:
                        self.cntlr.addToLog(_("%(error)s \nunsuccessful retrieval of %(URL)s \nswitching to work offline"),
                                            messageCode="webCache:attemptingOfflineOperation",
                                            messageArgs={"error": err, "URL": url},
                                            level=logging.ERROR)
                        # try working offline
                        self.workOffline = True
                        return filepath
                    else:  # don't switch offline unexpectedly in scripted (batch) operation
                        self.cntlr.addToLog(_("%(error)s \nunsuccessful retrieval of %(URL)s"),
                                            messageCode="webCache:unsuccessfulRetrieval",
                                            messageArgs={"error": err, "URL": url},
                                            level=logging.ERROR)
                        if os.path.exists(filepathtmp):
                            os.remove(filepathtmp)
                        return None

                # rename temporarily named downloaded file to desired name
                if os.path.exists(filepath):
                    try:
                        if os.path.isfile(filepath) or os.path.islink(filepath):
                            os.remove(filepath)
                        elif os.path.isdir(filepath):
                            shutil.rmtree(filepath)
                    except Exception as err:
                        self.cntlr.addToLog(_("%(error)s \nUnsuccessful removal of prior file %(filepath)s \nPlease remove with file manager."),
                                            messageCode="webCache:cachedPriorFileLocked",
                                            messageArgs={"error": err, "filepath": filepath},
                                            level=logging.ERROR)
                try:
                    os.rename(filepathtmp, filepath)
                    if self._logDownloads:
                        self.cntlr.addToLog(_("Downloaded %(URL)s"),
                                            messageCode="webCache:download",
                                            messageArgs={"URL": url, "filepath": filepath},
                                            level=logging.INFO)
                except Exception as err:
                    self.cntlr.addToLog(_("%(error)s \nUnsuccessful renaming of downloaded file to active file %(filepath)s \nPlease remove with file manager."),
                                        messageCode="webCache:cacheDownloadRenamingError",
                                        messageArgs={"error": err, "filepath": filepath},
                                        level=logging.ERROR)
                webFileTime = lastModifiedTime(headers)
                if webFileTime: # set mtime to web mtime
                    os.utime(filepath,(webFileTime,webFileTime))
                self.cachedUrlCheckTimes[url] = timeNowStr
                self.cachedUrlCheckTimesModified = True
                return filepath

        if url.startswith("file://"): url = url[7:]
        elif url.startswith("file:\\"): url = url[6:]
        if os.sep == '\\':
            url = url.replace('/', '\\')
        return url

    def internetRecheckFailedRecovery(self, filepath, url, err, timeNowStr):
        self.cntlr.addToLog(_("During refresh of web file ignoring error: %(error)s for %(URL)s"),
                            messageCode="webCache:unableToRefreshFile",
                            messageArgs={"URL": url, "error": err},
                            level=logging.INFO)
        # skip this checking cycle, act as if retrieval was ok
        self.cachedUrlCheckTimes[url] = timeNowStr
        self.cachedUrlCheckTimesModified = True
        return filepath

    def reportProgress(self, blockCount, blockSize, totalSize):
        if totalSize > 0:
            self.cntlr.showStatus(_("web caching {0}: {1:.0f} of {2:.0f} KB").format(
                    self.progressUrl,
                    blockCount * blockSize / 1024,
                    totalSize / 1024))
        else:
            self.cntlr.showStatus(_("web caching {0}: {1:.0f} KB").format(
                    self.progressUrl,
                    blockCount * blockSize / 1024))

    def clear(self):
        for cachedProtocol in ("http", "https"):
            cachedProtocolDir = os.path.join(self.cacheDir, cachedProtocol)
            if os.path.exists(cachedProtocolDir):
                shutil.rmtree(cachedProtocolDir, True)

    def getheaders(self, url):
        if url and isHttpUrl(url):
            try:
                fp = self.opener.open(url, timeout=self.timeout)
                headers = fp.info()
                fp.close()
                return headers
            except Exception:
                pass
        return {}

    def geturl(self, url):  # get the url that the argument url redirects or resolves to
        if url and isHttpUrl(url):
            try:
                fp = self.opener.open(url, timeout=self.timeout)
                actualurl = fp.geturl()
                fp.close()
                return actualurl
            except Exception:
                pass
        return None

    def retrieve(self, url, filename=None, filestream=None, reporthook=None, data=None):
        # return filename, headers (in dict), initial file bytes (to detect logon requests)
        headers = None
        initialBytes = b''
        fp = self.opener.open(url, data, timeout=self.timeout)
        try:
            headers = fp.info()
            if filename:
                tfp = open(filename, 'wb')
            elif filestream:
                tfp = filestream
            try:
                result = filename, headers
                bs = 1024*8
                size = -1
                read = 0
                blocknum = 0
                if reporthook:
                    if "content-length" in headers:
                        size = int(headers["Content-Length"])
                    reporthook(blocknum, bs, size)
                isGzipped = "gzip" in headers.get("content-encoding", "")
                if isGzipped:
                    decompressor = zlib.decompressobj(16+zlib.MAX_WBITS) #this magic number can be inferred from the structure of a gzip file
                while 1:
                    block = fp.read(bs)
                    if not block:
                        break
                    if isGzipped:
                        block = decompressor.decompress(block)
                    read += len(block)
                    tfp.write(block)
                    if blocknum == 0:
                        initialBytes = block
                    blocknum += 1
                    if reporthook:
                        reporthook(blocknum, bs, size)
            finally:
                if filename:
                    tfp.close()
        finally:
            if fp:
                fp.close()
        # raise exception if actual size does not match content-length header
        if size >= 0 and read < size:
            raise ContentTooShortError(
                _("retrieval incomplete: got only %i out of %i bytes")
                % (read, size), result)

        if filestream:
            tfp.seek(0)
        return filename, headers, initialBytes

'''
class WebCacheUrlOpener(request.FancyURLopener):
    def __init__(self, cntlr, proxies=None):
        self.cntlr = cntlr
        super(WebCacheUrlOpener, self).__init__(proxies)
        self.version = 'Mozilla/5.0'

    def http_error_401(self, url, fp, errcode, errmsg, headers, data=None, retry=False):
        super(WebCacheUrlOpener, self).http_error_401(url, fp, errcode, errmsg, headers, data, True)

    def http_error_407(self, url, fp, errcode, errmsg, headers, data=None, retry=False):
        super(WebCacheUrlOpener, self).http_error_407(self, url, fp, errcode, errmsg, headers, data, True)

    def prompt_user_passwd(self, host, realm):
        return self.cntlr.internet_user_password(host, realm)
'''
