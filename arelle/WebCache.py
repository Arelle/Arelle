'''
Created on Oct 5, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os, posixpath, sys, re, shutil, time, urllib.request, pickle
from urllib.error import (URLError, HTTPError, ContentTooShortError)
from urllib.parse import unquote

def proxyDirFmt(httpProxyTuple):
    if isinstance(httpProxyTuple,tuple) and len(httpProxyTuple) == 5:
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
    
    def __init__(self, cntlr, httpProxyTuple):
        self.cntlr = cntlr
        #self.proxies = urllib.request.getproxies()
        #self.proxies = {'ftp': 'ftp://63.192.17.1:3128', 'http': 'http://63.192.17.1:3128', 'https': 'https://63.192.17.1:3128'}
        
        
        self.resetProxies(httpProxyTuple)
        
        #self.opener.addheaders = [('User-agent', 'Mozilla/5.0')]

        #self.opener = WebCacheUrlOpener(cntlr, proxyDirFmt(httpProxyTuple)) # self.proxies)
        
        if sys.platform == "darwin":
            self.cacheDir = cntlr.userAppDir.replace("Application Support","Caches")
        else:  #windows and unix
            self.cacheDir = cntlr.userAppDir + os.sep + "cache"
        self.workOffline = False
        self.maxAgeSeconds = 60.0 * 60.0 * 24.0 * 7.0 # seconds before checking again for file
        self.urlCheckPickleFile = cntlr.userAppDir + os.sep + "cachedUrlCheckTimes.pickle"
        try:
            with open(self.urlCheckPickleFile, 'rb') as f:
                self.cachedUrlCheckTimes = pickle.load(f)
        except Exception:
            self.cachedUrlCheckTimes = {}
        self.cachedUrlCheckTimesModified = False
            
    def saveUrlCheckTimes(self):
        if self.cachedUrlCheckTimesModified:
            with open(self.urlCheckPickleFile, 'wb') as f:
                pickle.dump(self.cachedUrlCheckTimes, f, pickle.HIGHEST_PROTOCOL)
        self.cachedUrlCheckTimesModified = False
        
    def resetProxies(self, httpProxyTuple):
        try:
            from ntlm import HTTPNtlmAuthHandler
            self.hasNTLM = True
        except ImportError:
            self.hasNTLM = False
        self.proxy_handler = urllib.request.ProxyHandler(proxyDirFmt(httpProxyTuple))
        self.proxy_auth_handler = urllib.request.ProxyBasicAuthHandler()
        self.http_auth_handler = urllib.request.HTTPBasicAuthHandler()
        if self.hasNTLM:
            self.ntlm_auth_handler = HTTPNtlmAuthHandler.HTTPNtlmAuthHandler()            
            self.opener = urllib.request.build_opener(self.proxy_handler, self.ntlm_auth_handler, self.proxy_auth_handler, self.http_auth_handler)
        else:
            self.opener = urllib.request.build_opener(self.proxy_handler, self.proxy_auth_handler, self.http_auth_handler)

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
                    normedPath = os.path.normpath(os.path.join(os.path.dirname(base),url))
            else:
                normedPath = url
            if normedPath.startswith("file://"): normedPath = normedPath[7:]
            elif normedPath.startswith("file:\\"): normedPath = normedPath[6:]
        else:
            normedPath = url
        
        if normedPath:
            if normedPath.startswith('http:'):
                return normedPath.replace('\\','/')
            if normedPath.startswith(self.cacheDir):
                urlparts = normedPath[len(self.cacheDir)+1:].partition(os.sep)
                normedPath = urlparts[0] + '://' + urlparts[2].replace('\\','/')
        return normedPath
    
    def getfilename(self, url, base=None, reload=False):
        if url is None:
            return url
        if base is not None:
            url = self.normalizeUrl(url, base)
        if url.startswith('http://'):
            # form cache file name
            filepath = self.cacheDir + os.sep + 'http' + os.sep + url[7:]
            # handle default directory requests
            if filepath.endswith("/"):
                filepath += "default.unknown"
            if os.sep == '\\':
                filepath = filepath.replace('/', '\\')
            if self.workOffline:
                return filepath
            filepathtmp = filepath + ".tmp"
            timeNow = time.time()
            if not reload and os.path.exists(filepath):
                if timeNow - self.cachedUrlCheckTimes.get(url, 0.0) > self.maxAgeSeconds:
                    # weekly check if newer file exists
                    newerOnWeb = False
                    try: # no provision here for proxy authentication!!!
                        remoteFileTime = lastModifiedTime( self.getheaders(url) )
                        if remoteFileTime and remoteFileTime > os.path.getmtime(filepath):
                            newerOnWeb = True
                    except:
                        pass # for now, forget about authentication here
                    if not newerOnWeb:
                        # update ctime by copying file and return old file
                        self.cachedUrlCheckTimes[url] = timeNow
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
                                      url,
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
                        if err.code == 401 and 'www-authenticate' in err.headers:
                            match = re.match('[ \t]*([^ \t]+)[ \t]+realm="([^"]*)"', err.headers['www-authenticate'])
                            if match:
                                scheme, realm = match.groups()
                                if scheme.lower() == 'basic':
                                    host = os.path.dirname(url)
                                    userPwd = self.cntlr.internet_user_password(host, realm)
                                    if isinstance(userPwd,tuple):
                                        self.http_auth_handler.add_password(realm=realm,uri=host,user=userPwd[0],passwd=userPwd[1]) 
                                        retryCount -= 1
                                        continue
                                self.cntlr.addToLog(_("'{0}' www-authentication for realm '{1}' is required to access {2}\n{3}").format(scheme, realm, url, err))
                        elif err.code == 407 and 'proxy-authenticate' in err.headers:
                            match = re.match('[ \t]*([^ \t]+)[ \t]+realm="([^"]*)"', err.headers['proxy-authenticate'])
                            if match:
                                scheme, realm = match.groups()
                                host = self.proxy_handler.proxies.get('http')
                                if scheme.lower() == 'basic':
                                    userPwd = self.cntlr.internet_user_password(host, realm)
                                    if isinstance(userPwd,tuple):
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
                self.cachedUrlCheckTimes[url] = timeNow
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
                fp = self.opener.open(url)
                headers = fp.info()
                fp.close()
                return headers
            except Exception:
                pass
        return {}
    
    def geturl(self, url):  # get the url that the argument url redirects or resolves to
        if url and url.startswith('http://'):
            try:
                fp = self.opener.open(url)
                actualurl = fp.geturl()
                fp.close()
                return actualurl
            except Exception:
                pass
        return None
        
    def retrieve(self, url, filename, reporthook=None, data=None):
        fp = self.opener.open(url, data)
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
class WebCacheUrlOpener(urllib.request.FancyURLopener):
    def __init__(self, cntlr, proxies=None):
        self.cntlr = cntlr
        super().__init__(proxies)
        self.version = 'Mozilla/5.0'

    def http_error_401(self, url, fp, errcode, errmsg, headers, data=None, retry=False):
        super().http_error_401(url, fp, errcode, errmsg, headers, data, True)
        
    def http_error_407(self, url, fp, errcode, errmsg, headers, data=None, retry=False):
        super().http_error_407(self, url, fp, errcode, errmsg, headers, data, True)
        
    def prompt_user_passwd(self, host, realm):
        return self.cntlr.internet_user_password(host, realm)
'''
    