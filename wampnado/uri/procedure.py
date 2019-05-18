"""
Classes and methods for Procedure URIs for RPCs. 
"""
from datetime import datetime
from warnings import warn
from inspect import iscoroutinefunction, isfunction
from asyncio import create_task, get_event_loop

from wampnado.uri import URI, URIType
from wampnado.uri.error import WAMPSimpleException
from wampnado.features import Options
from wampnado.messages import Code, ResultMessage, InterruptMessage, InvocationMessage, ResultMessage

class Procedure(URI):
    """
    A RPC URI.
    """

    # This is a dictionary of the *class*, not the instance, therefore there is a single dictionary that can be used to look up any request.
    # This is necessary because request responses are done by id.
    pending = {}

    def __init__(self, name, provider):
        """
        provider is one of three things:
        1.  Some subclass of Handler.  In this case, we're dealing with a normal procedure that we invoke with an INVOCATION message to the registering client.
        2.  A regular function, in which case it is called and the result returned immediately.
        """
        super().__init__(name, URIType.PROCEDURE)

        if isfunction(provider):
            self.pseudo = True
            self.callback = provider
        else:
            self.pseudo = False
            self.provider = provider

    def write_message(self, msg):
        """
        Send a  message to the provider.
        """
        return self.provider.write_message(msg)


    def invoke(self, invoking_handler, request_id, *args, options=Options(), **kwargs):
        """
        Send an invokation message to the provider, or for pseudo-rpcs, just runs it directly and returns the result.
        Options:
        receive_progress (bool): Set to true to allow progressive yields.  Otherwise, the first yield will end the request.
        """
        try:
            if self.pseudo:
                result = self.callback(*args, **kwargs)
                return ResultMessage(request_id=request_id, details={}, args=result)
            else:
                type(self).pending[request_id] = (invoking_handler, datetime.utcnow(), options)
                return self.write_message(InvocationMessage(request_id=request_id, registration_id=self.registration_id, args=args, kwargs=kwargs, details=options))
        # Convert a simple exception into a full one.
        except WAMPSimpleException as e:
            raise e.to_exception(Code.CALL, request_id)
        except Exception as e:
            raise invoking_handler.realm.errors.general_error.to_exception(Code.CALL, request_id, e)

    def cancel(self, request_id):
        """
        Removes a pending request without fulfilling it.
        """
        self.provider.write_message(InterruptMessage(request_id=request_id))
        type(self).pending.pop(request_id)

    def disconnect(self, handler):
        """
        Removes a given handler from any role in the uri.
        """
        if hasattr(self, 'provider') and self.provider is not None and self.provider.sessionid == handler.sessionid:
            self.provider = None

    @property
    def live(self):
        return (hasattr(self, 'provider') and self.provider is not None) or self.pseudo

    @classmethod
    def yield_result(cls, yielding_handler, yield_msg):
        """
        Send a RESULT message when a YIELD message is received.
        Options:
        progress (bool): A progressive response.  The request will be kept open, and the *details* send to back in the response will have the progress flag set.
        """
        if yield_msg.request_id in cls.pending:
            (invoking_handler, request_time, call_options) = cls.pending[yield_msg.request_id]
            invoking_handler.write_message(ResultMessage(request_id=yield_msg.request_id, details=yield_msg.options, args=yield_msg.args, kwargs=yield_msg.kwargs))
            if not yield_msg.options.progress or not call_options.receive_progress:
                cls.pending.pop(yield_msg.request_id)
        else:
            # If the client is gone, tell the yielding client to stop sending results.
            if yield_msg.options.progress:
                yielding_handler.write_message(InterruptMessage(request_id=yield_msg.request_id, options=Options(mode='killnowait')))
            warn('request_id {} not pending'.format(yield_msg.request_id))
