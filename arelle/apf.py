__author__ = "Régis Décamps"

import os, imp, sys
import locale, gettext

'''
Arelle plugin framework is heavily inspired by Marty Alchin's Simple plugin framework.
http://martyalchin.com/2008/jan/10/simple-plugin-framework/
'''
PLUGIN_DIRECTORY = "plugins"
_ = lambda x:x #TODO: load arelle gettext
def l10n(modulepath, domain):
    ''' This utility function returns the gettext.gettext method for the default locale
    when it is available. Otherwise it returns the identity function.
    A plugin should use it this way:
    _ = apf.gettext()
    '''
    if isinstance(modulepath, list):
        modulepath = modulepath[0]
    try:
        localedir = modulepath + os.sep + 'locale'
        languages = locale.getdefaultlocale()
        t = gettext.translation(domain, localedir, languages)
        # define a short alias
        return t.gettext
    except:
        print(sys.exc_info())
        return lambda x: x
    
class MountPoint(type):
    '''
    * A way to declare a mount point for plugins. Since plugins are an example of loose coupling, there needs to be a neutral location, somewhere between the plugins and the code that uses them, that each side of the system can look at, without having to know the details of the other side. Trac calls this is an “extension point”.
    * A way to register a plugin at a particular mount point. Since internal code can’t (or at the very least, shouldn’t have to) look around to find plugins that might work for it, there needs to be a way for plugins to announce their presence. This allows the guts of the system to be blissfully ignorant of where the plugins come from; again, it only needs to care about the mount point.
    * A way to retrieve the plugins that have been registered. Once the plugins have done their thing at the mount point, the rest of the system needs to be able to iterate over the installed plugins and use them according to its need.

    Add the parameter `metaclass = MountPoint` in any class to make it a mont point.

    '''
    def __init__(cls, name, bases, attrs):
        if not hasattr(cls, 'plugins'):
            # This branch only executes when processing the mount point itself.
            # So, since this is a new plugin type, not an implementation, this
            # class shouldn't be registered as a plugin. Instead, it sets up a
            # list where plugins can be registered later.
            cls.plugins = []
        else:
            # This must be a plugin implementation, which should be registered.
            # Simply appending it to the list is all that's needed to keep
            # track of it later.
            cls.plugins.append(cls)

def load_plugins():
    '''
    Utility method to load all plugins found in PLUGIN_DIRECTORY
    '''
    for dir in os.listdir(PLUGIN_DIRECTORY): #TODO several directories, eg User Application Data
        if (os.path.isfile(dir)):
            continue
        try :
            file, path, description = imp.find_module(dir, [PLUGIN_DIRECTORY])
            module = imp.load_module(dir, file, path, description)
            print(_("Plugin %(plugin)s v%(version)s by %(author)s loaded") % \
                    {'plugin':dir, 'version':module.__version__, 'author':module.__author__})
        except :
            # non modules will fail
            print(_("Plugin %(plugin) failed to load: %(reason)") % \
                    { 'plugin':dir, 'reason':sys.exc_info()[1]})
            pass
class ExtensionsAt(object):
    ''' Descriptor to get plugins on a given mount point.
    '''
    def __init__(self, mount_point):
        ''' Initialize the descriptor with the mount point wanted.
        Eg: ExtensionsAt(apf.GUIMenu) to get extensions that change the GUI Menu.
        '''
        self.mount = mount_point

    def __get__(self, instance, owner=None):
        ''' Plugin are instanciated with the object that is calling them.
        '''
        return [p(instance) for p in self.mount.plugins]

''' Extension points are defined bellow'''

class GUIMenu(object, metaclass=MountPoint):
    ''' Plugins can inherit this mount point in order to amending the menu of the GUI.

     A plugin that registers this mount point must have attributes
     * label
     * command
     
     It must implement
     def execute(self):
     '''
    def __init__(self, controller):
        self.modelManager = controller.modelManager
        self.controller = controller

class CommandLineOption(object, metaclass=MountPoint):
    ''' Plugins can inherit this mount point in order to add a command line option.

    A plugin that registers this mount point must implement the method
    * execute(self):
    and must have attributes
    * name: name of the option (without '--'). 
    * action: Actions tell optparse what to do when it encounters an option on the command line. 'store', 'store_true', 'store_false'
    * help: help message
    The value obtained from the parser will be stored in self.__name__
    '''
    def __init__(self, controller):
        self.modelManager = controller.modelManager
        self.gui = None
    
