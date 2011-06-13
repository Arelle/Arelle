'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import xml.sax, xml.sax.handler
import os, re, io
from arelle import XbrlConst

XMLpattern = re.compile(r".*(<|&lt;|&#x3C;|&#60;)[A-Za-z_]+[A-Za-z0-9_:]*[^>]*(/>|>|&gt;|/&gt;).*", re.DOTALL)
CDATApattern = re.compile(r"<!\[CDATA\[(.+)\]\]")
#EFM table 5-1 and all &xxx; patterns
docCheckPattern = re.compile(r"&\w+;|[^0-9A-Za-z`~!@#$%&\*\(\)\.\-+ \[\]\{\}\|\\:;\"'<>,_?/=\t\n\m\f]") # won't match &#nnn;
entityPattern = re.compile(r"&\w+;") # won't match &#nnn;

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

def checkfile(modelXbrl, filepath):
    result = []
    lineNum = 1
    with modelXbrl.fileSource.file(filepath) as f:
        while True:
            line = f.readline()
            if line == "":
                break;
            # check for disallowed characters or entity codes
            for match in docCheckPattern.finditer(line):
                str = match.group()
                if str.startswith("&"):
                    if not str in xhtmlEntities:
                        modelXbrl.error(
                            "Disallowed entity code {0} in file {1} line {2} col {3}".format(
                                      str, os.path.basename(filepath), lineNum, match.start()), 
                            "err", "EFM.5.2.2.6", "GFM.1.01.02")
                elif modelXbrl.modelManager.disclosureSystem.EFM:
                    modelXbrl.error(
                        "Disallowed character '{0}' in file {1} at line {2} col {3}".format(
                                  str, os.path.basename(filepath), lineNum, match.start()), 
                        "err", "EFM.5.2.1.1")
            result.append(line)
            lineNum += 1
    return io.StringIO(initial_value=''.join(result))
        
def removeEntities(text):
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

def validateTextBlockFacts(modelXbrl):
    handler = TextBlockHandler(modelXbrl)
    
    for f1 in modelXbrl.facts:
        # build keys table for 6.5.14
        concept = f1.concept
        if f1.xsiNil != "true" and \
           concept is not None and \
           concept.isTextBlock and \
           XMLpattern.match(f1.value):
            handler.fact = f1
            # test encoded entity tags
            for match in entityPattern.finditer(f1.value):
                entity = match.group()
                if not entity in xhtmlEntities:
                    modelXbrl.error(
                        _("{0} has disallowed entity {1}").format(
                                  handler.errorDescription(), entity), 
                        "err", "EFM.6.05.16", "GFM.1.2.15")                    
            # test html
            for xmltext in [f1.value] + CDATApattern.findall(f1.value):
                try:
                    xml.sax.parseString(
                        "<?xml version='1.0' encoding='utf-8' ?>\n<body>\n{0}\n</body>\n".format(
                         removeEntities(xmltext)).encode('utf-8'),handler,handler)
                except (xml.sax.SAXParseException,
                        xml.sax.SAXException,
                        UnicodeDecodeError) as err:
                    # ignore errors which are not errors (e.g., entity codes checked previously
                    if not err.endswith("undefined entity"):
                        handler.modelXbrl.error(
                            _("{0} has text which causes the XML error {1}").format(
                                      handler.errorDescription(), err), 
                            "err", "EFM.6.05.15", "GFM.1.02.14")
            handler.fact = None
    handler.modelXbrl = None
    
def validateFootnote(modelXbrl, footnote, parent=None):
    handler = TextBlockHandler(modelXbrl)
    if parent is None:
        parent = footnote
    
    if parent != footnote:
        for i in range(len(footnote.attributes)):
            attr = footnote.attributes.item(i)
            if not (attr.name in htmlAttributes and \
                (footnote.localName in htmlAttributes[attr.name] or '*' in htmlAttributes[attr.name])):
                modelXbrl.error(
                    _("Footnote {0} has attribute '{1}' not allowed for <{2}>").format(
                        footnote.getAttributeNS(XbrlConst.xlink, "label"),
                        attr.name, attr.value), 
                    "err", "EFM.6.05.34")
            elif (attr.name == "href" and footnote.localName == "a") or \
                 (attr.name == "src" and footnote.localName == "img"):
                if "javascript:" in attr.value:
                    modelXbrl.error(
                        _("Footnote {0} has javascript in '{1}' for <{2}>").format(
                        footnote.getAttributeNS(XbrlConst.xlink, "label"),
                        attr.name, footnote.localName), 
                        "err", "EFM.6.05.34")
                elif attr.value.startswith("http://www.sec.gov/Archives/edgar/data/") and footnote.localName == "a":
                    pass
                elif "http:" in attr.value or "https:" in attr.value or "ftp:" in attr.value:
                    modelXbrl.error(
                        _("Footnote {0} has an invalid external reference in '{1}' for <{2}>: {3}").format(
                        footnote.getAttributeNS(XbrlConst.xlink, "label"),
                        attr.name, footnote.localName, attr.value), 
                        "err", "EFM.6.05.34")
            
    for child in footnote.childNodes:

        if child.nodeType == 1: #element
            if not child.localName in bodyTags:
                modelXbrl.error(
                    _("Footnote {0} has disallowed html tag: <{1}>").format(
                        footnote.getAttributeNS(XbrlConst.xlink, "label"),
                        child.localName), 
                    "err", "EFM.6.05.34")
            else:
                validateFootnote(modelXbrl, child, footnote)

    handler.modelXbrl = None


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
            self.modelXbrl.error(
                _("{0} has disallowed html tag: <{1}>").format(
                          self.errorDescription(), name), 
                "err", "EFM.6.05.16")
        else:
            for item in attrs.items():
                if not (item[0] in htmlAttributes and \
                    (name in htmlAttributes[item[0]] or '*' in htmlAttributes[item[0]])):
                    self.modelXbrl.error(
                        _("{0} has attribute '{1}' not allowed for <{2}>").format(
                                  self.errorDescription(), item[0], name), 
                        "err", "EFM.6.05.16")
                elif (item[0] == "href" and name == "a") or \
                     (item[0] == "src" and name == "img"):
                    if "javascript:" in item[1]:
                        self.modelXbrl.error(
                            _("{0} has javascript in '{1}' for <{2}>").format(
                                      self.errorDescription(), item[0], name), 
                            "err", "EFM.6.05.16")
                    elif item[1].startswith("http://www.sec.gov/Archives/edgar/data/") and name == "a":
                        pass
                    elif "http:" in item[1] or "https:" in item[1] or "ftp:" in item[1]:
                        self.modelXbrl.error(
                            _("{0} has an invalid external reference in '{2}' for <{2}>").format(
                                      self.errorDescription(), item[0], name), 
                            "err", "EFM.6.05.16")

    def characters (self, ch):
        if ">" in ch:
            self.modelXbrl.error(
                _("{0} has a '>' in text, not well-formed XML: '{1}'").format(
                          self.errorDescription(), ch), 
                "err", "EFM.6.05.15")

    def endElement(self, name):
        if name == "body":
            self.nestedBodyCount -= 1
            
    def error(self, err):
        self.modelXbrl.error(
            _("{0} has text which causes the XML error {1} line {2} col {3}").format(
                      self.errorDescription(), 
                      err.getMessage(), err.getLineNumber(), err.getColumnNumber()), 
            "err", "EFM.6.05.15")
    
    def fatalError(self, err):
        msg = err.getMessage()
        self.modelXbrl.error(
            _("{0} has text which causes the XML fatal error {1} line {2} col {3}").format(
                  self.errorDescription(), 
                  msg, err.getLineNumber(), err.getColumnNumber()), 
            "err", "EFM.6.05.15")
    
    def warning(self, err):
        self.modelXbrl.error(
            _("{0} has text which causes the XML warning {1} line {2} col {3}").format(
                      self.errorDescription(), 
                      err.getMessage(), err.getLineNumber(), err.getColumnNumber()), 
            "wrn", "EFM.6.05.15")
        
    def errorDescription(self):
        return _("Fact {0} of context {1}").format(
              self.fact.qname, self.fact.contextID)
            
