'''
Created on Oct 20, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import zipfile, tarfile, os, io, errno, base64, gzip, zlib, re, struct, random, time
from lxml import etree
from arelle import XmlUtil
from arelle import PackageManager
from arelle.UrlUtil import isHttpUrl
from operator import indexOf
pluginClassMethods = None # dynamic import

archivePathSeparators = (".zip" + os.sep, ".tar.gz" + os.sep, ".eis" + os.sep, ".xml" + os.sep, ".xfd" + os.sep, ".frm" + os.sep, '.taxonomyPackage.xml' + os.sep) + \
                        ((".zip/", ".tar.gz/", ".eis/", ".xml/", ".xfd/", ".frm/", '.taxonomyPackage.xml/') if os.sep != "/" else ()) #acomodate windows and http styles

archiveFilenameSuffixes = {".zip", ".tar.gz", ".eis", ".xml", ".xfd", ".frm"}

POST_UPLOADED_ZIP = os.sep + "POSTupload.zip"
SERVER_WEB_CACHE = os.sep + "_HTTP_CACHE"

XMLdeclaration = re.compile(r"<\?xml[^><\?]*\?>", re.DOTALL)

TAXONOMY_PACKAGE_FILE_NAMES = ('.taxonomyPackage.xml', 'catalog.xml') # pre-PWD packages

def openFileSource(filename, cntlr=None, sourceZipStream=None, checkIfXmlIsEis=False, reloadCache=False, base=None, sourceFileSource=None):
    if sourceZipStream:
        filesource = FileSource(POST_UPLOADED_ZIP, cntlr)
        filesource.openZipStream(sourceZipStream)
        if filename:
            filesource.select(filename)
        return filesource
    else:
        if cntlr and base:
            filename = cntlr.webCache.normalizeUrl(filename, base=base)
        archivepathSelection = archiveFilenameParts(filename, checkIfXmlIsEis)
        if archivepathSelection is not None:
            archivepath = archivepathSelection[0]
            selection = archivepathSelection[1]
            if sourceFileSource and sourceFileSource.isArchive and selection in sourceFileSource.dir and selection.endswith(".zip"):
                filesource = FileSource(filename, cntlr)
                selection = None
            else:
                filesource = FileSource(archivepath, cntlr, checkIfXmlIsEis)
            filesource.open(reloadCache)
            if selection:
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

class FileNamedBytesIO(io.BytesIO):  # provide Bytes IO in memory but behave as a fileName string
    def __init__(self, fileName, *args, **kwargs):
        super(FileNamedBytesIO, self).__init__(*args, **kwargs)
        self.fileName = fileName

    def close(self):
        del self.fileName
        super(FileNamedBytesIO, self).close()

    def __str__(self):
        return self.fileName

class ArchiveFileIOError(IOError):
    def __init__(self, fileSource, errno, fileName):
        super(ArchiveFileIOError, self).__init__(errno,
                                                 _("Archive {}").format(fileSource.url),
                                                 fileName)
        self.fileName = fileName
        self.url = fileSource.url

class FileSource:
    def __init__(self, url, cntlr=None, checkIfXmlIsEis=False):
        global pluginClassMethods
        if pluginClassMethods is None: # dynamic import
            from arelle.PluginManager import pluginClassMethods
        self.url = str(url)  # allow either string or FileNamedStringIO
        self.baseIsHttp = isHttpUrl(self.url)
        self.cntlr = cntlr
        self.type = self.url.lower()[-7:]
        self.isTarGz = self.type == ".tar.gz"
        if not self.isTarGz:
            self.type = self.type[3:]
        self.isZip = self.type == ".zip"
        self.isZipBackslashed = False # windows style backslashed paths
        self.isEis = self.type == ".eis"
        self.isXfd = (self.type == ".xfd" or self.type == ".frm")
        self.isRss = (self.type == ".rss" or self.url.endswith(".rss.xml"))
        self.isInstalledTaxonomyPackage = False
        self.isOpen = False
        self.fs = None
        self.selection = None
        self.filesDir = None
        self.referencedFileSources = {}  # archive file name, fileSource object
        self.taxonomyPackage = None # taxonomy package
        self.mappedPaths = None  # remappings of path segments may be loaded by taxonomyPackage manifest

        # for SEC xml files, check if it's an EIS anyway
        if (not (self.isZip or self.isEis or self.isXfd or self.isRss) and
            self.type == ".xml"):
            if os.path.split(self.url)[-1] in TAXONOMY_PACKAGE_FILE_NAMES:
                self.isInstalledTaxonomyPackage = True
            elif checkIfXmlIsEis:
                try:
                    file = open(self.cntlr.webCache.getfilename(self.url), 'r', errors='replace')
                    l = file.read(256) # may have comments before first element
                    file.close()
                    if re.match(r"\s*(<[?]xml[^?]+[?]>)?\s*(<!--.*-->\s*)*<(cor[a-z]*:|sdf:)?edgarSubmission", l):
                        self.isEis = True
                except EnvironmentError as err:
                    if self.cntlr:
                        self.cntlr.addToLog(_("[{0}] {1}").format(type(err).__name__, err))
                    pass

    def logError(self, err):
        if self.cntlr:
            self.cntlr.addToLog(_("[{0}] {1}").format(type(err).__name__, err))

    def open(self, reloadCache=False):
        if not self.isOpen:
            if (self.isZip or self.isTarGz or self.isEis or self.isXfd or self.isRss or self.isInstalledTaxonomyPackage) and self.cntlr:
                self.basefile = self.cntlr.webCache.getfilename(self.url, reload=reloadCache)
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
                self.loadTaxonomyPackageMappings()

    def loadTaxonomyPackageMappings(self, errors=[], expectTaxonomyPackage=None):
        if not self.mappedPaths and (self.taxonomyPackageMetadataFiles or expectTaxonomyPackage):
            if PackageManager.validateTaxonomyPackage(self.cntlr, self, errors=errors):
                metadata = self.baseurl + os.sep + self.taxonomyPackageMetadataFiles[0]
                self.taxonomyPackage = PackageManager.parsePackage(self.cntlr, self, metadata,
                                                                   os.sep.join(os.path.split(metadata)[:-1]) + os.sep,
                                                                   errors=errors)
                self.mappedPaths = self.taxonomyPackage.get("remappings")

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
        self.referencedFileSources.clear()
        if self.isZip and self.isOpen:
            self.fs.close()
            self.fs = None
            self.isOpen = False
            self.isZip = self.isZipBackslashed = False
        if self.isTarGz and self.isOpen:
            self.fs.close()
            self.fs = None
            self.isOpen = False
            self.isTarGz = False
        if self.isEis and self.isOpen:
            self.eisDocument.getroot().clear() # unlink nodes
            self.eisDocument = None
            self.isOpen = False
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
        return bool(self.isZip and self.taxonomyPackageMetadataFiles) or self.isInstalledTaxonomyPackage

    @property
    def taxonomyPackageMetadataFiles(self):
        for f in (self.dir or []):
            if f.endswith("/META-INF/taxonomyPackage.xml"): # must be in a sub directory in the zip
                return [f]  # standard package
        return [f for f in (self.dir or []) if os.path.split(f)[-1] in TAXONOMY_PACKAGE_FILE_NAMES]

    def isInArchive(self,filepath, checkExistence=False):
        archiveFileSource = self.fileSourceContainingFilepath(filepath)
        if archiveFileSource is None:
            return False
        if checkExistence:
            archiveFileName = filepath[len(archiveFileSource.basefile) + 1:].replace("\\", "/") # must be / file separators
            return archiveFileName in archiveFileSource.dir
        return True # True only means that the filepath maps into the archive, not that the file is really there

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

    def file(self, filepath, binary=False, stripDeclaration=False, encoding=None):
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
                    if archiveFileSource.isZipBackslashed:
                        f = archiveFileName.replace("/", "\\")
                    else:
                        f = archiveFileName.replace("\\","/")
                    b = archiveFileSource.fs.read(f)
                    if binary:
                        return (io.BytesIO(b), )
                    if encoding is None:
                        encoding = XmlUtil.encoding(b)
                    if stripDeclaration:
                        b = stripDeclarationBytes(b)
                    return (FileNamedTextIOWrapper(filepath, io.BytesIO(b), encoding=encoding),
                            encoding)
                except KeyError:
                    raise ArchiveFileIOError(self, errno.ENOENT, archiveFileName)
            elif archiveFileSource.isTarGz:
                try:
                    fh = archiveFileSource.fs.extractfile(archiveFileName)
                    b = fh.read()
                    fh.close() # doesn't seem to close properly using a with construct
                    if binary:
                        return (io.BytesIO(b), )
                    if encoding is None:
                        encoding = XmlUtil.encoding(b)
                    if stripDeclaration:
                        b = stripDeclarationBytes(b)
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
                            if encoding is None:
                                encoding = XmlUtil.encoding(b, default="latin-1")
                            return (io.TextIOWrapper(io.BytesIO(b), encoding=encoding),
                                    encoding)
                raise ArchiveFileIOError(self, errno.ENOENT, archiveFileName)
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
                            if encoding is None:
                                encoding = XmlUtil.encoding(b, default="latin-1")
                            return (io.TextIOWrapper(io.BytesIO(b), encoding=encoding),
                                    encoding)
                raise ArchiveFileIOError(self, errno.ENOENT, archiveFileName)
            elif archiveFileSource.isInstalledTaxonomyPackage:
                # remove TAXONOMY_PACKAGE_FILE_NAME from file path
                if filepath.startswith(archiveFileSource.basefile):
                    l = len(archiveFileSource.basefile)
                    for f in TAXONOMY_PACKAGE_FILE_NAMES:
                        if filepath[l - len(f):l] == f:
                            filepath = filepath[0:l - len(f) - 1] + filepath[l:]
                            break
        for pluginMethod in pluginClassMethods("FileSource.File"): #custom overrides for decription, etc
            fileResult = pluginMethod(self.cntlr, filepath, binary, stripDeclaration)
            if fileResult is not None:
                return fileResult
        if binary:
            return (openFileStream(self.cntlr, filepath, 'rb'), )
        elif encoding:
            return (openFileStream(self.cntlr, filepath, 'rt', encoding=encoding), )
        else:
            return openXmlFileStream(self.cntlr, filepath, stripDeclaration)

    def exists(self, filepath):
        archiveFileSource = self.fileSourceContainingFilepath(filepath)
        if archiveFileSource is not None:
            if filepath.startswith(archiveFileSource.basefile):
                archiveFileName = filepath[len(archiveFileSource.basefile) + 1:]
            else: # filepath.startswith(self.baseurl)
                archiveFileName = filepath[len(archiveFileSource.baseurl) + 1:]
            if (archiveFileSource.isZip or archiveFileSource.isTarGz or
                archiveFileSource.isEis or archiveFileSource.isXfd or
                archiveFileSource.isRss or self.isInstalledTaxonomyPackage):
                return archiveFileName.replace("\\","/") in archiveFileSource.dir
        for pluginMethod in pluginClassMethods("FileSource.Exists"): #custom overrides for decription, etc
            existsResult = pluginMethod(self.cntlr, filepath)
            if existsResult is not None:
                return existsResult
        # assume it may be a plain ordinary file path
        return os.path.exists(filepath)

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
                f = zipinfo.filename
                if '\\' in f:
                    self.isZipBackslashed = True
                    f = f.replace("\\", "/")
                files.append(f)
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

    def basedUrl(self, selection):
        if isHttpUrl(selection) or os.path.isabs(selection):
            return selection
        elif self.baseIsHttp or os.sep == '/':
            return self.baseurl + "/" + selection
        else: # MSFT os.sep == '\\'
            return self.baseurl + os.sep + selection.replace("/", os.sep)

    def select(self, selection):
        self.selection = selection
        if not selection:
            self.url = None
        else:
            if isinstance(selection, list): # json list
                self.url = [self.basedUrl(s) for s in selection]
            # elif isinstance(selection, dict): # json objects
            else:
                self.url = self.basedUrl(selection)

def openFileStream(cntlr, filepath, mode='r', encoding=None):
    if PackageManager.isMappedUrl(filepath):
        filepath = PackageManager.mappedUrl(filepath)
    elif isHttpUrl(filepath) and cntlr and hasattr(cntlr, "modelManager"): # may be called early in initialization for PluginManager
        filepath = cntlr.modelManager.disclosureSystem.mappedUrl(filepath)
    if archiveFilenameParts(filepath): # file is in an archive
        return openFileSource(filepath, cntlr).file(filepath, binary='b' in mode, encoding=encoding)[0]
    if isHttpUrl(filepath) and cntlr:
        _cacheFilepath = cntlr.webCache.getfilename(filepath, normalize=True) # normalize is separate step in ModelDocument retrieval, combined here
        if _cacheFilepath is None:
            raise IOError(_("Unable to open file: {0}.").format(filepath))
        filepath = _cacheFilepath
    if not filepath and cntlr:
        raise IOError(_("Unable to open file: \"{0}\".").format(filepath))
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
    encoding = XmlUtil.encoding(hdrBytes,
                                default=cntlr.modelManager.disclosureSystem.defaultXmlEncoding
                                        if cntlr else 'utf-8')
    # encoding default from disclosure system could be None
    if encoding.lower() in ('utf-8','utf8','utf-8-sig') and (cntlr is None or not cntlr.isGAE) and not stripDeclaration:
        text = None
        openedFileStream.close()
    else:
        openedFileStream.seek(0)
        text = openedFileStream.read().decode(encoding or 'utf-8')
        openedFileStream.close()
        # allow filepath to close
    # this may not be needed for Mac or Linux, needs confirmation!!!
    if text is None:  # ok to read as utf-8
        return io.open(filepath, 'rt', encoding=encoding or 'utf-8'), encoding
    else:
        if stripDeclaration:
            # strip XML declaration
            xmlDeclarationMatch = XMLdeclaration.search(text)
            if xmlDeclarationMatch: # remove it for lxml
                start,end = xmlDeclarationMatch.span()
                text = text[0:start] + text[end:]
        return (FileNamedStringIO(filepath, initial_value=text), encoding)

def stripDeclarationBytes(xml):
    xmlStart = xml[0:120]
    indexOfDeclaration = xmlStart.find(b"<?xml")
    if indexOfDeclaration >= 0:
        indexOfDeclarationEnd = xmlStart.find(b"?>", indexOfDeclaration)
        if indexOfDeclarationEnd >= 0:
            return xml[indexOfDeclarationEnd + 2:]
    return xml

def saveFile(cntlr, filepath, contents, encoding=None, mode='wt'):
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
        _dirpath = os.path.dirname(filepath)
        if not os.path.exists(_dirpath): # directory must exist before io.open
            os.makedirs(_dirpath)
        with io.open(filepath, mode, encoding=(encoding or 'utf-8')) as f:
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
