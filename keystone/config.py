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

import gettext
import sys
import os

from keystone.common import logging
from keystone.openstack.common import cfg


gettext.install('keystone', unicode=1)


class ConfigMixin(object):
    def __call__(self, config_files=None, *args, **kw):
        if config_files is not None:
            self._opts['config_file']['opt'].default = config_files
        kw.setdefault('args', [])
        return super(ConfigMixin, self).__call__(*args, **kw)

    def set_usage(self, usage):
        self.usage = usage
        self._oparser.usage = usage


class Config(ConfigMixin, cfg.ConfigOpts):
    pass


class CommonConfig(ConfigMixin, cfg.CommonConfigOpts):
    pass


def setup_logging(conf):
    """
    Sets up the logging options for a log with supplied name

    :param conf: a cfg.ConfOpts object
    """

    if conf.log_config:
        # Use a logging configuration file for all settings...
        if os.path.exists(conf.log_config):
            logging.config.fileConfig(conf.log_config)
            return
        else:
            raise RuntimeError('Unable to locate specified logging '
                               'config file: %s' % conf.log_config)

    root_logger = logging.root
    if conf.debug:
        root_logger.setLevel(logging.DEBUG)
    elif conf.verbose:
        root_logger.setLevel(logging.INFO)
    else:
        root_logger.setLevel(logging.WARNING)

    formatter = logging.Formatter(conf.log_format, conf.log_date_format)

    if conf.use_syslog:
        try:
            facility = getattr(logging.SysLogHandler,
                               conf.syslog_log_facility)
        except AttributeError:
            raise ValueError(_('Invalid syslog facility'))

        handler = logging.SysLogHandler(address='/dev/log',
                                        facility=facility)
    elif conf.log_file:
        logfile = conf.log_file
        if conf.log_dir:
            logfile = os.path.join(conf.log_dir, logfile)
        handler = logging.WatchedFileHandler(logfile)
    else:
        handler = logging.StreamHandler(sys.stdout)

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


CONF = CommonConfig(project='keystone')

global_opts = [
    cfg.StrOpt('bind_host', default='0.0.0.0'),
    cfg.StrOpt('compute_port'),
    cfg.StrOpt('admin_port'),
    cfg.StrOpt('public_port'),
    ]

CONF.register_opts(global_opts)
