'''
Created on Oct 22, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import re, os, sys
if sys.version[0] >= '3':
    from urllib.parse import urldefrag, unquote
    isPy3 = True
else:
    from urlparse import urldefrag
    from arelle.PythonUtil import py3unquote as unquote
    isPy3 = False

def authority(url):
    if url is not None and url.startswith("http://"):
        pathpart = url.find("/",7)
        if pathpart > -1:
            return url[0:pathpart]
    return url  #no path part of url

absoluteUrlPattern = None
# this pattern doesn't allow some valid unicode characters
#relativeUrlPattern = re.compile(r"(^[/:\.+-_@%;?&=!~\*'\(\)\w ]+(#[\w_%\-\.\(/\)]+)?$)|(^#[\w_%\-\.\(/\)]+$)")
# try this instead from http://www.ietf.org/rfc/rfc2396.txt (B)
relativeUrlPattern = re.compile(r"^(([^:/\?#]+):)?(//([^/\?#]*))?([^\?#]*)(\?([^#]*))?(#([^#]*))?$")

def splitDecodeFragment(url):
    urlPart, fragPart = urldefrag(url)
    if isPy3:
        return (urlPart, unquote(fragPart, "utf-8", errors=None))
    else:
        return _STR_UNICODE(urlPart), unquote(_STR_UNICODE(fragPart), "utf-8", errors=None)

def isValidAbsolute(url):
    global absoluteUrlPattern
    if absoluteUrlPattern is None:
        # regex to validate a full URL from http://stackoverflow.com/questions/827557/how-do-you-validate-a-url-with-a-regular-expression-in-python/835527#835527
        absoluteUrlPattern = re.compile(
            r"(?:http://(?:(?:(?:(?:(?:[a-zA-Z\d](?:(?:[a-zA-Z\d]|-)*[a-zA-Z\d])?)\."
            r")*(?:[a-zA-Z](?:(?:[a-zA-Z\d]|-)*[a-zA-Z\d])?))|(?:(?:\d+)(?:\.(?:\d+)"
            r"){3}))(?::(?:\d+))?)(?:/(?:(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F"
            r"\d]{2}))|[;:@&=])*)(?:/(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{"
            r"2}))|[;:@&=])*))*)(?:\?(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{"
            r"2}))|[;:@&=])*))?)?)|(?:ftp://(?:(?:(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?"
            r":%[a-fA-F\d]{2}))|[;?&=])*)(?::(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-"
            r"fA-F\d]{2}))|[;?&=])*))?@)?(?:(?:(?:(?:(?:[a-zA-Z\d](?:(?:[a-zA-Z\d]|-"
            r")*[a-zA-Z\d])?)\.)*(?:[a-zA-Z](?:(?:[a-zA-Z\d]|-)*[a-zA-Z\d])?))|(?:(?"
            r":\d+)(?:\.(?:\d+)){3}))(?::(?:\d+))?))(?:/(?:(?:(?:(?:[a-zA-Z\d$\-_.+!"
            r"*'(),]|(?:%[a-fA-F\d]{2}))|[?:@&=])*)(?:/(?:(?:(?:[a-zA-Z\d$\-_.+!*'()"
            r",]|(?:%[a-fA-F\d]{2}))|[?:@&=])*))*)(?:;type=[AIDaid])?)?)|(?:news:(?:"
            r"(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))|[;/?:&=])+@(?:(?:("
            r"?:(?:[a-zA-Z\d](?:(?:[a-zA-Z\d]|-)*[a-zA-Z\d])?)\.)*(?:[a-zA-Z](?:(?:["
            r"a-zA-Z\d]|-)*[a-zA-Z\d])?))|(?:(?:\d+)(?:\.(?:\d+)){3})))|(?:[a-zA-Z]("
            r"?:[a-zA-Z\d]|[_.+-])*)|\*))|(?:nntp://(?:(?:(?:(?:(?:[a-zA-Z\d](?:(?:["
            r"a-zA-Z\d]|-)*[a-zA-Z\d])?)\.)*(?:[a-zA-Z](?:(?:[a-zA-Z\d]|-)*[a-zA-Z\d"
            r"])?))|(?:(?:\d+)(?:\.(?:\d+)){3}))(?::(?:\d+))?)/(?:[a-zA-Z](?:[a-zA-Z"
            r"\d]|[_.+-])*)(?:/(?:\d+))?)|(?:telnet://(?:(?:(?:(?:(?:[a-zA-Z\d$\-_.+"
            r"!*'(),]|(?:%[a-fA-F\d]{2}))|[;?&=])*)(?::(?:(?:(?:[a-zA-Z\d$\-_.+!*'()"
            r",]|(?:%[a-fA-F\d]{2}))|[;?&=])*))?@)?(?:(?:(?:(?:(?:[a-zA-Z\d](?:(?:[a"
            r"-zA-Z\d]|-)*[a-zA-Z\d])?)\.)*(?:[a-zA-Z](?:(?:[a-zA-Z\d]|-)*[a-zA-Z\d]"
            r")?))|(?:(?:\d+)(?:\.(?:\d+)){3}))(?::(?:\d+))?))/?)|(?:gopher://(?:(?:"
            r"(?:(?:(?:[a-zA-Z\d](?:(?:[a-zA-Z\d]|-)*[a-zA-Z\d])?)\.)*(?:[a-zA-Z](?:"
            r"(?:[a-zA-Z\d]|-)*[a-zA-Z\d])?))|(?:(?:\d+)(?:\.(?:\d+)){3}))(?::(?:\d+"
            r"))?)(?:/(?:[a-zA-Z\d$\-_.+!*'(),;/?:@&=]|(?:%[a-fA-F\d]{2}))(?:(?:(?:["
            r"a-zA-Z\d$\-_.+!*'(),;/?:@&=]|(?:%[a-fA-F\d]{2}))*)(?:%09(?:(?:(?:[a-zA"
            r"-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))|[;:@&=])*)(?:%09(?:(?:[a-zA-Z\d$"
            r"\-_.+!*'(),;/?:@&=]|(?:%[a-fA-F\d]{2}))*))?)?)?)?)|(?:wais://(?:(?:(?:"
            r"(?:(?:[a-zA-Z\d](?:(?:[a-zA-Z\d]|-)*[a-zA-Z\d])?)\.)*(?:[a-zA-Z](?:(?:"
            r"[a-zA-Z\d]|-)*[a-zA-Z\d])?))|(?:(?:\d+)(?:\.(?:\d+)){3}))(?::(?:\d+))?"
            r")/(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))*)(?:(?:/(?:(?:[a-zA"
            r"-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))*)/(?:(?:[a-zA-Z\d$\-_.+!*'(),]|("
            r"?:%[a-fA-F\d]{2}))*))|\?(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]"
            r"{2}))|[;:@&=])*))?)|(?:mailto:(?:(?:[a-zA-Z\d$\-_.+!*'(),;/?:@&=]|(?:%"
            r"[a-fA-F\d]{2}))+))|(?:file://(?:(?:(?:(?:(?:[a-zA-Z\d](?:(?:[a-zA-Z\d]"
            r"|-)*[a-zA-Z\d])?)\.)*(?:[a-zA-Z](?:(?:[a-zA-Z\d]|-)*[a-zA-Z\d])?))|(?:"
            r"(?:\d+)(?:\.(?:\d+)){3}))|localhost)?/(?:(?:(?:(?:[a-zA-Z\d$\-_.+!*'()"
            r",]|(?:%[a-fA-F\d]{2}))|[?:@&=])*)(?:/(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|("
            r"?:%[a-fA-F\d]{2}))|[?:@&=])*))*))|(?:prospero://(?:(?:(?:(?:(?:[a-zA-Z"
            r"\d](?:(?:[a-zA-Z\d]|-)*[a-zA-Z\d])?)\.)*(?:[a-zA-Z](?:(?:[a-zA-Z\d]|-)"
            r"*[a-zA-Z\d])?))|(?:(?:\d+)(?:\.(?:\d+)){3}))(?::(?:\d+))?)/(?:(?:(?:(?"
            r":[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))|[?:@&=])*)(?:/(?:(?:(?:[a-"
            r"zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))|[?:@&=])*))*)(?:(?:;(?:(?:(?:["
            r"a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))|[?:@&])*)=(?:(?:(?:[a-zA-Z\d"
            r"$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))|[?:@&])*)))*)|(?:ldap://(?:(?:(?:(?:"
            r"(?:(?:[a-zA-Z\d](?:(?:[a-zA-Z\d]|-)*[a-zA-Z\d])?)\.)*(?:[a-zA-Z](?:(?:"
            r"[a-zA-Z\d]|-)*[a-zA-Z\d])?))|(?:(?:\d+)(?:\.(?:\d+)){3}))(?::(?:\d+))?"
            r"))?/(?:(?:(?:(?:(?:(?:(?:[a-zA-Z\d]|%(?:3\d|[46][a-fA-F\d]|[57][Aa\d])"
            r")|(?:%20))+|(?:OID|oid)\.(?:(?:\d+)(?:\.(?:\d+))*))(?:(?:%0[Aa])?(?:%2"
            r"0)*)=(?:(?:%0[Aa])?(?:%20)*))?(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F"
            r"\d]{2}))*))(?:(?:(?:%0[Aa])?(?:%20)*)\+(?:(?:%0[Aa])?(?:%20)*)(?:(?:(?"
            r":(?:(?:[a-zA-Z\d]|%(?:3\d|[46][a-fA-F\d]|[57][Aa\d]))|(?:%20))+|(?:OID"
            r"|oid)\.(?:(?:\d+)(?:\.(?:\d+))*))(?:(?:%0[Aa])?(?:%20)*)=(?:(?:%0[Aa])"
            r"?(?:%20)*))?(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))*)))*)(?:("
            r"?:(?:(?:%0[Aa])?(?:%20)*)(?:[;,])(?:(?:%0[Aa])?(?:%20)*))(?:(?:(?:(?:("
            r"?:(?:[a-zA-Z\d]|%(?:3\d|[46][a-fA-F\d]|[57][Aa\d]))|(?:%20))+|(?:OID|o"
            r"id)\.(?:(?:\d+)(?:\.(?:\d+))*))(?:(?:%0[Aa])?(?:%20)*)=(?:(?:%0[Aa])?("
            r"?:%20)*))?(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))*))(?:(?:(?:"
            r"%0[Aa])?(?:%20)*)\+(?:(?:%0[Aa])?(?:%20)*)(?:(?:(?:(?:(?:[a-zA-Z\d]|%("
            r"?:3\d|[46][a-fA-F\d]|[57][Aa\d]))|(?:%20))+|(?:OID|oid)\.(?:(?:\d+)(?:"
            r"\.(?:\d+))*))(?:(?:%0[Aa])?(?:%20)*)=(?:(?:%0[Aa])?(?:%20)*))?(?:(?:[a"
            r"-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))*)))*))*(?:(?:(?:%0[Aa])?(?:%2"
            r"0)*)(?:[;,])(?:(?:%0[Aa])?(?:%20)*))?)(?:\?(?:(?:(?:(?:[a-zA-Z\d$\-_.+"
            r"!*'(),]|(?:%[a-fA-F\d]{2}))+)(?:,(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-f"
            r"A-F\d]{2}))+))*)?)(?:\?(?:base|one|sub)(?:\?(?:((?:[a-zA-Z\d$\-_.+!*'("
            r"),;/?:@&=]|(?:%[a-fA-F\d]{2}))+)))?)?)?)|(?:(?:z39\.50[rs])://(?:(?:(?"
            r":(?:(?:[a-zA-Z\d](?:(?:[a-zA-Z\d]|-)*[a-zA-Z\d])?)\.)*(?:[a-zA-Z](?:(?"
            r":[a-zA-Z\d]|-)*[a-zA-Z\d])?))|(?:(?:\d+)(?:\.(?:\d+)){3}))(?::(?:\d+))"
            r"?)(?:/(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))+)(?:\+(?:(?:"
            r"[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))+))*(?:\?(?:(?:[a-zA-Z\d$\-_"
            r".+!*'(),]|(?:%[a-fA-F\d]{2}))+))?)?(?:;esn=(?:(?:[a-zA-Z\d$\-_.+!*'(),"
            r"]|(?:%[a-fA-F\d]{2}))+))?(?:;rs=(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA"
            r"-F\d]{2}))+)(?:\+(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))+))*)"
            r"?))|(?:cid:(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))|[;?:@&="
            r"])*))|(?:mid:(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))|[;?:@"
            r"&=])*)(?:/(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))|[;?:@&=]"
            r")*))?)|(?:vemmi://(?:(?:(?:(?:(?:[a-zA-Z\d](?:(?:[a-zA-Z\d]|-)*[a-zA-Z"
            r"\d])?)\.)*(?:[a-zA-Z](?:(?:[a-zA-Z\d]|-)*[a-zA-Z\d])?))|(?:(?:\d+)(?:\."
            r"(?:\d+)){3}))(?::(?:\d+))?)(?:/(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a"
            r"-fA-F\d]{2}))|[/?:@&=])*)(?:(?:;(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a"
            r"-fA-F\d]{2}))|[/?:@&])*)=(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d"
            r"]{2}))|[/?:@&])*))*))?)|(?:imap://(?:(?:(?:(?:(?:(?:(?:[a-zA-Z\d$\-_.+"
            r"!*'(),]|(?:%[a-fA-F\d]{2}))|[&=~])+)(?:(?:;[Aa][Uu][Tt][Hh]=(?:\*|(?:("
            r"?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))|[&=~])+))))?)|(?:(?:;["
            r"Aa][Uu][Tt][Hh]=(?:\*|(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2"
            r"}))|[&=~])+)))(?:(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))|["
            r"&=~])+))?))@)?(?:(?:(?:(?:(?:[a-zA-Z\d](?:(?:[a-zA-Z\d]|-)*[a-zA-Z\d])"
            r"?)\.)*(?:[a-zA-Z](?:(?:[a-zA-Z\d]|-)*[a-zA-Z\d])?))|(?:(?:\d+)(?:\.(?:"
            r"\d+)){3}))(?::(?:\d+))?))/(?:(?:(?:(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:"
            r"%[a-fA-F\d]{2}))|[&=~:@/])+)?;[Tt][Yy][Pp][Ee]=(?:[Ll](?:[Ii][Ss][Tt]|"
            r"[Ss][Uu][Bb])))|(?:(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))"
            r"|[&=~:@/])+)(?:\?(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))|["
            r"&=~:@/])+))?(?:(?:;[Uu][Ii][Dd][Vv][Aa][Ll][Ii][Dd][Ii][Tt][Yy]=(?:[1-"
            r"9]\d*)))?)|(?:(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))|[&=~"
            r":@/])+)(?:(?:;[Uu][Ii][Dd][Vv][Aa][Ll][Ii][Dd][Ii][Tt][Yy]=(?:[1-9]\d*"
            r")))?(?:/;[Uu][Ii][Dd]=(?:[1-9]\d*))(?:(?:/;[Ss][Ee][Cc][Tt][Ii][Oo][Nn"
            r"]=(?:(?:(?:[a-zA-Z\d$\-_.+!*'(),]|(?:%[a-fA-F\d]{2}))|[&=~:@/])+)))?))"
            r")?)|(?:nfs:(?:(?://(?:(?:(?:(?:(?:[a-zA-Z\d](?:(?:[a-zA-Z\d]|-)*[a-zA-"
            r"Z\d])?)\.)*(?:[a-zA-Z](?:(?:[a-zA-Z\d]|-)*[a-zA-Z\d])?))|(?:(?:\d+)(?:"
            r"\.(?:\d+)){3}))(?::(?:\d+))?)(?:(?:/(?:(?:(?:(?:(?:[a-zA-Z\d\$\-_.!~*'"
            r"(),])|(?:%[a-fA-F\d]{2})|[:@&=+])*)(?:/(?:(?:(?:[a-zA-Z\d\$\-_.!~*'(),"
            r"])|(?:%[a-fA-F\d]{2})|[:@&=+])*))*)?)))?)|(?:/(?:(?:(?:(?:(?:[a-zA-Z\d"
            r"\$\-_.!~*'(),])|(?:%[a-fA-F\d]{2})|[:@&=+])*)(?:/(?:(?:(?:[a-zA-Z\d\$\-"
            r"_.!~*'(),])|(?:%[a-fA-F\d]{2})|[:@&=+])*))*)?))|(?:(?:(?:(?:(?:[a-zA-"
            r"Z\d\$\-_.!~*'(),])|(?:%[a-fA-F\d]{2})|[:@&=+])*)(?:/(?:(?:(?:[a-zA-Z\d"
            r"\$\-_.!~*'(),])|(?:%[a-fA-F\d]{2})|[:@&=+])*))*)?)))" )
    return absoluteUrlPattern.match(url) is not None
       
def isValid(url):
    return relativeUrlPattern.match(url) is not None

def isAbsolute(url):
    if url:
        scheme, sep, path = url.partition(":")
        if scheme in ("http", "https", "ftp"):
            return path.startswith("//")
        if scheme == "urn":
            return True
    return False

def parseRfcDatetime(rfc2822date):
    from email.utils import parsedate
    from datetime import datetime
    if rfc2822date:
        d = parsedate(rfc2822date)
        if d:
            return datetime(d[0],d[1],d[2],d[3],d[4],d[5])
    return None
       
def relativeUri(baseUri, relativeUri): # return uri relative to this modelDocument uri
    if relativeUri.startswith('http://'):
        return relativeUri
    else:
        return os.path.relpath(relativeUri, os.path.dirname(baseUri)).replace('\\','/')

