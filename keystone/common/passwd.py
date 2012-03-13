# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2011 - 2012 Justin Santa Barbara
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

import passlib.hash

from keystone.openstack.common import cfg


crypt_strength_opt = cfg.IntOpt('crypt_strength', default=40000)


def get_crypt_strength(conf):
    """Return the crypt_strength config value."""
    conf.register_opt(crypt_strength_opt)
    return conf.crypt_strength


def hash_password(conf, password):
    """Hash a password. Hard."""
    password_utf8 = password.encode('utf-8')
    if passlib.hash.sha512_crypt.identify(password_utf8):
        return password_utf8
    h = passlib.hash.sha512_crypt.encrypt(password_utf8,
                                          rounds=get_crypt_strength(conf))
    return h


def ldap_hash_password(password):
    """Hash a password. Hard."""
    password_utf8 = password.encode('utf-8')
    h = passlib.hash.ldap_salted_sha1.encrypt(password_utf8)
    return h


def check_password(password, hashed):
    """Check that a plaintext password matches hashed.

    hashpw returns the salt value concatenated with the actual hash value.
    It extracts the actual salt if this value is then passed as the salt.

    """
    if password is None:
        return False
    password_utf8 = password.encode('utf-8')
    return passlib.hash.sha512_crypt.verify(password_utf8, hashed)


def ldap_check_password(password, hashed):
    if password is None:
        return False
    password_utf8 = password.encode('utf-8')
    h = passlib.hash.ldap_salted_sha1.encrypt(password_utf8)
    return passlib.hash.ldap_salted_sha1.verify(password_utf8, hashed)
