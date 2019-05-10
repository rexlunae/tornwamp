""" WAMP-PubSub processors.
"""
from tornado import gen

from wampnado.identifier import create_global_id
from wampnado.messages import ErrorMessage, EventMessage, PublishMessage, PublishedMessage, SubscribeMessage, SubscribedMessage, BroadcastMessage
from wampnado.processors import Processor
from wampnado.auth import default_roles

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

        subscription_id = self.handler.realm.add_subscriber(
            received_message.uri,
            self.handler,
            msg=received_message,
        )

        return SubscribedMessage(
            request_id=received_message.request_id,
            subscription_id=subscription_id
        )


class PublishProcessor(Processor):
    """
    Responsible for dealing PUBLISH messages.
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
        

