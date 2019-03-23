"""
Classes and methods for Procedure URIs for RPCs. 
"""

from tornwamp.uri import URI, URIType

class Procedure(URI):
    """
    An RPC URI.
    """

    def __init__(self, name, provider):
        super().__init__(name, URIType.PROCEDURE)
        self.provider = provider

    @property
    def connections(self):
        """
        Returns the provider.  There is always exactly one.
        """
        return {self.registration_id: self.provider}

    def invoke(self, msg):
        """
        Send an INVOCATION message to the provider.
        """
        request_id = msg.request_id         # Read the message id from the message.  We just trust that this has been generated correctly.

        self.provider.write_message(msg)

    def _disconnect_publisher(self):
        """
        Disconnect periodically in order not to have several unused connections
        of old topics.
        """
        if self._publisher_connection is not None:
            self._publisher_connection.disconnect()


