"""
RPC processors.

Compatible with WAMP Document Revision: RC3, 2014/08/25, available at:
https://github.com/tavendo/WAMP/blob/master/spec/basic.md
"""

import asyncio
from warnings import warn

from tornado import gen

from wampnado.messages import CallMessage, RPCRegisterMessage, RPCRegisteredMessage, ResultMessage, ErrorMessage, EventMessage, YieldMessage, InvocationMessage
from wampnado.processors import Processor
from wampnado.messages import Code
from wampnado.uri.procedure import Procedure
from wampnado.uri.error import WAMPSimpleException
from wampnado.auth import default_roles

default_roles.register('call')
default_roles.register('register')
default_roles.register('yield')


class YieldProcessor(Processor):
    """
    Responsible for dealing YIELD messages.
    """
    def process(self):
        """
        Sends the final value of the RPC to the original caller.  One of two things may issue:
        1.  An ERROR message back to the yield'ing client.  If this happens, an exception will be raised, and there is therefore no return.
        2.  A RESULT message to the original calling client.  Since this does not return anything to the yield'ing client, we return None.
        """
        yield_message = YieldMessage(*self.message.value)

        self.handler.realm.roles.authorize('yield', self.handler, yield_message.code, yield_message.request_id)

        Procedure.yield_result(self.handler, yield_message)

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
        received_message = RPCRegisterMessage(*self.message.value)

        self.handler.realm.roles.authorize('register', self.handler, received_message.code, received_message.request_id)

        (_, registration_id) = self.handler.realm.create_procedure(received_message.uri, self.handler, received_message)
        return RPCRegisteredMessage(
            request_id=received_message.request_id,
            registration_id=registration_id,
        )

class RegisteredProcessor(Processor):
    """
    Responsible for dealing SUBSCRIBED messages.
    """
    def process(self):
        """
        Return SUBSCRIBE message based on the input HELLO message.
        """
        received_message = RPCRegisteredMessage(*self.message.value)
        self.handler.add_rpc(received_message.request_id, received_message.registration_id)
        return None



class CallProcessor(Processor):
    """
    Responsible for dealing with CALL messages.
    """
    def process(self):
        """
        Invokes a procedure.  It can be either a true RPC, fulfilled by a remote client via the
        CALL->INVOCATION->YIELD->RESULT pathway or by either a pseudo-rpc fulfulled. Both pseudo-
        rpcs and errors can be fulfilled by returning the result, but a true RPC just registers
        the invocation as pending and returns nothing.
        """
        msg = CallMessage(*self.message.value)


        try:
            self.handler.realm.roles.authorize('call', self.handler)

            uri = self.handler.realm.get(msg.procedure)
            return uri.invoke(self.handler, msg.request_id, *msg.args, **msg.kwargs)

        except WAMPSimpleException as e:
            raise e.to_exception(msg.code, msg.request_id)


class InvokeProcessor(Processor):
    """
    Handles pubsub events
    """
    def process(self):
        """
        Runs the callback.  YIELDs on success.
        """
        msg = InvocationMessage(*self.message.value)
        try:
            ret_args = self.handler.event(msg)
            return YieldMessage(*ret_args, request_id=msg.request_id)

        except WAMPSimpleException as e:
            raise e.to_exception(msg.code, msg.request_id)

