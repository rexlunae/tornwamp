"""
Implement Tornado WAMP Handler.
"""
from inspect import isawaitable
from warnings import warn
from datetime import datetime
from asyncio import Future
from copy import deepcopy

from tornado.websocket import WebSocketClosedError

from wampnado.identifier import create_global_id
from wampnado.realm import get_realm
from wampnado.uri.error import WAMPSimpleException
from wampnado.agent import WAMPAgent
from wampnado.transports.tcp.client import TCPConnectorClient, TCPSocketClientTransport
from wampnado.messages import AbortMessage, Code, Message, SubscribeMessage, RPCRegisterMessage, CallMessage, WelcomeMessage, HelloMessage
from wampnado.processors import AbortProcessor, ClientErrorProcessor, UnhandledProcessor, GoodbyeProcessor, WelcomeProcessor, pubsub, rpc
from wampnado.serializer import JSON_PROTOCOL, BINARY_PROTOCOL, NONE_PROTOCOL
from wampnado.features import client_features

class Registration(Future):
    """
    Represents the callback registration for both subscriptions and rpcs.
    The return value is only relevant if it is an RPC.
    Set include_uri=True to have the uri included as a keyword parameter.  This allows single callbacks to process
    multiple uris.
    """
    def __init__(self, uri_name, callback=None, include_uri=False):
        self.uri_name = uri_name
        self.callback = callback
        self.created = datetime.utcnow()
        super().__init__()
        


class WAMPMetaClientHandler(WAMPAgent):
    """
    A metaclass for client handlers.  Any client, regardless of the transport, is responsible for
    establishing a connection, which then creates an object for handling the connection.
    """
    @classmethod
    def factory(cls, *args, connector_cls=TCPConnectorClient, connector_init_args=[], connector_init_kwargs={},
        client_cls=TCPSocketClientTransport, **kwargs):
        """
        Makes a class to handle the specified transport.
        """
        class Client(client_cls, cls):
            def __init__(self, stream, *args, **kwargs):
                client_cls.__init__(self, stream, *args, **kwargs)
                cls.__init__(self, stream)

        class Connector(connector_cls):
            def __init__(self, *args, **kwargs):
                connector_cls.__init__(self, *connector_init_args, **connector_init_kwargs, transport_cls=Client)


        return Connector(*args, **kwargs)


    def __init__(self, stream, *args, preferred_protocol=BINARY_PROTOCOL, **kwargs):
        super().__init__()
        self.preferred_protocol = preferred_protocol
        self.realm_id = 'unset'
        self.authid = None
        self.authrole = 'anonymous'
        self.authmethod = 'anonymous'

        self.subscriptions = {}
        self.registrations = {}
        self.requests = {}

        # Add the messages handlers that only the server responds to.
        self.processors = {
            **deepcopy(super().processors),
            **{
                Code.ERROR: ClientErrorProcessor,
                Code.REGISTERED: rpc.RegisteredProcessor,
                Code.INVOCATION: rpc.InvokeProcessor,
                Code.SUBSCRIBED: pubsub.SubscribedProcessor,
                Code.PUBLISHED: pubsub.PublishedProcessor,
                Code.EVENT: pubsub.EventProcessor,
            }
        }

    def register_subscription(self, request_id, subscription_id):
        """
        Called when a SUBSCRIBED message is received.  Checks that the subscription was requested, and then adds it.
        Raises an exception if the request was not pending.
        """
        if request_id not in self.requests:
            raise self.realm.errors.not_pending.to_simple_exception('Request not pending', request_id=request_id)

        self.subscriptions[subscription_id] = self.requests.pop(request_id)

    def register_rpc(self, request_id, registration_id):
        """
        Called when a REGISTERED message is received.  Checks that the registration was requested, and then adds it.
        Raises an exception if the request was not pending.
        """
        if request_id not in self.requests:
            raise self.realm.errors.not_pending.to_simple_exception('Request not pending', request_id=request_id)

        self.registrations[registration_id] = self.requests.pop(request_id)

    async def subscribe(self, uri_name, callback, include_uri=False, **options):
        msg = SubscribeMessage(options=options)
        self.requests[msg.request_id]=Registration(uri_name, callback, include_uri)
        self.write_message(msg)

        await self.requests[msg.request_id]


    async def register(self, uri_name, callback, include_uri=False, **options):
        msg = RPCRegisterMessage(options=options)
        self.requests[msg.request_id]=Registration(uri_name, callback, include_uri)
        self.write_message(msg)

        await self.requests[msg.request_id]

    async def call(self, uri_name, callback=None, *args, options={}, include_uri=False, **kwargs):
        request_id = create_global_id()
        msg = CallMessage(procedure=uri_name, request_id=request_id, options=options, args=args, kwargs=kwargs)
        self.requests[request_id]=Registration(uri_name, callback=callback, include_uri=include_uri)
        self.write_message(msg)

        await self.requests[request_id]

    def event(self, subscription_id, *args, **kwargs):
        if self.subscriptions[subscription_id].include_uri:
            self.subscriptions[subscription_id].callback(*args, **kwargs, uri_name=self.subscriptions[subscription_id].uri_name)
        else:
            self.subscriptions[subscription_id].callback(*args, **kwargs)

    def invoke(self, registration_id, *args, **kwargs):
        if self.registrations[registration_id].include_uri:
            return self.registrations[registration_id].callback(*args, **kwargs, uri_name=self.registrations[registration_id].uri_name)
        else:
            return self.registrations[registration_id].callback(*args, **kwargs)

    def error(self, request_id, *args, **kwargs):
        if request_id in self.requests:
            self.requests[request_id].set_exception(WAMPSimpleException('Received', *args, **kwargs))

    def result(self, request_id, *args, **kwargs):
        if request_id in self.requests:
            self.requests[request_id].set_result((args, kwargs))

    def on_close(self):
        """
        Overrides the base class to clean up our connections and registrations.
        """
        self.realm.disconnect(self)
        self.realm.deregister_handler(self.realm_id)
        
        # This is a meta-class, so we're assuming that we have a parent class, even if it isn't listed.
        super().on_close()

    def join_realm(self, name, details=client_features):
        """
        Request to join the specified realm from the server.  It will not actually join the realm, but rather,
        when the server sends back a welcome message, it will be attached to it.
        """
        hello_message = HelloMessage(realm=name, details=details)

        self.write_message(hello_message)




    def broadcast_messages(self, processor):
        """
        """
        for msg in processor.broadcast_messages:
            uri = self.realm.get(msg.uri_name)

            # Only publish if there is someone listening.
            if uri is not None:
                uri.publish(self, msg)



class WAMPMetaClientHandlerDebug(WAMPMetaClientHandler):
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






