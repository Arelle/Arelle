'''
See COPYRIGHT.md for copyright information.

Provides infrastructure for local viewers of GUI applications such as inline XBRL viewers

'''
from arelle.webserver.bottle import Bottle, request, static_file, HTTPResponse
import threading, time, logging, sys, traceback

class LocalViewer:
    noCacheHeaders = {'Cache-Control': 'no-cache, no-store, must-revalidate',
                      'Pragma': 'no-cache',
                      'Expires': '0'}

    def __init__(self, title, staticReportsRoot):
        self.title = title
        self.port = None # viewer unique port
        self.reportsFolders = [staticReportsRoot] # first entry is root of common report files, rest are per-report root
        self.cntlr = None

    def init(self, cntlr, reportsFolder):
        try:
            if self.port is None: # already initialized
                self.cntlr = cntlr

                # find available port
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(("",0))
                s.listen(1)
                self.port = s.getsockname()[1]
                s.close()

                # start server
                localserver = Bottle()

                localserver.route('/<file:path>', 'GET', self.get)
                localserver.route('<relpath:path>', 'GET', self.get)
                # start local server on the port on a separate thread
                threading.Thread(target=localserver.run,
                                 kwargs=dict(server='cheroot', host='localhost', port=self.port, quiet=True),
                                 daemon=True).start()
                time.sleep(2) # allow other thread to run and start up

            localhost = "http://localhost:{}/{}".format(self.port, len(self.reportsFolders))
            self.reportsFolders.append(reportsFolder)
            self.cntlr.addToLog(_("{}: http://localhost:{}").format(self.title, self.port),
                                messageCode="localViewer:listen",level=logging.DEBUG)
            #cntlr.addToLog("localhost={}".format(localhost), messageCode="localViewer:listen",level=logging.DEBUG)
            return localhost
        except Exception as ex:
            self.cntlr.addToLog(_("{} exception: http://localhost:{} \nException: {} \nTraceback: {}").format(
                self.title, self.port,
                ex, traceback.format_tb(sys.exc_info()[2])), messageCode="localViewer:exception",level=logging.DEBUG)

    def get(self, file=None, relpath=None):
        self.cntlr.addToLog("http://localhost:{}/{}".format(self.port,file), messageCode="localViewer:get",level=logging.DEBUG)
        try:
            return self.getLocalFile(file, relpath, request)
        except HTTPResponse:
            raise # re-raise, such as to support redirects
        except Exception as ex:
            self.cntlr.addToLog(_("{} exception: file: {} \nException: {} \nTraceback: {}").format(
                self.title, file, ex, traceback.format_tb(sys.exc_info()[2])), messageCode="localViewer:exception",level=logging.DEBUG)
