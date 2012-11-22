#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
This module is a library to build anonymous usage statistics, with Google analytics,
using the Google measurement protocol.
"""
__author__ = "Régis Décamps"
"""

Copyright 2012 Régis Décamps

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

# this should work both on Python 2 and Python 3
try:
    # exists only in Python 2
    import urllib2 as urlbib
    from urllib import urlencode
except ImportError:
    import urllib.request as urlbib
    from urllib.parse import urlencode


# TODO make this abstract
class AbstractTracker(object):
    """
    The tracker represents a tracking session for Google analytics.
    It provides methods to track screen view and events within the application.
    """
    # Google analytics API point
    GA_URL = 'http://www.google-analytics.com/collect'
    # Google analytics API version
    GA_VERSION = 1
    ENCODING = 'utf-8'

    def __init__(self, tracking_id, client_id=None, **kwargs):
        """
        Create a tracking session.

        You must provide your own Tracking ID; see http://support.google.com/analytics/bin/answer.py?answer=1032385

        The client ID identifies a particular user and device instance.
        You should generate a random Client ID for each install (see `random_uuid()`)
        and store in the application settings.

        :param tracking_id:  Tracking ID / Web property / Property ID
        :type tracking_id: string of the form UA-XXXX-Y
        :param client_id: Anonymous client ID
        :type client_id: string in the form of a RFC4122 UID, eg 35009a79-1a05-49d7-b876-2b884d0f825b


        """
        self.tracking_id = tracking_id
        if client_id is None:
            client_id = random_uuid()
        self.client_id = client_id

    def _track(self, hit_type, params=None):
        """
        Tracking method, called by subclasses.
        :param hit_type: hit type, should be provided by a subclass method.
        :param params: the query parameters, should be provided by the subclass method.
        """
        params['v'] = AbstractTracker.GA_VERSION
        params['tid'] = self.tracking_id
        params['cid'] = self.client_id
        params['c'] = hit_type

        query = urlencode(params).encode(AbstractTracker.ENCODING)
        request = urllib.Request(AbstractTracker.GA_URL)
        # adding charset parameter to the Content-Type header.
        request.add_header('Content-Type', "application/x-www-form-urlencoded;charset=" + AbstractTracker.ENCODING)
        print(request)
        print(query)
        #response = urlbib.urlopen(request, query)
        # TODO handle response?


class AppTracker(AbstractTracker):
    """
    A Google analytics tracker for mobile or desktop applications.
    """

    def __init__(self, app_name, tracking_id, client_id, **kwargs):
        """
        :param app_name: The application name
        :type app_name: string

        Keyword arguments can be:

        * `version`: version of the application. Default value: 1.
        """
        super(AbstractTracker, self).__init__(self, tracking_id, client_id, **kwargs)
        self.app_name = app_name
        self.app_version = kwargs.get('version', 1)

    def track_screen(self):
        params = {}
        params['an'] = self.app_name
        params['av'] = self.app_version
        self._track('appview', params)


def random_uuid():
    """
    Generates a random UUID, based on the host ID and current time, as defined per RFC 4122 uuid1.
    :return: a UUID `str`
    """
    import uuid

    u = uuid.uuid1()
    return str(u)


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
