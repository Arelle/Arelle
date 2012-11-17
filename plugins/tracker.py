# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish, dis-
# tribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the fol-
# lowing conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABIL-
# ITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHOR BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, 
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.


import random
# Adapted by Regis to work on Python 2 & 3
try:
    import urllib2 as urllib
except ImportError:
    import urllib.request as urllib

# defined __STR_BASE
from arelle import PythonUtil
from arelle import ModelManager

__author__ = 'R\u00e9gis D\u00e9camps'
__copyright__ = "Copyright 2012, Autorit\u00e9 de contr\u00f4le prudentiel"
__credits__ = ["Chris Moyer"]
__license__ = "Apache-2"
__version__ = "0.1"
__email__ = "regis.decamps@banque-france.fr"
__status__ = "Development"

def google_analytics_plugin(controller):
    """
    initialize the Google analytics tracker
    """
    controller.addToLog("Initialize google analytics")
    ga = GATracker("UA-36372431-1", None)
    # Monkey patching of existing methods
    # until introspection is done, the plugin tracks the methods explicitly listed bellow
    ModelManager.ModelManager.load = ga_decorated(ga, ModelManager.ModelManager.load)


def ga_decorated(ga, func):
    """
    Decorator for functions that will be tracked with Google ga.
    """

    def wrapper(*args, **kwargs):
        """
        This wrapper precedes a function call with a call to Google ga.
        """
        # Call (async?) Google ga before the function is executed
        ga_function(ga, func)

        func(*args, **kwargs)

    return wrapper


def ga_function(ga, function):
    """
    Track the invocation of a function.
    """
    # TODO This returns a GIF image and I have no idea what I should do of it
    # ga.trackPage(url, ip, title, value)
    ga.trackPageview(function.__module__, None, function.__name__, "")

# Manigest for this plugin
__pluginInfo__ = {
    'name': 'ga',
    'version': '0.1',
    'description': '''Google analytics collects anonymous usage statistics, so that Arelle can be improved on features that are most frequently used''',
    'localeURL': "locale",
    'localeDomain': 'ga_i18n',
    'license': 'Apache-2',
    'author': 'R\u00e9gis D\u00e9camps',
    'copyright': '(c) Copyright 2012 Mark V Systems Limited, All rights reserved.',
    'ModelManager.load': google_analytics_plugin
}

# This module comes from https://bitbucket.org/cmoyer/pyga/src/b17332438b6f/ga/tracker.py
class GATracker(object):
    """Google Analytics Tracker
    Much thanks to http://www.vdgraaf.info/google-ga-without-javascript.html
    for describing how to do this server-side
    """
    GA_HOST = "https://ssl.google-analytics.com"
    GA_PATH = "__utm.gif"
    GA_VERSION = "4.4sh"

    def __init__(self, utmac, utmhn, session=None):
        """Initialize the tracker with the UA code, and the Hostname"""
        random.seed()
        self.utmac = utmac # The UA code (UA-000000-1)
        self.utmhn = utmhn # The Hostname to track under
        if not session:
            session = random.randint(10000000, 99999999)
        self.session = session # The session ID for this user


    def trackEvent(self, category=None, action="", label="", value="", url="/", title="", ip=None, referrer="-"):
        """Track a specific event
        @param category: The category of this event
        @type category: str
        @param action: The action name of this event
        @type action: str
        @param label: An optional label for this event
        @type label: str
        @param value: An optional value for this event
        @type value: str
        @param url: The URL that we say they hit
        @type url: str
        @param title: The Page Title of the URL they hit
        @type title: str
        @param ip: An optional IP address to set in the X-Forwarded-For
        @type ip: str or None
        @param referrer: An optional Referrer
        @type referrer: str
        """
        # Make the "value" safe
        # Strip out all non-alphanumeric characters
        import re

        safe_chars = re.compile('[\W_]+')
        value = safe_chars.sub('', value)[0:40]

        args = []
        args.append(['utmwv', self.GA_VERSION])
        args.append(['utmn', self.session])
        args.append(['utmhn', self.utmhn])
        title = urllib.quote(title.strip()[0:1024], "")
        referrer = urllib.quote(referrer, "")
        if not url.startswith("/"):
            url = "/%s" % url
        if category:
            category = urllib.quote(category, "")
            action = urllib.quote(action, "")
            label = urllib.quote(label, "")
            args.append(['utmt', 'event'])
            args.append(['utme', '5(%s*%s*%s)' % (category, action, label)])
        args.append(['utmdt', title])
        args.append(['utmhid', random.randint(100000000, 999999999)])
        args.append(['utmr', referrer])
        args.append(['utmp', urllib.quote(url, "")])
        args.append(['utmac', self.utmac])
        utmcc = [
            "__utma%3D999.999.999.999.999.1%3B",
            "__utmv%3D" + str(domainHash(self.utmhn)) + "." + str(value) + "%3B",
        ]
        args.append(['utmcc', "%2B".join(utmcc)])
        args.append(['gaq', '1'])

        arg_str = None
        for arg in args:
            s = "%s=%s" % (arg[0], arg[1])
            if not arg_str:
                arg_str = s
            else:
                arg_str += "&%s" % s

        request = urllib.Request("%s/%s?%s" % (self.GA_HOST, self.GA_PATH, arg_str))
        request.add_header("Referer", "http://%s%s" % (self.utmhn, url))
        if ip:
            request.add_header("X-Forwarded-For", ip)
        return urllib.urlopen(request).read()

    def trackPageview(self, url="/", ip=None, title="", value=""):
        return self.trackEvent(url=url, ip=ip, title=title, value=value)

# Domain Hash Function from GoogleAnalytics ga.js
def domainHash(d):
    a = 1
    c = 0
    if d:
        a = 0
        h = len(d) - 1
        while h >= 0:
            o = ord(d[h])
            a = (a << 6 & 268435455) + o + (o << 14)
            c = a & 266338304
            if c != 0:
                a = a ^ c >> 21
            h -= 1
    return a
