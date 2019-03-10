"""
RPC processors.

Compatible with WAMP Document Revision: RC3, 2014/08/25, available at:
https://github.com/tavendo/WAMP/blob/master/spec/basic.md
"""

import asyncio

from tornado import gen

from tornwamp.topic import topics
from tornwamp.messages import CallMessage, RPCRegisteredMessage, ResultMessage, ErrorMessage, EventMessage
from tornwamp.processors import Processor
from tornwamp.processors.rpc import customize

class RegisterProcessor(Processor):
    """
    Responsible for dealing REGISTER messages.
    """
    def process(self):
        """
        Return REGISTERED message based on the input HELLO message.
        """
        # REGISTERED messages do not contain the uri of the procedure:
        received_message = RPCRegisteredMessage(*self.message.value)
        allow, msg = customize.authorize_registration(received_message.topic, self.connection)
        if allow:
            registration_id = topics.add_rpc(received_message.topic, self.connection)
            answer = RPCRegisteredMessage(
                request_id=received_message.request_id,
                registration_id=registration_id
            )
            #self.broadcast_messages = customize.get_subscribe_broadcast_messages(received_message, registration_id, self.connection.id)
        else:
            answer = ErrorMessage(
                request_id=received_message.request_id,
                request_code=received_message.code,
                uri="tornwamp.register.unauthorized"
            )
            answer.error(msg)
        self.answer_message = answer


class CallProcessor(Processor):
    """
    Responsible for dealing with CALL messages.
    """
    def process(self):
        """
        Call method defined in tornwamp.customize.procedures (dict).

        Each method should return:
        - RESPONSE
        - ERROR

        Which will be the processor's answer message.'
        """
        msg = CallMessage(*self.message.value)
        method_name = msg.procedure
        if method_name in customize.procedures:
            method = customize.procedures[method_name]
            answer = method(*msg.args, call_message=msg, connection=self.connection, **msg.kwargs)
        else:
            error_uri = "wamp.rpc.unsupported.procedure"
            error_msg = "The procedure {} doesn't exist".format(method_name)
            response_msg = ErrorMessage(
                request_code=msg.code,
                request_id=msg.request_id,
                details={"call": msg.json},
                uri=error_uri
            )
            response_msg.error(error_msg)
            answer = response_msg
        self.answer_message = answer
