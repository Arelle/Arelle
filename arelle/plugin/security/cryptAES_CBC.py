'''
See COPYRIGHT.md for copyright information.

Template crypt module using AES CBC mode.

Requires installing pycrypto (not any other crypto module)

Customize for an integrated security environment

Input file parameters may be in JSON (without newlines for pretty printing as below):


[ {"file": "file path to instance or inline xhtml", or "ixds":{"file": filepath, ...}
   "key": "base 64 encoded key",
   "iv": "base 64 encoded iv",
    ... (any other custom entrypoint parameters)
  },
 {"file": "file 2"...
]

On Windows, the input file argument must be specially quoted if passed in via Java
due to a Java bug on Windows shell interface (without the newlines for pretty printing below):

"[{\"file\":\"z:\\Documents\\dir\\gpc_gd1-20130930.htm\",
    \"key\": \"base 64 encoded key\",
    \"iv\": \"base 64 encoded iv\",
    ... (any other custom entrypoint parameters)
    }]"

The ownerObject may be a validation object related to the instance or to a collection of instances.

Customize method of detecting an encrypted file.  This example appends "~" to distinguish files which are encrypted.

'''
import os, io, base64
from arelle import FileSource, XmlUtil
from arelle.Version import authorLabel, copyrightLabel
AES = None  # Cipher.Crypto AES is only imported if an encrypted input is noticed

ENCRYPTED_FILE_SUFFIX = "~" # appended to any file which has been encrypted

def securityInit(ownerObject, options, filesource, entrypointfiles, sourceZipStream):
    ownerObject.hasEncryption = False
    ownerObject.cipherKey = None
    ownerObject.cipherIv = None

def securityFilingStart(ownerObject, options, filesource, entrypointfiles, sourceZipStream):
    # check if any files have an encryption key specified, if so activate security
    if isinstance(entrypointfiles, list) and any("key" in entrypointfile for entrypointfile in entrypointfiles):
        # AES encryption must be installed
        global AES
        from Crypto.Cipher import AES # must have AES encryption loaded in server
        ownerObject.hasEncryption = True

def securityFileSourceExists(ownerObject, filepath):
    # handle FileSource existence requests which might involve encrypted files
    if ownerObject.hasEncryption and os.path.exists(filepath + ENCRYPTED_FILE_SUFFIX):
        return True
    return None

def securityFileSourceFile(cntlr, ownerObject, filepath, binary, stripDeclaration):
    # handle FileSource file requests which can return encrypted contents
    if ownerObject.hasEncryption:
        for entrypointfile in ownerObject.entrypointfiles:
            if (filepath == entrypointfile.get("file") or
                any(filepath == ixfile.get("file") for ixfile in entrypointfile.get("ixds",()))
                ) and "key" in entrypointfile and "iv" in entrypointfile:
                ownerObject.cipherIv = base64.decodebytes(entrypointfile["iv"].encode())
                ownerObject.cipherKey = base64.decodebytes(entrypointfile["key"].encode())
                break # set new iv, key based on entrypointfiles
        # may be a non-entry file (xsd, linkbase, jpg) using entry's iv, key
        if os.path.exists(filepath + ENCRYPTED_FILE_SUFFIX) and ownerObject.cipherKey is not None and ownerObject.cipherIv is not None:
            encrdata = io.open(filepath + ENCRYPTED_FILE_SUFFIX, "rb").read()
            cipher = AES.new(ownerObject.cipherKey, AES.MODE_CBC, iv=ownerObject.cipherIv)
            bytesdata = cipher.decrypt(encrdata)
            encrdata = None # dereference before decode operation
            if binary: # return bytes
                return (FileSource.FileNamedBytesIO(filepath, bytesdata[0:-bytesdata[-1]]), ) # trim AES CBC padding
            # detect encoding if there is an XML header
            encoding = XmlUtil.encoding(bytesdata[0:512],
                                        default=cntlr.modelManager.disclosureSystem.defaultXmlEncoding
                                                if cntlr else 'utf-8')
            # return decoded string
            text = bytesdata[0:-bytesdata[-1]].decode(encoding or 'utf-8') # trim AES CBC padding and decode
            bytesdata = None # dereference before text operation
            if stripDeclaration: # file source may strip XML declaration for libxml
                xmlDeclarationMatch = FileSource.XMLdeclaration.search(text)
                if xmlDeclarationMatch: # remove it for lxml
                    start,end = xmlDeclarationMatch.span()
                    text = text[0:start] + text[end:]
            return (FileSource.FileNamedStringIO(filepath, initial_value=text), encoding)
    return None

def securityWrite(ownerObject, filepath, data):
    if ownerObject.hasEncryption and ownerObject.cipherKey is not None and ownerObject.cipherIv is not None:
        cipher = AES.new(ownerObject.cipherKey, AES.MODE_CBC, iv=ownerObject.cipherIv)
        if isinstance(data, str): # encode string into bytes
            bytesdata = data.encode("utf-8")
        else: # data is binary, doesn't need encoding
            bytesdata = data
        padlength = 16 - (len(bytesdata) % 16) # AES CBC padding
        bytesdata += padlength * (chr(padlength).encode())
        encrdata = cipher.encrypt(bytesdata)
        if isinstance(data, str): bytesdata = None # dereference before open operation
        with open(filepath + ENCRYPTED_FILE_SUFFIX, "wb") as fh:
            fh.write(encrdata)
        return True # written successfully
    return None

__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Security Crypt AES_CBC',
    'version': '1.0',
    'description': '''AES_CBC security encryption''',
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'Security.Crypt.Init': securityInit,
    'Security.Crypt.Filing.Start': securityFilingStart,
    'Security.Crypt.FileSource.Exists': securityFileSourceExists,
    'Security.Crypt.FileSource.File': securityFileSourceFile,
    'Security.Crypt.Write': securityWrite
}
