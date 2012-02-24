# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Main entry point into the Token service."""

import datetime

from keystone import config
from keystone.common import manager
from keystone.openstack.common import cfg


class Manager(manager.Manager):
    """Default pivot point for the Token backend.

    See :mod:`keystone.common.manager.Manager` for more details on how this
    dynamically calls the backend.

    """

    opt_group = cfg.OptGroup('token')
    driver_opt = cfg.StrOpt('driver',
                            default='keystone.token.backends.kvs.Token')

    def __init__(self, conf):
        super(Manager, self).__init__(conf, self.opt_group, self.driver_opt)


class Driver(object):
    """Interface description for a Token driver."""

    expiration_opt = cfg.IntOpt('expiration', default=86400)

    def get_token(self, token_id):
        """Get a token by id.

        :param token_id: identity of the token
        :type token_id: string
        :returns: token_ref
        :raises: keystone.exception.TokenNotFound

        """
        raise NotImplementedError()

    def create_token(self, token_id, data):
        """Create a token by id and data.

        :param token_id: identity of the token
        :type token_id: string
        :param data: dictionary with additional reference information

        ::

            {
                expires=''
                id=token_id,
                user=user_ref,
                tenant=tenant_ref,
                metadata=metadata_ref
            }

        :type data: dict
        :returns: token_ref or None.

        """
        raise NotImplementedError()

    def delete_token(self, token_id):
        """Deletes a token by id.

        :param token_id: identity of the token
        :type token_id: string
        :returns: None.
        :raises: keystone.exception.TokenNotFound

        """
        raise NotImplementedError()

    def _get_default_expire_time(self):
        """Determine when a token should expire based on the config.

        :returns: datetime.datetime object

        """
        config.CONF.register_group(Manager.opt_group)
        config.CONF.register_opt(self.expiration_opt, group='token')
        expire_delta = datetime.timedelta(seconds=config.CONF.token.expiration)
        return datetime.datetime.now() + expire_delta
