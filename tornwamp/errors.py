"""
This module manages and holds reserved the URIs for error messages and other pre-defined WAMP URIs.
It should always be used by the broker for all URIs used to issue errors, because that allows it to check the spelling of the URI.

https://wamp-proto.org/_static/gen/wamp_latest.html#predefined-uris
"""
from tornwamp.uri.manager import uri_registry

# The first two of these aren't technically errors, but just messages used in closing a connection.  But close enough.
CloseRealm = uri_registry.create_error('wamp.close.close_realm')
GoodByeAndOut = uri_registry.create_error('wamp.close.goodbye_and_out')

InvalidURI = uri_registry.create_error('wamp.error.invalid_uri')
NoSuchProcedure = uri_registry.create_error('wamp.error.no_such_procedure')
ProcedureAlreadyExists = uri_registry.create_error('wamp.error.procedure_already_exists')
NoSuchRegistration = uri_registry.create_error('wamp.error.no_such_registration')
NoSuchSubscript = uri_registry.create_error('wamp.error.no_such_subscription')
InvalidArgument = uri_registry.create_error('wamp.error.invalid_argument')
SystemShutdown = uri_registry.create_error('wamp.close.system_shutdown')
ProtocolViolation = uri_registry.create_error('wamp.error.protocol_violation')
NotAuthorized = uri_registry.create_error('wamp.error.not_authorized')
AuthorizationFailed = uri_registry.create_error('wamp.error.authorization_failed')
NoSuchRealm = uri_registry.create_error('wamp.error.no_such_realm')
NoSuchRole = uri_registry.create_error('wamp.error.no_such_role')
Cancelled = uri_registry.create_error('wamp.error.canceled')
OptionNotAllowed = uri_registry.create_error('wamp.error.option_not_allowed')
NoEligibleCallee = uri_registry.create_error('wamp.error.no_eligible_callee')
OptionDisallowed__DiscloseMe = uri_registry.create_error('wamp.error.option_disallowed.disclose_me')
NetworkFailure = uri_registry.create_error('wamp.error.network_failure')


