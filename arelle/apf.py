import ast

__author__ = "Régis Décamps"

import os, imp
import sys

'''
Arelle plugin framework is heavily inspired by Marty Alchin's Simple plugin framework.
http://martyalchin.com/2008/jan/10/simple-plugin-framework/
'''
PLUGIN_DIRECTORY = "plugins"

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


def list_plugins():
    '''
    Utility method to list available plugins
    '''
    l = list()
    for dir in os.listdir(PLUGIN_DIRECTORY): #TODO several directories, eg User Application Data
        if (os.path.isfile(dir)):
            continue
        l.append(dir)
    return l


def load_plugins(**kwargs):
    '''
    Utility method to load plugins.
    If neither `name` nor `names` are specified, it loads all modules found in PLUGIN_DIRECTORY.
    @type  ignored: a list of string
    @param ignored: the list of plugins to ignore (by name)
    @type name: a string
    @param name: name of a single plugin to load
    @type names: a list of string
    @param names: the list of plugins to load. If undefined, plugins from PLUGIN_DIRECTORY are loaded
    @return The list of loaded modules
    '''
    ignored_plugins = ()
    names = None
    for key in kwargs:
        if key == 'ignore':
            ignored_plugins = kwargs[key]
        elif key == 'names':
            names = kwargs[key]
        elif key == 'name':
            names = (kwargs[key],)
    if names is None:
        names = list_plugins()
    loaded_plugins = {}
    for addon in names:
        if addon in ignored_plugins:
            print("Plugin %(addon)s not loaded because it is disabled" % {'addon': addon})
            continue
        if addon in loaded_plugins:
            print("Plugin %(addon)s not reloaded because it has already been loaded" % {'addon': addon})
            continue
        try:
            file = None # defines variable for catch clause
            file, path, description = imp.find_module(addon, [PLUGIN_DIRECTORY])
            module = imp.load_module(addon, file, path, description)
            print("Plugin {} v{} by {} loaded".format(addon, module.__version__, module.__author__))
            loaded_plugins[addon] = module
        except:
            # non modules will fail
            # not a big deal, but file may have been opened by find_module
            if file is not None:
                file.close()
                # and printing the stack can help understand what happened
            print(sys.exc_info()[1])
    return loaded_plugins


def get_module_info(name):
    #TODO several directories, eg User Application Data
    filename = os.path.join(PLUGIN_DIRECTORY, name, '__init__.py')
    with open(filename) as f:
        module_info = imp.new_module(name)
        tree = ast.parse(f.read(), filename=filename)
        for item in tree.body:
            if isinstance(item, ast.Assign):
                attr = item.targets[0].id
                if attr in ('__author__','__version__','__desc__'):
                    setattr(module_info, attr, item.value.s)
        return module_info


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
    
