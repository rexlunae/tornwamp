from wampnado import processors
from wampnado.uri import URIType
from wampnado.uri.topic import Topic
from wampnado.uri.procedure import Procedure
from wampnado.uri.error import Error
from wampnado.identifier import create_global_id
from wampnado.features import Options
from re import compile

# A lot of these calls need the message passed in so that they can raise exceptions, but there really isn't a message in the case of internal use, so we fake it.
fake_message = Options(request_id=None, code=None)

class URIManager:
    """
    Manages all existing uris to which handlers can potentially
    publish, subscribe, or call to.
    """
    def __init__(self):
        # A table of the registrations issued to URIs under this realm.
        self.registrations = {}

        # A table of the URIs.
        self.uris = {}

        self.uri_pattern = compile(r"^([0-9a-z_]+\.)*([0-9a-z_]+)$")

        # Reserve all the standard errors.
        self.errors = Options(
            # The first two of these aren't technically errors, but just messages used in closing a connection.  But close enough.
            close_realm=self.create_error('wamp.close.close_realm')[0],
            goodbye_and_out=self.create_error('wamp.close.goodbye_and_out')[0],

            # These are the errors that are required and standardized by WAMP Protocol standard
            invalid_uri=self.create_error('wamp.error.invalid_uri')[0],
            no_such_procedure=self.create_error('wamp.error.no_such_procedure')[0],
            procedure_already_exists=self.create_error('wamp.error.procedure_already_exists')[0],
            no_such_registration=self.create_error('wamp.error.no_such_registration')[0],
            no_such_subscription=self.create_error('wamp.error.no_such_subscription')[0],
            invalid_argument=self.create_error('wamp.error.invalid_argument')[0],
            system_shutdown=self.create_error('wamp.close.system_shutdown')[0],
            protocol_violation=self.create_error('wamp.error.protocol_violation')[0],
            not_authorized=self.create_error('wamp.error.not_authorized')[0],
            authorization_failed=self.create_error('wamp.error.authorization_failed')[0],
            no_such_realm=self.create_error('wamp.error.no_such_realm')[0],
            no_such_role=self.create_error('wamp.error.no_such_role')[0],
            cancelled=self.create_error('wamp.error.canceled')[0],
            option_not_allowed=self.create_error('wamp.error.option_not_allowed')[0],
            no_eligible_callee=self.create_error('wamp.error.no_eligible_callee')[0],
            option_disallowed__disclose_me=self.create_error('wamp.error.option_disallowed.disclose_me')[0],
            network_failure=self.create_error('wamp.error.network_failure')[0],

            # These aren't part of the WAMP standard, but I use them, so here they are.
            not_pending=self.create_error('wamp.error.not_pending')[0],    # Sent if we get a YIELD message but there is no call pending.
            unsupported=self.create_error('wamp.error.unsupported')[0],    # Sent when we get a message that we don't recognize.
            general_error=self.create_error('wamp.error.general_error')[0],    # Sent when we get a message that we don't recognize.
        )


    def get(self, uri_name, msg=fake_message):
        """
        Looks up and returns the specified uri object by name.  If it is not found, it will raise the appropriate exception, unless noraise is true.
        """
        if not self.uri_pattern.match(uri_name):
            raise self.errors.invalid_uri.to_exception(request_id=msg.request_id, request_code=msg.code, details=Options(uri=uri_name))

        return  self.uris.get(uri_name)

    def create(self, name, uri_obj, returnifexists=True, msg=fake_message):
        """
        Adds a new uri agnostic of type.  Usually, this should be called by other methods inside this object.
        """
        uri = self.get(name, msg=msg)

        # Only add if it doesn't exist.
        if uri is None:
            self.uris[name] = uri_obj
            registration_id = self.uris[name].registration_id
            self.registrations[registration_id] = name
            return self.uris[name], registration_id
        elif returnifexists:
            return uri, uri.registration_id
        else:
            return None


    def create_topic(self, name, msg=fake_message):
        """
        Creates a uri that can be subscribed and published to.
        """
        args = self.create(name, Topic(name))

        if args[0].uri_type != URIType.TOPIC:
            raise self.errors.no_such_subscription.to_exception(msg.code, msg.request_id)

        return args


    def create_error(self, name):
        """
        Adds an entry for an error URI.
        """
        args = self.create(name, Error(name))

        return args

    def create_procedure(self, name, provider_handler, msg=fake_message):
        """
        Add a new procedure provided by the provider_handler.  request_msg should generally be specified whenever the user.
        """
        args = self.create(name, Procedure(name, provider_handler), returnifexists=False)
        if args is None:
            raise self.errors.procedure_already_exists.to_exception(msg.code, msg.request_id)

        return args


    def remove(self, registration_id):
        """
        Removes a given registration, regardless of type.
        """
        name = self.registrations.pop(registration_id, False)
        if name:
            for registration_id, registration_uri in self.registrations:
                if name == registration_uri:
                    self.registrations.pop(name)
            return self.uris.pop(name)


    def add_subscriber(self, uri_name, handler, msg=fake_message):
        """
        Add a handler as a uri's subscriber.  
        """
        (uri, _) = self.create_topic(uri_name, msg=msg)
        subscription_id = self.uris[uri.name].add_subscriber(handler)
        return subscription_id

    def remove_subscriber(self, uri, handler):
        """
        Remove a connection a uri's subscriber provided:
        - uri
        - handler
        """
        uri = self.uris.get(uri)
        uri.remove_subscriber(handler)

        # If there are no publishers and no subscribers, delete it.
        if len(uri.subscriptions.keys) == 0 and len(uri.publishers.keys) == 0:
            self.remove(uri)

    def disconnect(self, handler, notify=False):
        """
        Removes a handler from the manager, effectively disconnecting it from the realm.  Can be called upon the closure of the
        transport as part of its cleanup, or by an authorized client to kick the other client.
        """
        for name in list(self.uris.keys()):
            self.uris[name].disconnect(handler)
            if not self.uris[name].live:
                del self.uris[name]
        if notify:
            pass    # XXX Send the final message.



