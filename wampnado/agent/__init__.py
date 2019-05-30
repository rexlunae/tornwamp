"""
Code common to clients and servers.
"""
from inspect import isawaitable

from tornado.websocket import WebSocketClosedError

from wampnado.messages import Code, AbortMessage
from wampnado.processors import AbortProcessor, UnhandledProcessor, GoodbyeProcessor, ErrorProcessor, HelloProcessor, rpc, pubsub
from wampnado.serializer import JSON_PROTOCOL, BINARY_PROTOCOL, NONE_PROTOCOL
from wampnado.messages import Message

class WAMPAgent:
    """
    Class the describes methods common to both clients and servers.  Incomplete in and of itself.
    """
    processors = {
        Code.ABORT: AbortProcessor,
        Code.GOODBYE: GoodbyeProcessor,
        Code.ERROR: ErrorProcessor,

        # Server:
        #Code.HELLO: HelloProcessor,
        #Code.SUBSCRIBE: pubsub.SubscribeProcessor,
        #Code.PUBLISH: pubsub.PublishProcessor,
        #Code.YIELD: rpc.YieldProcessor,
        #Code.CALL: rpc.CallProcessor,
        #Code.REGISTER: rpc.RegisterProcessor,

    }


    def write_message(self, msg):
        """
        Reads a message to the WebSocket in the format selected for it.
        """
        if self.protocol == JSON_PROTOCOL:
            return super().write_message(msg.json)
        elif self.protocol == BINARY_PROTOCOL:
            return super().write_message(msg.msgpack, binary=True)
        elif self.protocol == NONE_PROTOCOL:
            return super().write_message(msg)
        else:
            warn('unknown protocol ' + self.protocol)

    def read_message(self, txt):
        """
        Reads a message in whatever format is selected for the WebSocket.
        """
        if self.protocol == JSON_PROTOCOL:
            return Message.from_text(txt)
        elif self.protocol == BINARY_PROTOCOL:
            return Message.from_bin(txt)
        elif self.protocol == NONE_PROTOCOL:
            # If we're using NONE_PROTOCOL, txt is actually just the message.
            return txt
        else:
            warn('unknown protocol ' + self.protocol)

    async def handle_message(self, msg):
        Processor = self.processors.get(msg.code, UnhandledProcessor)
        processor = Processor(msg, self)

        #if self.connection and not self.connection.zombie:  # TODO: cover branch else
        answer = processor.answer_message
        if isawaitable(answer):
            answer = await answer
        if answer is not None:
            print(type(self))
            self.write_message(answer)

        self.broadcast_messages(processor)

        if processor.must_close:
            self.on_close(processor.close_code, processor.close_reason)

    async def on_message(self, txt):
        """
        Handle incoming messages on the WebSocket. Each message will be parsed
        and handled by a Processor, which can be (re)defined by the user
        changing the value of 'processors' dict, available at
        wampnado.customize module.
        """
        try:
            msg = self.read_message(txt)
            await self.handle_message(msg)
        except WebSocketClosedError as e:
            warn('closed connection {} due to {}'.format(self.sessionid, e))
            self.on_close()

    def abort(self, handler, error_msg, details, reason=None):
        """
        Used to abort a connection while the user is trying to establish it.
        """
        if reason is None:
            abort_message = AbortMessage(reason=self.realm.not_authorized.to_uri())

        abort_message.error(error_msg, details)
        handler.write_message(abort_message.json)
        handler.close(1, error_msg)

