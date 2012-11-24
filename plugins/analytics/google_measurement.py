#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
This module is a library to build anonymous usage statistics, with Google analytics,
using the Google measurement protocol.
"""
# this should work both on Python 2 and Python 3
try:
    # exists only in Python 2
    import urllib2 as urlbib
    from urllib import urlencode
except ImportError:
    import urllib.request as urlbib
    from urllib.parse import urlencode

__author__ = "Régis Décamps"
__license__="""Copyright 2012 Régis Décamps

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

        data = urlencode(params).encode(AbstractTracker.ENCODING)
        request = urlbib.Request(AbstractTracker.GA_URL, data)
        # adding charset parameter to the Content-Type header.
        request.add_header('Content-Type', "application/x-www-form-urlencoded;charset=" + AbstractTracker.ENCODING)
        response = urlbib.urlopen(request)
        # TODO handle response?
        with open("ga.gif",'wb') as f:
            while not response.closed:
                f.write(response.read())

class AppTracker(AbstractTracker):
    """
    A Google analytics tracker for mobile or desktop applications.
    """

    def __init__(self, app_name, tracking_id, client_id=None, **kwargs):
        """
        :param app_name: The application name
        :type app_name: string

        Keyword arguments can be:

        * `version`: version of the application. Default value: 1.
        """
        super(AppTracker, self).__init__(tracking_id, client_id, **kwargs)
        self.app_name = app_name
        self.app_version = kwargs.get('version', 1)

    def _track(self, hit_type, params=None):
        if params is None:
            params = dict()
        params['an'] = self.app_name
        params['av'] = self.app_version
        super(AppTracker,self)._track(hit_type, params)


    def track_screen(self,screen_name):
        """
        Track a screen view.
        """
        params = dict()
        params['cd'] = screen_name
        self._track('appview', params)

    def track_event(self, category, action):
        """
        Track an event within the application.
        """
        params = dict()
        params['ec'] = category
        params['ea'] = action
        self._track('event', params)

    def track_user_timing(self, category, variable, duration, label=None):
        """
        :param category: Specifies the user timing category.
        :param variable: Specifies the user timing variable.
        :param duration: Specifies the user timing value.
        :type duration: `int` value in milliseconds.
        """
        params = dict()
        params['utc'] = category
        params['utv'] = variable
        params['utt'] = duration
        if label is not None:
            params['utv'] = label
        self._track('timing', params)


def random_uuid():
    """
    Generates a random UUID, based on the host ID and current time, as defined per RFC 4122 uuid1.
    :return: a UUID `str`
    """
    import uuid

    u = uuid.uuid1()
    return str(u)
