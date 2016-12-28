"""
TornWAMP user-configurable structures.
"""
from tornado import gen

from tornwamp import topic as tornwamp_topic
from tornwamp.processors import GoodbyeProcessor, HelloProcessor, pubsub, rpc
from tornwamp.messages import Code


processors = {
    Code.HELLO: HelloProcessor,
    Code.GOODBYE: GoodbyeProcessor,
    Code.SUBSCRIBE: pubsub.SubscribeProcessor,
    Code.CALL: rpc.CallProcessor,
    Code.PUBLISH: pubsub.PublishProcessor
}
#    2: 'welcome',
#    3: 'abort',
#    4: 'challenge',
#    5: 'authenticate',
#    7: 'heartbeat',
#    8: 'error',
#    17: 'published',
#    33: 'subscribed',
#    34: 'unsubscribe',
#    35: 'unsubscribed',
#    36: 'event',
#    49: 'cancel',
#    50: 'result',
#    64: 'register',
#    65: 'registered',
#    66: 'unregister',
#    67: 'unregistered',
#    68: 'invocation',
#    69: 'interrupt',
#    70: 'yield'


@gen.coroutine
def broadcast_message(processor):
    if processor.broadcast_message is not None:
        topic = tornwamp_topic.topics.get(processor.broadcast_message.topic_name)
        yield topic.publish(processor.broadcast_message)
