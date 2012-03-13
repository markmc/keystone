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

from __future__ import absolute_import

import json
import sys
import textwrap

from keystone import config
from keystone.common import utils


class BaseApp(object):
    def __init__(self, conf, argv=None):
        self.conf = conf
        self.argv = argv

    def run(self):
        return self.main()

    def missing_param(self, param):
        print 'Missing parameter: %s' % param
        self.conf.print_help()
        print_commands(CMDS)
        sys.exit(1)


class DbSync(BaseApp):
    """Sync the database."""

    name = 'db_sync'

    def main(self):
        for k in ['identity', 'catalog', 'policy', 'token']:
            driver = utils.import_object(self.conf[k].driver, self.conf)
            if hasattr(driver, 'db_sync'):
                driver.db_sync()


class ImportLegacy(BaseApp):
    """Import a legacy database."""

    name = 'import_legacy'

    def main(self):
        from keystone.common.sql import legacy
        if len(self.argv) < 2:
            return self.missing_param('old_db')
        old_db = self.argv[1]
        migration = legacy.LegacyMigration(self.conf, old_db)
        migration.migrate_all()


class ExportLegacyCatalog(BaseApp):
    """Export the service catalog from a legacy database."""

    name = 'export_legacy_catalog'

    def main(self):
        from keystone.common.sql import legacy
        if len(self.argv) < 2:
            return self.missing_param('old_db')
        old_db = self.argv[1]
        migration = legacy.LegacyMigration(self.conf, old_db)
        print '\n'.join(migration.dump_catalog())


class ImportNovaAuth(BaseApp):
    """Import a dump of nova auth data into keystone."""

    name = 'import_nova_auth'

    def __init__(self, *args, **kw):
        super(ImportNovaAuth, self).__init__(*args, **kw)

    def main(self):
        from keystone.common.sql import nova
        if len(self.argv) < 2:
            return self.missing_param('dump_file')
        dump_file = self.argv[1]
        dump_data = json.loads(open(dump_file).read())
        nova.import_auth(self.conf, dump_data)


CMDS = {'db_sync': DbSync,
        'import_legacy': ImportLegacy,
        'export_legacy_catalog': ExportLegacyCatalog,
        'import_nova_auth': ImportNovaAuth,
        }


def print_commands(cmds):
    print
    print 'Available commands:'
    o = []
    max_length = max([len(k) for k in cmds]) + 2
    for k, cmd in sorted(cmds.iteritems()):
        initial_indent = '%s%s: ' % (' ' * (max_length - len(k)), k)
        tw = textwrap.TextWrapper(initial_indent=initial_indent,
                                  subsequent_indent=' ' * (max_length + 2),
                                  width=80)
        o.extend(tw.wrap(
            (cmd.__doc__ and cmd.__doc__ or 'no docs').strip().split('\n')[0]))
    print '\n'.join(o)


def run(cmd, conf, args):
    return CMDS[cmd](conf, argv=args).run()


def main(argv=None, config_files=None):
    conf = config.CONF
    conf.reset()
    conf.set_usage('%prog COMMAND')
    args = conf(config_files=config_files, args=argv)

    if len(args) < 2:
        conf.print_help()
        print_commands(CMDS)
        sys.exit(1)

    cmd = args[1]
    if cmd in CMDS:
        return run(cmd, conf, (args[:1] + args[2:]))
    else:
        print_commands(CMDS)
        sys.exit("Unknown command: %s" % cmd)
