"""
Classes for WAMP router/servers.
"""

from warnings import warn
from copy import deepcopy

from wampnado.identifier import create_global_id
from wampnado.realm import get_realm
from wampnado.agent import WAMPAgent
from wampnado.transports import WebSocketTransport
from wampnado.messages import AbortMessage, Code, Message
from wampnado.processors import AbortProcessor, HelloProcessor, UnhandledProcessor, GoodbyeProcessor, pubsub, rpc
from wampnado.serializer import JSON_PROTOCOL, BINARY_PROTOCOL, NONE_PROTOCOL

class WAMPMetaServerHandler(WAMPAgent):
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
        class Server(cls, transport_cls):
            def __init__(self, *args, **kwargs):
                super(cls, self).__init__(*args, **kwargs)
                super(transport_cls, self).__init__(*args, *transport_init_args, **kwargs, **transport_init_kwargs)

        return Server


    def __init__(self, *args, preferred_protocol=BINARY_PROTOCOL, **kwargs):
        super().__init__(*args, **kwargs)
        self.preferred_protocol = preferred_protocol
        self.sessionid = create_global_id()
        self.realm_id = 'unset'
        self.authid = None
        self.authrole = 'anonymous'
        self.authmethod = 'anonymous'
 
        # Add the messages handlers that only the server responds to.
        self.processors = {
            **deepcopy(super().processors),
            **{
                Code.HELLO: HelloProcessor,
                Code.SUBSCRIBE: pubsub.SubscribeProcessor,
                Code.PUBLISH: pubsub.PublishProcessor,
                Code.YIELD: rpc.YieldProcessor,
                Code.CALL: rpc.CallProcessor,
                Code.REGISTER: rpc.RegisterProcessor,
            }
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

    def broadcast_messages(self, processor):
        """
        """
        for msg in processor.broadcast_messages:
            uri = self.realm.get(msg.uri_name)

            # Only publish if there is someone listening.
            if uri is not None:
                uri.publish(self, msg)



class WAMPMetaServerHandlerDebug(WAMPMetaServerHandler):
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
