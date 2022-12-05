'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations
from typing import IO, TYPE_CHECKING, Any, Union, cast
import zipfile, tarfile, os, io, errno, base64, gzip, zlib, re, struct, random
from lxml import etree
from arelle import XmlUtil
from arelle import PackageManager
from arelle.UrlUtil import isHttpUrl
from arelle.typing import TypeGetText
import arelle.PluginManager


_: TypeGetText

if TYPE_CHECKING:
    from arelle.Cntlr import Cntlr
    from _typeshed import SupportsRead


archivePathSeparators = (".zip" + os.sep, ".tar.gz" + os.sep, ".eis" + os.sep, ".xml" + os.sep, ".xfd" + os.sep, ".frm" + os.sep, '.taxonomyPackage.xml' + os.sep) + \
                        ((".zip/", ".tar.gz/", ".eis/", ".xml/", ".xfd/", ".frm/", '.taxonomyPackage.xml/') if os.sep != "/" else ()) #acomodate windows and http styles

archiveFilenameSuffixes = {".zip", ".tar.gz", ".eis", ".xml", ".xfd", ".frm"}

POST_UPLOADED_ZIP = os.sep + "POSTupload.zip"
SERVER_WEB_CACHE = os.sep + "_HTTP_CACHE"

XMLdeclaration = re.compile(r"<\?xml[^><\?]*\?>", re.DOTALL)

TAXONOMY_PACKAGE_FILE_NAMES = ('.taxonomyPackage.xml', 'catalog.xml') # pre-PWD packages

def openFileSource(
    filename: str | None,
    cntlr: Cntlr | None = None,
    sourceZipStream: str | None = None,
    checkIfXmlIsEis: bool = False,
    reloadCache: bool = False,
    base: str | None = None,
    sourceFileSource: FileSource | None = None,
) -> FileSource:
    if sourceZipStream:
        filesource = FileSource(POST_UPLOADED_ZIP, cntlr)
        filesource.openZipStream(sourceZipStream)
        if filename:
            filesource.select(filename)
        return filesource
    else:
        if cntlr and base:
            filename = cntlr.webCache.normalizeUrl(filename, base=base) # type: ignore[no-untyped-call]

        assert filename is not None
        archivepathSelection = archiveFilenameParts(filename, checkIfXmlIsEis)
        if archivepathSelection is not None:
            archivepath = archivepathSelection[0]
            selection: str | None = archivepathSelection[1]

            assert selection is not None
            if (
                sourceFileSource is not None
                and sourceFileSource.dir is not None
                and sourceFileSource.isArchive
                and selection in sourceFileSource.dir
                and selection.endswith(".zip")
            ):
                assert cntlr is not None
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

def archiveFilenameParts(filename: str | None, checkIfXmlIsEis: bool = False) -> tuple[str, str] | None:
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
    def __init__(self, fileName: str, *args: Any, **kwargs: Any) -> None:
        super(FileNamedStringIO, self).__init__(*args, **kwargs)
        self.fileName = fileName

    def close(self) -> None:
        del self.fileName
        super(FileNamedStringIO, self).close()

    def __str__(self) -> str:
        return self.fileName

class FileNamedTextIOWrapper(io.TextIOWrapper):  # provide string IO in memory but behave as a fileName string
    def __init__(self, fileName: str, *args: Any, **kwargs: Any):
        super(FileNamedTextIOWrapper, self).__init__(*args, **kwargs)
        self.fileName = fileName

    def __str__(self) -> str:
        return self.fileName

class FileNamedBytesIO(io.BytesIO):  # provide Bytes IO in memory but behave as a fileName string
    def __init__(self, fileName: str, *args: Any, **kwargs: Any) -> None:
        super(FileNamedBytesIO, self).__init__(*args, **kwargs)
        self.fileName = fileName

    def close(self) -> None:
        del self.fileName
        super(FileNamedBytesIO, self).close()

    def __str__(self) -> str:
        return self.fileName

class ArchiveFileIOError(IOError):
    def __init__(self, fileSource: FileSource, errno: int, fileName: str) -> None:
        super(ArchiveFileIOError, self).__init__(errno,
                                                 _("Archive {}").format(fileSource.url),
                                                 fileName)
        self.fileName = fileName
        self.url = fileSource.url

class FileSource:

    eisDocument: etree._ElementTree | None
    fs: zipfile.ZipFile | tarfile.TarFile | io.StringIO | None
    filesDir: list[str] | None
    referencedFileSources: dict[str, FileSource]
    rssDocument: etree._ElementTree | None
    selection: str | list[str] | None
    url: str | list[str] | None
    basefile: str | list[str] | None
    xfdDocument: etree._ElementTree | None

    def __init__(self, url: str, cntlr: Cntlr | None = None, checkIfXmlIsEis: bool = False) -> None:
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
                    assert self.cntlr is not None
                    _filename = self.cntlr.webCache.getfilename(self.url)
                    assert _filename is not None
                    file = open(_filename, 'r', errors='replace')
                    l = file.read(256) # may have comments before first element
                    file.close()
                    if re.match(r"\s*(<[?]xml[^?]+[?]>)?\s*(<!--.*-->\s*)*<(cor[a-z]*:|sdf:)?edgarSubmission", l):
                        self.isEis = True
                except EnvironmentError as err:
                    if self.cntlr:
                        self.cntlr.addToLog(_("[{0}] {1}").format(type(err).__name__, err))
                    pass

    def logError(self, err: Exception) -> None:
        if self.cntlr:
            self.cntlr.addToLog(_("[{0}] {1}").format(type(err).__name__, err))

    def open(self, reloadCache: bool = False) -> None:
        if not self.isOpen:
            if (self.isZip or self.isTarGz or self.isEis or self.isXfd or self.isRss or self.isInstalledTaxonomyPackage) and self.cntlr:
                assert isinstance(self.url, str)
                self.basefile = self.cntlr.webCache.getfilename(self.url, reload=reloadCache)
            else:
                self.basefile = self.url
            self.baseurl = self.url # url gets changed by selection
            if not self.basefile:
                return  # an error should have been logged
            if self.isZip:
                try:
                    assert isinstance(self.basefile, str)
                    fileStream = openFileStream(self.cntlr, self.basefile, 'rb')
                    self.fs = zipfile.ZipFile(fileStream, mode="r")
                    self.isOpen = True
                except EnvironmentError as err:
                    self.logError(err)
                    pass
            elif self.isTarGz:
                try:
                    assert isinstance(self.basefile, str)
                    self.fs = tarfile.open(self.basefile, "r:gz")
                    self.isOpen = True
                except EnvironmentError as err:
                    self.logError(err)
                    pass
            elif self.isEis:
                # check first line of file
                buf = b''
                try:
                    assert isinstance(self.basefile, str)
                    file: io.BufferedReader | io.BytesIO | io.StringIO | None = open(self.basefile, 'rb')
                    assert isinstance(file, (io.BufferedReader, io.BytesIO))
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
                        _str = buf.decode(XmlUtil.encoding(buf))
                        endEncoding = _str.index("?>", 0, 128)
                        if endEncoding > 0:
                            _str = _str[endEncoding+2:]
                        _file = io.StringIO(initial_value=_str)
                        parser = etree.XMLParser(recover=True, huge_tree=True)
                        self.eisDocument = etree.parse(_file, parser=parser)
                        _file.close()
                        self.isOpen = True
                    except EnvironmentError as err:
                        self.logError(err)
                        return # provide error message later
                    except etree.LxmlError as err:
                        self.logError(err)
                        return # provide error message later

            elif self.isXfd:
                # check first line of file
                assert isinstance(self.basefile, str)
                file = open(self.basefile, 'rb')
                firstline = file.readline()
                if firstline.startswith(b"application/x-xfdl;content-encoding=\"asc-gzip\""):
                    # file has been gzipped
                    base64input = file.read(-1)
                    file.close()
                    file = None

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
                    assert file is not None
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
                    assert isinstance(self.basefile, str)
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

    def loadTaxonomyPackageMappings(self, errors: list[str] = [], expectTaxonomyPackage: bool = False) -> None:
        if not self.mappedPaths and (self.taxonomyPackageMetadataFiles or expectTaxonomyPackage):
            if PackageManager.validateTaxonomyPackage(self.cntlr, self, errors=errors):
                assert isinstance(self.baseurl, str)
                metadata = self.baseurl + os.sep + self.taxonomyPackageMetadataFiles[0]
                self.taxonomyPackage = PackageManager.parsePackage(self.cntlr, self, metadata,  # type: ignore[no-untyped-call]
                                                                   os.sep.join(os.path.split(metadata)[:-1]) + os.sep,
                                                                   errors=errors)

                assert self.taxonomyPackage is not None
                self.mappedPaths = self.taxonomyPackage.get("remappings")

    def openZipStream(self, sourceZipStream: str) -> None:
        if not self.isOpen:
            assert isinstance(self.url, str)
            self.basefile = self.url
            self.baseurl = self.url # url gets changed by selection
            self.fs = zipfile.ZipFile(sourceZipStream, mode="r")
            self.isOpen = True

    def close(self) -> None:
        if self.referencedFileSources:
            for referencedFileSource in self.referencedFileSources.values():
                referencedFileSource.close()
        self.referencedFileSources.clear()
        if self.isZip and self.isOpen:
            assert self.fs is not None
            self.fs.close()
            self.fs = None
            self.isOpen = False
            self.isZip = self.isZipBackslashed = False
        if self.isTarGz and self.isOpen:
            assert self.fs is not None
            self.fs.close()
            self.fs = None
            self.isOpen = False
            self.isTarGz = False
        if self.isEis and self.isOpen:
            assert self.eisDocument is not None
            self.eisDocument.getroot().clear() # unlink nodes
            self.eisDocument = None
            self.isOpen = False
            self.isEis = False
        if self.isXfd and self.isOpen:
            assert self.xfdDocument is not None
            self.xfdDocument.getroot().clear() # unlink nodes
            self.xfdDocument = None
            self.isXfd = False
        if self.isRss and self.isOpen:
            assert self.rssDocument is not None
            self.rssDocument.getroot().clear() # unlink nodes
            self.rssDocument = None
            self.isRss = False
        if self.isInstalledTaxonomyPackage:
            self.isInstalledTaxonomyPackage = False
            self.isOpen = False
        self.filesDir = None

    @property
    def isArchive(self) -> bool:
        return self.isZip or self.isTarGz or self.isEis or self.isXfd or self.isInstalledTaxonomyPackage

    @property
    def isTaxonomyPackage(self) -> bool:
        return bool(self.isZip and self.taxonomyPackageMetadataFiles) or self.isInstalledTaxonomyPackage

    @property
    def taxonomyPackageMetadataFiles(self) -> list[str]:
        for f in (self.dir or []):
            if f.endswith("/META-INF/taxonomyPackage.xml"): # must be in a sub directory in the zip
                return [f]  # standard package
        return [f for f in (self.dir or []) if os.path.split(f)[-1] in TAXONOMY_PACKAGE_FILE_NAMES]

    def isInArchive(self, filepath: str | None, checkExistence: bool = False) -> bool:
        archiveFileSource = self.fileSourceContainingFilepath(filepath)
        if archiveFileSource is None:
            return False
        if checkExistence:
            assert isinstance(filepath, str)
            assert isinstance(archiveFileSource.basefile, str)
            assert archiveFileSource.dir is not None
            archiveFileName = filepath[len(archiveFileSource.basefile) + 1:].replace("\\", "/") # must be / file separators
            return archiveFileName in archiveFileSource.dir
        return True # True only means that the filepath maps into the archive, not that the file is really there

    def isMappedUrl(self, url: str) -> bool:
        if self.mappedPaths is not None:
            return any(url.startswith(mapFrom)
                       for mapFrom in self.mappedPaths)
        return False

    def mappedUrl(self, url: str) -> str:
        if self.mappedPaths:
            for mapFrom, mapTo in self.mappedPaths.items():
                if url.startswith(mapFrom):
                    url = mapTo + url[len(mapFrom):]
                    break
        return url

    def fileSourceContainingFilepath(self, filepath: str | None) -> FileSource | None:
        if self.isOpen:
            # archiveFiles = self.dir
            ''' change to return file source if archive would be in there (vs actually is in archive)
            if ((filepath.startswith(self.basefile) and
                 filepath[len(self.basefile) + 1:] in archiveFiles) or
                (filepath.startswith(self.baseurl) and
                 filepath[len(self.baseurl) + 1:] in archiveFiles)):
                return self
            '''
            assert isinstance(filepath, str)
            assert isinstance(self.basefile, str)
            assert isinstance(self.baseurl, str)
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

    def file(
        self,
        filepath: str,
        binary: bool = False,
        stripDeclaration: bool = False,
        encoding: str | None = None,
    ) -> (
            tuple[io.BytesIO | IO[Any]]
            | tuple[FileNamedTextIOWrapper, str | None]
            | tuple[io.TextIOWrapper, str | None]
        ):
        '''
            for text, return a tuple of (open file handle, encoding)
            for binary, return a tuple of (open file handle, )
        '''
        archiveFileSource = self.fileSourceContainingFilepath(filepath)
        if archiveFileSource is not None:
            assert isinstance(archiveFileSource.basefile, str)

            if filepath.startswith(archiveFileSource.basefile):
                archiveFileName = filepath[len(archiveFileSource.basefile) + 1:]
            else: # filepath.startswith(self.baseurl)
                assert isinstance(archiveFileSource.baseurl, str)
                archiveFileName = filepath[len(archiveFileSource.baseurl) + 1:]
            if archiveFileSource.isZip:
                try:
                    if archiveFileSource.isZipBackslashed:
                        f = archiveFileName.replace("/", "\\")
                    else:
                        f = archiveFileName.replace("\\","/")

                    assert isinstance(archiveFileSource.fs, zipfile.ZipFile)
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
                    assert isinstance(archiveFileSource.fs, tarfile.TarFile)
                    fh = archiveFileSource.fs.extractfile(archiveFileName)
                    assert fh is not None
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
                    # Note 2022-09-06
                    # The following error is raised by mypy, indicating there's a bug here:
                    # Missing positional argument "fileName"
                    # Not fixing this bug as a part of this PR
                    # Also expecting second argument to be int but is str here
                    raise ArchiveFileIOError(self, archiveFileName) # type: ignore[call-arg, arg-type]
            elif archiveFileSource.isEis:
                assert self.eisDocument is not None
                for docElt in self.eisDocument.iter(tag="{http://www.sec.gov/edgar/common}document"):
                    outfn = docElt.findtext("{http://www.sec.gov/edgar/common}conformedName")
                    if outfn == archiveFileName:
                        b64data = docElt.findtext("{http://www.sec.gov/edgar/common}contents")
                        if b64data:
                            b = base64.b64decode(b64data.encode("latin-1"))
                            # remove BOM codes if present
                            if len(b) > 3 and b[0] == 239 and b[1] == 187 and b[2] == 191:
                                start = 3
                                length = len(b) - 3
                                b = b[start:start + length]
                            else:
                                start = 0
                                length = len(b)
                            if binary:
                                return (io.BytesIO(b), )
                            if encoding is None:
                                encoding = XmlUtil.encoding(b, default="latin-1")
                            return (io.TextIOWrapper(io.BytesIO(b), encoding=encoding),
                                    encoding)
                raise ArchiveFileIOError(self, errno.ENOENT, archiveFileName)
            elif archiveFileSource.isXfd:
                assert archiveFileSource.xfdDocument is not None
                for data in archiveFileSource.xfdDocument.iter(tag="data"):
                    outfn = data.findtext("filename")
                    if outfn == archiveFileName:
                        b64data = data.findtext("mimedata")
                        if b64data:
                            b = base64.b64decode(b64data.encode("latin-1"))
                            # remove BOM codes if present
                            if len(b) > 3 and b[0] == 239 and b[1] == 187 and b[2] == 191:
                                start = 3
                                length = len(b) - 3
                                b = b[start:start + length]
                            else:
                                start = 0
                                length = len(b)
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
                    assert archiveFileSource.basefile is not None
                    l = len(archiveFileSource.basefile)
                    for f in TAXONOMY_PACKAGE_FILE_NAMES:
                        if filepath[l - len(f):l] == f:
                            filepath = filepath[0:l - len(f) - 1] + filepath[l:]
                            break

        # custom overrides for decription, etc
        for pluginMethod in arelle.PluginManager.pluginClassMethods("FileSource.File"):
            fileResult = pluginMethod(self.cntlr, filepath, binary, stripDeclaration)
            if fileResult is not None:
                return fileResult # type: ignore[no-any-return]
        if binary:
            return (openFileStream(self.cntlr, filepath, 'rb'), )
        elif encoding:
            return (openFileStream(self.cntlr, filepath, 'rt', encoding=encoding), )
        else:
            return openXmlFileStream(self.cntlr, filepath, stripDeclaration)

    def exists(self, filepath: str) -> bool:
        archiveFileSource = self.fileSourceContainingFilepath(filepath)
        if archiveFileSource is not None:
            # Note 2022-09-12
            # Can we handle this with an assert? Feels like we need to check if this is a str when
            # also testing for startswith
            if isinstance(archiveFileSource.basefile, str) and filepath.startswith(archiveFileSource.basefile):
                archiveFileName = filepath[len(archiveFileSource.basefile) + 1:]
            else: # filepath.startswith(self.baseurl)
                assert isinstance(archiveFileSource.baseurl, str)
                archiveFileName = filepath[len(archiveFileSource.baseurl) + 1:]
            if (archiveFileSource.isZip or archiveFileSource.isTarGz or
                archiveFileSource.isEis or archiveFileSource.isXfd or
                archiveFileSource.isRss or self.isInstalledTaxonomyPackage):
                assert archiveFileSource.dir is not None
                return archiveFileName.replace("\\","/") in archiveFileSource.dir

        # custom overrides for decription, etc
        for pluginMethod in arelle.PluginManager.pluginClassMethods("FileSource.Exists"):
            existsResult = pluginMethod(self.cntlr, filepath)
            if existsResult is not None:
                return cast(bool, existsResult)
        # assume it may be a plain ordinary file path
        return os.path.exists(filepath)

    @property
    def dir(self) -> list[str] | None:
        self.open()
        if not self.isOpen:
            return None
        elif self.filesDir is not None:
            return self.filesDir
        elif self.isZip:
            files: list[str] = []

            assert isinstance(self.fs, zipfile.ZipFile)
            for zipinfo in self.fs.infolist():
                f = zipinfo.filename
                if '\\' in f:
                    self.isZipBackslashed = True
                    f = f.replace("\\", "/")
                files.append(f)
            self.filesDir = files
        elif self.isTarGz:
            assert isinstance(self.fs, tarfile.TarFile)
            self.filesDir = self.fs.getnames()
        elif self.isEis:
            files = []
            assert self.eisDocument is not None
            for docElt in self.eisDocument.iter(tag="{http://www.sec.gov/edgar/common}document"):
                outfn = docElt.findtext("{http://www.sec.gov/edgar/common}conformedName")
                if outfn:
                    files.append(outfn)
            self.filesDir = files
        elif self.isXfd:
            files = []
            assert self.xfdDocument is not None
            for data in self.xfdDocument.iter(tag="data"):
                outfn = data.findtext("filename")
                if outfn:
                    if len(outfn) > 2 and outfn[0].isalpha() and \
                        outfn[1] == ':' and outfn[2] == '\\':
                        continue
                    files.append(outfn)
            self.filesDir = files
        elif self.isRss:
            files = []  # return title, descr, pubdate, linst doc
            edgr = "http://www.sec.gov/Archives/edgar"
            try:
                assert self.rssDocument is not None
                for dsElt in XmlUtil.descendants(self.rssDocument, None, "item"):
                    instDoc = None
                    for instDocElt in XmlUtil.descendants(dsElt, edgr, "xbrlFile"):
                        instDocEltDesc = instDocElt.get("(http://www.sec.gov/Archives/edgar}description")
                        assert instDocEltDesc is not None
                        if instDocEltDesc.endswith("INSTANCE DOCUMENT"):
                            instDoc = instDocElt.get("(http://www.sec.gov/Archives/edgar}url")
                            break
                    if not instDoc:
                        continue
                    # Note 2022-09-17
                    # files is a list[str] but here we are appending a tuple here.
                    # I don't wish to alter any code behaviour so ignoring for now.
                    descendantTitle = XmlUtil.descendant(dsElt, None, "title")
                    descendantCompanyName = XmlUtil.descendant(dsElt, edgr, "companyName")
                    descendantFormType = XmlUtil.descendant(dsElt, edgr, "formType")
                    descendantFilingDate = XmlUtil.descendant(dsElt, edgr, "filingDate")
                    descendantCikNumber = XmlUtil.descendant(dsElt, edgr, "cikNumber")
                    descendantPeriod = XmlUtil.descendant(dsElt, edgr, "period")
                    descendantDescription = XmlUtil.descendant(dsElt, None, "description")
                    descendantPubDate = XmlUtil.descendant(dsElt, None, "pubDate")
                    assert descendantTitle is not None
                    assert descendantCompanyName is not None
                    assert descendantFormType is not None
                    assert descendantFilingDate is not None
                    assert descendantCikNumber is not None
                    assert descendantPeriod is not None
                    assert descendantDescription is not None
                    assert descendantPubDate is not None
                    files.append(( # type: ignore[arg-type]
                        XmlUtil.text(descendantTitle),
                        # tooltip
                        "{0}\n {1}\n {2}\n {3}\n {4}".format(
                            XmlUtil.text(descendantCompanyName),
                            XmlUtil.text(descendantFormType),
                            XmlUtil.text(descendantFilingDate),
                            XmlUtil.text(descendantCikNumber),
                            XmlUtil.text(descendantPeriod)),
                        XmlUtil.text(descendantDescription),
                        XmlUtil.text(descendantPubDate),
                        instDoc))
                self.filesDir = files
            except (EnvironmentError,
                    etree.LxmlError) as err:
                pass
        elif self.isInstalledTaxonomyPackage:
            files = []
            assert isinstance(self.baseurl, str)
            baseurlPathLen = len(os.path.dirname(self.baseurl)) + 1
            def packageDirsFiles(dir: str) -> None:
                for file in os.listdir(dir):
                    path = dir + "/" + file   # must have / and not \\ even on windows
                    files.append(path[baseurlPathLen:])
                    if os.path.isdir(path):
                        packageDirsFiles(path)
            packageDirsFiles(self.baseurl[0:baseurlPathLen - 1])
            self.filesDir = files

        return self.filesDir

    def basedUrl(self, selection: str) -> str:
        if isHttpUrl(selection) or os.path.isabs(selection):
            return selection
        elif self.baseIsHttp or os.sep == '/':
            assert isinstance(self.baseurl, str)
            return self.baseurl + "/" + selection
        else: # MSFT os.sep == '\\'
            assert isinstance(self.baseurl, str)
            return self.baseurl + os.sep + selection.replace("/", os.sep)

    def select(self, selection: str | list[str] | None) -> None:
        self.selection = selection
        if not selection:
            self.url = None
        else:
            if isinstance(selection, list): # json list
                self.url = [self.basedUrl(s) for s in selection]
            # elif isinstance(selection, dict): # json objects
            else:
                self.url = self.basedUrl(selection)

def openFileStream(
    cntlr: Cntlr | None, filepath: str, mode: str = "r", encoding: str | None = None
) -> io.BytesIO | IO[Any]:
    filestream: io.IOBase | FileNamedStringIO | None
    if PackageManager.isMappedUrl(filepath):  # type: ignore[no-untyped-call]
        filepath = PackageManager.mappedUrl(filepath)  # type: ignore[no-untyped-call]
    elif (
            isHttpUrl(filepath)
            and cntlr
            and hasattr(cntlr, "modelManager")
        ): # may be called early in initialization for PluginManager
        filepath = cntlr.modelManager.disclosureSystem.mappedUrl(filepath)  # type: ignore[no-untyped-call]
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
            cntlr.webCache.retrieve(cntlr.webCache.cacheFilepathToUrl(filepath),  # type: ignore[no-untyped-call]
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
        encoding = XmlUtil.encoding(hdrBytes)
        openedFileStream.close()
        return io.open(filepath, mode=mode, encoding=encoding)
    else:
        # local file system
        return io.open(filepath, mode=mode, encoding=encoding)

def openXmlFileStream(
    cntlr: Cntlr | None, filepath: str, stripDeclaration: bool = False
) -> tuple[io.TextIOWrapper, str]:
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

def stripDeclarationBytes(xml: bytes) -> bytes:
    xmlStart = xml[0:120]
    indexOfDeclaration = xmlStart.find(b"<?xml")
    if indexOfDeclaration >= 0:
        indexOfDeclarationEnd = xmlStart.find(b"?>", indexOfDeclaration)
        if indexOfDeclarationEnd >= 0:
            return xml[indexOfDeclarationEnd + 2:]
    return xml

def saveFile(cntlr: Cntlr, filepath: str, contents: str, encoding: str | None = None, mode: str='wt') -> None:
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

def gaeGet(key: str) -> bytes | None:
    # returns bytes (not string) value
    global gaeMemcache
    if gaeMemcache is None:
        from google.appengine.api import memcache as gaeMemcache

    assert gaeMemcache is not None
    chunk_keys = gaeMemcache.get(key)
    if chunk_keys is None:
        return None
    chunks = []
    if isinstance(chunk_keys, str):
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


def gaeDelete(key: str) -> bool:
    assert gaeMemcache is not None
    chunk_keys = gaeMemcache.get(key)
    if chunk_keys is None:
        return False
    if isinstance(chunk_keys, str):
        chunk_keys = []
    chunk_keys.append(key)
    gaeMemcache.delete_multi(chunk_keys)
    return True


# Note 2022-09-12
# Looks like maybe memcache of google.appengine.api is Python 2?
def gaeSet(key: str, bytesValue: bytes) -> bool: # stores bytes, not string valye
    global gaeMemcache
    if gaeMemcache is None:
        from google.appengine.api import memcache as gaeMemcache
    compressedValue = zlib.compress(bytesValue)

    # delete previous entity with the given key
    # in order to conserve available memcache space.
    gaeDelete(key)

    valueSize = len(compressedValue)
    assert gaeMemcache is not None

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
    return cast(bool, gaeMemcache.set(key, chunkKeys, time=GAE_EXPIRE_WEEK))
