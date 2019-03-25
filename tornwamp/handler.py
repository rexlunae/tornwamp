"""
Implement Tornado WAMP Handler.
"""
from tornado import gen
from tornado.websocket import WebSocketHandler

from warnings import warn

from tornwamp import session
from tornwamp.identifier import create_global_id
from tornwamp.uri.manager import URIManager
from tornwamp.messages import AbortMessage, Code, Message
from tornwamp.processors import UnhandledProcessor, GoodbyeProcessor, HelloProcessor, pubsub, rpc

BINARY_PROTOCOL = 'wamp.2.msgpack'
JSON_PROTOCOL = 'wamp.2.json'


class ErrorStruct:
    def __init__(self, **entries):
        self.__dict__.update(entries)

realms = {}


class WAMPRealm(dict):
    """
    Represents a realm in WAMP parlance.  Connections within a realm can see and communicate with each other, those outside it cannot.
    """
    def __init__(self, name):
        self.name = name
        self.handlers = {}

        self.uri_registry = URIManager()

        self.errors = ErrorStruct(**{
            # The first two of these aren't technically errors, but just messages used in closing a connection.  But close enough.
            'close_realm': self.uri_registry.create_error('wamp.close.close_realm'),
            'goodbye_and_out': self.uri_registry.create_error('wamp.close.goodbye_and_out'),

            # These are the errors that are required and standardized by WAMP Protocol standard
            'invalid_uri': self.uri_registry.create_error('wamp.error.invalid_uri'),
            'no_such_procedure': self.uri_registry.create_error('wamp.error.no_such_procedure'),
            'procedure_already_exists': self.uri_registry.create_error('wamp.error.procedure_already_exists'),
            'no_such_registration': self.uri_registry.create_error('wamp.error.no_such_registration'),
            'no_such_subscript': self.uri_registry.create_error('wamp.error.no_such_subscription'),
            'invalid_argument': self.uri_registry.create_error('wamp.error.invalid_argument'),
            'system_shutdown': self.uri_registry.create_error('wamp.close.system_shutdown'),
            'protocol_violation': self.uri_registry.create_error('wamp.error.protocol_violation'),
            'not_authorized': self.uri_registry.create_error('wamp.error.not_authorized'),
            'authorization_failed': self.uri_registry.create_error('wamp.error.authorization_failed'),
            'no_such_realm': self.uri_registry.create_error('wamp.error.no_such_realm'),
            'no_such_role': self.uri_registry.create_error('wamp.error.no_such_role'),
            'cancelled': self.uri_registry.create_error('wamp.error.canceled'),
            'option_not_allowed': self.uri_registry.create_error('wamp.error.option_not_allowed'),
            'no_eligible_callee': self.uri_registry.create_error('wamp.error.no_eligible_callee'),
            'option_disallowed__disclose_me': self.uri_registry.create_error('wamp.error.option_disallowed.disclose_me'),
            'network_failure': self.uri_registry.create_error('wamp.error.network_failure'),

            # These aren't part of the WAMP standard, but I use them, so here they are.
            'not_pending': self.uri_registry.create_error('wamp.error.not_pending'),    # Sent if we get a YIELD message but there is no call pending.
            'unsupported': self.uri_registry.create_error('wamp.error.unsupported'),    # Sent when we get a message that we don't recognize.

        })

    #def __del__(self):
    #    del realms[self.name]

    def register_handler(self, handler):
        """
        Add the handler to the realm.
        """
        id = create_global_id()
        self.handlers[id] = handler
        return id

    def deregister_handler(self, id):
        """
        Remove the handler from the realm.  If the handler is the only one in the realm, the realm itself will be cleaned up.
        """
        del self.handlers[id]
        if len(self.handlers) == 0:
            del realms[self.name]



class WAMPHandler(WebSocketHandler):
    """
    WAMP WebSocket Handler.  There is one of these per connection, so this is only an object to handle a single connection.
    """

    def __init__(self, *args, preferred_protocol=BINARY_PROTOCOL, **kargs):
        self.connection = None
        self.preferred_protocol = preferred_protocol
        super(WAMPHandler, self).__init__(*args, **kargs)

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
        tornwamp.customize module.
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



    processors = {
        Code.HELLO: HelloProcessor,
        Code.GOODBYE: GoodbyeProcessor,
        Code.SUBSCRIBE: pubsub.SubscribeProcessor,
        Code.CALL: rpc.CallProcessor,
        Code.REGISTER: rpc.RegisterProcessor,
        Code.PUBLISH: pubsub.PublishProcessor,
        Code.YIELD: rpc.YieldProcessor,
    }
#    2: 'welcome',
#    3: 'abort',
#    4: 'challenge',
#    5: 'authenticate',
#    7: 'heartbeat',
#    8: 'error',
#    17: 'published',
#    33: 'subscribed',
#    34: 'unsubscribe',
#    35: 'unsubscribed',
#    36: 'event',
#    49: 'cancel',
#    50: 'result',
#    64: 'register',
#    65: 'registered',
#    66: 'unregister',
#    67: 'unregistered',
#    68: 'invocation',
#    69: 'interrupt',
#    70: 'yield'


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
        super(WAMPHandler, self).close(code, reason)
