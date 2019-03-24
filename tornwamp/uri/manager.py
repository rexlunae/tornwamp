from tornwamp import processors
from tornwamp.uri import URIType
from tornwamp.uri.topic import Topic
from tornwamp.uri.procedure import Procedure
from tornwamp.uri.error import Error
from tornwamp.identifier import create_global_id


class URIManager(dict):
    """
    Manages all existing topics to which connections can potentially
    publish, subscribe, or call to.
    """
    def __init__(self):
        self.redis = None

    def create_topic(self, name):
        """
        Creates a topic that can be subscribed and published to.
        """
        self[name] = self.get(name, Topic(name, redis=self.redis))

    def create_error(self, name):
        """
        Adds an entry for an error URI.
        """
        new_uri = Error(name)
        uri = self.get(name, new_uri)
        self[name] = uri
        return self[name]


    def create_rpc(self, name, connection, invoke=None):
        """
        Add a new RPC target on this connection.
        """
        new_uri = Procedure(name, provider=connection)
        uri = self.get(name, new_uri)
        registration_id = new_uri.registration_id
        processors.rpc.customize.procedures[name] = [invoke, [], {}]
        self[name] = uri
        return registration_id

    def remove_rpc(self, name, registration_id):
        uri = self.get(name)
        if uri is not None:
            pass
            # XXX - Figure this out.

    def add_subscriber(self, uri, connection, registration_id=None):
        """
        Add a connection as a topic's subscriber.
        """
        new_topic = Topic(uri, self.redis)
        topic = self.get(uri, new_topic)
        registration_id = registration_id or create_global_id()
        topic.add_subscriber(registration_id, connection)
        self[uri] = topic
        connection.add_subscription_channel(registration_id, uri)
        return registration_id

    def remove_subscriber(self, uri, registration_id):
        """
        Remove a connection a topic's subscriber provided:
        - uri
        - subscription_id
        """
        topic = self.get(uri)
        if topic is not None and topic.uri_type == URIType.TOPIC:
            connection = topic.remove_subscriber(registration_id)
            connection.remove_subscription_channel(uri)
        else:
            from warnings import warn
            warn('uri ' + topic.uri_type + ' is of type ' + topic.uri_type)

    def add_publisher(self, uri, connection, subscription_id=None):
        """
        Add a connection as a topic's publisher.
        """
        topic = self.get(uri, Topic(uri, self.redis))
        subscription_id = subscription_id or create_global_id()
        topic.publishers[subscription_id] = connection
        self[uri] = topic
        connection.add_publishing_channel(subscription_id, uri)
        return subscription_id

    def remove_publisher(self, uri, subscription_id):
        """
        Remove a connection a topic's subscriber
        """
        topic = self.get(uri)
        if topic and subscription_id in topic.publishers:
            connection = topic.publishers.pop(subscription_id)
            connection.remove_publishing_channel(uri)

    def remove_connection(self, connection):
        """
        Connection is to be removed, scrap all connection publishers/subscribers in every topic
        """
        for name, registration_id in connection.uris.get("publisher", {}).items():
            uri = self.get(name)
            uri.publishers.pop(registration_id, None)

        for name, registration_id in connection.uris.get("subscriber", {}).items():
            uri = self.get(name)
            uri.remove_subscriber(registration_id)

        for name, registration_id in connection.uris.get("rpcs", {}).items():
            uri = self.pop(name, None)

    def get_connection(self, name, registration_id):
        """
        Get topic connection provided uri and subscription_id. Try to find
        it in subscribers, otherwise, fetches from publishers.
        Return None if it is not available in any.
        """
        uri = self[name]
        return uri.subscribers.get(registration_id) or uri.publishers.get(registration_id)

    @property
    def dict(self):
        """
        Return a dict that is serializable.
        """
        return {k: topic.dict for k, topic in self.items()}


