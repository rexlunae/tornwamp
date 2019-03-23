"""
Classes and methods for Topic URIs for pub/sub
"""
import tornadis
from tornado import ioloop

from tornwamp import utils
from tornwamp.uri import URI, URIType, deliver_event_messages
from tornwamp.identifier import create_global_id

PUBSUB_TIMEOUT = 60
PUBLISHER_CONNECTION_TIMEOUT = 3 * 3600 * 1000  # 3 hours in miliseconds


class RedisUnavailableError(Exception):
    pass


class Topic(URI):
    """
    A topic URI for use with pub/sub functionality.
    """

    def __init__(self, name, redis=None):
        super().__init__(name, URIType.TOPIC, redis=redis)
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
        return {**self.subscribers, **self.publishers}

    def publish(self, broadcast_msg):
        """
        Publish event_msg to all subscribers. This method will publish to
        redis if redis is available. Otherwise, it will run locally and can
        be called without yield.

        The parameter publisher_connection_id is used to not publish the
        message back to the publisher.
        """
        event_msg = broadcast_msg.event_message
        deliver_event_messages(self, event_msg, broadcast_msg.publisher_connection_id)
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


    def _disconnect_publisher(self):
        """
        Disconnect periodically in order not to have several unused connections
        of old topics.
        """
        if self._publisher_connection is not None:
            self._publisher_connection.disconnect()

    def _on_redis_message(self, fut):
        result = fut.result()
        if isinstance(result, tornadis.ConnectionError) or isinstance(result, tornadis.ClientError):
            # Connection with redis was lost
            self._drop_subscribers()
        elif result is not None:
            self._register_redis_callback()
            type_, uri, raw_msg = result
            assert type_.decode("utf-8") == u"message", "got wrong message type from pop_message: {}".format(type_)
            self._on_event_message(uri.decode('utf-8'), raw_msg)
        else:
            self._register_redis_callback()

