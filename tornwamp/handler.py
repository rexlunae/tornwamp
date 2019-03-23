"""
Implement Tornado WAMP Handler.
"""
from tornado import gen
from tornado.websocket import WebSocketHandler

from warnings import warn

from tornwamp import customize, session
from tornwamp.uri.manager import uri_registry
from tornwamp.messages import AbortMessage, Message
from tornwamp.processors import UnhandledProcessor

BINARY_PROTOCOL = 'wamp.2.msgpack'
JSON_PROTOCOL = 'wamp.2.json'

def abort(handler, error_msg, details, reason='tornwamp.error.unauthorized'):
    """
    Used to abort a connection while the user is trying to establish it.
    """
    abort_message = AbortMessage(reason=reason)
    abort_message.error(error_msg, details)
    handler.write_message(abort_message.json)
    handler.close(1, error_msg)


class WAMPHandler(WebSocketHandler):
    """
    WAMP WebSocket Handler.
    """

    def __init__(self, *args, preferred_protocol=BINARY_PROTOCOL, **kargs):
        self.connection = None
        self.preferred_protocol = preferred_protocol
        super(WAMPHandler, self).__init__(*args, **kargs)

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

    def write_message(self, msg):
        """
        Reads a message to the WebSocket in the format selected for it.
        """
        if self.protocol == JSON_PROTOCOL:
            return super(WAMPHandler, self).write_message(msg.json)
        elif self.protocol == BINARY_PROTOCOL:
            return super(WAMPHandler, self).write_message(msg.msgpack, binary=True)
        else:
            warn('unknown protocol ' + self.protocol)

    def read_message(self, txt):
        """
        Reads a message in whatever format is selected for the WebSocket.
        """
        if self.protocol == JSON_PROTOCOL:
            return Message.from_text(txt)
        elif self.protocol == BINARY_PROTOCOL:
            return Message.from_bin(txt)
        else:
            warn('unknown protocol ' + self.protocol)

    def authorize(self):
        """
        Override for authorizing connection before the WebSocket is opened.
        Sample usage: analyze the request cookies.

        Return a tuple containing:
        - boolean (if connection was accepted or not)
        - dict (containing details of the authentication)
        - string (explaining why the connection was not accepted)
        """
        return True, {}, ""

    def register_connection(self):
        """
        Add connection to connection's manager.
        """
        session.connections[self.connection.id] = self.connection

    def deregister_connection(self):
        """
        Remove connection from connection's manager.
        """
        if self.connection:
            uri_registry.remove_connection(self.connection)
            # XXX - Add procedure cleanup.
        return session.connections.pop(self.connection.id, None) if self.connection else None

    def open(self):
        """
        Responsible for authorizing or aborting WebSocket connection.
        It calls 'authorize' method and, based on its response, sends
        a ABORT message to the client.
        """
        authorized, details, error_msg = self.authorize()
        if authorized:
            self.connection = session.ClientConnection(self, **details)
            self.register_connection()
        else:
            abort(self, error_msg, details)

    async def on_message(self, txt):
        """
        Handle incoming messages on the WebSocket. Each message will be parsed
        and handled by a Processor, which can be (re)defined by the user
        changing the value of 'processors' dict, available at
        tornwamp.customize module.
        """
        msg = self.read_message(txt)
        Processor = customize.processors.get(msg.code, UnhandledProcessor)
        processor = Processor(msg, self.connection)

        if self.connection and not self.connection.zombie:  # TODO: cover branch else
            if processor.answer_message is not None:
                self.write_message(processor.answer_message)

        customize.broadcast_messages(processor)

        if processor.must_close:
            self.close(processor.close_code, processor.close_reason)

    def close(self, code=None, reason=None):
        """
        Invoked when a WebSocket is closed.
        """
        self.deregister_connection()
        super(WAMPHandler, self).close(code, reason)
