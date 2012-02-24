# vim: tabstop=4 shiftwidth=4 softtabstop=4

from keystone.openstack.common import cfg


sql_group = cfg.OptGroup('sql')
sql_opts = [
    cfg.StrOpt('connection', default='sqlite:///bla.db'),
    cfg.StrOpt('idle_timeout', default=200),
    ]


def _register_opts(conf):
    conf.register_group(sql_group)
    conf.register_opts(sql_opts, group=sql_group)


def get_sql_connection(conf):
    _register_opts(conf)
    return conf.sql.connection


def get_sql_idle_timeout(conf):
    _register_opts(conf)
    return conf.sql.idle_timeout
