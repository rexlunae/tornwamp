"""
A module to regularize the errors that WAMP can issue.
"""

from enum import Enum

from tornwamp.uri import URI, URIType

class Error(URI):
    """
    An Error is a type of URI that cannot be invoked, subscribed to, or published to.  However, they are also completely stateless,
    kept distinct from other URIs by convention, and cannot reasonably be registered ahead of time in the URIManager because no list
    of them could every be considered complete.  Therefore, the only registered Errors are going to be those defined by the standard
    and held by the broker, to prevent anything else from being registered on them.

    https://wamp-proto.org/_static/gen/wamp_latest.html#predefined-uris
    """

    def __init__(self, name):
        super().__init__(name, URIType.ERROR)

    # Errors don't have connections, so this is always empty.  Provided to for compatibility with Topics and Procedures.
    connections = {}

    def _disconnect_publisher(self):
        """
        Compatibility-only.
        """
        pass

    def __str__(self):
        """
        Allows the error to serialize to a string.
        """
        return self.name

