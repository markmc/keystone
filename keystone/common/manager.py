# vim: tabstop=4 shiftwidth=4 softtabstop=4

import functools

from keystone.common import utils


class Manager(object):
    """Base class for intermediary request layer.

    The Manager layer exists to support additional logic that applies to all
    or some of the methods exposed by a service that are not specific to the
    HTTP interface.

    It also provides a stable entry point to dynamic backends.

    An example of a probable use case is logging all the calls.

    """

    def __init__(self, conf, opt_group, driver_opt):
        self.conf = conf
        self.conf.register_group(opt_group)
        self.conf.register_opt(driver_opt, group=opt_group)

        driver_name = conf[opt_group.name][driver_opt.name]
        self.driver = utils.import_object(driver_name, conf)

    def __getattr__(self, name):
        """Forward calls to the underlying driver."""
        # NOTE(termie): context is the first argument, we're going to strip
        #               that for now, in the future we'll probably do some
        #               logging and whatnot in this class
        f = getattr(self.driver, name)

        @functools.wraps(f)
        def _wrapper(context, *args, **kw):
            return f(*args, **kw)
        setattr(self, name, _wrapper)
        return _wrapper
