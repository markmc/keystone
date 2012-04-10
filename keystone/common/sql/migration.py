# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack LLC
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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

import os
import sys

import sqlalchemy
from migrate.versioning import api as versioning_api

from keystone.common.sql import opts


try:
    from migrate.versioning import exceptions as versioning_exceptions
except ImportError:
    try:
        # python-migration changed location of exceptions after 1.6.3
        # See LP Bug #717467
        from migrate import exceptions as versioning_exceptions
    except ImportError:
        sys.exit('python-migrate is not installed. Exiting.')


def db_sync(conf, version=None):
    if version is not None:
        try:
            version = int(version)
        except ValueError:
            raise Exception('version should be an integer')

    sql_connection = opts.get_sql_connection(conf)

    current_version = db_version(sql_connection)
    repo_path = _find_migrate_repo()
    if version is None or version > current_version:
        return versioning_api.upgrade(sql_connection, repo_path, version)
    else:
        return versioning_api.downgrade(sql_connection, repo_path, version)


def db_version(sql_connection):
    repo_path = _find_migrate_repo()
    try:
        return versioning_api.db_version(sql_connection, repo_path)
    except versioning_exceptions.DatabaseNotControlledError:
        return db_version_control(sql_connection, version=0)


def db_version_control(sql_connection, version=None):
    repo_path = _find_migrate_repo()
    versioning_api.version_control(sql_connection, repo_path, version)
    return version


def _find_migrate_repo():
    """Get the path for the migrate repository."""
    path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                        'migrate_repo')
    assert os.path.exists(path)
    return path
