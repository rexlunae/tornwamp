"""
Pre-packaged transports.
"""
import socket

from warnings import warn
from asyncio import gather
from datetime import datetime

from tornado.websocket import WebSocketHandler

from wampnado.identifier import create_global_id
from wampnado.realm import realms
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

        Considering the server wanted to disconnect the client for some reason,
        we leave the client in a "zombie" state, so it can't subscribe to
        uris and can't receive messages from other clients.
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



class LocalTransport(Transport):
    """
    This is basically a fake transport that simulates the functions of a transport
    locally.  It saves encode/decode time because it doesn't actually need to serialize
    and it can pass data by reference.  It is useful to add client-like functionality
    to the router while maintaining the conceptual separation between the two.  It may also
    be useful for mocking.
    """

    # Local transports always use the "NONE_PROTOCOL"
    protocol = NONE_PROTOCOL

    supported_protocols = {
        NONE_PROTOCOL: True
    }

