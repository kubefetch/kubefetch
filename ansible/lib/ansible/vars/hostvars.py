# (c) 2012-2014, Michael DeHaan <michael.dehaan@gmail.com>
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

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import collections

from jinja2.runtime import Undefined

from ansible.module_utils._text import to_bytes
from ansible.template import Templar

STATIC_VARS = [
    'ansible_version',
    'ansible_play_hosts',
    'inventory_hostname',
    'inventory_hostname_short',
    'inventory_file',
    'inventory_dir',
    'groups',
    'group_names',
    'omit',
    'playbook_dir',
    'play_hosts',
    'role_names',
    'ungrouped',
]

try:
    from hashlib import sha1
except ImportError:
    from sha import sha as sha1

__all__ = ['HostVars']


# Note -- this is a Mapping, not a MutableMapping
class HostVars(collections.Mapping):
    ''' A special view of vars_cache that adds values from the inventory when needed. '''

    def __init__(self, inventory, variable_manager, loader):
        self._lookup = dict()
        self._inventory = inventory
        self._loader = loader
        self._variable_manager = variable_manager
        variable_manager._hostvars = self
        self._cached_result = dict()

    def set_variable_manager(self, variable_manager):
        self._variable_manager = variable_manager
        variable_manager._hostvars = self

    def set_inventory(self, inventory):
        self._inventory = inventory

    def _find_host(self, host_name):
        # does not use inventory.hosts so it can create localhost on demand
        return self._inventory.get_host(host_name)

    def raw_get(self, host_name):
        '''
        Similar to __getitem__, however the returned data is not run through
        the templating engine to expand variables in the hostvars.
        '''
        host = self._find_host(host_name)
        if host is None:
            return Undefined(name="hostvars['%s']" % host_name)

        return self._variable_manager.get_vars(host=host, include_hostvars=False)

    def __getitem__(self, host_name):
        data = self.raw_get(host_name)
        sha1_hash = sha1(to_bytes(data)).hexdigest()
        if sha1_hash not in self._cached_result:
            templar = Templar(variables=data, loader=self._loader)
            self._cached_result[sha1_hash] = templar.template(data, fail_on_undefined=False, static_vars=STATIC_VARS)
        return self._cached_result[sha1_hash]

    def set_host_variable(self, host, varname, value):
        self._variable_manager.set_host_variable(host, varname, value)

    def set_nonpersistent_facts(self, host, facts):
        self._variable_manager.set_nonpersistent_facts(host, facts)

    def set_host_facts(self, host, facts):
        self._variable_manager.set_host_facts(host, facts)

    def __contains__(self, host_name):
        # does not use inventory.hosts so it can create localhost on demand
        return self._find_host(host_name) is not None

    def __iter__(self):
        for host in self._inventory.hosts:
            yield host

    def __len__(self):
        return len(self._inventory.hosts)

    def __repr__(self):
        out = {}
        for host in self._inventory.hosts:
            out[host] = self.get(host)
        return repr(out)
