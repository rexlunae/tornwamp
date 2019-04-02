"""
Pre-packages transports.
"""
from tornado.websocket import WebSocketHandler

class WebSocketTransport(WebSocketHandler):
    """
    The wrapper for using a WebSocket.
    """


class LocalTransport():
    """
    This is basically a fake transport that simulates the functions of a transport
    locally.  It saves encode/decode time because it doesn't actually need to serialize
    and it can pass data by reference.  It is useful to add client-like functionality
    to the router while maintaining the conceptual separation between the two.  It may also
    be useful for mocking.
    """

    def write_message(self, msg):
        pass

    def read_message(self, txt):
        pass