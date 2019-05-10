from threading import Thread
from queue import Queue
from warnings import warn

from wampnado.handler import WAMPMetaHandler
from wampnado.messages import Code, CallMessage, ResultMessage, InvocationMessage, YieldMessage, ErrorMessage, SubscribeMessage, RPCRegisterMessage, HelloMessage
from wampnado.realm import get_realm
from wampnado.identifier import create_global_id
from wampnado.transports import LocalTransport
from wampnado.uri import URIType
from wampnado.messages import Code, YieldMessage, ErrorMessage, BroadcastMessage, build_error_message

class LocalClient():
    """
    The client end of a LocalTransport.
    """
    def __init__(self):
        # The transport is the server-side representation of this client.
        self.transport = WAMPMetaHandler.factory(transport_cls=LocalTransport)(client=self)
        self.message_queue_in = Queue()
        self.message_queue_out = Queue()
        self.handlers = {}
        self.pending_requests = {}

    def process(self, message):
        print(repr(message.value))

        if message.code == Code.INVOCATION:
            method = self.handlers[message.uri]
            result_args, result_kwargs = method(*message.args, **message.kwargs)
            self.transport.send_message(YieldMessage(request_id=message.request_id, args=result_args, kwargs=result_kwargs))
        else:
            raise(NotImplementedError)

    def run(self):
        while True:
            warn('-')
            message = self.transport.receive_message()
            warn('+')
            self.process(message)
            

    async def attach_realm(self, name):
        """
        Called by the client to place itself in a realm.
        """
        await self.transport.send_message(HelloMessage(realm=name))
        #self.realm = get_realm(name)


    async def subscribe(self, uri, handler):
        self.handlers[uri] = (handler, URIType.TOPIC)

    def publish(self, uri, message):
        """
        Called by the client to publish a message.
        """
        raise(NotImplementedError)

    async def register(self, uri, handler, options={}):
        # Register the handler with the client.
        request_id = create_global_id()
        print('Request for registration pending...' + str(request_id))
        result = await self.transport.send_message(RPCRegisterMessage(request_id=request_id, uri=uri, options=options))
        print(result)
        self.handlers[uri] = (handler, URIType.PROCEDURE)
        return result

    
    async def call(self, uri, *args, options={}, **kwargs):
        """
        Called by the client to issue a call to the server.
        """
        request_id = create_global_id()

        # Create a future to wait for the request.
        self.pending_requests[request_id] = await self.transport.send_message(CallMessage(procedure=uri, request_id=request_id, options=options, args=args, kwargs=kwargs))



    async def invoke(self, uri, request_id, *args, options={}, **kwargs):
        """
        Called by the dealer to issue a call to the client.  The client returns the resulting message.
        """
        (procedure, uri_type) = self.handlers[uri]
        if uri_type == URIType.PROCEDURE:
            try:
                return YieldMessage(procedure(*args, options=options, **kwargs), request_id=request_id, options=options)
            except e as Exception:
                return ErrorMessage(uri=self.transport.realm.errors.general_error.to_uri(), request_id=request_id, args=args, kwargs=kwargs, request_code=Code.INVOCATION).error(e)
        else:
            return ErrorMessage(uri=self.transport.realm.errors.no_such_registration.to_uri(), request_id=request_id, args=args, kwargs=kwargs, request_code=Code.INVOCATION).error("Not a procedure")

    def broadcast(self, uri, publisher_id, data):
        """
        Called by the broker to issue send a message to a client.  There is no return.
        """
        (procedure, uri_type) = self.handlers[uri]
        if uri_type == URIType.TOPIC:
            BroadcastMessage(procedure(publisher_id, data))

    


