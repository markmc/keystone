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

import json

import webob.exc

from keystone.common import wsgi
from keystone.openstack.common import cfg


# Header used to transmit the auth token
AUTH_TOKEN_HEADER = 'X-Auth-Token'


# Environment variable used to pass the request context
CONTEXT_ENV = 'openstack.context'


# Environment variable used to pass the request params
PARAMS_ENV = 'openstack.params'


class TokenAuthMiddleware(wsgi.Middleware):
    def process_request(self, request):
        token = request.headers.get(AUTH_TOKEN_HEADER)
        context = request.environ.get(CONTEXT_ENV, {})
        context['token_id'] = token
        request.environ[CONTEXT_ENV] = context


class AdminTokenAuthMiddleware(wsgi.Middleware):
    """A trivial filter that checks for a pre-defined admin token.

    Sets 'is_admin' to true in the context, expected to be checked by
    methods that are admin-only.

    """

    admin_token_opt = cfg.StrOpt('admin_token', default='ADMIN')

    def __init__(self, application, conf):
        super(AdminTokenAuthMiddleware, self).__init__(application, conf)
        self.conf.register_opt(self.admin_token_opt)

    def process_request(self, request):
        token = request.headers.get(AUTH_TOKEN_HEADER)
        context = request.environ.get(CONTEXT_ENV, {})
        context['is_admin'] = self._is_admin_token(token)
        request.environ[CONTEXT_ENV] = context

    def _is_admin_token(self, token):
        return token == self.conf.admin_token


class PostParamsMiddleware(wsgi.Middleware):
    """Middleware to allow method arguments to be passed as POST parameters.

    Filters out the parameters `self`, `context` and anything beginning with
    an underscore.

    """

    def process_request(self, request):
        params_parsed = request.params
        params = {}
        for k, v in params_parsed.iteritems():
            if k in ('self', 'context'):
                continue
            if k.startswith('_'):
                continue
            params[k] = v

        request.environ[PARAMS_ENV] = params


class JsonBodyMiddleware(wsgi.Middleware):
    """Middleware to allow method arguments to be passed as serialized JSON.

    Accepting arguments as JSON is useful for accepting data that may be more
    complex than simple primitives.

    In this case we accept it as urlencoded data under the key 'json' as in
    json=<urlencoded_json> but this could be extended to accept raw JSON
    in the POST body.

    Filters out the parameters `self`, `context` and anything beginning with
    an underscore.

    """
    def process_request(self, request):
        # Ignore unrecognized content types. Empty string indicates
        # the client did not explicitly set the header
        if not request.content_type in ('application/json', ''):
            return

        params_json = request.body
        if not params_json:
            return

        params_parsed = {}
        try:
            params_parsed = json.loads(params_json)
        except ValueError:
            msg = "Malformed json in request body"
            raise webob.exc.HTTPBadRequest(explanation=msg)
        finally:
            if not params_parsed:
                params_parsed = {}

        params = {}
        for k, v in params_parsed.iteritems():
            if k in ('self', 'context'):
                continue
            if k.startswith('_'):
                continue
            params[k] = v

        request.environ[PARAMS_ENV] = params
