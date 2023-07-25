from __future__ import annotations
import socket

INTERNET_CONNECTIVITY = 'internetConnectivity'
OFFLINE = 'offline'


class WarnSocket(socket.socket):
    """
    This is a simple wrapper around the socket to print a warning if Arelle attempts to download something while running in offline mode.
    """
    def __init__(self, family: int = -1, type: int = -1, proto: int = -1, fileno: int | None = None):
        print("Arelle is running in offline mode but is attempting a download.")
        super().__init__(family, type, proto, fileno)


def warnSocket() -> None:
    socket.socket = WarnSocket  # type: ignore [misc]
