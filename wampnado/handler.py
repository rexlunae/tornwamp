"""
Implement Tornado WAMP Handler.
"""
from warnings import warn

from wampnado import session
from wampnado.realm import WAMPRealm, realms
from wampnado.transports import WebSocketTransport
from wampnado.messages import AbortMessage, Code, Message
from wampnado.processors import UnhandledProcessor, GoodbyeProcessor, HelloProcessor, pubsub, rpc

BINARY_PROTOCOL = 'wamp.2.msgpack'
JSON_PROTOCOL = 'wamp.2.json'

class WAMPMetaHandler:
    """
    A metaclass for handlers.  Call the factory with the class of a transport.
    Returns a class that can be instantiated by Tornado's IOloop using that transport.

    WAMPMetaHandler.factory(WebSocketTransport)

    Or, since WebSocket is the default, this:

    WAMPMetaHandler.factory()
    """
    @classmethod
    def factory(cls, transport_cls=WebSocketTransport):
        """
        Makes a class to handle the specified transport.
        """
        class A(cls, transport_cls):
            pass
        
        return A


    def __init__(self, *args, preferred_protocol=BINARY_PROTOCOL, **kargs):
        self.preferred_protocol = preferred_protocol
        self.connection = None
        self.realm_id = 'unset'
        super().__init__(*args, **kargs)

    processors = {
        Code.HELLO: HelloProcessor,
        Code.GOODBYE: GoodbyeProcessor,
        Code.SUBSCRIBE: pubsub.SubscribeProcessor,
        Code.CALL: rpc.CallProcessor,
        Code.REGISTER: rpc.RegisterProcessor,
        Code.PUBLISH: pubsub.PublishProcessor,
        Code.YIELD: rpc.YieldProcessor,
    }


    def on_close(self):
        """
        Overrides the base class to clean up our connections and registrations.
        """
        self.realm.uri_registry.remove_connection(self.connection)
        self.realm.deregister_handler(self.realm_id)
        super().on_close()

    def attach_realm(self, name):
        """
        Attached the connection to a given realm.  Each connection can be attached to one and only one realm.
        This function can be overridden to add access controls to it.
        """
        if not name in realms:
            realms[name] = WAMPRealm(name)

        self.realm_id = realms[name].register_handler(self)

        # Doubly-linked
        self.realm = realms[name]

    def abort(self, handler, error_msg, details, reason=None):
        """
        Used to abort a connection while the user is trying to establish it.
        """
        if reason is None:
            abort_message = AbortMessage(reason=self.realm.not_authorized.to_uri())

        abort_message.error(error_msg, details)
        handler.write_message(abort_message.json)
        handler.close(1, error_msg)


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
            return super().write_message(msg.json)
        elif self.protocol == BINARY_PROTOCOL:
            return super().write_message(msg.msgpack, binary=True)
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

    def register_connection(self, connection):
        """
        Add connection to connection's manager.
        """
        session.connections[connection.id] = connection

    def deregister_connection(self):
        """
        Remove connection from connection's manager.
        """
        if self.connection:
            self.realm.uri_registry.remove_connection(self.connection)
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
            self.register_connection(self.connection)
        else:
            self.abort(self, error_msg, details)

    async def on_message(self, txt):
        """
        Handle incoming messages on the WebSocket. Each message will be parsed
        and handled by a Processor, which can be (re)defined by the user
        changing the value of 'processors' dict, available at
        wampnado.customize module.
        """
        msg = self.read_message(txt)
        Processor = self.processors.get(msg.code, UnhandledProcessor)
        processor = Processor(msg, self)

        if self.connection and not self.connection.zombie:  # TODO: cover branch else
            if processor.answer_message is not None:
                self.write_message(processor.answer_message)

        self.broadcast_messages(processor)

        if processor.must_close:
            self.close(processor.close_code, processor.close_reason)

    def broadcast_messages(self, processor):
        for msg in processor.broadcast_messages:
            topic = self.realm.uri_registry.get(msg.topic_name)

            # Only publish if there is someone listening.
            if topic is not None:
                topic.publish(msg)


    def close(self, code=None, reason=None):
        """
        Invoked when a WebSocket is closed.
        """
        self.deregister_connection()
        super().close(code, reason)



class WAMPMetaHandlerDebug(WAMPMetaHandler):
    """
    A metaclass for handlers.  Call the factory (inside the parent class)
    with the class of a transport.  Returns a class
    that can be instantiated by Tornado's IOloop using that transport.

    WAMPMetaHandlerDebug.factory(WebSocketHandler)
    """
    def write_message(self, msg):
        result = super().write_message(msg)
        print('tx|' + str(self.realm_id) + '|: ' + msg.json)
        return result

    def read_message(self, txt):
        message = super().read_message(txt)
        print('rx|' + str(self.realm_id) + '|: ' + message.json)
        return message






