"""
This module allows customization of methods used by pub/sub
"""


def deliver_event_messages(uri, event_msg, publisher_connection_id=None):
    """
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
