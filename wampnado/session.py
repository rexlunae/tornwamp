"""
Abstract websocket connections (dual channel between clients and server).
"""

from wampnado.identifier import create_global_id


class SessionTable(dict):
    """
    Connections manager.
    """

    @property
    def dict(self):
        """
        Return a python dictionary which could be jsonified.
        """
        return {key: value.dict for key, value in self.items()}

    @property
    def count(self):
        return [len(self.keys())]

    @property
    def list(self):
        return list(self.keys())

    def register(self, handler):
        self[handler.sessionid] = handler
        return handler.sessionid

    def deregister(self, sessionid):
        if sessionid in self:
            return self.pop(sessionid)


