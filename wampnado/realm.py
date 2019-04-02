"""
Realm management.
"""
from wampnado.uri.manager import URIManager
from wampnado.identifier import create_global_id


class ErrorStruct:
    def __init__(self, **entries):
        self.__dict__.update(entries)

realms = {}


class WAMPRealm(dict):
    """
    Represents a realm in WAMP parlance.  Connections within a realm can see and communicate with each other, those outside it cannot.
    """
    def __init__(self, name):
        self.name = name
        self.handlers = {}

        self.uri_registry = URIManager()

        self.errors = ErrorStruct(**{
            # The first two of these aren't technically errors, but just messages used in closing a connection.  But close enough.
            'close_realm': self.uri_registry.create_error('wamp.close.close_realm'),
            'goodbye_and_out': self.uri_registry.create_error('wamp.close.goodbye_and_out'),

            # These are the errors that are required and standardized by WAMP Protocol standard
            'invalid_uri': self.uri_registry.create_error('wamp.error.invalid_uri'),
            'no_such_procedure': self.uri_registry.create_error('wamp.error.no_such_procedure'),
            'procedure_already_exists': self.uri_registry.create_error('wamp.error.procedure_already_exists'),
            'no_such_registration': self.uri_registry.create_error('wamp.error.no_such_registration'),
            'no_such_subscript': self.uri_registry.create_error('wamp.error.no_such_subscription'),
            'invalid_argument': self.uri_registry.create_error('wamp.error.invalid_argument'),
            'system_shutdown': self.uri_registry.create_error('wamp.close.system_shutdown'),
            'protocol_violation': self.uri_registry.create_error('wamp.error.protocol_violation'),
            'not_authorized': self.uri_registry.create_error('wamp.error.not_authorized'),
            'authorization_failed': self.uri_registry.create_error('wamp.error.authorization_failed'),
            'no_such_realm': self.uri_registry.create_error('wamp.error.no_such_realm'),
            'no_such_role': self.uri_registry.create_error('wamp.error.no_such_role'),
            'cancelled': self.uri_registry.create_error('wamp.error.canceled'),
            'option_not_allowed': self.uri_registry.create_error('wamp.error.option_not_allowed'),
            'no_eligible_callee': self.uri_registry.create_error('wamp.error.no_eligible_callee'),
            'option_disallowed__disclose_me': self.uri_registry.create_error('wamp.error.option_disallowed.disclose_me'),
            'network_failure': self.uri_registry.create_error('wamp.error.network_failure'),

            # These aren't part of the WAMP standard, but I use them, so here they are.
            'not_pending': self.uri_registry.create_error('wamp.error.not_pending'),    # Sent if we get a YIELD message but there is no call pending.
            'unsupported': self.uri_registry.create_error('wamp.error.unsupported'),    # Sent when we get a message that we don't recognize.

        })

    def register_handler(self, handler):
        """
        Add the handler to the realm.
        """
        id = create_global_id()
        self.handlers[id] = handler
        return id

    def deregister_handler(self, id):
        """
        Remove the handler from the realm.  If the handler is the only one in the realm, the realm itself will be cleaned up.
        """
        del self.handlers[id]
        if len(self.handlers) == 0:
            del realms[self.name]

