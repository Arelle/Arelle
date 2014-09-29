'''
Created on Oct 20, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import zipfile, tarfile, os, io, base64, gzip, zlib, re, struct, random, time
from lxml import etree
from arelle import XmlUtil
from arelle.PackageManager import parsePackage
from arelle.UrlUtil import isHttpUrl

archivePathSeparators = (".zip" + os.sep, ".tar.gz" + os.sep, ".eis" + os.sep, ".xml" + os.sep, ".xfd" + os.sep, ".frm" + os.sep, '.taxonomyPackage.xml' + os.sep) + \
                        ((".zip/", ".tar.gz/", ".eis/", ".xml/", ".xfd/", ".frm/", '.taxonomyPackage.xml/') if os.sep != "/" else ()) #acomodate windows and http styles

POST_UPLOADED_ZIP = os.sep + "POSTupload.zip"
SERVER_WEB_CACHE = os.sep + "_HTTP_CACHE"

XMLdeclaration = re.compile(r"<\?xml[^><\?]*\?>", re.DOTALL)

TAXONOMY_PACKAGE_FILE_NAMES = ('.taxonomyPackage.xml', 'catalog.xml')

def openFileSource(filename, cntlr=None, sourceZipStream=None, checkIfXmlIsEis=False):
    if sourceZipStream:
        filesource = FileSource(POST_UPLOADED_ZIP, cntlr)
        filesource.openZipStream(sourceZipStream)
        filesource.select(filename)
        return filesource
    else:
        archivepathSelection = archiveFilenameParts(filename, checkIfXmlIsEis)
        if archivepathSelection is not None:
            archivepath = archivepathSelection[0]
            selection = archivepathSelection[1]
            filesource = FileSource(archivepath, cntlr, checkIfXmlIsEis)
            filesource.open()
            filesource.select(selection)
            return filesource
        # not archived content
        return FileSource(filename, cntlr, checkIfXmlIsEis) 

def archiveFilenameParts(filename, checkIfXmlIsEis=False):
    # check if path has an archive file plus appended in-archive content reference
    for archiveSep in archivePathSeparators:
        if (filename and 
            archiveSep in filename and
            (not archiveSep.startswith(".xml") or checkIfXmlIsEis)):
            filenameParts = filename.partition(archiveSep)
            fileDir = filenameParts[0] + archiveSep[:-1]
            if (isHttpUrl(fileDir) or
                os.path.isfile(fileDir)): # if local, be sure it is not a directory name
                return (fileDir, filenameParts[2])
    return None

class FileNamedStringIO(io.StringIO):  # provide string IO in memory but behave as a fileName string
    def __init__(self, fileName, *args, **kwargs):
        super(FileNamedStringIO, self).__init__(*args, **kwargs)
        self.fileName = fileName
        
    def close(self):
        del self.fileName
        super(FileNamedStringIO, self).close()

    def __str__(self):
        return self.fileName
    
class FileNamedTextIOWrapper(io.TextIOWrapper):  # provide string IO in memory but behave as a fileName string
    def __init__(self, fileName, *args, **kwargs):
        super(FileNamedTextIOWrapper, self).__init__(*args, **kwargs)
        self.fileName = fileName

    def __str__(self):
        return self.fileName
    
class ArchiveFileIOError(IOError):
    def __init__(self, fileSource, fileName):
        self.fileName = fileName
        self.url = fileSource.url
        
    def __str__(self):
        return _("Archive does not contain file: {0}, archive: {1}").format(self.fileName, self.url)
            
class FileSource:
    def __init__(self, url, cntlr=None, checkIfXmlIsEis=False):
        self.url = str(url)  # allow either string or FileNamedStringIO
        self.baseIsHttp = isHttpUrl(self.url)
        self.cntlr = cntlr
        self.type = self.url.lower()[-7:]
        self.isTarGz = self.type == ".tar.gz"
        if not self.isTarGz:
            self.type = self.type[3:]
        self.isZip = self.type == ".zip"
        self.isEis = self.type == ".eis"
        self.isXfd = (self.type == ".xfd" or self.type == ".frm")
        self.isRss = (self.type == ".rss" or self.url.endswith(".rss.xml"))
        self.isInstalledTaxonomyPackage = False
        self.isOpen = False
        self.fs = None
        self.selection = None
        self.filesDir = None
        self.referencedFileSources = {}  # archive file name, fileSource object
        self.mappedPaths = None  # remappings of path segments may be loaded by taxonomyPackage manifest
        
        # for SEC xml files, check if it's an EIS anyway
        if (not (self.isZip or self.isEis or self.isXfd or self.isRss) and
            self.type == ".xml"):
            if os.path.split(self.url)[-1] in TAXONOMY_PACKAGE_FILE_NAMES:
                self.isInstalledTaxonomyPackage = True
            elif checkIfXmlIsEis:
                try:
                    file = open(self.cntlr.webCache.getfilename(self.url), 'r', errors='replace')
                    l = file.read(128)
                    file.close()
                    if re.match(r"\s*(<[?]xml[^?]+[?]>)?\s*<cor[a-z]*:edgarSubmission", l):
                        self.isEis = True
                except EnvironmentError as err:
                    if self.cntlr:
                        self.cntlr.addToLog(_("[{0}] {1}").format(type(err).__name__, err))
                    pass
            
    def logError(self, err):
        if self.cntlr:
            self.cntlr.addToLog(_("[{0}] {1}").format(type(err).__name__, err))

    def open(self):
        if not self.isOpen:
            if (self.isZip or self.isTarGz or self.isEis or self.isXfd or self.isRss or self.isInstalledTaxonomyPackage) and self.cntlr:
                self.basefile = self.cntlr.webCache.getfilename(self.url)
            else:
                self.basefile = self.url
            self.baseurl = self.url # url gets changed by selection
            if not self.basefile:
                return  # an error should have been logged
            if self.isZip:
                try:
                    self.fs = zipfile.ZipFile(openFileStream(self.cntlr, self.basefile, 'rb'), mode="r")
                    self.isOpen = True
                except EnvironmentError as err:
                    self.logError(err)
                    pass
            elif self.isTarGz:
                try:
                    self.fs = tarfile.open(self.basefile, "r:gz")
                    self.isOpen = True
                except EnvironmentError as err:
                    self.logError(err)
                    pass
            elif self.isEis:
                # check first line of file
                buf = b''
                try:
                    file = open(self.basefile, 'rb')
                    more = True
                    while more:
                        l = file.read(8)
                        if len(l) < 8:
                            break
                        if len(buf) == 0 and l.startswith(b"<?xml "): # not compressed
                            buf = l + file.read()  # not compressed
                            break
                        compressedBytes = file.read( struct.unpack(">L", l[0:4])[0])
                        if len(compressedBytes) <= 0:
                            break
                        buf += zlib.decompress(compressedBytes)
                    file.close()
                except EnvironmentError as err:
                    self.logError(err)
                    pass
                #uncomment to save for debugging
                #with open("c:/temp/test.xml", "wb") as f:
                #    f.write(buf)
                
                if buf.startswith(b"<?xml "):
                    try:
                        # must strip encoding
                        str = buf.decode(XmlUtil.encoding(buf))
                        endEncoding = str.index("?>", 0, 128)
                        if endEncoding > 0:
                            str = str[endEncoding+2:]
                        file = io.StringIO(initial_value=str)
                        parser = etree.XMLParser(recover=True, huge_tree=True)
                        self.eisDocument = etree.parse(file, parser=parser)
                        file.close()
                        self.isOpen = True
                    except EnvironmentError as err:
                        self.logError(err)
                        return # provide error message later
                    except etree.LxmlError as err:
                        self.logError(err)
                        return # provide error message later
                
            elif self.isXfd:
                # check first line of file
                file = open(self.basefile, 'rb')
                firstline = file.readline()
                if firstline.startswith(b"application/x-xfdl;content-encoding=\"asc-gzip\""):
                    # file has been gzipped
                    base64input = file.read(-1)
                    file.close();
                    file = None;
    
                    fb = base64.b64decode(base64input)
                    ungzippedBytes = b""
                    totalLenUncompr = 0
                    i = 0
                    while i < len(fb):
                        lenCompr = fb[i + 0] * 256 + fb[i + 1]
                        lenUncomp = fb[i + 2] * 256 + fb[i + 3]
                        lenRead = 0
                        totalLenUncompr += lenUncomp

                        gzchunk = (bytes((31,139,8,0)) + fb[i:i+lenCompr])
                        try:
                            with gzip.GzipFile(fileobj=io.BytesIO(gzchunk)) as gf:
                                while True:
                                    readSize = min(16384, lenUncomp - lenRead)
                                    readBytes = gf.read(size=readSize)
                                    lenRead += len(readBytes)
                                    ungzippedBytes += readBytes
                                    if len(readBytes) == 0 or (lenUncomp - lenRead) <= 0:
                                        break
                        except IOError as err:
                            pass # provide error message later

                        i += lenCompr + 4
                    #for learning the content of xfd file, uncomment this:
                    #with open("c:\\temp\\test.xml", "wb") as fh:
                    #    fh.write(ungzippedBytes)
                    file = io.StringIO(initial_value=ungzippedBytes.decode("utf-8"))
                else:
                    # position to start of file
                    file.seek(0,io.SEEK_SET)
                    
                try:
                    self.xfdDocument = etree.parse(file)
                    file.close()
                    self.isOpen = True
                except EnvironmentError as err:
                    self.logError(err)
                    return # provide error message later
                except etree.LxmlError as err:
                    self.logError(err)
                    return # provide error message later
                
            elif self.isRss:
                try:
                    self.rssDocument = etree.parse(self.basefile)
                    self.isOpen = True
                except EnvironmentError as err:
                    self.logError(err)
                    return # provide error message later
                except etree.LxmlError as err:
                    self.logError(err)
                    return # provide error message later
            
            elif self.isInstalledTaxonomyPackage:
                self.isOpen = True
                # load mappings
                try:
                    metadataFiles = self.taxonomyPackageMetadataFiles
                    if len(metadataFiles) != 1:
                        raise IOError(_("Taxonomy package must contain one and only one metadata file: {0}.")
                                      .format(', '.join(metadataFiles)))
                    # HF: this won't work, see DialogOpenArchive for correct code
                    # not sure if it is used
                    taxonomyPackage = parsePackage(self.cntlr, self.url)
                    fileSourceDir = os.path.dirname(self.baseurl) + os.sep
                    self.mappedPaths = \
                        dict((prefix, 
                              remapping if isHttpUrl(remapping)
                              else (fileSourceDir + remapping.replace("/", os.sep)))
                              for prefix, remapping in taxonomyPackage["remappings"].items())
                except EnvironmentError as err:
                    self.logError(err)
                    return # provide error message later

    def openZipStream(self, sourceZipStream):
        if not self.isOpen:
            self.basefile = self.url
            self.baseurl = self.url # url gets changed by selection
            self.fs = zipfile.ZipFile(sourceZipStream, mode="r")
            self.isOpen = True    
            
    def close(self):
        if self.referencedFileSources:
            for referencedFileSource in self.referencedFileSources.values():
                referencedFileSource.close()
        self.referencedFileSources = None
        if self.isZip and self.isOpen:
            self.fs.close()
            self.isOpen = False
            self.isZip = False
        if self.isTarGz and self.isOpen:
            self.fs.close()
            self.isOpen = False
            self.isTarGz = False
        if self.isEis and self.isOpen:
            self.eisDocument.getroot().clear() # unlink nodes
            self.eisDocument = None
            self.isEis = False
        if self.isXfd and self.isOpen:
            self.xfdDocument.getroot().clear() # unlink nodes
            self.xfdDocument = None
            self.isXfd = False
        if self.isRss and self.isOpen:
            self.rssDocument.getroot().clear() # unlink nodes
            self.rssDocument = None
            self.isRss = False
        if self.isInstalledTaxonomyPackage:
            self.isInstalledTaxonomyPackage = False
            self.isOpen = False
        self.filesDir = None
        
    @property
    def isArchive(self):
        return self.isZip or self.isTarGz or self.isEis or self.isXfd or self.isInstalledTaxonomyPackage
    
    @property
    def isTaxonomyPackage(self):
        return (self.isZip and self.taxonomyPackageMetadataFiles) or self.isInstalledTaxonomyPackage
    
    @property
    def taxonomyPackageMetadataFiles(self):
        return [f for f in (self.dir or []) if os.path.split(f)[-1] in TAXONOMY_PACKAGE_FILE_NAMES]
    
    def isInArchive(self,filepath):
        return self.fileSourceContainingFilepath(filepath) is not None
    
    def isMappedUrl(self, url):
        if self.mappedPaths is not None:
            return any(url.startswith(mapFrom) 
                       for mapFrom in self.mappedPaths)
        return False        

    def mappedUrl(self, url):
        if self.mappedPaths:
            for mapFrom, mapTo in self.mappedPaths.items():
                if url.startswith(mapFrom):
                    url = mapTo + url[len(mapFrom):]
                    break
        return url
    
    def fileSourceContainingFilepath(self, filepath):
        if self.isOpen:
            # archiveFiles = self.dir
            ''' change to return file source if archive would be in there (vs actually is in archive)
            if ((filepath.startswith(self.basefile) and 
                 filepath[len(self.basefile) + 1:] in archiveFiles) or
                (filepath.startswith(self.baseurl) and 
                 filepath[len(self.baseurl) + 1:] in archiveFiles)):
                return self
            '''
            if (filepath.startswith(self.basefile) or
                filepath.startswith(self.baseurl)):
                return self
        referencedFileParts = archiveFilenameParts(filepath)
        if referencedFileParts is not None:
            referencedArchiveFile, referencedSelection = referencedFileParts
            if referencedArchiveFile in self.referencedFileSources:
                referencedFileSource = self.referencedFileSources[referencedArchiveFile]
                if referencedFileSource.isInArchive(filepath):
                    return referencedFileSource
            elif (not self.isOpen or 
                  (referencedArchiveFile != self.basefile and referencedArchiveFile != self.baseurl)):
                referencedFileSource = openFileSource(filepath, self.cntlr)
                if referencedFileSource:
                    self.referencedFileSources[referencedArchiveFile] = referencedFileSource
        return None
    
    def file(self, filepath, binary=False):
        ''' 
            for text, return a tuple of (open file handle, encoding)
            for binary, return a tuple of (open file handle, )
        '''
        archiveFileSource = self.fileSourceContainingFilepath(filepath)
        if archiveFileSource is not None:
            if filepath.startswith(archiveFileSource.basefile):
                archiveFileName = filepath[len(archiveFileSource.basefile) + 1:]
            else: # filepath.startswith(self.baseurl)
                archiveFileName = filepath[len(archiveFileSource.baseurl) + 1:]
            if archiveFileSource.isZip:
                try:
                    b = archiveFileSource.fs.read(archiveFileName.replace("\\","/"))
                    if binary:
                        return (io.BytesIO(b), )
                    encoding = XmlUtil.encoding(b)
                    return (FileNamedTextIOWrapper(filepath, io.BytesIO(b), encoding=encoding), 
                            encoding)
                except KeyError:
                    raise ArchiveFileIOError(self, archiveFileName)
            elif archiveFileSource.isTarGz:
                try:
                    fh = archiveFileSource.fs.extractfile(archiveFileName)
                    b = fh.read()
                    fh.close() # doesn't seem to close properly using a with construct
                    if binary:
                        return (io.BytesIO(b), )
                    encoding = XmlUtil.encoding(b)
                    return (FileNamedTextIOWrapper(filepath, io.BytesIO(b), encoding=encoding), 
                            encoding)
                except KeyError:
                    raise ArchiveFileIOError(self, archiveFileName)
            elif archiveFileSource.isEis:
                for docElt in self.eisDocument.iter(tag="{http://www.sec.gov/edgar/common}document"):
                    outfn = docElt.findtext("{http://www.sec.gov/edgar/common}conformedName")
                    if outfn == archiveFileName:
                        b64data = docElt.findtext("{http://www.sec.gov/edgar/common}contents")
                        if b64data:
                            b = base64.b64decode(b64data.encode("latin-1"))
                            # remove BOM codes if present
                            if len(b) > 3 and b[0] == 239 and b[1] == 187 and b[2] == 191:
                                start = 3;
                                length = len(b) - 3;
                                b = b[start:start + length]
                            else:
                                start = 0;
                                length = len(b);
                            if binary:
                                return (io.BytesIO(b), )
                            encoding = XmlUtil.encoding(b, default="latin-1")
                            return (io.TextIOWrapper(io.BytesIO(b), encoding=encoding), 
                                    encoding)
                raise ArchiveFileIOError(self, archiveFileName)
            elif archiveFileSource.isXfd:
                for data in archiveFileSource.xfdDocument.iter(tag="data"):
                    outfn = data.findtext("filename")
                    if outfn == archiveFileName:
                        b64data = data.findtext("mimedata")
                        if b64data:
                            b = base64.b64decode(b64data.encode("latin-1"))
                            # remove BOM codes if present
                            if len(b) > 3 and b[0] == 239 and b[1] == 187 and b[2] == 191:
                                start = 3;
                                length = len(b) - 3;
                                b = b[start:start + length]
                            else:
                                start = 0;
                                length = len(b);
                            if binary:
                                return (io.BytesIO(b), )
                            encoding = XmlUtil.encoding(b, default="latin-1")
                            return (io.TextIOWrapper(io.BytesIO(b), encoding=encoding), 
                                    encoding)
                raise ArchiveFileIOError(self, archiveFileName)
            elif archiveFileSource.isInstalledTaxonomyPackage:
                # remove TAXONOMY_PACKAGE_FILE_NAME from file path
                if filepath.startswith(archiveFileSource.basefile):
                    l = len(archiveFileSource.basefile)
                    for f in TAXONOMY_PACKAGE_FILE_NAMES:
                        if filepath[l - len(f):l] == f:
                            filepath = filepath[0:l - len(f) - 1] + filepath[l:]
                            break
        if binary:
            return (openFileStream(self.cntlr, filepath, 'rb'), )
        else:
            return openXmlFileStream(self.cntlr, filepath)

    
    @property
    def dir(self):
        self.open()
        if not self.isOpen:
            return None
        elif self.filesDir is not None:
            return self.filesDir
        elif self.isZip:
            files = []
            for zipinfo in self.fs.infolist():
                files.append(zipinfo.filename)
            self.filesDir = files
        elif self.isTarGz:
            self.filesDir = self.fs.getnames()
        elif self.isEis:
            files = []
            for docElt in self.eisDocument.iter(tag="{http://www.sec.gov/edgar/common}document"):
                outfn = docElt.findtext("{http://www.sec.gov/edgar/common}conformedName")
                if outfn:
                    files.append(outfn);
            self.filesDir = files
        elif self.isXfd:
            files = []
            for data in self.xfdDocument.iter(tag="data"):
                outfn = data.findtext("filename")
                if outfn:
                    if len(outfn) > 2 and outfn[0].isalpha() and \
                        outfn[1] == ':' and outfn[2] == '\\':
                        continue
                    files.append(outfn);
            self.filesDir = files
        elif self.isRss:
            files = []  # return title, descr, pubdate, linst doc
            edgr = "http://www.sec.gov/Archives/edgar"
            try:
                for dsElt in XmlUtil.descendants(self.rssDocument, None, "item"):
                    instDoc = None
                    for instDocElt in XmlUtil.descendants(dsElt, edgr, "xbrlFile"):
                        if instDocElt.get("(http://www.sec.gov/Archives/edgar}description").endswith("INSTANCE DOCUMENT"):
                            instDoc = instDocElt.get("(http://www.sec.gov/Archives/edgar}url")
                            break
                    if not instDoc:
                        continue
                    files.append((
                        XmlUtil.text(XmlUtil.descendant(dsElt, None, "title")),
                        # tooltip
                        "{0}\n {1}\n {2}\n {3}\n {4}".format(
                            XmlUtil.text(XmlUtil.descendant(dsElt, edgr, "companyName")),
                            XmlUtil.text(XmlUtil.descendant(dsElt, edgr, "formType")),
                            XmlUtil.text(XmlUtil.descendant(dsElt, edgr, "filingDate")),
                            XmlUtil.text(XmlUtil.descendant(dsElt, edgr, "cikNumber")),
                            XmlUtil.text(XmlUtil.descendant(dsElt, edgr, "period"))),
                        XmlUtil.text(XmlUtil.descendant(dsElt, None, "description")),
                        XmlUtil.text(XmlUtil.descendant(dsElt, None, "pubDate")),
                        instDoc))
                self.filesDir = files
            except (EnvironmentError,
                    etree.LxmlError) as err:
                pass
        elif self.isInstalledTaxonomyPackage:
            files = []
            baseurlPathLen = len(os.path.dirname(self.baseurl)) + 1
            def packageDirsFiles(dir):
                for file in os.listdir(dir):
                    path = dir + "/" + file   # must have / and not \\ even on windows
                    files.append(path[baseurlPathLen:])
                    if os.path.isdir(path): 
                        packageDirsFiles(path)
            packageDirsFiles(self.baseurl[0:baseurlPathLen - 1])
            self.filesDir = files
            
        return self.filesDir
    
    def select(self, selection):
        self.selection = selection
        if isHttpUrl(selection) or os.path.isabs(selection):
            self.url = selection
        elif self.baseIsHttp or os.sep == '/':
            self.url = self.baseurl + "/" + selection
        else: # MSFT os.sep == '\\'
            self.url = self.baseurl + os.sep + selection.replace("/", os.sep)
            
def openFileStream(cntlr, filepath, mode='r', encoding=None):
    if isHttpUrl(filepath) and cntlr:
        _cacheFilepath = cntlr.webCache.getfilename(filepath)
        if _cacheFilepath is None:
            raise IOError(_("Unable to open file: {0}.").format(filepath))
        filepath = _cacheFilepath
    # file path may be server (or memcache) or local file system
    if filepath.startswith(SERVER_WEB_CACHE) and cntlr:
        filestream = None
        cacheKey = filepath[len(SERVER_WEB_CACHE) + 1:].replace("\\","/")
        if cntlr.isGAE: # check if in memcache
            cachedBytes = gaeGet(cacheKey)
            if cachedBytes:
                filestream = io.BytesIO(cachedBytes)
        if filestream is None:
            filestream = io.BytesIO()
            cntlr.webCache.retrieve(cntlr.webCache.cacheFilepathToUrl(filepath),
                                    filestream=filestream)
            if cntlr.isGAE:
                gaeSet(cacheKey, filestream.getvalue())
        if mode.endswith('t') or encoding:
            contents = filestream.getvalue()
            filestream.close()
            filestream = FileNamedStringIO(filepath, contents.decode(encoding or 'utf-8'))
        return filestream
    # local file system
    elif encoding is None and 'b' not in mode:
        openedFileStream = io.open(filepath, mode='rb')
        hdrBytes = openedFileStream.read(512)
        encoding = XmlUtil.encoding(hdrBytes, default=None)
        openedFileStream.close()
        return io.open(filepath, mode=mode, encoding=encoding)
    else:
        # local file system
        return io.open(filepath, mode=mode, encoding=encoding)
    
def openXmlFileStream(cntlr, filepath, stripDeclaration=False):
    # returns tuple: (fileStream, encoding)
    openedFileStream = openFileStream(cntlr, filepath, 'rb')
    # check encoding
    hdrBytes = openedFileStream.read(512)
    encoding = XmlUtil.encoding(hdrBytes)
    if encoding.lower() in ('utf-8','utf8','utf-8-sig') and (cntlr is None or not cntlr.isGAE) and not stripDeclaration:
        text = None
        openedFileStream.close()
    else:
        openedFileStream.seek(0)
        text = openedFileStream.read().decode(encoding)
        openedFileStream.close()
        # allow filepath to close
    # this may not be needed for Mac or Linux, needs confirmation!!!
    if text is None:  # ok to read as utf-8
        return io.open(filepath, 'rt', encoding='utf-8'), encoding
    else:
        # strip XML declaration
        xmlDeclarationMatch = XMLdeclaration.search(text)
        if xmlDeclarationMatch: # remove it for lxml
            start,end = xmlDeclarationMatch.span()
            text = text[0:start] + text[end:]
        return (FileNamedStringIO(filepath, initial_value=text), encoding)
    
def saveFile(cntlr, filepath, contents, encoding=None):
    if isHttpUrl(filepath):
        _cacheFilepath = cntlr.webCache.getfilename(filepath)
        if _cacheFilepath is None:
            raise IOError(_("Unable to open file: {0}.").format(filepath))
        filepath = _cacheFilepath
    # file path may be server (or memcache) or local file system
    if filepath.startswith(SERVER_WEB_CACHE):
        cacheKey = filepath[len(SERVER_WEB_CACHE) + 1:].replace("\\","/")
        if cntlr.isGAE: # check if in memcache
            gaeSet(cacheKey, contents.encode(encoding or 'utf-8'))
    else:
        with io.open(filepath, 'wt', encoding=(encoding or 'utf-8')) as f:
            f.write(contents)
                          
# GAE Blobcache
gaeMemcache = None
GAE_MEMCACHE_MAX_ITEM_SIZE = 900 * 1024
GAE_EXPIRE_WEEK = 60 * 60 * 24 * 7 # one week

def gaeGet(key):
    # returns bytes (not string) value
    global gaeMemcache
    if gaeMemcache is None:
        from google.appengine.api import memcache as gaeMemcache
    chunk_keys = gaeMemcache.get(key)
    if chunk_keys is None:
        return None
    chunks = []
    if isinstance(chunk_keys, _STR_BASE):
        chunks.append(chunk_keys)  # only one shard
    else:
        for chunk_key in chunk_keys:
            # TODO: use memcache.get_multi() for speedup.
            # Don't forget about the batch operation size limit (currently 32Mb).
            chunk = gaeMemcache.get(chunk_key)
            if chunk is None:
                return None
            chunks.append(chunk)
    try:
        return zlib.decompress(b''.join(chunks)) # must be bytes join, not unicode
    except zlib.error:
        return None


def gaeDelete(key):
    chunk_keys = gaeMemcache.get(key)
    if chunk_keys is None:
        return False
    if isinstance(chunk_keys, _STR_BASE):
        chunk_keys = []
    chunk_keys.append(key)
    gaeMemcache.delete_multi(chunk_keys)
    return True


def gaeSet(key, bytesValue): # stores bytes, not string valye
    global gaeMemcache
    if gaeMemcache is None:
        from google.appengine.api import memcache as gaeMemcache
    compressedValue = zlib.compress(bytesValue)
    
    # delete previous entity with the given key
    # in order to conserve available memcache space.
    gaeDelete(key)
    
    valueSize = len(compressedValue)
    if valueSize < GAE_MEMCACHE_MAX_ITEM_SIZE: # only one segment
        return gaeMemcache.set(key, compressedValue, time=GAE_EXPIRE_WEEK)
    # else store in separate chunk shards
    chunkKeys = []
    for pos in range(0, valueSize, GAE_MEMCACHE_MAX_ITEM_SIZE):
        # TODO: use memcache.set_multi() for speedup, but don't forget
        # about batch operation size limit (32Mb currently).
        chunk = compressedValue[pos:pos + GAE_MEMCACHE_MAX_ITEM_SIZE]
        
        # the pos is used for reliable distinction between chunk keys.
        # the random suffix is used as a counter-measure for distinction
        # between different values, which can be simultaneously written
        # under the same key.
        chunkKey = '%s%d%d' % (key, pos, random.getrandbits(31))
        isSuccess = gaeMemcache.set(chunkKey, chunk, time=GAE_EXPIRE_WEEK)
        if not isSuccess:
            return False
        chunkKeys.append(chunkKey)
    return gaeMemcache.set(key, chunkKeys, time=GAE_EXPIRE_WEEK)


