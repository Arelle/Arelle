'''
Example extension plugin to provide custom REST api

See COPYRIGHT.md for copyright information.

To run test:
    arelleCmdLine.exe --webserver localhost:8080 --plugins ../examples/plugin/cmdWebServerExtension.py

'''

from arelle.CntlrWebMain import GET, Options, runOptionsAndGetResult
from arelle.Version import copyrightLabel

def my_test():
    return _("<html><body><h1>Test</h1><p>It works!</p></body></html>")

def my_run(file=None):
    options = Options() # inspired by CntlrWebMain.validate
    setattr(options, "entrypointFile", file)
    setattr(options, "validate", True)
    return runOptionsAndGetResult(options, "html", None, None)


def startWebServer(app, cntlr, host, port, server):
    # save
    # register /test-response to send a test response string
    app.route('/rest/my-test', "GET", my_test)
    # register /test/my-run to do a normal "validate" wprkflow cycle but with custom parameters
    app.route('/rest/my-run/<file:path>', ("GET", "POST"), my_run)

    return None  # return "skip-routes" ## uncomment to block normal api REST "routes"

__pluginInfo__ = {
    'name': 'REST Extensions',
    'version': '0.9',
    'description': "Sample REST API extensions (or replacements).",
    'license': 'Apache-2',
    'author': 'R\xe9gis D\xce9camps',
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrWebMain.StartWebServer': startWebServer,
}
