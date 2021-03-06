"""
A module to regularize the errors that WAMP can issue.
"""

from wampnado.uri import URI, URIType
from wampnado.messages import ErrorMessage


class WAMPException(Exception):
    """
    An exception class that can be raised to generate a WAMP error message up the call stack.
    """
    def __init__(self, error_uri, request_code, request_id, *args, **kwargs):
        self.error_uri = error_uri
        self.request_code = request_code
        self.request_id = request_id
        self.args = args
        self.kwargs = kwargs
        super().__init__()

    def __str__(self):
        return str(self.message())

    def message(self):
        """
        What should be displayed if the exception is not caught and sent as an error message to the client.
        """
        return self.error_uri.message(self.request_code, self.request_id, *self.args, **self.kwargs)

class WAMPSimpleException(Exception):
    """
    Some exceptions may be raised in a context where there's no natural reason to
    have all of the information needed to raise a WAMPException.  This exception can be raised in those contexts,
    so that it can be caught and converted into a full WAMPException further up the call stack.

    Generally, this is the type of exception that should be used by external modules.
    """
    def __init__(self, error_uri, reason, *args, **kwargs):
        self.error_uri = error_uri
        self.reason = reason
        self.args = args
        self.kwargs = kwargs

    def to_exception(self, request_code, request_id):
        return WAMPException(self.error_uri, request_code, request_id, *self.args, reason=self.reason, **self.kwargs)

class Error(URI):
    """
    An Error is a type of URI that cannot be invoked, subscribed to, or published to.  However, they are also completely stateless,
    kept distinct from other URIs by convention, and cannot reasonably be registered ahead of time in the URIManager because no list
    of them could every be considered complete.  Therefore, the only registered Errors are going to be those defined by the standard
    and held by the broker, to prevent anything else from being registered on them.

    https://wamp-proto.org/_static/gen/wamp_latest.html#predefined-uris

    Our errors are also Exceptions, which means that they can be raised directly.
    """

    def __init__(self, name):
        super().__init__(name, URIType.ERROR)

    # Errors don't have connections, so this is always empty.  Provided to for compatibility with Topics and Procedures.
    connections = {}

    def disconnect(self, handler):
        """
        Errors don't have handlers, so we don't really need to do anything.  We just need to have something to avoid an error.
        """
    @property
    def live(self):
        return True

    def message(self, request_code, request_id, *args, details={}, **kwargs):
        return ErrorMessage(uri=self.name, request_code=request_code, request_id=request_id, details=details, args=args, kwargs=kwargs)

    def to_exception(self, request_code, request_id, *args, **kwargs):
        """
        Returns an exception appropriate for raising.  That can be directly converted into an ERROR message.
        """
        return WAMPException(self, request_code, request_id, *args, **kwargs)

    def to_simple_exception(self, reason, *args, **kwargs):
        """
        Returns an exception that can be raised but does not contain all the information to generate an ERROR message.
        Must be converted up the call stack into an exception.
        """
        return WAMPSimpleException(self, reason, *args, **kwargs)
    

    def raise_to(self, handler, request_code, request_id, *args, **kwargs):
        """
        Raises the error and sends it to the given handler.  This is used when some activity is initiated by one handler, and sent to another.
        """
        handler.write_message(self.message(request_code, request_id, *args, **kwargs))
