from arelle import apf
from random import randint
import sys
'''
Hello dolly is a simple "Hello world" to demonstrate how plugins
are written for Arelle
'''
class HelloDolly(object):
    ''' The core class generates a random lyrics.'''
    LYRICS = ["I said hello, dolly,......well, hello, dolly", \
            "It's so nice to have you back where you belong ", \
            "You're lookin' swell, dolly.......i can tell, dolly ", \
            "You're still glowin'...you're still crowin'...you're still goin' strong ", \
            "I feel that room swayin'......while the band's playin' ", \
            "One of your old favourite songs from way back when ", \
            "So..... take her wrap, fellas.......find her an empty lap, fellas ", \
            "Dolly'll never go away again" ]
    def get_lyric(self):
        return self.LYRICS[randint(0, len(self.LYRICS))]
    
class HelloMenu(apf.GUIMenu):
    ''' By extending the GUIMenu mount point, the plugin can interact with
     the GUI'''
    label = "Hello Dolly"
    def execute(self):
        hello_dolly = HelloDolly().get_lyric();
        self.controller.addToLog(hello_dolly)
        import tkinter
        tkinter.messagebox.showinfo(self.label, hello_dolly, parent=self.controller.parent)            
        
class HelloCli(apf.CommandLineOption):
    ''' By extending the CommandLineOption mount point, this plugin can be 
    invoked from command-line.'''
    name = "hello-dolly"
    action = "store_true"
    help = "Print a random lyric from _Hello, Dolly_"
    
    def execute(self):
        hello_dolly = HelloDolly().get_lyric();
        try:
            self.modelManager.modelXbrl.info("info", hello_dolly)
        except:
            print(hello_dolly)
