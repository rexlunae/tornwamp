"""
The authentication and authorization functions.
"""
from copy import deepcopy

from wampnado.features import Options

class Roles(Options):
    """
    A class for tracking whether the permissions that exist.
    """

    def register(self, role, blacklist=[], whitelist=[], default=True):
        """
        Register's a role as being available for permissions checks.
        """
        self[role] = Options(blacklist=blacklist, whitelist=whitelist, default=True)

    def blacklist(self, role, handler):
        perm_tables = self.get(role)

        # If the role isn't defined, that's an application error, rather than a WAMP error.
        if perm_tables is None:
            raise NotImplementedError('No such role defined {}'.format(role))

        if handler not in perm_tables.blacklist:
            perm_tables.blacklist.append(handler)

    def whitelist(self, role, handler):
        perm_tables = self.get(role)

        # If the role isn't defined, that's an application error, rather than a WAMP error.
        if perm_tables is None:
            raise NotImplementedError('No such role defined {}'.format(role))

        if handler not in perm_tables.whitelist:
            perm_tables.whitelist.append(handler)

    def authorize(self, role, handler, request_id, request_code, *args, noraise=False, **kwargs):
        """
        Checks the permissions of the handler to the given role.  If approved, returns True.  If not approved, it will raise
        a WAMPError exception...unless noraise is True, in which case it will return false.
        """
        perm_tables = self.get(role)
        authid = handler.authid
        authrole = handler.authrole
        sessionid = handler.sessionid
        if perm_tables is not None:
            if authid in perm_tables.whitelist \
              or authrole in perm_tables.whitelist \
              or sessionid in perm_tables.whitelist \
              or (authid is None and perm_tables.default) \
              or (authrole is None and perm_tables.default) \
              or (sessionid is None and perm_tables.default) \
              or (authid not in perm_tables.blacklist) \
              or (authrole not in perm_tables.blacklist) \
              or (sessionid not in perm_tables.blacklist):
                return True

        if not noraise:
            raise handler.realm.errors.not_authorized.to_exception(request_id=request_id, request_code=request_code, args=args, kwargs=kwargs)
        return False

    def copy(self):
        return deepcopy(self)

# This should be copied to each realm when it's created.
default_roles = Roles()
