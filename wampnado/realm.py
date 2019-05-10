"""
Realm management.
"""
from wampnado.uri.manager import URIManager
from wampnado.identifier import create_global_id
from wampnado.features import Options
from wampnado.session import SessionTable
from wampnado.auth import default_roles

realms = {}


class Realm(URIManager):
    """
    Represents a realm in WAMP parlance.  Connections within a realm can see and communicate with each other, those outside it cannot.
    A Realm is basically a URIManager with session information added in.
    """
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.sessions = SessionTable()

        self.roles = default_roles.copy()

        # This is a bunch of functions implementing the pseudo-RPCs for session management.
        def count_func():
            return self.sessions.count 
        def list_func():
            return self.sessions.list

        self.rpcs = Options(
            wamp_session_count=self.create_procedure('wamp.session.count', count_func)[0],
            wamp_session_list=self.create_procedure('wamp.session.list', list_func)[0],
        )

    def register_handler(self, handler):
        """
        Add the handler to the realm.
        """
        return self.sessions.register(handler)

    def deregister_handler(self, id):
        """
        Remove the handler from the realm.  If the handler is the only one in the realm, the realm itself will be cleaned up.
        """
        self.sessions.deregister(id)
        if self.sessions.count == 0:
            del realms[self.name]


def get_realm(name):
    """
    If the realm exists, return it.  If it does not exist, create it, then return it.
    """
    if not name in realms:
        realms[name] = Realm(name)

    return realms[name]

