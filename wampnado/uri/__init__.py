"""
Used to handle PubSub uris publishers and subscribers
"""
from enum import Enum
import tornadis

from wampnado import messages
from wampnado.identifier import create_global_id

# XXX - TODO:
#The following algorithm MUST be applied to find a single RPC registration to which a call is routed:
#Check for exact matching registration. If this match exists — use it.
#If there are prefix-based registrations, find the registration with the longest prefix match. Longest means it has more URI components matched, e.g. for call URI a1.b2.c3.d4 registration a1.b2.c3 has higher priority than registration a1.b2. If this match exists — use it.
#If there are wildcard-based registrations, find the registration with the longest portion of URI components matched before each wildcard. E.g. for call URI a1.b2.c3.d4 registration a1.b2..d4 has higher priority than registration a1...d4, see below for more complex examples. If this match exists — use it.
#If there is no exact match, no prefix match, and no wildcard match, then Dealer MUST return ERROR wamp.error.no_such_procedure.



# https://wamp-proto.org/_static/gen/wamp_latest.html#identifiers
class URIType(Enum):
    """
    The type of URI that we're dealing with.
    """
    TOPIC = 0
    PROCEDURE = 1
    ERROR = 2
    
class URI(object):
    """
    Represent a URI.  This should probably be mostly used through the subclasses.
    """
    def __init__(self, name, uri_type):
        self.registration_id=create_global_id()
        self.name = name
        self.uri_type = uri_type

    def _on_event_message(self, uri, raw_msg):
        msg = messages.BroadcastMessage.from_text(raw_msg.decode("utf-8"))
        #assert_msg = "broadcast message uri and redis pub/sub queue must match ({} != {})".format(uri, msg.uri)
        #assert uri == msg.uri, assert_msg
        if msg.publisher_node_id != messages.PUBLISHER_NODE_ID.hex:
            deliver_event_messages(self, msg.event_message, None)

    def __str__(self):
        return self.name

    def __repr__(self):
        return "URI('" + str(self.name) + "', " + str(self.uri_type) + ")"

def deliver_event_messages(uri, event_msg, publisher_connection_id=None):
    """
    Allows customization of methods used by pub/sub

    This method may be overridden. It is called whenever an EventMessage
    is published.

    Parameters:
        uri - uri in which the message was published
        event_msg - published message
        publisher_connection_id - if it is not None, it is the websocket
        connection id of the publisher
    """
    for subscription_id, subscriber in uri.subscribers.items():
        if publisher_connection_id is None or subscriber.id != publisher_connection_id:
            event_msg.subscription_id = subscription_id
            subscriber._websocket.write_message(event_msg)

