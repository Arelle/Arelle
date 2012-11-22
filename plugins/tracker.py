"""
This module offers Google analytics feature
"""

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

from .google_measurement import AppTracker
# defined __STR_BASE
from arelle import ModelManager

__author__ = 'R\u00e9gis D\u00e9camps'
__copyright__ = "Copyright 2012, Autorit\u00e9 de contr\u00f4le prudentiel"
__credits__ = []
__license__ = "Apache-2"
__version__ = "0.1"
__email__ = "regis.decamps@banque-france.fr"
__status__ = "Development"

def google_analytics_plugin(controler):
    """
    initialize the Google analytics tracker
    """
    controler.addToLog("Initialize google analytics")
    ga = AppTracker("UA-36372431-1", None)
    # Monkey patching of existing methods
    # until introspection is done, the plugin tracks the methods explicitly listed bellow
    ModelManager.ModelManager.load  = ga_decorated(ga, ModelManager.ModelManager.load)

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
    'Cntrl.init': google_analytics_plugin
}
