"""
Used to handle PubSub topics publishers and subscribers
"""
from enum import Enum
from tornado import gen, ioloop
import tornadis

from tornwamp import messages, utils
from tornwamp.uri import customize
from tornwamp.identifier import create_global_id
from tornwamp import processors

PUBSUB_TIMEOUT = 60
PUBLISHER_CONNECTION_TIMEOUT = 3 * 3600 * 1000  # 3 hours in miliseconds

# https://wamp-proto.org/_static/gen/wamp_latest.html#identifiers
class URIType(Enum):
    """
    The type of URI that we're dealing with.
    """
    TOPIC = 0
    PROCEDURE = 1
    ERROR = 2


class RedisUnavailableError(Exception):
    pass


class URIManager(dict):
    """
    Manages all existing topics to which connections can potentially
    publish, subscribe, or call to.
    """
    def __init__(self):
        self.redis = None

    def create_topic(self, topic_name):
        """
        Creates a new topic with given name with configured redis address
        """
        self[topic_name] = self.get(topic_name, URI(topic_name, self.redis))

    def add_subscriber(self, topic_name, connection, subscription_id=None):
        """
        Add a connection as a topic's subscriber.
        """
        new_topic = URI(topic_name, self.redis)
        topic = self.get(topic_name, new_topic)
        subscription_id = subscription_id or create_global_id()
        topic.add_subscriber(subscription_id, connection)
        self[topic_name] = topic
        connection.add_subscription_channel(subscription_id, topic_name)
        return subscription_id

    def add_rpc(self, topic_name, connection, invoke=None):
        """
        Add a new RPC target on this connection.
        """
        new_topic = URI(topic_name,  redis=self.redis, rpc=True, provider=connection,)
        topic = self.get(topic_name, new_topic)
        #registration_id = create_global_id()
        registration_id = new_topic.registration_id
        processors.rpc.customize.procedures[topic_name] = [invoke, [], {}]
        self[topic_name] = topic
        #connection.add_publishing_channel(registration_id, topic_name)
        return registration_id

    def remove_subscriber(self, topic_name, subscription_id):
        """
        Remove a connection a topic's subscriber provided:
        - topic_name
        - subscription_id
        """
        topic = self.get(topic_name)
        if topic is not None:
            connection = topic.remove_subscriber(subscription_id)
            connection.remove_subscription_channel(topic_name)

    def add_publisher(self, topic_name, connection, subscription_id=None):
        """
        Add a connection as a topic's publisher.
        """
        topic = self.get(topic_name, Topic(topic_name, self.redis))
        subscription_id = subscription_id or create_global_id()
        topic.publishers[subscription_id] = connection
        self[topic_name] = topic
        connection.add_publishing_channel(subscription_id, topic_name)
        return subscription_id

    def remove_publisher(self, topic_name, subscription_id):
        """
        Remove a connection a topic's subscriber
        """
        topic = self.get(topic_name)
        if topic and subscription_id in topic.publishers:
            connection = topic.publishers.pop(subscription_id)
            connection.remove_publishing_channel(topic_name)

    def remove_connection(self, connection):
        """
        Connection is to be removed, scrap all connection publishers/subscribers in every topic
        """
        for topic_name, subscription_id in connection.topics.get("publisher", {}).items():
            topic = self.get(topic_name)
            topic.publishers.pop(subscription_id, None)

        for topic_name, subscription_id in connection.topics.get("subscriber", {}).items():
            topic = self.get(topic_name)
            topic.remove_subscriber(subscription_id)

    def get_connection(self, topic_name, subscription_id):
        """
        Get topic connection provided topic_name and subscription_id. Try to find
        it in subscribers, otherwise, fetches from publishers.
        Return None if it is not available in any.
        """
        topic = self[topic_name]
        return topic.subscribers.get(subscription_id) or topic.publishers.get(subscription_id)

    @property
    def dict(self):
        """
        Return a dict that is serializable.
        """
        return {k: topic.dict for k, topic in self.items()}

# Generally, we should only have one uri manager.  And this is it.
uri_registry = URIManager()


class URI(object):
    """
    Represent a URI, containing its name, subscribers and publishers, or provider connections.
    """
    def __init__(self, name, rpc=False, provider=None, redis=None):
        self.registration_id=create_global_id()
        self.name = name
        if rpc:
            self.rpc = rpc
            assert provider is not None
            self.provider = provider
        else:
            self.subscribers = {}
            self.publishers = {}
        self.redis_params = redis
        if self.redis_params is not None:
            self._publisher_connection = tornadis.Client(ioloop=ioloop.IOLoop.current(), autoconnect=True, **self.redis_params)
            self._periodical_disconnect = ioloop.PeriodicCallback(
                self._disconnect_publisher,
                PUBLISHER_CONNECTION_TIMEOUT
            )
            self._periodical_disconnect.start()
        else:
            self._publisher_connection = None
        self._subscriber_connection = None

    @property
    def connections(self):
        """
        Return a set of topic connections - no matter if they are subscribers or publishers.
        """
        # About merging two dictionaries without changing the original one:

        # first version:
        # dict(self.subscribers, **self.publishers)
        # but it doesn't work with Python 3.5 if keyword args aren't strings

        # cool fancy Python3.5 way:
        # {**self.subscribers, **self.publishers}

        # Python 2+3 boring compatible way:
        conns = self.subscribers.copy()
        conns.update(self.publishers)
        return conns

    @property
    def dict(self):
        """
        Return a dict that is serializable.
        """
        subscribers = {subscription_id: conn.dict for subscription_id, conn in self.subscribers.items()}
        publishers = {subscription_id: conn.dict for subscription_id, conn in self.publishers.items()}
        data = {
            "name": self.name,
            "subscribers": subscribers,
            "publishers": publishers
        }
        return data

    def invoke(self, msg):
        """
        Send an INVOCATION message to the provider.
        """
        assert self.rpc == True
        request_id = msg.request_id         # Read the message id from the message.  We just trust that this has been generated correctly.

        self.provider.write_message(msg)

    def publish(self, broadcast_msg):
        """
        Publish event_msg to all subscribers. This method will publish to
        redis if redis is available. Otherwise, it will run locally and can
        be called without yield.

        The parameter publisher_connection_id is used to not publish the
        message back to the publisher.
        """
        event_msg = broadcast_msg.event_message
        customize.deliver_event_messages(self, event_msg, broadcast_msg.publisher_connection_id)
        if self._publisher_connection is not None:
            ret = utils.run_async(self._publisher_connection.call("PUBLISH", self.name, broadcast_msg))
            if isinstance(ret, tornadis.ConnectionError):
                raise RedisUnavailableError(ret)
            return ret

    def remove_subscriber(self, subscriber_id):
        """
        Removes subscriber from topic
        """
        if subscriber_id in self.subscribers:
            subscriber = self.subscribers.pop(subscriber_id)
            if self._subscriber_connection is not None and not self.subscribers:
                self._subscriber_connection.disconnect()
                self._subscriber_connection = None
            return subscriber

    def add_subscriber(self, subscription_id, connection):
        """
        Add subscriber to a topic. It will register in redis if it is
        available (ie. redis parameter was passed to the constructor),
        otherwise, it will be a simple in memory operation only.
        """
        if self.redis_params is not None and self._subscriber_connection is None:
            self._subscriber_connection = tornadis.PubSubClient(autoconnect=False, ioloop=ioloop.IOLoop.current(), **self.redis_params)

            ret = utils.run_async(self._subscriber_connection.connect())
            if not ret:
                raise RedisUnavailableError(ret)

            try:
                ret = utils.run_async(self._subscriber_connection.pubsub_subscribe(self.name))
            except TypeError:
                # workaround tornadis bug
                # (https://github.com/thefab/tornadis/pull/39)
                # This can be reached in Python 3.x
                raise RedisUnavailableError(str(self.redis_params))
            if not ret:
                # this will only be reached when the previously mentioned bug
                # is fixed
                # This can be reached in Python 2.7
                raise RedisUnavailableError(ret)

            self._register_redis_callback()
        self.subscribers[subscription_id] = connection

    def _register_redis_callback(self):
        """
        Listens for new messages. If connection was dropped, then disconnect
        all subscribers.
        """
        if self._subscriber_connection is not None and self._subscriber_connection.is_connected():
            future = self._subscriber_connection.pubsub_pop_message(deadline=PUBSUB_TIMEOUT)
            ioloop.IOLoop.current().add_future(future, self._on_redis_message)
        else:
            # Connection with redis was lost
            self._drop_subscribers()

    def _drop_subscribers(self):
        """
        Drop all subscribers of this topic. This is called when connection to
        redis is lost.

        In case we get disconnected from redis we want to drop the connection
        of all subscribers so they know this happened.  Otherwise,
        subscribers could unknowingly lose messages.
        """
        for subscriber_id in list(self.subscribers.keys()):
            subscriber = self.remove_subscriber(subscriber_id)
            subscriber._websocket.close()

    def _on_event_message(self, topic_name, raw_msg):
        msg = messages.BroadcastMessage.from_text(raw_msg.decode("utf-8"))
        assert_msg = "broadcast message topic and redis pub/sub queue must match ({} != {})".format(topic_name, msg.topic_name)
        assert topic_name == msg.topic_name, assert_msg
        if msg.publisher_node_id != messages.PUBLISHER_NODE_ID.hex:
            customize.deliver_event_messages(self, msg.event_message, None)

    def _on_redis_message(self, fut):
        result = fut.result()
        if isinstance(result, tornadis.ConnectionError) or isinstance(result, tornadis.ClientError):
            # Connection with redis was lost
            self._drop_subscribers()
        elif result is not None:
            self._register_redis_callback()
            type_, topic_name, raw_msg = result
            assert type_.decode("utf-8") == u"message", "got wrong message type from pop_message: {}".format(type_)
            self._on_event_message(topic_name.decode('utf-8'), raw_msg)
        else:
            self._register_redis_callback()

    def _disconnect_publisher(self):
        """
        Disconnect periodically in order not to have several unused connections
        of old topics.
        """
        if self._publisher_connection is not None:
            self._publisher_connection.disconnect()
