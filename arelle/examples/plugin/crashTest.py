'''
Crash test is a plug in to cause an uncaught exception to test its recover

(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''
def crashMenuEntender(cntlr, menu):
    menu.add_command(label="Crash now!!!", underline=0, command=lambda: crashMenuCommand(cntlr) )

def crashMenuCommand(cntlr):
    foo = 25
    foo /= 0

def crashCommandLineOptionExtender(parser):
    parser.add_option("--crash-test", 
                      action="store_true", 
                      dest="crashTest", 
                      help=_('Test what happens with an exception'))

def crashCommandLineXbrlRun(cntlr, options, modelXbrl, *args):
    if getattr(options, "crashTest", False):
        foo = 25
        foo /= 0


__pluginInfo__ = {
    'name': 'Crash Test',
    'version': '0.9',
    'description': "Used to test that uncaught exceptions report their cause to the Arelle user.",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2012 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': crashMenuEntender,
    'CntlrCmdLine.Options': crashCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Run': crashCommandLineXbrlRun,
}
