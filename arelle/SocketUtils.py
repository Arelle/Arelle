import socket

INTERNET_CONNECTIVITY = 'internetConnectivity'
OFFLINE = 'offline'


class WarnSocket(socket.socket):
    """
    This is a simple wrapper around the socket to print a warning if Arelle attempts to download somthing while running in offline mode.
    """
    def __init__(self, family=-1, type=-1, proto=-1, fileno=None):
        print(f"Arelle is running in offline mode but is attempting a download.")
        super().__init__(family, type, proto, fileno)


def warnSocket():
    socket.socket = WarnSocket
