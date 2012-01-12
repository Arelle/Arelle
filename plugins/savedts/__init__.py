__author__ = "Régis Décamps"
__version__ = "0.1"
__desc__ = '''
This plugin adds a feature to package the whole DTS into a zip archive.
Note that remote files are not included in the package.
'''
import os, gettext, locale
from arelle import apf
#don't use `gettext.install` as it is global to the application
_ = apf.l10n(__path__, __name__)

from . import savedts
