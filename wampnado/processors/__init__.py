"""
Processors are responsible for parsing received WAMP messages and providing
feedback to the server on what should be done (e.g. send answer message order
close connection).
"""
import six
from abc import ABCMeta, abstractmethod
from warnings import warn

from tornado import gen

from wampnado.messages import Message, ErrorMessage, GoodbyeMessage, HelloMessage, WelcomeMessage
from wampnado.uri.error import WAMPException

class Processor(six.with_metaclass(ABCMeta)):
    """
    Abstract class which defines the base behavior for processing messages
    sent to the Websocket.

    Classes that extend this are supposed to overwride process method.
    """
    __metaclass__ = ABCMeta

    def __init__(self, message, handler):
        """
        message: json
        handler: handler object
        """
        # XXX self.session_id = getattr(handler.connection, "id", None)
        self.handler = handler

        # message just received by the WebSocket
        self.message = message

        # messages to be sent by the WebSocket
        self.answer_message = None  # response message

        # messages broadcasted to all subscribers
        self.broadcast_messages = []

        # the attributes below are in case we are expected to close the socket
        self.must_close = False
        self.close_code = None
        self.close_reason = None

        try:
            self.answer_message = self.process()
        except WAMPException as e:
            self.answer_message = e.message()


    @abstractmethod
    def process(self):
        """
        Responsible for processing the input message and may change the default
        values for the following attributes:
        - answer_message
        - group_messages

        - must_close
        - close_code (1000 or in the range 3000 to 4999)
        - close_message
        """
        raise(NotImplementedError)


class UnhandledProcessor(Processor):
    """
    Raises an error when the provided message can't be parsed
    """
    def process(self):
        message = Message(*self.message.value)
        description = "Unsupported message {0}".format(self.message.value)
        out_message = ErrorMessage(
            request_code=message.code,
            request_id=message.id,
            uri=self.handler.realm.errors.unsupported.to_uri()
        )
        out_message.error(description)
        return out_message

class AbortProcessor(Processor):
    """
    Responsible for handling ABORT messages.  Closes the connection and cleans up.
    """
    def process(self):
        """
        Close the connection, return nothing.
        """
        self.handler.close()
        return None


class HelloProcessor(Processor):
    """
    Responsible for handling HELLO messages.
    Server receives a HELLO from the client.
    """
    def process(self):
        """
        Return WELCOME message based on the input HELLO message.
        """
        hello_message = HelloMessage(*self.message.value)
        welcome_message = WelcomeMessage()
        self.handler.attach_realm(hello_message.realm, hello_message=hello_message.details)
        return welcome_message


class WelcomeProcessor(Processor):
    """
    Responsible for handling WELCOME messages.
    Client receives a WELCOME from the server in response to a HELLO.
    """
    def process(self):
        """
        Return WELCOME message based on the input HELLO message.  Accept session_id from the server.
        """
        welcome_message = WelcomeMessage(*self.message.value)
        self.handler.session_id = welcome_message.session_id
        return None


class GoodbyeProcessor(Processor):
    """
    Responsible for dealing GOODBYE messages.
    """
    def process(self):
        self.must_close = True
        # Excerpt from RFC6455 (The WebSocket Protocol)
        # "Endpoints MAY: use the following pre-defined status codes when sending
        # a Close frame:
        #   1000 indicates a normal closure, meaning that the purpose for
        #   which the connection was established has been fulfilled."
        # http://tools.ietf.org/html/rfc6455#section-7.4
        self.close_code = 1000
        self.close_reason = self.answer_message.details.get('message', '')
        return GoodbyeMessage(*self.message.value)

class ClientErrorProcessor(Processor):
    """
    Processes ERROR messages on the client.
    """
    def process(self):
        """
        Send the error.
        """
        msg = ErrorMessage(*self.message.value)
        self.handler.error(*msg.args, **msg.kwargs)

class ErrorProcessor(Processor):
    """
    Processes ERROR messages on the server.  Should propagate the error back to the erring client.
    """
    def process(self):
        """
        Close the connection, return nothing.
        """
        msg = ErrorMessage(*self.message.value)
        warn(*msg.args, **msg.kwargs)
