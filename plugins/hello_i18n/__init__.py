__author__ = "Régis Décamps"
__version__ = "0.1"
__desc__ = '''
This is the classic "Hello World" plugin that demonstrates how to correctly
internationalize a plugin.
'''

import os, gettext, locale

#don't use `gettext.install`as it is global to the application
from arelle import apf
_ = apf.l10n(__path__,__name__)
#  _("hello world") will now return the locale version of "hello world"
from . import hello
