""" WAMP-PubSub processors.
"""
from tornado import gen

from wampnado.identifier import create_global_id
from wampnado.messages import ErrorMessage, EventMessage, PublishMessage, PublishedMessage, SubscribeMessage, SubscribedMessage, BroadcastMessage
from wampnado.processors import Processor
from wampnado.auth import default_roles
from wampnado.uri.error import WAMPSimpleException

default_roles.register('subscribe')
default_roles.register('publish')

class SubscribeProcessor(Processor):
    """
    Responsible for dealing SUBSCRIBE messages.
    """
    def process(self):
        """
        Return SUBSCRIBE message based on the input HELLO message.
        """
        received_message = SubscribeMessage(*self.message.value)

        self.handler.realm.roles.authorize('subscribe', self.handler, received_message.code, received_message.request_id)

        try:
            subscription_id = self.handler.realm.add_subscriber(
                received_message.uri,
                self.handler,
            )
        except WAMPSimpleException as e:
            raise e.to_exception(received_message.code, received_message.request_id)

        return SubscribedMessage(
            request_id=received_message.request_id,
            subscription_id=subscription_id
        )

class SubscribedProcessor(Processor):
    """
    Responsible for dealing SUBSCRIBED messages.
    """
    def process(self):
        """
        Return SUBSCRIBE message based on the input HELLO message.
        """
        received_message = SubscribedMessage(*self.message.value)
        self.handler.add_subscriber(received_message.request_id, received_message.subscription_id)
        return None

class PublishProcessor(Processor):
    """
    Responsible for dealing PUBLISH messages received by the server.
    """
    def process(self):
        """
        Return PUBLISHED message based on the PUBLISH message received.
        """
        received_message = PublishMessage(*self.message.value)
        uri = self.handler.realm.get(received_message.uri_name, msg=received_message)

        self.handler.realm.roles.authorize('publish', self.handler, received_message.code, received_message.request_id, *received_message.args, **received_message.kwargs)

        # This will return the PublishedMessage if the appropriate option is set.
        return uri.publish(self.handler, received_message)
        

class PublishedProcessor(Processor):
    """
    Responsible for dealing PUBLISHED messages received by the client.
    """
    def process(self):
        """
        """
        received_message = PublishedMessage(*self.message.value)
        if hasattr(self.handler, 'on_published'):
            self.handler.on_published(received_message.request_id, received_message.publication_id)

class EventProcessor(Processor):
    """
    Handles pubsub events
    """
    def process(self):
        """
        """
        received_message = EventMessage(*self.message.value)
        self.handler.event(received_message)
