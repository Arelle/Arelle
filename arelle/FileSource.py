'''
Created on Oct 20, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import zipfile, os, io, base64, gzip, zlib, re, struct
from lxml import etree
from arelle import XmlUtil

archivePathSeparators = (".zip" + os.sep, ".eis" + os.sep, ".xml" + os.sep, ".xfd" + os.sep, ".frm" + os.sep) + \
                        ((".zip/", ".eis/", ".xml/", ".xfd/", ".frm/") if os.sep != "/" else ()) #acomodate windows and http styles

XMLdeclaration = re.compile(r"<\?xml[^><\?]*\?>", re.DOTALL)

def openFileSource(filename, cntlr=None, sourceZipStream=None, checkIfXmlIsEis=False):
    if sourceZipStream:
        filesource = FileSource("POSTupload.zip", cntlr)
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
        if (archiveSep in filename and
            (not archiveSep.startswith(".xml") or checkIfXmlIsEis)):
            filenameParts = filename.partition(archiveSep)
            fileDir = filenameParts[0] + archiveSep[:-1]
            if os.path.isfile(fileDir): # be sure it is not a directory name
                return (fileDir, filenameParts[2])
    return None

class FileNamedStringIO(io.StringIO):  # provide string IO in memory but behave as a fileName string
    def __init__(self, fileName):
        super(FileNamedStringIO, self).__init__()
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
        self.baseIsHttp = self.url.startswith("http://")
        self.cntlr = cntlr
        self.type = self.url.lower()[-4:]
        self.isZip = self.type == ".zip"
        self.isEis = self.type == ".eis"
        self.isXfd = (self.type == ".xfd" or self.type == ".frm")
        self.isRss = (self.type == ".rss" or self.url.endswith(".rss.xml"))
        self.isOpen = False
        self.fs = None
        self.selection = None
        self.filesDir = None
        self.referencedFileSources = {}  # archive file name, fileSource object
        
        # for SEC xml files, check if it's an EIS anyway
        if (not (self.isZip or self.isEis or self.isXfd or self.isRss) and
            self.type == ".xml" and
            checkIfXmlIsEis):
            match = b'<?xml version="1.0" ?><cor:edgarSubmission'
            try:
                file = open(self.cntlr.webCache.getfilename(self.url), 'rb')
                l = file.read(len(match))
                file.close()
                if l == match:
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
            if (self.isZip or self.isEis or self.isXfd or self.isRss) and self.cntlr:
                self.basefile = self.cntlr.webCache.getfilename(self.url)
            else:
                self.basefile = self.url
            self.baseurl = self.url # url gets changed by selection
            if not self.basefile:
                return  # an error should have been logged
            if self.isZip:
                self.fs = zipfile.ZipFile(self.basefile, mode="r")
                self.isOpen = True    
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
                        file = io.StringIO(initial_value=buf.decode("utf-8"))
                        self.eisDocument = etree.parse(file)
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
        self.filesDir = None
        
    @property
    def isArchive(self):
        return self.isZip or self.isEis or self.isXfd
    
    def isInArchive(self,filepath):
        return self.fileSourceContainingFilepath(filepath) is not None
    
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
    
    def file(self,filepath):
        archiveFileSource = self.fileSourceContainingFilepath(filepath)
        if archiveFileSource is not None:
            if filepath.startswith(archiveFileSource.basefile):
                archiveFileName = filepath[len(archiveFileSource.basefile) + 1:]
            else: # filepath.startswith(self.baseurl)
                archiveFileName = filepath[len(archiveFileSource.baseurl) + 1:]
            if archiveFileSource.isZip:
                b = archiveFileSource.fs.read(archiveFileName.replace("\\","/"))
                encoding = XmlUtil.encoding(b)
                return (io.TextIOWrapper(io.BytesIO(b), encoding=encoding), 
                        encoding)
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
                            encoding = XmlUtil.encoding(b, default="latin-1")
                            return (io.TextIOWrapper(io.BytesIO(b), encoding=encoding), 
                                    encoding)
                raise ArchiveFileIOError(self, archiveFileName)
        # check encoding
        with open(filepath, 'rb') as fb:
            hdrBytes = fb.read(512)
            encoding = XmlUtil.encoding(hdrBytes)
            if encoding.lower() in ('utf-8','utf8'):
                text = None
            else:
                fb.seek(0)
                text = fb.read().decode(encoding)
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
            return (io.StringIO(initial_value=text), encoding)

    
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
        return self.filesDir
    
    def select(self, selection):
        self.selection = selection
        if selection.startswith("http://") or os.path.isabs(selection):
            self.url = selection
        elif self.baseIsHttp or os.sep == '/':
            self.url = self.baseurl + "/" + selection
        else: # MSFT os.sep == '\\'
            self.url = self.baseurl + os.sep + selection.replace("/", os.sep)
