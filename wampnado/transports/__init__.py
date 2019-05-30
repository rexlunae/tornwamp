"""
Pre-packaged transports.
"""
from datetime import datetime

from tornado.websocket import WebSocketHandler

from wampnado.serializer import JSON_PROTOCOL, BINARY_PROTOCOL, NONE_PROTOCOL


class Transport:
    """
    The base class for transports.
    """
    def zombify(self):
        """
        Make current connection a zombie:
        - remove all its uris
        - remove it from the TopicsManager

        In WAMP, in order to disconnect, we're supposed to do a GOODBYE
        handshake.
        """
        self.zombification_datetime = datetime.now().isoformat()
        self.zombie = True


class WebSocketTransport(WebSocketHandler, Transport):
    """
    The wrapper for using a Tornado WebSocket.  It can be passed into Tornado as a handler.
    """
    supported_protocols = {
        JSON_PROTOCOL: True,
        BINARY_PROTOCOL: True,
    }

    def select_subprotocol(self, subprotocols):
        """
        Select WAMP 2 subprocotol
        """
        current_protocol = JSON_PROTOCOL    # All WAMP implementations should support json, so we default to that.
        for protocol in subprotocols:
            if self.supported_protocols[protocol]:
                current_protocol = protocol
                if protocol == self.preferred_protocol:
                    self.protocol = protocol
                    return protocol

        self.protocol = current_protocol
        return current_protocol



class LocalTransport(Transport):
    """
    This is basically a fake transport that simulates the functions of a transport for the
    local thread.  It saves encode/decode time because it doesn't actually need to serialize
    and it can pass data by reference.  It is useful to add client-like functionality
    to the router while maintaining the conceptual separation between the two.  It may also
    be useful for mocking, but note that a lot of the code paths are different from real 
    transports.
    """

    # Local transports always use the "NONE_PROTOCOL"
    protocol = NONE_PROTOCOL

    supported_protocols = {
        NONE_PROTOCOL: True
    }
