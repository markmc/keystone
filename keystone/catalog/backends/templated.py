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

from keystone.common import logging
from keystone.catalog.backends import kvs
from keystone.openstack.common import cfg


def parse_templates(template_lines):
    o = {}
    for line in template_lines:
        if ' = ' not in line:
            continue

        k, v = line.strip().split(' = ')
        if not k.startswith('catalog.'):
            continue

        parts = k.split('.')

        region = parts[1]
        # NOTE(termie): object-store insists on having a dash
        service = parts[2].replace('_', '-')
        key = parts[3]

        region_ref = o.get(region, {})
        service_ref = region_ref.get(service, {})
        service_ref[key] = v

        region_ref[service] = service_ref
        o[region] = region_ref

    return o


class TemplatedCatalog(kvs.Catalog):
    """A backend that generates endpoints for the Catalog based on templates.

    It is usually configured via config entries that look like:

      catalog.$REGION.$SERVICE.$key = $value

    and is stored in a similar looking hierarchy. Where a value can contain
    values to be interpolated by standard python string interpolation that look
    like (the % is replaced by a $ due to paste attmepting to interpolate on
    its own:

      http://localhost:$(public_port)s/

    When expanding the template it will pass in a dict made up of the conf
    instance plus a few additional key-values, notably tenant_id and user_id.

    It does not care what the keys and values are but it is worth noting that
    keystone_compat will expect certain keys to be there so that it can munge
    them into the output format keystone expects. These keys are:

      name - the name of the service, most likely repeated for all services of
             the same type, across regions.

      adminURL - the url of the admin endpoint

      publicURL - the url of the public endpoint

      internalURL - the url of the internal endpoint

    """

    template_opt = cfg.StrOpt('template_file',
                              default='./etc/default_catalog.templates')
    compute_port_opt = cfg.StrOpt('compute_port', default=3000)

    def __init__(self, conf, templates=None):
        kvs.Catalog.__init__(self, conf)
        if templates:
            self.templates = templates
        else:
            conf.register_opt(self.template_opt, group='catalog')
            self._load_templates(conf.catalog.template_file)

    def _load_templates(self, template_file):
        self.templates = parse_templates(open(template_file))

    def get_catalog(self, user_id, tenant_id, metadata=None):
        self.conf.register_opt(self.compute_port_opt)
        d = dict(self.conf.iteritems())
        d.update({'tenant_id': tenant_id,
                  'user_id': user_id})

        o = {}
        for region, region_ref in self.templates.iteritems():
            o[region] = {}
            for service, service_ref in region_ref.iteritems():
                o[region][service] = {}
                for k, v in service_ref.iteritems():
                    v = v.replace('$(', '%(')
                    o[region][service][k] = v % d

        return o
