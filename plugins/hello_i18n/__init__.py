__author__ = "Régis Décamps"
__version__ = "0.1"
__desc__ = '''
This is the classic "Hello World" plugin that demonstrates how to correctly
internationalize a plugin.
'''

import os, gettext, locale
#don't use `gettext.install`as it is global to the application
localedir = __path__[0] + os.sep + 'locale'
t = gettext.translation(__name__, localedir, languages=locale.getdefaultlocale())
# define a short alias
_ = t.gettext

from . import hello
