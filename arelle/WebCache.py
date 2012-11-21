'''
Created on Oct 5, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os, posixpath, sys, re, shutil, time, calendar, io, json
if sys.version[0] >= '3':
    from urllib.parse import quote, unquote
    from urllib.error import (URLError, HTTPError, ContentTooShortError)
    from urllib import request
    from urllib import request as proxyhandlers
else: # python 2.7.2
    from urllib import quote, unquote
    from urllib import ContentTooShortError
    from urllib2 import URLError, HTTPError
    import urllib2 as proxyhandlers
    
DIRECTORY_INDEX_FILE = "!~DirectoryIndex~!"

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
    
    def __init__(self, cntlr, httpProxyTuple):
        self.cntlr = cntlr
        #self.proxies = request.getproxies()
        #self.proxies = {'ftp': 'ftp://63.192.17.1:3128', 'http': 'http://63.192.17.1:3128', 'https': 'https://63.192.17.1:3128'}
        self._timeout = None        
        
        self.resetProxies(httpProxyTuple)
        
        #self.opener.addheaders = [('User-agent', 'Mozilla/5.0')]

        #self.opener = WebCacheUrlOpener(cntlr, proxyDirFmt(httpProxyTuple)) # self.proxies)
        
        if sys.platform == "darwin" and "/Application Support/" in cntlr.userAppDir:
            self.cacheDir = cntlr.userAppDir.replace("Application Support","Caches")
            self.encodeFileChars = re.compile(r'[:^]') 
            
        else:  #windows and unix
            self.cacheDir = cntlr.userAppDir + os.sep + "cache"
            if sys.platform.startswith("win"):
                self.encodeFileChars = re.compile(r'[<>:"\\|?*^]')
            else:
                self.encodeFileChars = re.compile(r'[:^]') 
        self.decodeFileChars = re.compile(r'\^[0-9]{3}')
        self.workOffline = False
        self.maxAgeSeconds = 60.0 * 60.0 * 24.0 * 7.0 # seconds before checking again for file
        self.urlCheckJsonFile = cntlr.userAppDir + os.sep + "cachedUrlCheckTimes.json"
        try:
            with io.open(self.urlCheckJsonFile, 'rt', encoding='utf-8') as f:
                self.cachedUrlCheckTimes = json.load(f)
        except Exception:
            self.cachedUrlCheckTimes = {}
        self.cachedUrlCheckTimesModified = False
            

    @property
    def timeout(self):
        return self._timeout or WebCache.default_timeout

    @timeout.setter
    def timeout(self, seconds):
        self._timeout = seconds

    def saveUrlCheckTimes(self):
        if self.cachedUrlCheckTimesModified:
            with io.open(self.urlCheckJsonFile, 'wt', encoding='utf-8') as f:
                jsonStr = _STR_UNICODE(json.dumps(self.cachedUrlCheckTimes, ensure_ascii=False, indent=0)) # might not be unicode in 2.7
                f.write(jsonStr)  # 2.7 gets unicode this way
        self.cachedUrlCheckTimesModified = False
        
    def resetProxies(self, httpProxyTuple):
        try:
            from ntlm import HTTPNtlmAuthHandler
            self.hasNTLM = True
        except ImportError:
            self.hasNTLM = False
        self.proxy_handler = proxyhandlers.ProxyHandler(proxyDirFmt(httpProxyTuple))
        self.proxy_auth_handler = proxyhandlers.ProxyBasicAuthHandler()
        self.http_auth_handler = proxyhandlers.HTTPBasicAuthHandler()
        if self.hasNTLM:
            self.ntlm_auth_handler = HTTPNtlmAuthHandler.HTTPNtlmAuthHandler()            
            self.opener = proxyhandlers.build_opener(self.proxy_handler, self.ntlm_auth_handler, self.proxy_auth_handler, self.http_auth_handler)
        else:
            self.opener = proxyhandlers.build_opener(self.proxy_handler, self.proxy_auth_handler, self.http_auth_handler)

        #self.opener.close()
        #self.opener = WebCacheUrlOpener(self.cntlr, proxyDirFmt(httpProxyTuple))
        
    
    def normalizeUrl(self, url, base=None):
        if url and not (url.startswith('http://') or os.path.isabs(url)):
            if base is not None and not base.startswith('http:') and '%' in url:
                url = unquote(url)
            if base:
                if base.startswith("http://"):
                    prot, sep, path = base.partition("://")
                    normedPath = prot + sep + posixpath.normpath(os.path.dirname(path) + "/" + url)
                else:
                    if '%' in base:
                        base = unquote(base)
                    normedPath = os.path.normpath(os.path.join(os.path.dirname(base),url))
            else:
                normedPath = url
            if normedPath.startswith("file://"): normedPath = normedPath[7:]
            elif normedPath.startswith("file:\\"): normedPath = normedPath[6:]
            
            # no base, not normalized, must be relative to current working directory
            if base is None and not os.path.isabs(url): 
                normedPath = os.path.abspath(normedPath)
        else:
            normedPath = url
        
        if normedPath:
            if normedPath.startswith('http://'):
                pathpart = normedPath[7:].replace('\\','/')
                endingSep = '/' if pathpart[-1] == '/' else ''  # normpath drops ending directory separator
                return "http://" + posixpath.normpath(pathpart) + endingSep
            normedPath = os.path.normpath(normedPath)
            if normedPath.startswith(self.cacheDir):
                normedPath = self.cacheFilepathToUrl(normedPath)
        return normedPath

    def encodeForFilename(self, pathpart):
        return self.encodeFileChars.sub(lambda m: '^{0:03}'.format(ord(m.group(0))), pathpart)
    
    def urlToCacheFilepath(self, url):
        filepath = [self.cacheDir, 'http'] 
        pathparts = url[7:].split('/')
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
            
    def getfilename(self, url, base=None, reload=False, checkModifiedTime=False, normalize=False, filenameOnly=False):
        if url is None:
            return url
        if base is not None or normalize:
            url = self.normalizeUrl(url, base)
        urlScheme, schemeSep, urlSchemeSpecificPart = url.partition("://")
        if schemeSep and urlScheme == "http":
            # form cache file name (substituting _ for any illegal file characters)
            filepath = self.urlToCacheFilepath(url)
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
            timeNow = time.time()
            timeNowStr = time.strftime('%Y-%m-%dT%H:%M:%S UTC', time.gmtime(timeNow))
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
                    savedfile, headers = self.retrieve(
                    #savedfile, headers = self.opener.retrieve(
                                      quotedUrl,
                                      filename=filepathtmp,
                                      reporthook=self.reportProgress)
                    retryCount = 0
                except ContentTooShortError as err:
                    self.cntlr.addToLog(_("{0} \nretrieving {1}").format(err,url))
                    if os.path.exists(filepathtmp):
                        os.remove(filepathtmp)
                    return None
                    # handle file is bad
                except (HTTPError, URLError) as err:
                    try:
                        if err.code == 401 and 'www-authenticate' in err.hdrs:
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
                                self.cntlr.addToLog(_("'{0}' www-authentication for realm '{1}' is required to access {2}\n{3}").format(scheme, realm, url, err))
                        elif err.code == 407 and 'proxy-authenticate' in err.hdrs:
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
                                self.cntlr.addToLog(_("'{0}' proxy-authentication for realm '{1}' is required to access {2}\n{3}").format(scheme, realm, url, err))
                                    
                    except AttributeError:
                        pass
                    self.cntlr.addToLog(_("{0} \nretrieving {1}").format(err,url))
                    return None
                
                except Exception as err:
                    self.cntlr.addToLog(_("{0} \nunsuccessful retrieval of {1} \nswitching to work offline").format(err,url))
                    # try working offline
                    self.workOffline = True
                    return filepath
                
                # rename temporarily named downloaded file to desired name                
                if os.path.exists(filepath):
                    os.remove(filepath)
                os.rename(filepathtmp, filepath)
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
        shutil.rmtree(self.cacheDir + os.sep + 'http', True)
        
    def getheaders(self, url):
        if url and url.startswith('http://'):
            try:
                fp = self.opener.open(url, timeout=self.timeout)
                headers = fp.info()
                fp.close()
                return headers
            except Exception:
                pass
        return {}
    
    def geturl(self, url):  # get the url that the argument url redirects or resolves to
        if url and url.startswith('http://'):
            try:
                fp = self.opener.open(url, timeout=self.timeout)
                actualurl = fp.geturl()
                fp.close()
                return actualurl
            except Exception:
                pass
        return None
        
    def retrieve(self, url, filename, reporthook=None, data=None):
        fp = self.opener.open(url, data, timeout=self.timeout)
        try:
            headers = fp.info()
            tfp = open(filename, 'wb')
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
                while 1:
                    block = fp.read(bs)
                    if not block:
                        break
                    read += len(block)
                    tfp.write(block)
                    blocknum += 1
                    if reporthook:
                        reporthook(blocknum, bs, size)
            finally:
                tfp.close()
        finally:
            fp.close()
        # raise exception if actual size does not match content-length header
        if size >= 0 and read < size:
            raise ContentTooShortError(
                _("retrieval incomplete: got only %i out of %i bytes")
                % (read, size), result)

        return result

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
    