# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack LLC
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2010 OpenStack LLC.
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

"""Utility methods for working with WSGI servers."""

import json
import logging
import sys

import eventlet
import eventlet.wsgi
eventlet.patcher.monkey_patch(all=False, socket=True, time=True)
from paste import deploy
import routes
import routes.middleware
import webob
import webob.dec
import webob.exc

from keystone import exception
from keystone.common import utils
from keystone.openstack.common import cfg


admin_port_opt = cfg.IntOpt('admin_port', default=35357)
public_port_opt = cfg.IntOpt('public_port', default=5000)


def get_admin_port(conf):
    conf.register_opt(admin_port_opt)
    return conf.admin_port


def get_public_port(conf):
    conf.register_opt(public_port_opt)
    return conf.public_port


class WritableLogger(object):
    """A thin wrapper that responds to `write` and logs."""

    def __init__(self, logger, level=logging.DEBUG):
        self.logger = logger
        self.level = level

    def write(self, msg):
        self.logger.log(self.level, msg)


class Server(object):
    """Server class to manage multiple WSGI sockets and applications."""

    def __init__(self, application, port, threads=1000):
        self.application = application
        self.port = port
        self.pool = eventlet.GreenPool(threads)
        self.socket_info = {}
        self.greenthread = None

    def start(self, host='0.0.0.0', key=None, backlog=128):
        """Run a WSGI server with the given application."""
        logging.debug('Starting %(arg0)s on %(host)s:%(port)s' %
                      {'arg0': sys.argv[0],
                       'host': host,
                       'port': self.port})
        socket = eventlet.listen((host, self.port), backlog=backlog)
        self.greenthread = self.pool.spawn(self._run, self.application, socket)
        if key:
            self.socket_info[key] = socket.getsockname()

    def kill(self):
        if self.greenthread:
            self.greenthread.kill()

    def wait(self):
        """Wait until all servers have completed running."""
        try:
            self.pool.waitall()
        except KeyboardInterrupt:
            pass

    def _run(self, application, socket):
        """Start a WSGI server in a new green thread."""
        logger = logging.getLogger('eventlet.wsgi.server')
        eventlet.wsgi.server(socket, application, custom_pool=self.pool,
                             log=WritableLogger(logger))


class Request(webob.Request):
    pass


class BaseApplication(object):
    """Base WSGI application wrapper. Subclasses need to implement __call__."""

    def __call__(self, environ, start_response):
        r"""Subclasses will probably want to implement __call__ like this:

        @webob.dec.wsgify(RequestClass=Request)
        def __call__(self, req):
          # Any of the following objects work as responses:

          # Option 1: simple string
          res = 'message\n'

          # Option 2: a nicely formatted HTTP exception page
          res = exc.HTTPForbidden(detail='Nice try')

          # Option 3: a webob Response object (in case you need to play with
          # headers, or you want to be treated like an iterable, or or or)
          res = Response();
          res.app_iter = open('somefile')

          # Option 4: any wsgi app to be run next
          res = self.application

          # Option 5: you can get a Response object for a wsgi app, too, to
          # play with headers etc
          res = req.get_response(self.application)

          # You can then just return your response...
          return res
          # ... or set req.response and return None.
          req.response = res

        See the end of http://pythonpaste.org/webob/modules/dec.html
        for more info.

        """
        raise NotImplementedError('You must implement __call__')


class Application(BaseApplication):
    @webob.dec.wsgify
    def __call__(self, req):
        arg_dict = req.environ['wsgiorg.routing_args'][1]
        action = arg_dict.pop('action')
        del arg_dict['controller']
        logging.debug('arg_dict: %s', arg_dict)

        # allow middleware up the stack to provide context & params
        context = req.environ.get('openstack.context', {})
        context['query_string'] = dict(req.params.iteritems())
        params = req.environ.get('openstack.params', {})
        params.update(arg_dict)

        # TODO(termie): do some basic normalization on methods
        method = getattr(self, action)

        # NOTE(vish): make sure we have no unicode keys for py2.6.
        params = self._normalize_dict(params)

        try:
            result = method(context, **params)
        except exception.Error as e:
            logging.warning(e)
            return render_exception(e)

        if result is None or type(result) is str or type(result) is unicode:
            return result
        elif isinstance(result, webob.Response):
            return result
        elif isinstance(result, webob.exc.WSGIHTTPException):
            return result

        response = webob.Response()
        self._serialize(response, result)
        return response

    def _serialize(self, response, result):
        response.content_type = 'application/json'
        response.body = json.dumps(result, cls=utils.SmarterEncoder)

    def _normalize_arg(self, arg):
        return str(arg).replace(':', '_').replace('-', '_')

    def _normalize_dict(self, d):
        return dict([(self._normalize_arg(k), v)
                     for (k, v) in d.iteritems()])

    def assert_admin(self, context):
        if not context['is_admin']:
            try:
                user_token_ref = self.token_api.get_token(
                        context=context, token_id=context['token_id'])
            except exception.TokenNotFound:
                raise exception.Unauthorized()
            creds = user_token_ref['metadata'].copy()
            creds['user_id'] = user_token_ref['user'].get('id')
            creds['tenant_id'] = user_token_ref['tenant'].get('id')
            # NOTE(vish): this is pretty inefficient
            creds['roles'] = [self.identity_api.get_role(context, role)['name']
                              for role in creds.get('roles', [])]
            # Accept either is_admin or the admin role
            assert self.policy_api.can_haz(context,
                                           ('is_admin:1', 'roles:admin'),
                                            creds)


class Middleware(Application):
    """Base WSGI middleware.

    These classes require an application to be
    initialized that will be called next.  By default the middleware will
    simply call its wrapped app, or you can override __call__ to customize its
    behavior.

    """

    def __init__(self, application, conf):
        self.application = application
        self.conf = conf
        super(Application, self).__init__()

    def process_request(self, req):
        """Called on each request.

        If this returns None, the next application down the stack will be
        executed. If it returns a response then that response will be returned
        and execution will stop here.

        """
        return None

    def process_response(self, response):
        """Do whatever you'd like to the response."""
        return response

    @webob.dec.wsgify(RequestClass=Request)
    def __call__(self, req):
        response = self.process_request(req)
        if response:
            return response
        response = req.get_response(self.application)
        return self.process_response(response)


class Debug(Middleware):
    """Helper class for debugging a WSGI application.

    Can be inserted into any WSGI application chain to get information
    about the request and response.

    """

    @webob.dec.wsgify(RequestClass=Request)
    def __call__(self, req):
        logging.debug('%s %s %s', ('*' * 20), 'REQUEST ENVIRON', ('*' * 20))
        for key, value in req.environ.items():
            logging.debug('%s = %s', key, value)
        logging.debug('')
        logging.debug('%s %s %s', ('*' * 20), 'REQUEST BODY', ('*' * 20))
        for line in req.body_file:
            logging.debug(line)
        logging.debug('')

        resp = req.get_response(self.application)

        logging.debug('%s %s %s', ('*' * 20), 'RESPONSE HEADERS', ('*' * 20))
        for (key, value) in resp.headers.iteritems():
            logging.debug('%s = %s', key, value)
        logging.debug('')

        resp.app_iter = self.print_generator(resp.app_iter)

        return resp

    @staticmethod
    def print_generator(app_iter):
        """Iterator that prints the contents of a wrapper string."""
        logging.debug('%s %s %s', ('*' * 20), 'RESPONSE BODY', ('*' * 20))
        for part in app_iter:
            #sys.stdout.write(part)
            logging.debug(part)
            #sys.stdout.flush()
            yield part
        print


class Router(object):
    """WSGI middleware that maps incoming requests to WSGI apps."""

    def __init__(self, conf, mapper):
        """Create a router for the given routes.Mapper.

        Each route in `mapper` must specify a 'controller', which is a
        WSGI app to call.  You'll probably want to specify an 'action' as
        well and have your controller be an object that can route
        the request to the action-specific method.

        Examples:
          mapper = routes.Mapper()
          sc = ServerController()

          # Explicit mapping of one route to a controller+action
          mapper.connect(None, '/svrlist', controller=sc, action='list')

          # Actions are all implicitly defined
          mapper.resource('server', 'servers', controller=sc)

          # Pointing to an arbitrary WSGI app.  You can specify the
          # {path_info:.*} parameter so the target app can be handed just that
          # section of the URL.
          mapper.connect(None, '/v1.0/{path_info:.*}', controller=BlogApp())

        """
        self.conf = conf
        self.map = mapper
        self._router = routes.middleware.RoutesMiddleware(self._dispatch,
                                                          self.map)

    @webob.dec.wsgify(RequestClass=Request)
    def __call__(self, req):
        """Route the incoming request to a controller based on self.map.

        If no match, return a 404.

        """
        return self._router

    @staticmethod
    @webob.dec.wsgify(RequestClass=Request)
    def _dispatch(req):
        """Dispatch the request to the appropriate controller.

        Called by self._router after matching the incoming request to a route
        and putting the information into req.environ.  Either returns 404
        or the routed WSGI app's response.

        """
        match = req.environ['wsgiorg.routing_args'][1]
        if not match:
            return webob.exc.HTTPNotFound()
        app = match['controller']
        return app


class ComposingRouter(Router):
    def __init__(self, conf, mapper=None, routers=None):
        if mapper is None:
            mapper = routes.Mapper()
        super(ComposingRouter, self).__init__(conf, mapper)
        if routers is None:
            routers = []
        for router in routers:
            router.add_routes(mapper)


class ComposableRouter(Router):
    """Router that supports use by ComposingRouter."""

    def __init__(self, conf, mapper=None):
        if mapper is None:
            mapper = routes.Mapper()
        super(ComposableRouter, self).__init__(conf, mapper)
        self.add_routes(mapper)

    def add_routes(self, mapper):
        """Add routes to given mapper."""
        pass


class ExtensionRouter(Router):
    """A router that allows extensions to supplement or overwrite routes.

    Expects to be subclassed.
    """
    def __init__(self, application, conf, mapper=None):
        if mapper is None:
            mapper = routes.Mapper()
        super(ExtensionRouter, self).__init__(conf, mapper)
        self.application = application
        self.add_routes(mapper)
        mapper.connect('{path_info:.*}', controller=self.application)

    def add_routes(self, mapper):
        pass


class BasePasteFactory(object):

    """A base class for paste app and filter factories.

    Sub-classes must override the KEY class attribute and provide
    a __call__ method.
    """

    KEY = None

    def __init__(self, conf):
        self.conf = conf

    def __call__(self, global_conf, **local_conf):
        raise NotImplementedError

    def _import_factory(self, local_conf):
        """Import an app/filter class.

        Lookup the KEY from the PasteDeploy local conf and import the
        class named there. This class can then be used as an app or
        filter factory.

        Note we support the <module>:<class> format.

        Note also that if you do e.g.

          key =
              value

        then ConfigParser returns a value with a leading newline, so
        we strip() the value before using it.
        """
        class_name = local_conf[self.KEY].replace(':', '.').strip()
        return utils.import_class(class_name)


class AppFactory(BasePasteFactory):

    """A Generic paste.deploy app factory.

    This requires keystone.app_factory to be set to a callable which returns a
    WSGI app when invoked. The format of the name is <module>:<callable> e.g.

      [app:public_service]
      paste.app_factory = keystone.common.wsgi:app_factory
      keystone.app_factory = keystone.service:PublicRouter

    The WSGI app constructor must accept a ConfigOpts object as its only
    argument.
    """

    KEY = 'keystone.app_factory'

    def __call__(self, global_conf, **local_conf):
        """The actual paste.app_factory protocol method."""
        factory = self._import_factory(local_conf)
        return factory(self.conf)


class FilterFactory(AppFactory):

    """A Generic paste.deploy filter factory.

    This requires keystone.filter_factory to be set to a callable which returns
    a WSGI filter when invoked. The format is <module>:<callable> e.g.

      [filter:debug]
      paste.filter_factory = keystone.common.wsgi:filter_factory
      keystone.filter_factory = keystone.common.wsgi:Debug

    The WSGI filter constructor must accept a WSGI app and a ConfigOpts object
    as its two arguments.
    """

    KEY = 'keystone.filter_factory'

    def __call__(self, global_conf, **local_conf):
        """The actual paste.filter_factory protocol method."""
        factory = self._import_factory(local_conf)

        def filter(app):
            return factory(app, self.conf)

        return filter


def setup_paste_factories(conf):
    """Set up the generic paste app and filter factories.

    Set things up so that:

      paste.app_factory = keystone.common.wsgi:app_factory

    and

      paste.filter_factory = keystone.common.wsgi:filter_factory

    work correctly while loading PasteDeploy configuration.

    The app factories are constructed at runtime to allow us to pass a
    ConfigOpts object to the WSGI classes.

    :param conf: a ConfigOpts object
    """
    global app_factory, filter_factory
    app_factory = AppFactory(conf)
    filter_factory = FilterFactory(conf)


def teardown_paste_factories():
    """Reverse the effect of setup_paste_factories()."""
    global app_factory, filter_factory
    del app_factory
    del filter_factory


def paste_deploy_app(paste_config_file, app_name, conf):
    """Load a WSGI app from a PasteDeploy configuration.

    Use deploy.loadapp() to load the app from the PasteDeploy configuration,
    ensuring that the supplied ConfigOpts object is passed to the app and
    filter constructors.

    :param paste_config_file: a PasteDeploy config file
    :param app_name: the name of the app/pipeline to load from the file
    :param conf: a ConfigOpts object to supply to the app and its filters
    :returns: the WSGI app
    """
    setup_paste_factories(conf)
    try:
        return deploy.loadapp("config:%s" % paste_config_file, name=app_name)
    finally:
        teardown_paste_factories()


def render_response(body, status=(200, 'OK'), headers=None):
    """Forms a WSGI response"""
    resp = webob.Response()
    resp.status = '%s %s' % status
    resp.headerlist = headers or [('Content-Type', 'application/json')]

    resp.body = json.dumps(body)

    return resp


def render_exception(error):
    """Forms a WSGI response based on the current error."""
    return render_response(status=(error.code, error.title), body={
        'error': {
            'code': error.code,
            'title': error.title,
            'message': str(error),
        }
    })
