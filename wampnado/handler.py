"""
Implement Tornado WAMP Handler.
"""
from inspect import isawaitable
from warnings import warn

from tornado.websocket import WebSocketClosedError

from wampnado.identifier import create_global_id
from wampnado.realm import get_realm
from wampnado.transports import WebSocketTransport
from wampnado.messages import AbortMessage, Code, Message
from wampnado.processors import UnhandledProcessor, GoodbyeProcessor, HelloProcessor, pubsub, rpc
from wampnado.serializer import JSON_PROTOCOL, BINARY_PROTOCOL, NONE_PROTOCOL

class WAMPMetaHandler:
    """
    A metaclass for handlers.  Call the factory with the class of a transport.
    Returns a class that can be instantiated by Tornado's IOloop using that transport.

    WAMPMetaHandler.factory(WebSocketTransport)

    Or, since WebSocket is the default, this:

    WAMPMetaHandler.factory()
    """
    @classmethod
    def factory(cls, transport_cls=WebSocketTransport, transport_init_args=[], transport_init_kwargs={}):
        """
        Makes a class to handle the specified transport.
        """
        class A(cls, transport_cls):
            def __init__(self, *args, **kwargs):
                cls.__init__(self, *args, **kwargs)
                transport_cls.__init__(self, *args, *transport_init_args, **kwargs, **transport_init_kwargs)

        
        return A


    def __init__(self, *args, preferred_protocol=BINARY_PROTOCOL, **kargs):
        self.preferred_protocol = preferred_protocol
        self.sessionid = create_global_id()
        #self.connection = None
        self.realm_id = 'unset'
        self.authid = None
        self.authrole = 'anonymous'
        self.authmethod = 'anonymous'
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
        self.realm.disconnect(self)
        self.realm.deregister_handler(self.realm_id)
        
        # This is a meta-class, so we're assuming that we have a parent class, even if it isn't listed.
        super().on_close()

    def attach_realm(self, name, hello_message=None):
        """
        Attached the connection to a given realm.  Each connection can be attached to one and only one realm.
        This function can be overridden to add access controls to it.
        """
        self.realm = get_realm(name)
        self.realm_id = self.realm.register_handler(self)

        # Track the handshake information.
        self.hello_message=hello_message

    def abort(self, handler, error_msg, details, reason=None):
        """
        Used to abort a connection while the user is trying to establish it.
        """
        if reason is None:
            abort_message = AbortMessage(reason=self.realm.not_authorized.to_uri())

        abort_message.error(error_msg, details)
        handler.write_message(abort_message.json)
        handler.close(1, error_msg)

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
        elif self.protocol == NONE_PROTOCOL:
            return super().write_message(msg)
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
        elif self.protocol == NONE_PROTOCOL:
            # If we're using NONE_PROTOCOL, txt is actually just the message.
            return txt
            #return Message(txt.value)
        else:
            warn('unknown protocol ' + self.protocol)

    async def on_message(self, txt):
        """
        Handle incoming messages on the WebSocket. Each message will be parsed
        and handled by a Processor, which can be (re)defined by the user
        changing the value of 'processors' dict, available at
        wampnado.customize module.
        """
        try:
            msg = self.read_message(txt)
            Processor = self.processors.get(msg.code, UnhandledProcessor)
            processor = Processor(msg, self)

            #if self.connection and not self.connection.zombie:  # TODO: cover branch else
            answer = processor.answer_message
            if isawaitable(answer):
                answer = await answer
            if answer is not None:
                self.write_message(answer)

            self.broadcast_messages(processor)

            if processor.must_close:
                self.on_close(processor.close_code, processor.close_reason)
        except WebSocketClosedError as e:
            warn('closed connection {} due to {}'.format(self.sessionid, e))
            self.on_close()

    def broadcast_messages(self, processor):
        """
        """
        for msg in processor.broadcast_messages:
            uri = self.realm.get(msg.uri_name)

            # Only publish if there is someone listening.
            if uri is not None:
                uri.publish(self, msg)



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






