from arelle import apf
# _() is aliased in __init__.py
from . import _

class HelloWorld(object):
    ''' The core class says "Hello World".'''      
    def get_hello(self):
        return _("Hello World")
    
class HelloMenu(apf.GUIMenu):
    ''' By extending the GUIMenu mount point, the plugin can interact with
     the GUI'''
    label = _("Hello World")
    def execute(self):
        hello_world = HelloWorld().get_hello();
        self.controller.addToLog(hello_world)
        import tkinter
        tkinter.messagebox.showinfo(self.label, hello_world, parent=self.controller.parent)            
        
class HelloCli(apf.CommandLineOption):
    ''' By extending the CommandLineOption mount point, this plugin can be 
    invoked from command-line.'''
    name = "hello-world"
    action = "store_true"
    help =  _("Prints 'Hello world'")
    
    def execute(self):
        hello_world = HelloWorld().get_hello();
        try:
            self.modelManager.modelXbrl.info("info", hello_world)
        except:
            print(hello_world)
