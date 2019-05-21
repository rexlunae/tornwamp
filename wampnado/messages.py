"""
WAMP messages definitions and serializers.

Compatible with WAMP Document Revision: RC3, 2014/08/25, available at:
https://github.com/tavendo/WAMP/blob/master/spec/basic.md
"""
import json
import msgpack
import uuid
from copy import deepcopy

from enum import IntEnum, Enum
from io import BytesIO
from base64 import b64encode, standard_b64decode

from wampnado.identifier import create_global_id
from wampnado.features import server_features, Options

PUBLISHER_NODE_ID = uuid.uuid4()

def decode_b64(s):
    """
    Finds all the binary objects in the struct, and recursively converts them to base64 prepended by \0, per the WAMP standard.
    """
    if isinstance(s, dict):
        ret = {}
        for k,v in s.items():
            ret[k] = decode_b64(v)
        return ret
    elif isinstance(s, list) or isinstance(s, tuple):
        ret = []
        for v in s:
            ret.append(decode_b64(v))
        return ret
    elif isinstance(s, str) and s.beginswith('\0'):
        return standard_b64decode(s[1:])
    else:
        return s
    

def encode_bin_as_b64(s):
    """
    Finds all the binary objects in the struct, and recursively converts them to base64 prepended by \0, per the WAMP standard.
    """
    if isinstance(s, dict):
        ret = {}
        for k,v in s.items():
            ret[k] = encode_bin_as_b64(v)
        return ret
    elif isinstance(s, list) or isinstance(s, tuple):
        ret = []
        for v in s:
            ret.append(encode_bin_as_b64(v))
        return ret
    elif isinstance(s, bytes):
        return '\0{}'.format(b64encode(s).decode('ascii'))
    elif isinstance(s, Enum):
        return encode_bin_as_b64(s.value)
    else:
        return s
    


class Code(IntEnum):
    """
    Enum which represents currently supported WAMP messages.
    """
    HELLO = 1
    WELCOME = 2
    ABORT = 3
    # CHALLENGE = 4
    # AUTHENTICATE = 5
    GOODBYE = 6
    # HEARTBEAT = 7
    ERROR = 8
    PUBLISH = 16
    PUBLISHED = 17
    SUBSCRIBE = 32
    SUBSCRIBED = 33
    UNSUBSCRIBE = 34
    UNSUBSCRIBED = 35
    EVENT = 36
    CALL = 48
    # CANCEL = 49
    RESULT = 50
    REGISTER = 64
    REGISTERED = 65
    # UNREGISTER = 66
    # UNREGISTERED = 67
    INVOCATION = 68
    INTERRUPT = 69
    YIELD = 70


class BroadcastMessage(object):
    """
    This is a message that a procedure may want delivered.

    This class is composed of an EventMessage and a uri name
    """
    def __init__(self, uri_name, event_message, publisher_connection_id):
        assert isinstance(event_message, EventMessage), "only event messages are supported"
        self.uri_name = uri_name
        self.event_message = event_message
        self.publisher_connection_id = publisher_connection_id
        self.publisher_node_id = PUBLISHER_NODE_ID.hex

    @property
    def json(self):
        info_struct = {
            "publisher_node_id": self.publisher_node_id,
            "publisher_connection_id": self.publisher_connection_id,
            "uri_name": self.uri_name,
            "event_message": self.event_message.json,
        }
        return json.dumps(encode_bin_as_b64(info_struct))

    @property
    def msgpack(self):
        info_struct = {
            "publisher_node_id": self.publisher_node_id,
            "publisher_connection_id": self.publisher_connection_id,
            "uri_name": self.uri_name,
            "event_message": self.event_message.msgpack,
        }
        return msgpack.packb(info_struct, use_bin_type=True)

    @classmethod
    def from_text(cls, text):
        """
        Make a BroadcastMessage from text in a json struct
        """
        raw = json.loads(text)
        event_msg = EventMessage.from_text(raw["event_message"])
        msg = cls(
            uri_name=raw["uri_name"],
            event_message=event_msg,
            publisher_connection_id=raw["publisher_connection_id"]
        )
        msg.publisher_node_id = raw["publisher_node_id"]
        return msg

    @classmethod
    def from_bin(cls, bin):
        """
        Make a BroadcastMessage from a binary blob
        """
        raw = msgpack.unpackb(bin, raw=False)
        event_msg = EventMessage.from_text(raw["event_message"])
        msg = cls(
            uri_name=raw["uri_name"],
            event_message=event_msg,
            publisher_connection_id=raw["publisher_connection_id"]
        )
        msg.publisher_node_id = raw["publisher_node_id"]
        return msg


class Message(object):
    """
    Represent any WAMP message.
    """
    details = {}

    def __init__(self, code, *data, **kdata):
        self.code = code
        self.value = [code] + list(data)
        self.args = kdata.get("args", [])
        self.kwargs = kdata.get("kwargs", {})

    @property
    def id(self):
        """
        For all kinds of messages (except ERROR) that have [Request|id], it is
        in the second position of the array.
        """
        if (len(self.value) > 1) and isinstance(self.value[1], int):
            return self.value[1]
        return -1

    @property
    def json(self):
        """
        Create a JSON representation of this message.
        """
        message_value = deepcopy(self.value)
        return json.dumps(encode_bin_as_b64(message_value))

    @property
    def msgpack(self):
        """
        Create a MSGPack representation for this message.
        """
        message_value = deepcopy(self.value)
        for index, item in enumerate(message_value):
            if isinstance(item, Code):
                message_value[index] = item.value
        return msgpack.packb(message_value, use_bin_type=True)

    def error(self, text, info=None):
        """
        Add error description and aditional information.

        This is useful for ABORT and ERROR messages.
        """
        self.details["message"] = text
        if info:
            self.details["details"] = info

    @classmethod
    def from_text(cls, text):
        """
        Decode text to JSON and return a Message object accordingly.
        """
        raw = decode_b64(json.loads(text))
        raw[0] = Code(raw[0])  # make it an object of type Code
        return cls(*raw)

    @classmethod
    def from_bin(cls, bin):
        """
        Decode binary blob to a message and return a Message object accordingly.
        """
        raw = msgpack.unpackb(bin, raw=False)
        raw[0] = Code(raw[0])  # make it an object of type Code
        return cls(*raw)

    def _update_args_and_kargs(self):
        """
        Append args and kwargs to message value, according to their existance
        or not.
        """
        if self.kwargs:
            self.value.append(self.args)
            self.value.append(self.kwargs)
        else:
            if self.args:
                self.value.append(self.args)


class HelloMessage(Message):
    """
    Sent by a Client to initiate opening of a WAMP session:
    [HELLO, Realm|uri, Details|dict]

    https://github.com/tavendo/WAMP/blob/master/spec/basic.md#hello
    """

    def __init__(self, code=Code.HELLO, realm="", details=None):
        self.code = code
        self.realm = realm
        self.details = details if details else {}
        self.value = [self.code, self.realm, self.details]


class AbortMessage(Message):
    """
    Both the Router and the Client may abort the opening of a WAMP session
    [ABORT, Details|dict, Reason|uri]

    https://github.com/tavendo/WAMP/blob/master/spec/basic.md#abort
    """

    def __init__(self, code=Code.ABORT, details=None, reason=None):
        assert reason is not None, "AbortMessage must have a reason"
        self.code = code
        self.details = details or {}
        self.reason = reason
        self.value = [self.code, self.details, self.reason]


class WelcomeMessage(Message):
    """
    Sent from the server side to open a WAMP session.
    The WELCOME is a reply message to the Client's HELLO.

    [WELCOME, Session|id, Details|dict]

    https://github.com/tavendo/WAMP/blob/master/spec/basic.md#welcome
    """

    def __init__(self, code=Code.WELCOME, session_id=None, details=None):
        self.code = code
        self.session_id = session_id or create_global_id()
        self.details = details or server_features
        self.value = [self.code, self.session_id, self.details]


class GoodbyeMessage(Message):
    """
    Both the Server and the Client may abort the opening of a WAMP session
    [ABORT, Details|dict, Reason|uri]
    """

    def __init__(self, code=Code.GOODBYE, details=None, reason=None):
        self.code = code
        self.details = details or {}
        self.reason = reason or ""
        self.value = [self.code, self.details, self.reason]


class ResultMessage(Message):
    """
    Result of a call as returned by Dealer to Caller.

    [RESULT, CALL.Request|id, Details|dict]
    [RESULT, CALL.Request|id, Details|dict, YIELD.Arguments|list]
    [RESULT, CALL.Request|id, Details|dict, YIELD.Arguments|list, YIELD.ArgumentsKw|dict]
    """

    def __init__(self, code=Code.RESULT, request_id=None, details=None, args=None, kwargs=None):
        assert request_id is not None, "ResultMessage must have request_id"
        self.code = code
        self.request_id = request_id
        self.details = details or {}
        self.args = args or []
        self.kwargs = kwargs or {}
        self.value = [
            self.code,
            self.request_id,
            self.details
        ]
        self._update_args_and_kargs()


class CallMessage(Message):
    """
    Call as originally issued by the Caller to the Dealer.

    [CALL, Request|id, Options|dict, Procedure|uri]
    [CALL, Request|id, Options|dict, Procedure|uri, Arguments|list]
    [CALL, Request|id, Options|dict, Procedure|uri, Arguments|list, ArgumentsKw|dict]
    """

    def __init__(self, code=Code.CALL, request_id=None, options={}, procedure=None, args=[], kwargs={}):
        assert request_id is not None, "CallMessage must have request_id"
        assert procedure is not None, "CallMessage must have procedure"
        self.code = code
        self.request_id = request_id
        self.procedure = procedure
        self.options = Options(**options)
        self.args = args
        self.kwargs = kwargs
        self.value = [
            self.code,
            self.request_id,
            self.options,
            self.procedure,
        ]
        self._update_args_and_kargs()

class InterruptMessage(Message):
    """
    Stop a progressive result before it's finished.

    [INTERRUPT, INVOCATION.Request|id, Options|dict]
    """
    def __init__(self, code=Code.INTERRUPT, request_id=None, options={}):
        assert request_id is not None, "InterruptMessage must have request_id"
        self.request_id = request_id
        self.options = Options(**options)
        self.value = [
            self.code,
            self.request_id,
            self.options,
        ]

    

class InvocationMessage(Message):
    """
    Used by the dealer to request an RPC from a client.  The client should respond with a YIELD message if successful.

    [INVOCATION, Request|id, REGISTERED.Registration|id, Details|dict]
    [INVOCATION, Request|id, REGISTERED.Registration|id, Details|dict, CALL.Arguments|list]
    [INVOCATION, Request|id, REGISTERED.Registration|id, Details|dict, CALL.Arguments|list, CALL.ArgumentsKw|dict]
    """

    def __init__(self, code=Code.INVOCATION, request_id=None, registration_id=None, details={}, args=None, kwargs=None):
        if request_id is None:
            request_id = create_global_id()
        assert request_id is not None, "InvocationMessage must have request_id"
        assert registration_id is not None, "InvocationMessage must have registration_id"
        self.code = code
        self.request_id = request_id
        self.registration_id = registration_id or {}
        self.details = details
        self.args = args
        self.kwargs = kwargs
        self.value = [
            self.code,
            self.request_id,
            self.registration_id,
            self.details,
        ]
        self._update_args_and_kargs()


class YieldMessage(Message):
    """
    Used by the dealer to deliver the result of an RPC to the requesting client.  The client should respond with a YIELD message if successful.

    [YIELD, INVOCATION.Request|id, Options|dict]
    [YIELD, INVOCATION.Request|id, Options|dict, Arguments|list]
    [YIELD, INVOCATION.Request|id, Options|dict, Arguments|list, ArgumentsKw|dict]
    """

    def __init__(self, code=Code.YIELD, request_id=None, options=None, args=None, kwargs=None):
        assert request_id is not None, "YieldMessage must have request_id"
        self.code = code
        self.options = Options(**options)
        self.request_id = request_id
        self.args = args
        self.kwargs = kwargs
        self.value = [
            self.code,
            self.request_id,
            self.options,
        ]
        self._update_args_and_kargs()


class ErrorMessage(Message):
    """
    Error reply sent by a Peer as an error response to different kinds of
    requests.

    [ERROR, REQUEST.Type|int, REQUEST.Request|id, Details|dict, Error|uri]
    [ERROR, REQUEST.Type|int, REQUEST.Request|id, Details|dict, Error|uri,
        Arguments|list]
    [ERROR, REQUEST.Type|int, REQUEST.Request|id, Details|dict, Error|uri,
        Arguments|list, ArgumentsKw|dict]
    """

    def __init__(self, code=Code.ERROR, request_code=None, request_id=None, details=None, uri=None, args=None, kwargs=None):
        assert request_code is not None, "ErrorMessage must have request_code"
        assert request_id is not None, "ErrorMessage must have request_id"
        assert uri is not None, "ErrorMessage must have uri"
        self.code = code
        self.request_code = request_code
        self.request_id = request_id
        self.details = details or {}
        self.uri = uri
        self.args = args or []
        self.kwargs = kwargs or {}
        self.value = [
            self.code,
            self.request_code,
            self.request_id,
            self.details,
            self.uri
        ]
        self._update_args_and_kargs()


class SubscribeMessage(Message):
    """
    A Subscriber communicates its interest in a uri to the Server by sending
    a SUBSCRIBE message:
    [SUBSCRIBE, Request|id, Options|dict, uri|uri]
    """

    def __init__(self, code=Code.SUBSCRIBE, request_id=None, options=None, uri=None):
        assert request_id is not None, "SubscribeMessage must have request_id"
        assert uri is not None, "SubscribeMessage must have uri"
        self.code = code
        self.request_id = request_id
        self.options = Options(**options)
        self.uri = uri
        self.value = [self.code, self.request_id, self.options, self.uri]


class SubscribedMessage(Message):
    """
    If the Broker is able to fulfill and allow the subscription, it answers by
    sending a SUBSCRIBED message to the Subscriber:
    [SUBSCRIBED, SUBSCRIBE.Request|id, Subscription|id]
    """
    def __init__(self, code=Code.SUBSCRIBED, request_id=None, subscription_id=None):
        assert request_id is not None, "SubscribedMessage must have request_id"
        assert subscription_id is not None, "SubscribedMessage must have subscription_id"
        self.code = code
        self.request_id = request_id
        self.subscription_id = subscription_id
        self.value = [self.code, self.request_id, self.subscription_id]



class RPCRegisterMessage(Message):
    """
    A Registerer communicates its interest in a uri to the Server by sending
    a REGISTER message:
    [REGISTER, Request|id, Options|dict, uri|uri]
    """

    def __init__(self, code=Code.REGISTER, request_id=None, options=None, uri=None):
        assert request_id is not None, "RegisterMessage must have request_id"
        assert uri is not None, "RegisterMessage must have uri"
        self.code = code
        self.request_id = request_id
        self.options = Options(**options)
        self.uri = uri
        self.value = [self.code, self.request_id, self.options, self.uri]


class RPCRegisteredMessage(Message):
    """
    If the Broker is able to fulfill and allow the registration, it answers by
    sending a REGISTERED message to the Registerer:
    [REGISTERED, REGISTER.Request|id, Registration|id]
    """
    def __init__(self, code=Code.REGISTERED, request_id=None, registration_id=None):
        if registration_id is None:
            registration_id = create_global_id()
        assert request_id is not None, "RegisteredMessage must have request_id"
        assert registration_id is not None, "RegisteredMessage must have registration_id"
        self.code = code
        self.request_id = request_id
        self.registration_id = registration_id
        #self.uri = uri
        self.value = [self.code, self.request_id, self.registration_id]



class PublishMessage(Message):
    """
    Sent by a Publisher to a Broker to publish an event.

    [PUBLISH, Request|id, Options|dict, uri|uri]
    [PUBLISH, Request|id, Options|dict, uri|uri, Arguments|list]
    [PUBLISH, Request|id, Options|dict, uri|uri, Arguments|list, ArgumentsKw|dict]
    """
    def __init__(self, code=Code.PUBLISH, request_id=None, options={}, uri_name=None, args=None, kwargs=None):
        assert request_id is not None, "PublishMessage must have request_id"
        assert uri_name is not None, "PublishMessage must have uri"
        self.code = code
        self.request_id = request_id
        self.options = Options(**options)
        self.uri_name = uri_name
        self.args = args or []
        self.kwargs = kwargs or {}
        self.value = [self.code, self.request_id, self.options, self.uri_name]
        self._update_args_and_kargs()


class PublishedMessage(Message):
    """
    Acknowledge sent by a Broker to a Publisher for acknowledged publications.

    [PUBLISHED, PUBLISH.Request|id, Publication|id]
    """
    def __init__(self, code=Code.PUBLISHED, request_id=None, publication_id=None):
        assert request_id is not None, "PublishedMessage must have request_id"
        assert publication_id is not None, "PublishedMessage must have publication_id"
        self.code = code
        self.request_id = request_id
        self.publication_id = publication_id
        self.value = [self.code, self.request_id, self.publication_id]


class EventMessage(Message):
    """
    Event dispatched by Broker to Subscribers for subscription the event was matching.

    [EVENT, SUBSCRIBED.Subscription|id, PUBLISHED.Publication|id, Details|dict]
    [EVENT, SUBSCRIBED.Subscription|id, PUBLISHED.Publication|id, Details|dict, PUBLISH.Arguments|list]
    [EVENT, SUBSCRIBED.Subscription|id, PUBLISHED.Publication|id, Details|dict, PUBLISH.Arguments|list, PUBLISH.ArgumentsKw|dict]

    When transmitting an EventMessage between redis pubsubs the
    subscription_id will be omitted (it can only be resolved in the
    subscriber.)
    """
    def __init__(self, code=Code.EVENT, subscription_id=None, publication_id=None, details=None, args=None, kwargs=None):
        assert publication_id is not None, "EventMessage must have publication_id"
        self.code = code
        self._subscription_id = subscription_id
        self.publication_id = publication_id
        self.details = details or {}
        self.args = args or []
        self.kwargs = kwargs or {}
        self.value = [self.code, self.subscription_id, self.publication_id, self.details]
        self._update_args_and_kargs()

    @property
    def subscription_id(self):
        return self._subscription_id

    @subscription_id.setter
    def subscription_id(self, id_):
        self._subscription_id = id_
        self.value[1] = id_


class UnsubscribeMessage(Message):
    """
    Unsubscribe request sent by a Subscriber to a Broker to unsubscribe a subscription.
    [UNSUBSCRIBE, Request|id, SUBSCRIBED.Subscription|id]
    """
    def __init__(self, code=Code.UNSUBSCRIBE, request_id=None, subscription_id=None):
        assert request_id is not None, "UnsubscribeMessage must have request_id"
        assert subscription_id is not None, "UnsubscribeMessage must have subscription_id"
        self.code = code
        self.request_id = request_id
        self.subscription_id = subscription_id
        self.value = [self.code, self.request_id, self.subscription_id]


class UnsubscribedMessage(Message):
    """
    Acknowledge sent by a Broker to a Subscriber to acknowledge unsubscription.
    [UNSUBSCRIBED, UNSUBSCRIBE.Request|id]
    """
    def __init__(self, code=Code.UNSUBSCRIBED, request_id=None):
        assert request_id is not None, "UnsubscribedMessage must have request_id"
        self.code = code
        self.request_id = request_id
        self.value = [self.code, self.request_id]


CODE_TO_CLASS = {
    Code.HELLO: HelloMessage,
    Code.WELCOME: WelcomeMessage,
    Code.ABORT: AbortMessage,
    # CHALLENGE = 4
    # AUTHENTICATE = 5
    Code.GOODBYE: GoodbyeMessage,
    # HEARTBEAT = 7
    Code.ERROR: ErrorMessage,
    Code.PUBLISH: PublishMessage,
    Code.PUBLISHED: PublishedMessage,
    Code.SUBSCRIBE: SubscribeMessage,
    Code.SUBSCRIBED: SubscribedMessage,
    Code.UNSUBSCRIBE: UnsubscribeMessage,
    Code.UNSUBSCRIBED: UnsubscribedMessage,
    Code.EVENT: EventMessage,
    Code.CALL: CallMessage,
    # CANCEL = 49
    Code.RESULT: ResultMessage,
    Code.REGISTER: RPCRegisterMessage,          # 64
    Code.REGISTERED: RPCRegisteredMessage,      # 65
    # UNREGISTER = 66
    # UNREGISTERED = 67
    Code.INVOCATION: InvocationMessage,         # 68
    Code.INTERRUPT: InterruptMessage,
    # INTERRUPT = 69
    Code.YIELD: YieldMessage,                   # 70
}

ERROR_PRONE_CODES = [Code.CALL, Code.SUBSCRIBE, Code.UNSUBSCRIBE, Code.PUBLISH]


def build_error_message(in_message, uri, description):
    """
    Return ErrorMessage instance (*) provided:
    - incoming message which generated error
    - error uri
    - error description

    (*) If incoming message is not prone to ERROR message reponse, return None.
    """
    msg = Message.from_text(in_message)
    if msg.code in ERROR_PRONE_CODES:
        MsgClass = CODE_TO_CLASS[msg.code]
        msg = MsgClass.from_text(in_message)
        answer = ErrorMessage(
            request_code=msg.code,
            request_id=msg.request_id,
            uri=uri
        )
        answer.error(description)
        return answer
