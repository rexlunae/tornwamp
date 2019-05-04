"""
Controls which WAMP features are enabled or disabled.
"""

from uuid import uuid5, NAMESPACE_OID
from copy import deepcopy

class Options(dict):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __getattr__(self, name):
        return self[name]

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        if name in self:
            del self[name]
        else:
            raise AttributeError("No such attribute: " + name)


    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.items():
            setattr(result, k, deepcopy(v, memo))
        return result

    


# Supported client features.
#client_features = Options(
#    roles=Options(
#        caller=Options(
#            features=Options(
#                caller_identification=True,
#                call_canceling=True,
#                progressive_call_results=True,
#            )
#        ),
#        callee=Options(
#            features=Options(
#                caller_identification=True,
#                pattern_based_registration=True,
#                shared_registration=True,
#                progressive_call_results=True,
#                registration_revocation=True,
#            )
#        ),
#        publisher=Options(
#            features=Options(
#                publisher_identification=True,
#                subscriber_blackwhite_listing=True,
#                publisher_exclusion=True,
#            )
#        ),
#        subscriber=Options(
#            features=Options(
#                publisher_identification=True,
#                pattern_based_subscription=True,
#                subscription_revocation=True
#            )
#        )
#    )
#)


# Supported server features.
server_features = Options(
    # This is a unique id representing the identity of this library.  To give your implementation or application a unique identity, overload it.
    # It can be any string, so the format need not be adhered to.
    authid=str(uuid5(NAMESPACE_OID, 'wampnado')),

    authrole='anonymous',
    authmethod='anonymous',
    roles=Options(
        broker=Options(
            features=Options(
                #publisher_identification=True,
                #publisher_exclusion=True,
                #subscriber_blackwhite_listing=True,
            )
        ),
        dealer=Options(
            features=Options(
                progressive_call_results=True,
                caller_identification=True
            )
        )
    ),
)