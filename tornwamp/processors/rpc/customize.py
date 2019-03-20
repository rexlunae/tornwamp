"""
This module allows customization of which methods are supported when using
RPC.

The key of the procedures dict is the name of the procedure as received
when CALL is invoked. Each procedure should return a ResultMessage and a
list of BroadcastMessages. The former is returned to the caller of the
procedure, the later describes the notification message to be
broadcasted to the other active connections (further restrictions to the
broadcasted message can be added in the delivery methods).
"""
from warnings import warn

from tornwamp.messages import ResultMessage, InvocationMessage, ErrorMessage, Code
from tornwamp.topic import topics
from datetime import datetime

def authorize_registration(topic_name, connection):
    """
    Says if a user can register and RPC on a topic or not.
    Return: True or False and the error message ("" if no error occured).
    """
    assert topic_name, "authorize_registration requires topic_name"
    assert connection, "authorize_registration requires connection"

    if topic_name in procedures:
        return False, "Procedure {} already defined".format(topic_name)

    return True, ""

# Tracks open requests.  Contains a tuple of (connection, )
request_ids = {}

def invoke(call_message, connection, args, kwargs, *_trailing):
    """
    Places an RPC with the connection that registered it.  Once the result is
    sent to us, we will send it back to the caller, but the only time we can directly
    respond synchronously is if there is an error.
    """
    topic = topics.get(call_message.procedure)

    # Check that the procedure called has been registered.
    if topic is None:
        return ErrorMessage(request_code=Code.CALL, request_id=call_message.request_id, uri='wamp.uri.rpc.notfound')
    else:
        # Create INVOCATION message to the client that registered the RPC.
        invoke_msg = InvocationMessage(registration_id=topic.registration_id, details=call_message.details, args=args, kwargs=kwargs)

        # Keep track of the connection that wants the response.
        request_ids[invoke_msg.request_id] = (connection, datetime.utcnow())

        # Send the invocation message.
        topic.invoke(invoke_msg)

        # Don't return anything to teh caller...for now.
        return None




def ping(call_message, connection, *_trailing):
    """
    Return a answer (ResultMessage) and empty list direct_messages.
    """
    assert connection, "ping requires connection"

    answer = ResultMessage(
        request_id=call_message.request_id,
        details=call_message.details,
        args=["Ping response"]
    )
    return answer

procedures = {
    # 'uri': [function, provider_connection, args, kwargs]
    # args and kwargs will be merged with arguments recieved in the request.
    'ping': [ping, [], {}],
    'invoke': [invoke, ['foo'], {'bar':'baz'}]
}
