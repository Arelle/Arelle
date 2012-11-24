#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
This module is a library to build anonymous usage statistics, with Google analytics,
using the Google measurement protocol.
"""
# this should work both on Python 2 and Python 3
import threading

try:
    # exists only in Python 3
    import urllib.request as urlbib
    from urllib.parse import urlencode
    import queue
except ImportError:
    # Python 2
    import urllib2 as urlbib
    from urllib import urlencode
    import Queue as queue

__author__ = "Régis Décamps"
__license__ = """Copyright 2012 Régis Décamps

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

# List of complementary arguments that can be used in keyword arguments.
FIELDNAME_TO_PARAM = {
    # User language
    "language": 'ul',
    # When present, the IP address of the sender will be anonymized. For example, the IP will be anonymized if any of the following parameters are present in the payload: &aip=, &aip=0, or &aip=1
    "anonymizeIp": 'aip',
    # The character set used to encode the page / document.
    "encoding": 'de'
}

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
        self.params = dict()
        self.params['tid'] = tracking_id
        if client_id is None:
            client_id = random_uuid()
        self.params['cid'] = client_id
        self.params['v'] = AbstractTracker.GA_VERSION

        for k in kwargs:
            if k in FIELDNAME_TO_PARAM:
                self.params[FIELDNAME_TO_PARAM[k]] = kwargs[k]

        self.post_queue = queue.Queue()
        # spawn a new thread for HTTP requests
        threading.Thread(target=self._http_post_worker).start()


    def _track(self, hit_type, params=None):
        """
        Tracking method, called by subclasses.
        :param hit_type: hit type, should be provided by a subclass method.
        :param prams: A dict of other query parameters, should be provided by the subclass method.
        """
        http_params = dict()
        http_params.update(self.params)
        http_params['t'] = hit_type
        if params is not None:
            http_params.update(params)

        self.post_queue.put(http_params)

    def _http_post_worker(self):
        while True:
            params = self.post_queue.get(block=True)
            print(params)
            data = urlencode(params).encode(AbstractTracker.ENCODING)
            request = urlbib.Request(AbstractTracker.GA_URL, data)
            # adding charset parameter to the Content-Type header.
            request.add_header('Content-Type', "application/x-www-form-urlencoded;charset=" + AbstractTracker.ENCODING)
            response = urlbib.urlopen(request)
            # TODO handle response?


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
        self.params['an'] = app_name
        self.params['av'] = kwargs.get('version', 1)


    def track_screen(self, screen_name, params=None):
        """
        Track a screen view.
        """
        if params is None:
            params = dict()
        params['cd'] = screen_name
        self._track('appview', params)

    def track_event(self, category, action, label=None, value=-1, params=None):
        """
        Track an event within the application.
        :param category:  a category is a name that you supply as a way to group objects that you want to track. The term Category appears in the reporting interface as Top Categories in the Events Overview page.
        :param action: Typically, you will use the action parameter to name the type of event or interaction you want to track for a particular web object. For example, with a single "Videos" category, you can track a number of specific events with this parameter, such as play, stop, pause. You can supply any string for the action parameter. In some situations, the actual event or action name is not as meaningful, so you might use the action parameter to track other elements. For example, if you want to track page downloads, you could provide the document file type as the action parameter for the download event.
        :param label: With labels, you can provide additional information for events that you want to track, such as the movie title in the video example
        :param value: The report displays the total and average value for events. You can use this to track time, but there is also track_user_timing() for tat purpose.
        :type value: `int`
        """
        if params is None:
            params = dict()
        params['ec'] = category
        params['ea'] = action
        if label is not None:
            params['el'] = label
        if value > -1:
            params['ev'] = value
        self._track('event', params)

    def track_user_timing(self, category, variable, duration, label=None, params=None):
        """
        :param category: Specifies the user timing category.
        :param variable: Specifies the user timing variable, the name of the action of the resource being tracked.
        :param duration: Specifies the user timing value. the number of milliseconds in elapsed time.
        :type duration: `int` value in milliseconds
        :param label: add flexibility in visualizing user timings in the reports. Labels can also be used to focus on different sub experiments for the same category and variable combination.
        """
        if params is None:
            params = dict()
        params['utc'] = category
        params['utv'] = variable
        params['utt'] = duration
        if label is None:
            label = category + '.' + variable
        params['utl'] = label
        self._track('timing', params)


def random_uuid():
    """
    Generates a random UUID, based on the host ID and current time, as defined per RFC 4122 uuid1.
    :return: a UUID `str`
    """
    import uuid

    u = uuid.uuid1()
    return str(u)
