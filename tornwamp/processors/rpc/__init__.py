"""
RPC processors.

Compatible with WAMP Document Revision: RC3, 2014/08/25, available at:
https://github.com/tavendo/WAMP/blob/master/spec/basic.md
"""

import asyncio
from warnings import warn

from tornado import gen

from tornwamp.uri.manager import uri_registry
from tornwamp.messages import CallMessage, RPCRegisterMessage, RPCRegisteredMessage, ResultMessage, ErrorMessage, EventMessage, YieldMessage
from tornwamp.processors import Processor
from tornwamp.processors.rpc import customize
from tornwamp.messages import Code

class YieldProcessor(Processor):
    """
    Responsible for dealing YIELD messages.
    """
    def process(self):
        """
        Sends the final value of the RPC to the original caller.
        """
        yield_message = YieldMessage(*self.message.value)
        (destination_connection, date) = customize.request_ids.pop(yield_message.request_id, None)

        if destination_connection is None:
            return ErrorMessage(request_code=Code.YIELD, request_id=yield_message.request_id, uri='wamp.not.pending')
        elif destination_connection.zombie:
            warn('Lost connection before response' + str(yield_message.value))
        else:
            result_message = ResultMessage(request_id=yield_message.request_id, details=yield_message.details, args=yield_message.args, kwargs=yield_message.kwargs)
            destination_connection.write_message(result_message)

            # There is no return message from a yield.
            return None
    

class RegisterProcessor(Processor):
    """
    Responsible for dealing REGISTER messages.
    """
    def process(self):
        """
        Return REGISTERED message based on the input REGISTER message.
        """

        # We reprocess the message into a full RPCRegisterMessage to get all the methods and properties.
        full_message = RPCRegisterMessage(*self.message.value)
        allow, msg = customize.authorize_registration(full_message.topic, self.connection)
        
        # By default we send an error back.
        answer = ErrorMessage(
            request_id=full_message.request_id,
            request_code=full_message.code,
            uri="tornwamp.register.unauthorized"
        )
        answer.error(msg)

        if allow:
            registration_id = uri_registry.create_rpc(full_message.topic, self.connection, invoke=customize.invoke)
            answer = RPCRegisteredMessage(
                request_id=full_message.request_id,
                registration_id=registration_id,
            )
        self.answer_message = answer


class CallProcessor(Processor):
    """
    Responsible for dealing with CALL messages.
    """
    def process(self):
        """
        Call an RPC, either defined in tornwamp.customize.procedures (dict), or a remote call to another client.

        Each method should return:
        - RESULT
        - ERROR

        However, if the dealer cannot handle the call locally, the RESULT will be issued separately, and no message will issue from this routine.  This is the normal case.

        Which will be the processor's answer message.'
        """
        msg = CallMessage(*self.message.value)
        if msg.procedure in customize.procedures:
            [method, args, kwargs] = customize.procedures[msg.procedure]
            self.answer_message = method(msg, self.connection, [*msg.args, *args], { **msg.kwargs, **kwargs })
        else:
            response_msg = ErrorMessage(
                request_code=msg.code,
                request_id=msg.request_id,
                details={"call": msg.json},
                uri="wamp.rpc.unsupported.procedure"
            )
            response_msg.error("The procedure {} doesn't exist".format(msg.procedure))
            self.answer_message = response_msg
