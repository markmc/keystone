# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack LLC
# Copyright 2012 Justin Santa Barbara
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

from keystone.common import passwd
from keystone import config
from keystone import test


CONF = config.CONF


class PasswdTestCase(test.TestCase):
    def test_hash(self):
        password = 'right'
        wrong = 'wrongwrong'  # Two wrongs don't make a right
        hashed = passwd.hash_password(CONF, password)
        self.assertTrue(passwd.check_password(password, hashed))
        self.assertFalse(passwd.check_password(wrong, hashed))

    def test_hash_edge_cases(self):
        hashed = passwd.hash_password(CONF, 'secret')
        self.assertFalse(passwd.check_password('', hashed))
        self.assertFalse(passwd.check_password(None, hashed))

    def test_hash_unicode(self):
        password = u'Comment \xe7a va'
        wrong = 'Comment ?a va'
        hashed = passwd.hash_password(CONF, password)
        self.assertTrue(passwd.check_password(password, hashed))
        self.assertFalse(passwd.check_password(wrong, hashed))
