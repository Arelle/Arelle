#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
This module offers Google analytics feature
"""
import time
from plugins.analytics.google_measurement import AppTracker, random_uuid

"""

Copyright 2012 Regis Decamps

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
from arelle import ModelManager, CntlrWinMain, DialogAbout, DialogArcroleGroup, DialogLanguage, DialogFind, DialogOpenArchive, DialogOpenTaxonomyPackage, DialogPluginManager, DialogFormulaParameters, DialogNewFactItem, DialogRssWatch, DialogURL, DialogUserPassword, ValidateFormula

__author__ = 'R\u00e9gis D\u00e9camps'
__copyright__ = "Copyright 2012, Autorit\u00e9 de contr\u00f4le prudentiel"
__credits__ = []
__license__ = "Apache-2"
__version__ = "0.2"
__email__ = "regis.decamps@banque-france.fr"
__status__ = "Development"

def google_analytics_plugin(controller):
    """
    initialize the Google analytics tracker
    """
    try:
        uid = controller.config['analytics_client_id']
    except KeyError:
        uid = random_uuid()
        controller.config['analytics_client_id'] = uid
    controller.addToLog("Initialize google analytics for anonymous user " + uid)
    # TODO How can I know the version of Arelle?
    ga = AppTracker("Arelle", "UA-36372431-1", None, version=3)
    # Monkey patching of existing methods

    # until introspection is done, the plugin tracks the windows listed below
    #DialogAbout.DialogAbout.__init__ = ga_screen_decorated(ga, DialogAbout.DialogAbout, DialogAbout.DialogAbout.__init__)
    ga_decorate_screen(ga, DialogAbout.DialogAbout)
    ga_decorate_screen(ga, DialogArcroleGroup.DialogArcroleGroup)
    ga_decorate_screen(ga, DialogFind.DialogFind)
    ga_decorate_screen(ga, DialogFormulaParameters.DialogFormulaParameters)
    ga_decorate_screen(ga, DialogLanguage.DialogLanguage)
    ga_decorate_screen(ga, DialogNewFactItem.DialogNewFactItemOptions)
    ga_decorate_screen(ga, DialogOpenArchive.DialogOpenArchive)
    ga_decorate_screen(ga, DialogPluginManager.DialogPluginManager)
    ga_decorate_screen(ga, DialogRssWatch.DialogRssWatch)
    ga_decorate_screen(ga, DialogURL.DialogURL)
    ga_decorate_screen(ga, DialogUserPassword.DialogUserPassword)

    # until introspection is done, the plugin tracks the methods explicitly listed bellow
    ModelManager.ModelManager.load = ga_function_decorated(ga, ModelManager.ModelManager.load)
    ModelManager.ModelManager.validate = ga_function_decorated(ga, ModelManager.ModelManager.validate)
    ValidateFormula.validate = ga_function_decorated(ga, ValidateFormula.validate)

    # Another option is to reuse ModileManager.pro

    # Start a new tracking session with the controller window itself
    ga.track_screen(controller.__class__.__name__,  {'sc':'start'})


def ga_decorate_screen(ga, clazz):
    clazz.__init__ = ga_screen_decorated(ga, clazz.__name__, clazz.__init__)


def ga_screen_decorated(ga, screen_class_name, screen_class_init):
    """
    Decorator for classes that represent a window
    """

    def wrapper(*args, **kwargs):
        ga.track_screen(screen_class_name)
        screen_class_init(*args, **kwargs)

    return wrapper


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
        retval = func(*args, **kwargs)
        duration = (time.time() - start_time) * 1000 # in ms
        # TODO ga.track_user_timing()
        ga.track_user_timing(func.__module__, func.__name__, int(duration))
        return retval
    return wrapper


# Manigest for this plugin
__pluginInfo__ = {
    'name': 'ga',
    'version': '0.2',
    'description': '''Google analytics collects anonymous usage statistics, so that Arelle can be improved on features that are most frequently used'''
    ,
    'localeURL': "locale",
    'localeDomain': 'ga_i18n',
    'license': 'Apache-2',
    'author': 'R\u00e9gis D\u00e9camps',
    'copyright': 'Copyright 2012 Autorit\u00e9 de contr\u00f4le prudentiel',
    'Cntrl.init': google_analytics_plugin
}
