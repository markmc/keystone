# vim: tabstop=4 shiftwidth=4 softtabstop=4

import os

from keystone.common.sql import migration


def setup_test_database(conf):
    # TODO(termie): be smart about this
    try:
        os.unlink('bla.db')
    except Exception:
        pass
    migration.db_sync(conf)
