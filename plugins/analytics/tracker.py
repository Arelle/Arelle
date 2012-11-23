"""
This module offers Google analytics feature
"""
import time
from plugins.analytics.google_measurement import AppTracker, random_uuid

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

# defined __STR_BASE
from arelle import ModelManager, CntlrWinMain

__author__ = 'R\u00e9gis D\u00e9camps'
__copyright__ = "Copyright 2012, Autorit\u00e9 de contr\u00f4le prudentiel"
__credits__ = []
__license__ = "Apache-2"
__version__ = "0.1"
__email__ = "regis.decamps@banque-france.fr"
__status__ = "Development"

def google_analytics_plugin(controller):
    """
    initialize the Google analytics tracker
    """
    try:
        uid = controller.config['uuid']
    except KeyError:
        uid = random_uuid()
        controller.config['uuid'] = uid
    controller.addToLog("Initialize google analytics for anonymous user " + uid)
    ga = AppTracker("Arelle", "UA-36372431-1", None, version=3)
    # Monkey patching of existing methods
    # until introspection is done, the plugin tracks the methods explicitly listed bellow
    ModelManager.ModelManager.load = ga_function_decorated(ga, ModelManager.ModelManager.load)
    ModelManager.ModelManager.validate = ga_function_decorated(ga, ModelManager.ModelManager.validate)


def ga_function_decorated(ga, func):
    """
    Decorator for functions call, that will be tracked with Google ga.
    """

    def wrapper(*args, **kwargs):
        """
        This wrapper precedes a function call with a call to Google Analytics events,
        and succedes with a call to Google Analytics user timing.
        """
        # Call (async?) Google ga before the function is executed
        ga.track_event(func.__module__, func.__name__)
        start_time = time.time()
        # actually call the function
        func(*args, **kwargs)
        duration = (time.time() - start_time) * 1000 # in ms
        # TODO ga.track_user_timing()
        ga.track_user_timing(func.__module__, func.__name__, int(duration))

    return wrapper


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
    'Cntrl.init': google_analytics_plugin
}
