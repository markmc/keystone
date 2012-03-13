# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 OpenStack, LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Rules-based Policy Engine."""

from keystone import config
from keystone import exception
from keystone import policy
from keystone.common import logging
from keystone.common import policy as common_policy
from keystone.common import utils
from keystone.openstack.common import cfg


LOG = logging.getLogger('keystone.policy.backends.rules')

_POLICY_CACHE = None


def reset_policy_cache():
    global _POLICY_CACHE
    if not _POLICY_CACHE:
        _POLICY_CACHE = PolicyCache()
    else:
        _POLICY_CACHE.reset()


def load_policy(policy_file, reload_func=None):
    global _POLICY_CACHE
    _POLICY_CACHE.load(policy_file, reload_func)


class PolicyCache(object):

    def __init__(self):
        self.reset()

    def reset(self):
        self._policy_path = None
        self._cache = {}

    def load(self, policy_file, reload_func=None):
        if not self._policy_path:
            self._policy_path = utils.find_config(policy_file)
        utils.read_cached_file(self._policy_path,
                               self._cache,
                               reload_func=reload_func)


class Policy(policy.Driver):

    policy_opts = [
        cfg.StrOpt('policy_file',
                   default='policy.json',
                   help=_('JSON file representing policy')),
        cfg.StrOpt('policy_default_rule',
                   default='default',
                   help=_('Rule checked when requested rule is not found')),
        ]

    def __init__(self, conf):
        super(Policy, self).__init__(conf)
        self.conf.register_opts(self.policy_opts)
        self.reset()

    def reset(self):
        reset_policy_cache()
        common_policy.reset()

    def _set_brain(self, data):
        default_rule = self.conf.policy_default_rule
        common_policy.set_brain(
            common_policy.HttpBrain.load_json(data, default_rule))

    def enforce(self, credentials, action, target):
        """Verifies that the action is valid on the target in this context.

           :param credentials: user credentials
           :param action: string representing the action to be checked
               this should be colon separated for clarity.
               i.e. compute:create_instance
                    compute:attach_volume
                    volume:attach_volume

           :param object: dictionary representing the object of the action
               for object creation this should be a dictionary representing the
               location of the object e.g. {'tenant_id': object.tenant_id}

           :raises: `exception.Forbidden` if verification fails.

        """
        LOG.debug('enforce %s: %s', action, credentials)

        load_policy(self.conf.policy_file, reload_func=self._set_brain)

        match_list = ('rule:%s' % action,)

        try:
            common_policy.enforce(match_list, target, credentials)
        except common_policy.NotAuthorized:
            raise exception.Forbidden(action=action)
