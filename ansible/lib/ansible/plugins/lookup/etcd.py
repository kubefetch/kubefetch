# (c) 2013, Jan-Piet Mens <jpmens(at)gmail.com>
# (m) 2017, Juan Manuel Parrilla <jparrill@redhat.com>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
    author:
        - Jan-Piet Mens (@jpmens)
    lookup: etcd
    version_added: "2.1"
    short_description: get info from etcd server
    description:
        - Retrieves data from an etcd server
    options:
        _terms:
            description:
                - the list of keys to lookup on the etcd server
            type: list
            elements: string
            required: True
        _etcd_url:
            description:
                - Environment variable with the url for the etcd server
            default: 'http://127.0.0.1:4001'
            env:
              - name: ANSIBLE_ETCD_URL
            yaml:
              - key: etcd.url
        _etcd_version:
            description:
                - Environment variable with the etcd protocol version
            default: 'v1'
            env:
              - name: ANSIBLE_ETCD_VERSION
            yaml:
              - key: etcd.version
'''

EXAMPLES = '''
    - name: "a value from a locally running etcd"
      debug: msg={{ lookup('etcd', 'foo/bar') }}

    - name: "a values from a folder on a locally running etcd"
      debug: msg={{ lookup('etcd', 'foo') }}
'''

RETURN = '''
    _raw:
        description:
            - list of values associated with input keys
        type: list
        elements: strings
'''

import os

try:
    import json
except ImportError:
    import simplejson as json

from ansible.plugins.lookup import LookupBase
from ansible.module_utils.urls import open_url

# this can be made configurable, not should not use ansible.cfg
ANSIBLE_ETCD_URL = 'http://127.0.0.1:4001'
if os.getenv('ANSIBLE_ETCD_URL') is not None:
    ANSIBLE_ETCD_URL = os.environ['ANSIBLE_ETCD_URL']

ANSIBLE_ETCD_VERSION = 'v1'
if os.getenv('ANSIBLE_ETCD_VERSION') is not None:
    ANSIBLE_ETCD_VERSION = os.environ['ANSIBLE_ETCD_VERSION']


class Etcd:
    def __init__(self, url=ANSIBLE_ETCD_URL, version=ANSIBLE_ETCD_VERSION,
                 validate_certs=True):
        self.url = url
        self.version = version
        self.baseurl = '%s/%s/keys' % (self.url, self.version)
        self.validate_certs = validate_certs

    def _parse_node(self, node):
        # This function will receive all etcd tree,
        # if the level requested has any node, the recursion starts
        # create a list in the dir variable and it is passed to the
        # recursive function, and so on, if we get a variable,
        # the function will create a key-value at this level and
        # undoing the loop.
        path = {}
        if node.get('dir', False):
            for n in node.get('nodes', []):
                path[n['key'].split('/')[-1]] = self._parse_node(n)

        else:
            path = node['value']

        return path

    def get(self, key):
        url = "%s/%s?recursive=true" % (self.baseurl, key)
        data = None
        value = {}
        try:
            r = open_url(url, validate_certs=self.validate_certs)
            data = r.read()
        except:
            return None

        try:
            # I will not support Version 1 of etcd for folder parsing
            item = json.loads(data)
            if self.version == 'v1':
                # When ETCD are working with just v1
                if 'value' in item:
                    value = item['value']
            else:
                if 'node' in item:
                    # When a usual result from ETCD
                    value = self._parse_node(item['node'])

            if 'errorCode' in item:
                # Here return an error when an unknown entry responds
                value = "ENOENT"
        except:
            raise
            pass

        return value


class LookupModule(LookupBase):

    def run(self, terms, variables, **kwargs):

        validate_certs = kwargs.get('validate_certs', True)

        etcd = Etcd(validate_certs=validate_certs)

        ret = []
        for term in terms:
            key = term.split()[0]
            value = etcd.get(key)
            ret.append(value)
        return ret
