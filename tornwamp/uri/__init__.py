"""
Used to handle PubSub topics publishers and subscribers
"""
from enum import Enum
#from tornado import ioloop
import tornadis

from tornwamp import messages
from tornwamp.identifier import create_global_id

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
        #assert_msg = "broadcast message topic and redis pub/sub queue must match ({} != {})".format(uri, msg.uri)
        #assert uri == msg.uri, assert_msg
        if msg.publisher_node_id != messages.PUBLISHER_NODE_ID.hex:
            deliver_event_messages(self, msg.event_message, None)



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

