'''
See COPYRIGHT.md for copyright information.

Provides infrastructure for local viewers of GUI applications such as inline XBRL viewers

'''
from __future__ import annotations

import logging
import threading
import time
import traceback

from bottle import Bottle, HTTPResponse, request, LocalRequest  # type: ignore[import-untyped]

from arelle.typing import TypeGetText
from arelle.Cntlr import Cntlr

_: TypeGetText


class LocalViewer:
    noCacheHeaders: dict[str, str] = {'Cache-Control': 'no-cache, no-store, must-revalidate',
                      'Pragma': 'no-cache',
                      'Expires': '0'}

    def __init__(self, title: str, staticReportsRoot: str) -> None:
        self.title = title
        self.port: int | None = None # viewer unique port
        self.reportsFolders: list[str] = [staticReportsRoot] # first entry is root of common report files, rest are per-report root
        self.cntlr: Cntlr | None = None

    def init(self, cntlr: Cntlr, reportsFolder: str) -> str | None:
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
            assert self.cntlr is not None, "Cntlr not initialized"
            self.cntlr.addToLog(_("{}: http://localhost:{}").format(self.title, self.port),
                                messageCode="localViewer:listen",level=logging.DEBUG)
            return localhost
        except Exception as ex:
            assert self.cntlr is not None, "Cntlr not initialized"
            self.cntlr.addToLog(_("{} exception: http://localhost:{} \nException: {} \nTraceback: {}").format(
                self.title, self.port,
                ex, traceback.format_exc()), messageCode="localViewer:exception",level=logging.DEBUG)
            return None

    def get(self, file: str | None = None, relpath: str | None = None) -> object:
        assert self.cntlr is not None, "Cntlr not initialized"
        self.cntlr.addToLog("http://localhost:{}/{}".format(self.port,file), messageCode="localViewer:get",level=logging.DEBUG)
        try:
            return self.getLocalFile(file, relpath, request)
        except HTTPResponse:
            raise # re-raise, such as to support redirects
        except Exception as ex:
            self.cntlr.addToLog(_("{} exception: file: {} \nException: {} \nTraceback: {}").format(
                self.title, file, ex, traceback.format_exc()), messageCode="localViewer:exception",level=logging.DEBUG)
            return None

    def getLocalFile(self, file: str | None, relpath: str | None, request: LocalRequest) -> HTTPResponse:
        raise NotImplementedError
