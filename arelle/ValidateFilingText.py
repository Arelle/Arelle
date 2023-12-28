'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations
#import xml.sax, xml.sax.handler
from lxml.etree import XML, DTD, SubElement, _ElementTree, _Comment, _ProcessingInstruction, XMLSyntaxError, XMLParser
from dataclasses import dataclass
import os, io, base64
import regex as re
import string
from arelle.XbrlConst import ixbrlAll, xhtml
from arelle.XmlUtil import setXmlns, xmlstring, xmlDeclarationPattern, XmlDeclarationLocationException
from arelle.ModelObject import ModelObject
from arelle.UrlUtil import decodeBase64DataImage, isHttpUrl, scheme

XMLpattern = re.compile(r".*(<|&lt;|&#x3C;|&#60;)[A-Za-z_]+[A-Za-z0-9_:]*[^>]*(/>|>|&gt;|/&gt;).*", re.DOTALL)
CDATApattern = re.compile(r"<!\[CDATA\[(.+)\]\]")
#EFM table 5-1 and all &xxx; patterns
allowedCharacters =                  string.digits + string.ascii_letters + R"""`~!@#$%&*().-+ {}[]|\:;"'<>,_?/=""" + '\t\n\r\f'
disallowedCharactersPattern = re.compile(r"""[^0-9          A-Za-z              `~!@#$%&*(). + {}  | :;"'<>,_?/=       \t\n\r\f  \-\[\]\\]""")
allowedCharactersTranslationDict = dict.fromkeys(map(ord, allowedCharacters))
disallowedEntityPattern = re.compile(r'&\w+;') # won't match &#nnn;
namedEntityPattern = re.compile("&[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
                                r"[_\-\.:"
                                "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*;")
#entityPattern = re.compile("&#[0-9]+;|"
#                           "&#x[0-9a-fA-F]+;|"
#                           "&[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
#                                r"[_\-\.:"
#                                "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*;")

inlinePattern = re.compile(r"xmlns:[\w.-]+=['\"]http://www.xbrl.org/2013/inlineXBRL['\"]")
inlineSelfClosedElementPattern = re.compile(r"<(?P<element>([\w.-]+:)?(?P<localName>\w+))([^\w/][^<]*)?/>")
# The ESEF 2022 conformance suite G2-5-1_2 TC3_invalid depends on optional "/".
# <img src="data:image;base64,iVBOR...
imgDataMediaBase64Pattern = re.compile(r"data:image(?:/(?P<mimeSubtype>[^,;]*))?(?P<base64>;base64)?,(?P<data>.*)$", re.S)

edbodyDTD = None
isInlineDTD = None

''' replace with lxml DTD validation
bodyTags = {
    'a': (),
    'address': (),
    'b': (),
    'big': (),
    'blockquote': (),
    'br': (),
    'caption': (),
    'center': (),
    'cite': (),
    'code': (),
    'dd': (),
    'dfn': (),
    'dir': (),
    'div': (),
    'dl': (),
    'dt': (),
    'em': (),
    'font': (),
    'h1': (),
    'h2': (),
    'h3': (),
    'h4': (),
    'h5': (),
    'h6': (),
    'hr': (),
    'i': (),
    'img': (),
    'kbd': (),
    'li': (),
    'listing': (),
    'menu': (),
    'ol': (),
    'p': (),
    'plaintext': (),
    'pre': (),
    'samp': (),
    'small': (),
    'strike': (),
    'strong': (),
    'sub': (),
    'sup': (),
    'table': (),
    'td': (),
    'th': (),
    'tr': (),
    'tt': (),
    'u': (),
    'ul': (),
    'var': (),
    'xmp': ()
    }

htmlAttributes = {
    'align': ('h1','h2','h3','h4','h5','h6','hr', 'img', 'p','caption','div','table','td','th','tr'),
    'alink': ('body'),
    'alt': ('img'),
    'bgcolor': ('body','table', 'tr', 'th', 'td'),
    'border': ('table', 'img'),
    'cellpadding': ('table'),
    'cellspacing': ('table'),
    'class': ('*'),
    'clear': ('br'),
    'color': ('font'),
    'colspan': ('td','th'),
    'compact': ('dir','dl','menu','ol','ul'),
    'content': ('meta'),
    'dir': ('h1','h2','h3','h4','h5','h6','hr','p','img','caption','div','table','td','th','tr','font',
            'center','ol','li','ul','bl','a','big','pre','dir','address','blockqoute','menu','blockquote',
              'em', 'strong', 'dfn', 'code', 'samp', 'kbd', 'var', 'cite', 'sub', 'sup', 'tt', 'i', 'b', 'small', 'u', 'strike'),
    'lang': ('h1','h2','h3','h4','h5','h6','hr','p','img','caption','div','table','td','th','tr','font',
            'center','ol','li','ul','bl','a','big','pre','dir','address','blockqoute','menu','blockquote',
              'em', 'strong', 'dfn', 'code', 'samp', 'kbd', 'var', 'cite', 'sub', 'sup', 'tt', 'i', 'b', 'small', 'u', 'strike'),
    'height': ('td','th', 'img'),
    'href': ('a'),
    'id': ('*'),
    'link': ('body'),
    'name': ('meta','a', 'img'),
    'noshade': ('hr'),
    'nowrap': ('td','th'),
    'prompt': ('isindex'),
    'rel': ('link','a'),
    'rev': ('link','a'),
    'rowspan': ('td','th'),
    'size': ('hr','font'),
    'src': ('img'),
    'start': ('ol'),
    'style': ('*'),
    'text': ('body'),
    'title': ('*'),
    'type': ('li','ol','ul'),
    'valign': ('td','th','tr'),
    'vlink': ('body'),
    'width': ('hr','pre', 'table','td','th', 'img')
    }
'''

xhtmlEntities = {
    '&nbsp;': '&#160;',
    '&iexcl;': '&#161;',
    '&cent;': '&#162;',
    '&pound;': '&#163;',
    '&curren;': '&#164;',
    '&yen;': '&#165;',
    '&brvbar;': '&#166;',
    '&sect;': '&#167;',
    '&uml;': '&#168;',
    '&copy;': '&#169;',
    '&ordf;': '&#170;',
    '&laquo;': '&#171;',
    '&not;': '&#172;',
    '&shy;': '&#173;',
    '&reg;': '&#174;',
    '&macr;': '&#175;',
    '&deg;': '&#176;',
    '&plusmn;': '&#177;',
    '&sup2;': '&#178;',
    '&sup3;': '&#179;',
    '&acute;': '&#180;',
    '&micro;': '&#181;',
    '&para;': '&#182;',
    '&middot;': '&#183;',
    '&cedil;': '&#184;',
    '&sup1;': '&#185;',
    '&ordm;': '&#186;',
    '&raquo;': '&#187;',
    '&frac14;': '&#188;',
    '&frac12;': '&#189;',
    '&frac34;': '&#190;',
    '&iquest;': '&#191;',
    '&Agrave;': '&#192;',
    '&Aacute;': '&#193;',
    '&Acirc;': '&#194;',
    '&Atilde;': '&#195;',
    '&Auml;': '&#196;',
    '&Aring;': '&#197;',
    '&AElig;': '&#198;',
    '&Ccedil;': '&#199;',
    '&Egrave;': '&#200;',
    '&Eacute;': '&#201;',
    '&Ecirc;': '&#202;',
    '&Euml;': '&#203;',
    '&Igrave;': '&#204;',
    '&Iacute;': '&#205;',
    '&Icirc;': '&#206;',
    '&Iuml;': '&#207;',
    '&ETH;': '&#208;',
    '&Ntilde;': '&#209;',
    '&Ograve;': '&#210;',
    '&Oacute;': '&#211;',
    '&Ocirc;': '&#212;',
    '&Otilde;': '&#213;',
    '&Ouml;': '&#214;',
    '&times;': '&#215;',
    '&Oslash;': '&#216;',
    '&Ugrave;': '&#217;',
    '&Uacute;': '&#218;',
    '&Ucirc;': '&#219;',
    '&Uuml;': '&#220;',
    '&Yacute;': '&#221;',
    '&THORN;': '&#222;',
    '&szlig;': '&#223;',
    '&agrave;': '&#224;',
    '&aacute;': '&#225;',
    '&acirc;': '&#226;',
    '&atilde;': '&#227;',
    '&auml;': '&#228;',
    '&aring;': '&#229;',
    '&aelig;': '&#230;',
    '&ccedil;': '&#231;',
    '&egrave;': '&#232;',
    '&eacute;': '&#233;',
    '&ecirc;': '&#234;',
    '&euml;': '&#235;',
    '&igrave;': '&#236;',
    '&iacute;': '&#237;',
    '&icirc;': '&#238;',
    '&iuml;': '&#239;',
    '&eth;': '&#240;',
    '&ntilde;': '&#241;',
    '&ograve;': '&#242;',
    '&oacute;': '&#243;',
    '&ocirc;': '&#244;',
    '&otilde;': '&#245;',
    '&ouml;': '&#246;',
    '&divide;': '&#247;',
    '&oslash;': '&#248;',
    '&ugrave;': '&#249;',
    '&uacute;': '&#250;',
    '&ucirc;': '&#251;',
    '&uuml;': '&#252;',
    '&yacute;': '&#253;',
    '&thorn;': '&#254;',
    '&yuml;': '&#255;',
    '&quot;': '&#34;',
    '&amp;': '&#38;#38;',
    '&lt;': '&#38;#60;',
    '&gt;': '&#62;',
    '&apos;': '&#39;',
    '&OElig;': '&#338;',
    '&oelig;': '&#339;',
    '&Scaron;': '&#352;',
    '&scaron;': '&#353;',
    '&Yuml;': '&#376;',
    '&circ;': '&#710;',
    '&tilde;': '&#732;',
    '&ensp;': '&#8194;',
    '&emsp;': '&#8195;',
    '&thinsp;': '&#8201;',
    '&zwnj;': '&#8204;',
    '&zwj;': '&#8205;',
    '&lrm;': '&#8206;',
    '&rlm;': '&#8207;',
    '&ndash;': '&#8211;',
    '&mdash;': '&#8212;',
    '&lsquo;': '&#8216;',
    '&rsquo;': '&#8217;',
    '&sbquo;': '&#8218;',
    '&ldquo;': '&#8220;',
    '&rdquo;': '&#8221;',
    '&bdquo;': '&#8222;',
    '&dagger;': '&#8224;',
    '&Dagger;': '&#8225;',
    '&permil;': '&#8240;',
    '&lsaquo;': '&#8249;',
    '&rsaquo;': '&#8250;',
    '&euro;': '&#8364;',
    '&fnof;': '&#402;',
    '&Alpha;': '&#913;',
    '&Beta;': '&#914;',
    '&Gamma;': '&#915;',
    '&Delta;': '&#916;',
    '&Epsilon;': '&#917;',
    '&Zeta;': '&#918;',
    '&Eta;': '&#919;',
    '&Theta;': '&#920;',
    '&Iota;': '&#921;',
    '&Kappa;': '&#922;',
    '&Lambda;': '&#923;',
    '&Mu;': '&#924;',
    '&Nu;': '&#925;',
    '&Xi;': '&#926;',
    '&Omicron;': '&#927;',
    '&Pi;': '&#928;',
    '&Rho;': '&#929;',
    '&Sigma;': '&#931;',
    '&Tau;': '&#932;',
    '&Upsilon;': '&#933;',
    '&Phi;': '&#934;',
    '&Chi;': '&#935;',
    '&Psi;': '&#936;',
    '&Omega;': '&#937;',
    '&alpha;': '&#945;',
    '&beta;': '&#946;',
    '&gamma;': '&#947;',
    '&delta;': '&#948;',
    '&epsilon;': '&#949;',
    '&zeta;': '&#950;',
    '&eta;': '&#951;',
    '&theta;': '&#952;',
    '&iota;': '&#953;',
    '&kappa;': '&#954;',
    '&lambda;': '&#955;',
    '&mu;': '&#956;',
    '&nu;': '&#957;',
    '&xi;': '&#958;',
    '&omicron;': '&#959;',
    '&pi;': '&#960;',
    '&rho;': '&#961;',
    '&sigmaf;': '&#962;',
    '&sigma;': '&#963;',
    '&tau;': '&#964;',
    '&upsilon;': '&#965;',
    '&phi;': '&#966;',
    '&chi;': '&#967;',
    '&psi;': '&#968;',
    '&omega;': '&#969;',
    '&thetasym;': '&#977;',
    '&upsih;': '&#978;',
    '&piv;': '&#982;',
    '&bull;': '&#8226;',
    '&hellip;': '&#8230;',
    '&prime;': '&#8242;',
    '&Prime;': '&#8243;',
    '&oline;': '&#8254;',
    '&frasl;': '&#8260;',
    '&weierp;': '&#8472;',
    '&image;': '&#8465;',
    '&real;': '&#8476;',
    '&trade;': '&#8482;',
    '&alefsym;': '&#8501;',
    '&larr;': '&#8592;',
    '&uarr;': '&#8593;',
    '&rarr;': '&#8594;',
    '&darr;': '&#8595;',
    '&harr;': '&#8596;',
    '&crarr;': '&#8629;',
    '&lArr;': '&#8656;',
    '&uArr;': '&#8657;',
    '&rArr;': '&#8658;',
    '&dArr;': '&#8659;',
    '&hArr;': '&#8660;',
    '&forall;': '&#8704;',
    '&part;': '&#8706;',
    '&exist;': '&#8707;',
    '&empty;': '&#8709;',
    '&nabla;': '&#8711;',
    '&isin;': '&#8712;',
    '&notin;': '&#8713;',
    '&ni;': '&#8715;',
    '&prod;': '&#8719;',
    '&sum;': '&#8721;',
    '&minus;': '&#8722;',
    '&lowast;': '&#8727;',
    '&radic;': '&#8730;',
    '&prop;': '&#8733;',
    '&infin;': '&#8734;',
    '&ang;': '&#8736;',
    '&and;': '&#8743;',
    '&or;': '&#8744;',
    '&cap;': '&#8745;',
    '&cup;': '&#8746;',
    '&int;': '&#8747;',
    '&there;': '&#8756;',
    '&sim;': '&#8764;',
    '&cong;': '&#8773;',
    '&asymp;': '&#8776;',
    '&ne;': '&#8800;',
    '&equiv;': '&#8801;',
    '&le;': '&#8804;',
    '&ge;': '&#8805;',
    '&sub;': '&#8834;',
    '&sup;': '&#8835;',
    '&nsub;': '&#8836;',
    '&sube;': '&#8838;',
    '&supe;': '&#8839;',
    '&oplus;': '&#8853;',
    '&otimes;': '&#8855;',
    '&perp;': '&#8869;',
    '&sdot;': '&#8901;',
    '&lceil;': '&#8968;',
    '&rceil;': '&#8969;',
    '&lfloor;': '&#8970;',
    '&rfloor;': '&#8971;',
    '&lang;': '&#9001;',
    '&rang;': '&#9002;',
    '&loz;': '&#9674;',
    '&spades;': '&#9824;',
    '&clubs;': '&#9827;',
    '&hearts;': '&#9829;',
    '&diams;': '&#9830;',
    }

efmBlockedInlineHtmlElements = {
    'acronym', 'area', 'atob', 'base', 'bdo', 'button', 'cite', 'col', 'colgroup',
    'dd', 'del', 'embed', 'fieldset', 'form', 'function', 'input', 'ins', 'label', 'legend',
    'map', 'noscript', 'onclick', 'oncontextmenu', 'ondblclick', 'onfocus', 'onload',
    'object', 'option', 'param', 'q', 'script', 'select', 'style', 'textarea'
    }
efmBlockedInlineHtmlElementAttributes = {
    'a': ('name',),
    'body': ('link',),
    'html': ('lang',), # want the xml:lang attribute only in SEC filnigs
    'link': ('rel', 'rev')
}
elementsWithNoContent = {
    "relationship", # inline 1.1
    "schemaRef", "linkbaseRef", "roleRef", "arcroleRef", # xbrl instance
    "area", "base", "basefont", "br", "col", "frame", "hr", "img", "input", "isindex", "link", "meta", "param", # xhtml
    # elements which can have no text node siblings, tested with IE, Chrome and Safari
    "td", "tr"
    }


ModelDocumentTypeINLINEXBRL = None
ModelDocumentTypeINLINEXBRLDOCUMENTSET = None
def initModelDocumentTypeReferences():
    global ModelDocumentTypeINLINEXBRL, ModelDocumentTypeINLINEXBRLDOCUMENTSET
    if ModelDocumentTypeINLINEXBRL is None:
        from arelle.ModelDocument import Type
        ModelDocumentTypeINLINEXBRL = Type.INLINEXBRL
        ModelDocumentTypeINLINEXBRLDOCUMENTSET = Type.INLINEXBRLDOCUMENTSET

def checkfile(modelXbrl, filepath):
    result = []
    lineNum = 1
    foundXmlDeclaration = False
    validateEntryText = modelXbrl.modelManager.disclosureSystem.validateEntryText
    file, encoding = modelXbrl.fileSource.file(filepath)
    if validateEntryText and encoding == "utf-8-sig":
        modelXbrl.error(("EFM.5.02.01.01", "FERC.5.02.01.01"),
            _("Disallowed byte-order mark in file %(file)s."),
            modelDocument=filepath, text="byte-order mark", unicodeIndex="U+FEFF", file=os.path.basename(filepath), line=1, column=1)
    parserResults = {}
    class checkFileType(object):
        def start(self, tag, attr, nsmap=None): # check root XML element type
            parserResults["rootIsTestcase"] = tag.rpartition("}")[2] in ("testcases", "documentation", "testSuite", "testcase", "testSet")
            if tag in ("{http://www.w3.org/1999/xhtml}html", "{http://www.w3.org/1999/xhtml}xhtml"):
                if nsmap and any(ns in ixbrlAll for ns in nsmap.values()):
                    parserResults["isInline"] = True
                else:
                    parserResults["maybeInline"] = True
        def end(self, tag): pass
        def data(self, data): pass
        def close(self): pass
    _parser = XMLParser(recover=True, huge_tree=True, target=checkFileType())
    _isTestcase = False
    mayBeInline = isInline = False

    with file as f:
        while True:
            line = f.readline()
            if line == "":
                break;
            # check for disallowed characters or entity codes
            for match in disallowedEntityPattern.finditer(line):
                text = match.group()
                if not text in xhtmlEntities:
                    modelXbrl.error(("EFM.5.02.02.06", "GFM.1.01.02", "FERC.5.02.02.06"),
                        _("Disallowed entity code %(text)s in file %(file)s line %(line)s column %(column)s"),
                        modelDocument=filepath, text=text, file=os.path.basename(filepath), line=lineNum, column=match.start())
            # Finding disallowed characters with a large negated character class can be fairly slow on long lines.
            # Only run it if there are disallowed characters to find.
            if validateEntryText and not _isTestcase and line.translate(allowedCharactersTranslationDict):
                for match in disallowedCharactersPattern.finditer(line):
                    text = match.group()
                    if len(text) == 1:
                        modelXbrl.error(("EFM.5.02.01.01", "FERC.5.02.01.01"),
                            _("Disallowed character '%(text)s' (%(unicodeIndex)s) in file %(file)s at line %(line)s col %(column)s"),
                            modelDocument=filepath, text=text, unicodeIndex="U+{:04X}".format(ord(text)),
                            file=os.path.basename(filepath), line=lineNum, column=match.start())
                    else:
                        modelXbrl.error(("EFM.5.02.01.01", "FERC.5.02.01.01"),
                            _("Disallowed character '%(text)s' in file %(file)s at line %(line)s col %(column)s"),
                            modelDocument=filepath, text=text, file=os.path.basename(filepath), line=lineNum, column=match.start())
            if lineNum == 1:
                xmlDeclarationMatch = xmlDeclarationPattern.match(line)
                if xmlDeclarationMatch: # remove it for lxml
                    if xmlDeclarationMatch.group(1) is not None:
                        raise XmlDeclarationLocationException
                    start,end = xmlDeclarationMatch.span(2)
                    line = line[0:start] + line[end:]
                    foundXmlDeclaration = True
            if _parser: # feed line after removal of xml declaration
                _parser.feed(line.encode('utf-8','ignore'))
                if "rootIsTestcase" in parserResults: # root XML element has been encountered
                    _isTestcase = parserResults["rootIsTestcase"]
                    if "isInline" in parserResults:
                        isInline = True
                    elif "maybeInline" in parserResults:
                        mayBeInline = True
                    _parser = None # no point to parse past the root element
            if mayBeInline and inlinePattern.search(line):
                mayBeInline = False
                isInline = True
            if isInline and '/>' in line:
                for match in inlineSelfClosedElementPattern.finditer(line):
                    selfClosedLocalName = match.group('localName')
                    if selfClosedLocalName not in elementsWithNoContent:
                        modelXbrl.warning("ixbrl:selfClosedTagWarning",
                                          _("Self-closed element \"%(element)s\" may contain text or other elements and should not use self-closing tag syntax (/>) when empty; change these to end-tags in file %(file)s line %(line)s column %(column)s"),
                                          modelDocument=filepath, element=match.group('element'), file=os.path.basename(filepath), line=lineNum, column=match.start())
            result.append(line)
            lineNum += 1
    result = ''.join(result)
    if not foundXmlDeclaration: # may be multiline, try again
        xmlDeclarationMatch = xmlDeclarationPattern.match(result)
        if xmlDeclarationMatch: # remove it for lxml
            if xmlDeclarationMatch.group(1) is not None:
                raise XmlDeclarationLocationException
            start,end = xmlDeclarationMatch.span(2)
            result = result[0:start] + result[end:]
            foundXmlDeclaration = True

    return (io.StringIO(initial_value=result), encoding)

def loadDTD(modelXbrl):
    global edbodyDTD, isInlineDTD
    initModelDocumentTypeReferences()
    _isInline = modelXbrl.modelDocument.type == ModelDocumentTypeINLINEXBRL
    if isInlineDTD is None or isInlineDTD != _isInline:
        isInlineDTD = _isInline
        with open(os.path.join(modelXbrl.modelManager.cntlr.configDir,
                               "xhtml1-strict-ix.dtd" if _isInline else "edbody.dtd")) as fh:
            edbodyDTD = DTD(fh)

def removeEntities(text):
    ''' ARELLE-128
    entitylessText = []
    findAt = 0
    while (True):
        entityStart = text.find('&',findAt)
        if entityStart == -1: break
        entityEnd = text.find(';',entityStart)
        if entityEnd == -1: break
        entitylessText.append(text[findAt:entityStart])
        findAt = entityEnd + 1
    entitylessText.append(text[findAt:])
    return ''.join(entitylessText)
    '''
    return namedEntityPattern.sub("", text).replace('&','&amp;')

def validateTextBlockFacts(modelXbrl):
    #handler = TextBlockHandler(modelXbrl)
    loadDTD(modelXbrl)
    checkedGraphicsFiles = set() #  only check any graphics file reference once per fact
    allowedExternalHrefPattern = modelXbrl.modelManager.disclosureSystem.allowedExternalHrefPattern
    allowedImageTypes = modelXbrl.modelManager.disclosureSystem.allowedImageTypes

    if isInlineDTD:
        htmlBodyTemplate = "<body><div>\n{0}\n</div></body>\n"
    else:
        htmlBodyTemplate = "<body>\n{0}\n</body>\n"
    _xhtmlNs = "{{{}}}".format(xhtml)
    _xhtmlNsLen = len(_xhtmlNs)

    for f1 in modelXbrl.facts:
        # build keys table for 6.5.14
        concept = f1.concept
        if f1.xsiNil != "true" and \
           concept is not None and \
           concept.isTextBlock and \
           XMLpattern.match(f1.value):
            #handler.fact = f1
            # test encoded entity tags
            for match in namedEntityPattern.finditer(f1.value):
                entity = match.group()
                if not entity in xhtmlEntities:
                    modelXbrl.error(("EFM.6.05.16", "GFM.1.2.15", "FERC.6.05.16"),
                        _("Fact %(fact)s contextID %(contextID)s has disallowed entity %(entity)s"),
                        modelObject=f1, fact=f1.qname, contextID=f1.contextID, entity=entity, error=entity)
            # test html
            for xmltext in [f1.value] + CDATApattern.findall(f1.value):
                '''
                try:
                    xml.sax.parseString(
                        "<?xml version='1.0' encoding='utf-8' ?>\n<body>\n{0}\n</body>\n".format(
                         removeEntities(xmltext)).encode('utf-8'),handler,handler)
                except (xml.sax.SAXParseException,
                        xml.sax.SAXException,
                        UnicodeDecodeError) as err:
                    # ignore errors which are not errors (e.g., entity codes checked previously
                    if not err.endswith("undefined entity"):
                        handler.modelXbrl.error(("EFM.6.05.15", "GFM.1.02.14", "FERC.6.05.15"),
                            _("Fact %(fact)s contextID %(contextID)s has text which causes the XML error %(error)s"),
                            modelObject=f1, fact=f1.qname, contextID=f1.contextID, error=err)
                '''
                xmlBodyWithoutEntities = htmlBodyTemplate.format(removeEntities(xmltext))
                try:
                    textblockXml = XML(xmlBodyWithoutEntities)
                    if not edbodyDTD.validate( textblockXml ):
                        errors = edbodyDTD.error_log.filter_from_errors()
                        htmlError = any(e.type_name in ("DTD_INVALID_CHILD", "DTD_UNKNOWN_ATTRIBUTE")
                                        for e in errors)
                        modelXbrl.error(("EFM.6.05.16","FERC.6.05.16") if htmlError else ("EFM.6.05.15.dtdError", "GFM.1.02.14", "FERC.6.05.15.dtdError"),
                            _("Fact %(fact)s contextID %(contextID)s has text which causes the XML error %(error)s"),
                            modelObject=f1, fact=f1.qname, contextID=f1.contextID,
                            error=', '.join(e.message for e in errors),
                            messageCodes=("EFM.6.05.16", "EFM.6.05.15.dtdError", "GFM.1.02.14", "FERC.6.05.16", "FERC.6.05.15.dtdError"))
                    for elt in textblockXml.iter():
                        eltTag = elt.tag
                        if isinstance(elt, ModelObject) and elt.namespaceURI == xhtml:
                            eltTag = elt.localName
                        elif isinstance(elt, (_ElementTree, _Comment, _ProcessingInstruction)):
                            continue # comment or other non-parsed element
                        else:
                            eltTag = elt.tag
                            if eltTag.startswith(_xhtmlNs):
                                eltTag = eltTag[_xhtmlNsLen:]
                        if isInlineDTD and eltTag in efmBlockedInlineHtmlElements:
                            modelXbrl.error(("EFM.5.02.05.disallowedElement", "FERC.5.02.05.disallowedElement"),
                                _("%(validatedObjectLabel)s has disallowed element <%(element)s>"),
                                modelObject=elt, validatedObjectLabel=f1.qname,
                                element=eltTag)
                        for attrTag, attrValue in elt.items():
                            if isInlineDTD:
                                if attrTag in efmBlockedInlineHtmlElementAttributes.get(eltTag,()):
                                    modelXbrl.error(("EFM.5.02.05.disallowedAttribute", "FERC.5.02.05.disallowedAttribute"),
                                        _("%(validatedObjectLabel)s has disallowed attribute on element <%(element)s>: %(attribute)s=\"%(value)s\""),
                                        modelObject=elt, validatedObjectLabel=validatedObjectLabel,
                                        element=eltTag, attribute=attrTag, value=attrValue)
                            if ((attrTag == "href" and eltTag == "a") or
                                (attrTag == "src" and eltTag == "img")):
                                if "javascript:" in attrValue:
                                    modelXbrl.error(("EFM.6.05.16.activeContent", "FERC.6.05.16.activeContent"),
                                        _("Fact %(fact)s of context %(contextID)s has javascript in '%(attribute)s' for <%(element)s>"),
                                        modelObject=f1, fact=f1.qname, contextID=f1.contextID,
                                        attribute=attrTag, element=eltTag)
                                elif eltTag == "a" and (not allowedExternalHrefPattern or allowedExternalHrefPattern.match(attrValue)):
                                    pass
                                elif scheme(attrValue) in ("http", "https", "ftp"):
                                    modelXbrl.error(("EFM.6.05.16.externalReference", "FERC.6.05.16.externalReference"),
                                        _("Fact %(fact)s of context %(contextID)s has an invalid external reference in '%(attribute)s' for <%(element)s>"),
                                        modelObject=f1, fact=f1.qname, contextID=f1.contextID,
                                        attribute=attrTag, element=eltTag)
                                if attrTag == "src" and allowedImageTypes and attrValue not in checkedGraphicsFiles:
                                    if scheme(attrValue)  == "data":
                                        try: # allow embedded newlines
                                            dataURLParts = parseImageDataURL(attrValue)
                                            if (not allowedImageTypes["data-scheme"] or
                                                not dataURLParts or not dataURLParts.mimeSubtype or not dataURLParts.isBase64
                                                or dataURLParts.mimeSubtype not in allowedImageTypes["mime-types"]
                                                or not dataURLParts.base64GraphicHeaderTypeMatchesMimeSubtype()):
                                                modelXbrl.error(("EFM.6.05.16.graphicDataUrl", "FERC.6.05.16.graphicDataUrl"),
                                                    _("Fact %(fact)s of context %(contextID)s references a graphics data URL which isn't accepted or valid '%(attribute)s' for <%(element)s>"),
                                                    modelObject=f1, fact=f1.qname, contextID=f1.contextID,
                                                    attribute=attrValue[:32], element=eltTag)
                                        except base64.binascii.Error as err:
                                            modelXbrl.error(("EFM.6.05.16.graphicDataEncodingError", "FERC.6.05.16.graphicDataEncodingError"),
                                                _("Fact %(fact)s of context %(contextID)s Base64 encoding error %(err)s in <%(element)s>"),
                                                modelObject=f1, fact=f1.qname, contextID=f1.contextID, err=err,
                                                attribute=attrValue[:32], element=eltTag)
                                    elif attrValue.lower()[-3:] not in allowedImageTypes["img-file-extensions"]:
                                        modelXbrl.error(("EFM.6.05.16.graphicFileType", "FERC.6.05.16.graphicFileType"),
                                            _("Fact %(fact)s of context %(contextID)s references a graphics file which isn't %(allowedExtensions)s '%(attribute)s' for <%(element)s>"),
                                            modelObject=f1, fact=f1.qname, contextID=f1.contextID, allowedExtensions=allowedImageTypes["img-file-extensions"],
                                            attribute=attrValue, element=eltTag)
                                    else:   # test file contents
                                        try:
                                            if validateGraphicFile(f1, attrValue) != attrValue.lower()[-3:]:
                                                modelXbrl.error(("EFM.6.05.16.graphicFileContent", "FERC.6.05.16.graphicFileContent"),
                                                    _("Fact %(fact)s of context %(contextID)s references a graphics file which has invalid format '%(attribute)s' for <%(element)s>"),
                                                    modelObject=f1, fact=f1.qname, contextID=f1.contextID,
                                                    attribute=attrValue, element=eltTag)
                                        except IOError as err:
                                            modelXbrl.error(("EFM.6.05.16.graphicFileError", "FERC.6.05.16.graphicFileError"),
                                                _("Fact %(fact)s of context %(contextID)s references a graphics file which isn't openable '%(attribute)s' for <%(element)s>, error: %(error)s"),
                                                modelObject=f1, fact=f1.qname, contextID=f1.contextID,
                                                attribute=attrValue, element=eltTag, error=err)
                                    checkedGraphicsFiles.add(attrValue)
                        if eltTag == "table" and any(a is not None for a in elt.iterancestors("table")):
                            modelXbrl.error(("EFM.6.05.16.nestedTable", "FERC.6.05.16.nestedTable"),
                                _("Fact %(fact)s of context %(contextID)s has nested <table> elements."),
                                modelObject=f1, fact=f1.qname, contextID=f1.contextID)
                except (XMLSyntaxError,
                        UnicodeDecodeError) as err:
                    #if not err.endswith("undefined entity"):
                    modelXbrl.error(("EFM.6.05.15", "GFM.1.02.14", "FERC.6.05.15"),
                        _("Fact %(fact)s contextID %(contextID)s has text which causes the XML error %(error)s"),
                        modelObject=f1, fact=f1.qname, contextID=f1.contextID, error=err)

                checkedGraphicsFiles.clear()

            #handler.fact = None
                #handler.modelXbrl = None

def copyHtml(sourceXml, targetHtml):
    for sourceChild in sourceXml.iterchildren():
        if isinstance(sourceChild, ModelObject):
            targetChild = SubElement(targetHtml,
                                     sourceChild.localName if sourceChild.namespaceURI == xhtml else sourceChild.tag)
            for attrTag, attrValue in sourceChild.items():
                targetChild.set("lang" if attrTag == "{http://www.w3.org/XML/1998/namespace}lang" else attrTag, attrValue)
            copyHtml(sourceChild, targetChild)

def validateFootnote(modelXbrl, footnote):
    #handler = TextBlockHandler(modelXbrl)
    loadDTD(modelXbrl)
    validatedObjectLabel = _("Footnote {}").format(footnote.get("{http://www.w3.org/1999/xlink}label"))

    try:
        footnoteHtml = XML("<body/>")
        copyHtml(footnote, footnoteHtml) # convert from xhtml to html (with no prefixes) for DTD validation
        if not edbodyDTD.validate( footnoteHtml ):
            modelXbrl.error(("EFM.6.05.34.dtdError", "FERC.6.05.34.dtdError"),
                _("%(validatedObjectLabel)s causes the XML error %(error)s"),
                modelObject=footnote, validatedObjectLabel=validatedObjectLabel,
                error=', '.join(e.message for e in edbodyDTD.error_log.filter_from_errors()))
        validateHtmlContent(modelXbrl, footnote, footnoteHtml, validatedObjectLabel, modelXbrl.modelManager.disclosureSystem.validationType + ".6.05.34.")
    except (XMLSyntaxError,
            UnicodeDecodeError) as err:
        #if not err.endswith("undefined entity"):
        modelXbrl.error(("EFM.6.05.34", "FERC.6.05.34"),
            _("%(validatedObjectLabel)s causes the XML error %(error)s"),
            modelObject=footnote, validatedObjectLabel=validatedObjectLabel,
            error=edbodyDTD.error_log.filter_from_errors())

def validateHtmlContent(modelXbrl, referenceElt, htmlEltTree, validatedObjectLabel, messageCodePrefix, isInline=False):
    checkedGraphicsFiles = set() # only check any graphics file reference once per footnote
    _xhtmlNs = "{{{}}}".format(xhtml)
    _xhtmlNsLen = len(_xhtmlNs)
    _tableTags = ("table", _xhtmlNs + "table")
    _anchorAncestorTags = set(_xhtmlNs + tag for tag in ("html", "body", "div"))
    allowedExternalHrefPattern = modelXbrl.modelManager.disclosureSystem.allowedExternalHrefPattern
    allowedImageTypes = modelXbrl.modelManager.disclosureSystem.allowedImageTypes
    for elt in htmlEltTree.iter():
        if isinstance(elt, ModelObject) and elt.namespaceURI == xhtml:
            eltTag = elt.localName
        elif isinstance(elt, (_ElementTree, _Comment, _ProcessingInstruction)):
            continue # comment or other non-parsed element
        else:
            eltTag = elt.tag
            if eltTag.startswith(_xhtmlNs):
                eltTag = eltTag[_xhtmlNsLen:]
        if isInline:
            if eltTag in efmBlockedInlineHtmlElements:
                modelXbrl.error(("EFM.5.02.05.disallowedElement", "FERC.5.02.05.disallowedElement"),
                    _("%(validatedObjectLabel)s has disallowed element <%(element)s>"),
                    modelObject=elt, validatedObjectLabel=validatedObjectLabel,
                    element=eltTag)
            if eltTag == "a" and "href" not in elt.keys() and any(a.tag not in _anchorAncestorTags for a in elt.iterancestors()):
                modelXbrl.warning(("EFM.5.02.05.anchorElementPosition", "FERC.5.02.05.anchorElementPosition"),
                    _("If element <a> does not have attribute @href, it should not have any ancestors other than html, body, or div.  Disallowed ancestors: %(disallowedAncestors)s"),
                    modelObject=elt, disallowedAncestors=", ".join(a.tag.rpartition('}')[2] for a in elt.iterancestors() if a.tag not in _anchorAncestorTags))
        for attrTag, attrValue in elt.items():
            if isInline:
                if attrTag in efmBlockedInlineHtmlElementAttributes.get(eltTag,()):
                    modelXbrl.error(("EFM.5.02.05.disallowedAttribute", "FERC.5.02.05.disallowedAttribute"),
                        _("%(validatedObjectLabel)s has disallowed attribute on element <%(element)s>: %(attribute)s=\"%(value)s\""),
                        modelObject=elt, validatedObjectLabel=validatedObjectLabel,
                        element=eltTag, attribute=attrTag, value=attrValue)
                elif attrTag == "{http://www.w3.org/XML/1998/namespace}base":
                    modelXbrl.error(("EFM.5.02.05.xmlBaseDisallowed", "FERC.5.02.05.xmlBaseDisallowed"),
                        _("%(validatedObjectLabel)s has disallowed attribute on element <%(element)s>: xml:base=\"%(value)s\""),
                        modelObject=elt, validatedObjectLabel=validatedObjectLabel,
                        element=eltTag, value=attrValue)
                elif attrTag == "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation":
                    modelXbrl.warning(("EFM.5.02.05.schemaLocationDisallowed", "FERC.5.02.05.schemaLocationDisallowed"),
                        _("%(validatedObjectLabel)s has disallowed attribute on element <%(element)s>: xsi:schemaLocation=\"%(value)s\""),
                        modelObject=elt, validatedObjectLabel=validatedObjectLabel,
                        element=eltTag, value=attrValue)
            if ((attrTag == "href" and eltTag == "a") or
                (attrTag == "src" and eltTag == "img")):
                if "javascript:" in attrValue:
                    modelXbrl.error(messageCodePrefix + "activeContent",
                        _("%(validatedObjectLabel)s has javascript in '%(attribute)s' for <%(element)s>"),
                        modelObject=elt, validatedObjectLabel=validatedObjectLabel,
                        attribute=attrTag, element=eltTag,
                        messageCodes=("EFM.6.05.34.activeContent", "EFM.5.02.05.activeContent", "FERC.6.05.34.activeContent", "FERC.5.02.05.activeContent"))
                elif eltTag == "a" and (not allowedExternalHrefPattern or allowedExternalHrefPattern.match(attrValue)):
                    pass
                elif scheme(attrValue) in ("http", "https", "ftp"):
                    modelXbrl.error(messageCodePrefix + "externalReference",
                        _("%(validatedObjectLabel)s has an invalid external reference in '%(attribute)s' for <%(element)s>: %(value)s"),
                        modelObject=elt, validatedObjectLabel=validatedObjectLabel,
                        attribute=attrTag, element=eltTag, value=attrValue,
                        messageCodes=("EFM.6.05.34.externalReference", "EFM.5.02.05.externalReference", "FERC.6.05.34.externalReference", "FERC.5.02.05.externalReference"))
                if attrTag == "src" and allowedImageTypes and attrValue not in checkedGraphicsFiles:
                    if scheme(attrValue) == "data":
                        try: # allow embedded newlines
                            dataURLParts = parseImageDataURL(attrValue)
                            if (not allowedImageTypes["data-scheme"] or
                                not dataURLParts or not dataURLParts.mimeSubtype or not dataURLParts.isBase64
                                or dataURLParts.mimeSubtype not in allowedImageTypes["mime-types"]
                                or not dataURLParts.base64GraphicHeaderTypeMatchesMimeSubtype()):
                                modelXbrl.error(messageCodePrefix + "graphicDataUrl",
                                    _("%(validatedObjectLabel)s references a graphics data URL which isn't accepted '%(attribute)s' for <%(element)s>"),
                                    modelObject=elt, validatedObjectLabel=validatedObjectLabel,
                                    attribute=attrValue[:32], element=eltTag)
                        except base64.binascii.Error as err:
                            modelXbrl.error(messageCodePrefix + "graphicDataEncodingError",
                                    _("%(validatedObjectLabel)s references a graphics data URL with Base64 encoding error %(err)s in <%(element)s>"),
                                    modelObject=elt, validatedObjectLabel=validatedObjectLabel,
                                    element=eltTag, err=err)
                    elif attrValue.lower()[-3:] not in allowedImageTypes["img-file-extensions"]:
                        modelXbrl.error(messageCodePrefix + "graphicFileType",
                            _("%(validatedObjectLabel)s references a graphics file which isn't %(allowedExtensions)s '%(attribute)s' for <%(element)s>"),
                            modelObject=elt, validatedObjectLabel=validatedObjectLabel,
                            attribute=attrValue, element=eltTag, allowedExtensions=allowedImageTypes["img-file-extensions"],
                            messageCodes=("EFM.6.05.34.graphicFileType", "EFM.5.02.05.graphicFileType", "FERC.6.05.34.graphicFileType", "FERC.5.02.05.graphicFileType"))
                    else:   # test file contents
                        try:
                            if validateGraphicFile(referenceElt, attrValue) != attrValue.lower()[-3:]:
                                modelXbrl.error(messageCodePrefix +"graphicFileContent",
                                    _("%(validatedObjectLabel)s references a graphics file which has invalid format '%(attribute)s' for <%(element)s>"),
                                    modelObject=elt, validatedObjectLabel=validatedObjectLabel,
                                    attribute=attrValue, element=eltTag,
                                    messageCodes=("EFM.6.05.34.graphicFileContent", "EFM.5.02.05.graphicFileContent", "FERC.6.05.34.graphicFileContent", "FERC.5.02.05.graphicFileContent"))
                        except IOError as err:
                            modelXbrl.error(messageCodePrefix + "graphicFileError",
                                _("%(validatedObjectLabel)s references a graphics file which isn't openable '%(attribute)s' for <%(element)s>, error: %(error)s"),
                                modelObject=elt, validatedObjectLabel=validatedObjectLabel,
                                attribute=attrValue, element=eltTag, error=err,
                                messageCodes=("EFM.6.05.34.graphicFileError", "EFM.5.02.05.graphicFileError", "FERC.6.05.34.graphicFileError", "FERC.5.02.05.graphicFileError"))
                    checkedGraphicsFiles.add(attrValue)
            if eltTag == "meta" and attrTag == "content" and not attrValue.startswith("text/html"):
                modelXbrl.error(messageCodePrefix + "disallowedMetaContent",
                    _("%(validatedObjectLabel)s <meta> content is \"%(metaContent)s\" but must be \"text/html\""),
                    modelObject=elt, validatedObjectLabel=validatedObjectLabel,
                    metaContent=attrValue,
                    messageCodes=("EFM.6.05.34.disallowedMetaContent", "EFM.5.02.05.disallowedMetaContent", "FERC.6.05.34.disallowedMetaContent", "FERC.5.02.05.disallowedMetaContent"))
        if eltTag == "table" and any(a.tag in _tableTags
                                     for a in elt.iterancestors()):
            modelXbrl.error(messageCodePrefix + "nestedTable",
                _("%(validatedObjectLabel)s has nested <table> elements."),
                modelObject=elt, validatedObjectLabel=validatedObjectLabel,
                messageCodes=("EFM.6.05.34.nestedTable", "EFM.5.02.05.nestedTable", "FERC.6.05.34.nestedTable", "FERC.5.02.05.nestedTable"))

'''
    if parent is None:
        parent = footnote

    if parent != footnote:
        for attrName, attrValue in footnote.items():
            if not (attrName in htmlAttributes and \
                (footnote.localName in htmlAttributes[attrName] or '*' in htmlAttributes[attrName])):
                modelXbrl.error("EFM.6.05.34",
                    _("Footnote %(xlinkLabel)s has attribute '%(attribute)s' not allowed for <%(element)s>"),
                    modelObject=parent, xlinkLabel=parent.get("{http://www.w3.org/1999/xlink}label"),
                    attribute=attrName, element=footnote.localName)
            elif (attrName == "href" and footnote.localName == "a") or \
                 (attrName == "src" and footnote.localName == "img"):
                if "javascript:" in attrValue:
                    modelXbrl.error("EFM.6.05.34",
                        _("Footnote %(xlinkLabel)s has javascript in '%(attribute)s' for <%(element)s>"),
                        modelObject=parent, xlinkLabel=parent.get("{http://www.w3.org/1999/xlink}label"),
                        attribute=attrName, element=footnote.localName)
                elif attrValue.startswith("http://www.sec.gov/Archives/edgar/data/") and footnote.localName == "a":
                    pass
                elif "http:" in attrValue or "https:" in attrValue or "ftp:" in attrValue:
                    modelXbrl.error("EFM.6.05.34",
                        _("Footnote %(xlinkLabel)s has an invalid external reference in '%(attribute)s' for <%(element)s>: %(value)s"),
                        modelObject=parent, xlinkLabel=parent.get("{http://www.w3.org/1999/xlink}label"),
                        attribute=attrName, element=footnote.localName, value=attrValue)

    for child in footnote.iterchildren():
        if isinstance(child,ModelObject): #element
            if not child.localName in bodyTags:
                modelXbrl.error("EFM.6.05.34",
                    _("Footnote %(xlinkLabel)s has disallowed html tag: <%(element)s>"),
                    modelObject=parent, xlinkLabel=parent.get("{http://www.w3.org/1999/xlink}label"),
                    element=child.localName)
            else:
                validateFootnote(modelXbrl, child, footnote)

    #handler.modelXbrl = None


class TextBlockHandler(xml.sax.ContentHandler, xml.sax.ErrorHandler):

    def __init__ (self, modelXbrl):
        self.modelXbrl = modelXbrl

    def startDocument(self):
        self.nestedBodyCount = 0

    def startElement(self, name, attrs):
        if name == "body":
            self.nestedBodyCount += 1
            if self.nestedBodyCount == 1:   # outer body is ok
                return
        if not name in bodyTags:
            self.modelXbrl.error("EFM.6.05.16",
                _("Fact %(fact)s of context %(contextID)s has disallowed html tag: <%(element)s>"),
                modelObject=self.fact, fact=self.fact.qname, contextID=self.fact.contextID,
                element=name)
        else:
            for item in attrs.items():
                if not (item[0] in htmlAttributes and \
                    (name in htmlAttributes[item[0]] or '*' in htmlAttributes[item[0]])):
                    self.modelXbrl.error("EFM.6.05.16",
                        _("Fact %(fact)s of context %(contextID)s has attribute '%(attribute)s' not allowed for <%(element)s>"),
                        modelObject=self.fact, fact=self.fact.qname, contextID=self.fact.contextID,
                        attribute=item[0], element=name)
                elif (item[0] == "href" and name == "a") or \
                     (item[0] == "src" and name == "img"):
                    if "javascript:" in item[1]:
                        self.modelXbrl.error("EFM.6.05.16",
                            _("Fact %(fact)s of context %(contextID)s has javascript in '%(attribute)s' for <%(element)s>"),
                            modelObject=self.fact, fact=self.fact.qname, contextID=self.fact.contextID,
                            attribute=item[0], element=name)
                    elif item[1].startswith("http://www.sec.gov/Archives/edgar/data/") and name == "a":
                        pass
                    elif "http:" in item[1] or "https:" in item[1] or "ftp:" in item[1]:
                        self.modelXbrl.error("EFM.6.05.16",
                            _("Fact %(fact)s of context %(contextID)s has an invalid external reference in '%(attribute)s' for <%(element)s>"),
                            modelObject=self.fact, fact=self.fact.qname, contextID=self.fact.contextID,
                            attribute=item[0], element=name)

    def characters (self, ch):
        if ">" in ch:
            self.modelXbrl.error("EFM.6.05.15",
                _("Fact %(fact)s of context %(contextID)s has a '>' in text, not well-formed XML: '%(text)s'"),
                 modelObject=self.fact, fact=self.fact.qname, contextID=self.fact.contextID, text=ch)

    def endElement(self, name):
        if name == "body":
            self.nestedBodyCount -= 1

    def error(self, err):
        self.modelXbrl.error("EFM.6.05.15",
            _("Fact %(fact)s of context %(contextID)s has text which causes the XML error %(error)s line %(line)s column %(column)s"),
             modelObject=self.fact, fact=self.fact.qname, contextID=self.fact.contextID,
             error=err.getMessage(), line=err.getLineNumber(), column=err.getColumnNumber())

    def fatalError(self, err):
        msg = err.getMessage()
        self.modelXbrl.error("EFM.6.05.15",
            _("Fact %(fact)s of context %(contextID)s has text which causes the XML fatal error %(error)s line %(line)s column %(column)s"),
             modelObject=self.fact, fact=self.fact.qname, contextID=self.fact.contextID,
             error=err.getMessage(), line=err.getLineNumber(), column=err.getColumnNumber())

    def warning(self, err):
        self.modelXbrl.warning("EFM.6.05.15",
            _("Fact %(fact)s of context %(contextID)s has text which causes the XML warning %(error)s line %(line)s column %(column)s"),
             modelObject=self.fact, fact=self.fact.qname, contextID=self.fact.contextID,
             error=err.getMessage(), line=err.getLineNumber(), column=err.getColumnNumber())
'''

@dataclass
class ImageDataURLParts:
    mimeSubtype: str | None
    isBase64: bool
    data: str
    def base64GraphicHeaderTypeMatchesMimeSubtype(self) -> bool:
        headerType = validateGraphicHeaderType(decodeBase64DataImage(self.data))
        return headerType == self.mimeSubtype or headerType == 'jpg' and self.mimeSubtype == 'jpeg'

def parseImageDataURL(uri: str) -> ImageDataURLParts | None:
    m = imgDataMediaBase64Pattern.match(uri)
    return ImageDataURLParts(
        mimeSubtype=m.group('mimeSubtype'),
        isBase64=bool(m.group('base64')),
        data=m.group('data'),
    ) if m else None

def validateGraphicHeaderType(data: bytes) -> str:
    if data[:2] == b"\xff\xd8":
        return "jpg"
    elif data[:3] == b"GIF" and data[3:6] in (b'89a', b'89b', b'87a'):
        return "gif"
    elif data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    elif data[:2] in (b"MM", b"II"):
        return "tiff"
    elif data[:2] in (b"BM", b"BA"):
        return "bmp"
    elif data[:4] == b"\x00\x00\x01\x00":
        return "ico"
    elif data[:4] == b"\x00\x00\x02\x00":
        return "cur"
    elif len(data) == 0:
        return "none"
    else:
        return "unrecognized"

def validateGraphicFile(elt, graphicFile):
    base = elt.modelDocument.baseForElement(elt)
    normalizedUri = elt.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(graphicFile, base)
    if not elt.modelXbrl.fileSource.isInArchive(normalizedUri):
        normalizedUri = elt.modelXbrl.modelManager.cntlr.webCache.getfilename(normalizedUri)
    # all Edgar graphic files must be resolved locally
    #normalizedUri = elt.modelXbrl.modelManager.cntlr.webCache.getfilename(normalizedUri)
    if normalizedUri: # may be None if file doesn't exist
        with elt.modelXbrl.fileSource.file(normalizedUri,binary=True)[0] as fh:
            return validateGraphicHeaderType(fh.read(11))
    return None

def referencedFiles(modelXbrl, localFilesOnly=True):
    initModelDocumentTypeReferences()
    _parser = XMLParser(resolve_entities=False, remove_comments=True, remove_pis=True, huge_tree=True, recover=True)
    referencedFiles = set()
    # add referenced files that are html-referenced image and other files
    def addReferencedFile(docElt, elt):
        if elt.tag in ("a", "img", "{http://www.w3.org/1999/xhtml}a", "{http://www.w3.org/1999/xhtml}img"):
            for attrTag, attrValue in elt.items():
                if (attrTag in ("href", "src") and
                    scheme(attrValue) not in ("data", "javascript") and (
                        not localFilesOnly or
                        (not isHttpUrl(attrValue) and not os.path.isabs(attrValue)))):
                    attrValue = attrValue.partition('#')[0].strip() # remove anchor
                    if attrValue not in ("", "."): # ignore anchor references to base document
                        base = docElt.modelDocument.baseForElement(docElt)
                        normalizedUri = docElt.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(attrValue, base)
                        if not docElt.modelXbrl.fileSource.isInArchive(normalizedUri):
                            normalizedUri = docElt.modelXbrl.modelManager.cntlr.webCache.getfilename(normalizedUri) # may be nonexistent web file, returning None
                        if normalizedUri and (modelXbrl.fileSource.isInArchive(normalizedUri, checkExistence=True) or modelXbrl.fileSource.exists(normalizedUri)):
                            referencedFiles.add(attrValue) # add file name within source directory
    for fact in modelXbrl.facts:
        if fact.concept is not None and fact.isItem and fact.concept.isTextBlock:
            # check for img and other filing references so that referenced files are included in the zip.
            text = fact.textValue
            for xmltext in [text] + CDATApattern.findall(text):
                try:
                    for elt in XML("<body>\n{0}\n</body>\n".format(xmltext), parser=_parser).iter():
                        addReferencedFile(fact, elt)
                except (XMLSyntaxError, UnicodeDecodeError):
                    pass  # TODO: Why ignore UnicodeDecodeError?
    # footnote or other elements
    if modelXbrl.modelDocument.type == ModelDocumentTypeINLINEXBRLDOCUMENTSET:
        xbrlInstRoots = modelXbrl.ixdsHtmlElements
    else:
        xbrlInstRoots = [modelXbrl.modelDocument.xmlRootElement]
    for xbrlInstRoot in xbrlInstRoots:
        for elt in xbrlInstRoot.iter("{http://www.w3.org/1999/xhtml}a", "{http://www.w3.org/1999/xhtml}img"):
            addReferencedFile(elt, elt)
    return referencedFiles
