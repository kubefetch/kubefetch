# (c) 2017 Red Hat Inc.
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

from ansible.compat.tests.mock import patch
from ansible.modules.network.junos import junos_facts
from .junos_module import TestJunosModule, load_fixture, set_module_args

RPC_CLI_MAP = {
    'get-software-information': 'show version',
    'get-interface-information': 'show interfaces details',
    'get-system-memory-information': 'show system memory',
    'get-chassis-inventory': 'show chassis hardware',
    'get-system-storage': 'show system storage'
}


class TestJunosCommandModule(TestJunosModule):

    module = junos_facts

    def setUp(self):
        self.mock_get_config = patch('ansible.modules.network.junos.junos_facts.get_configuration')
        self.get_config = self.mock_get_config.start()

        self.mock_send_request = patch('ansible.modules.network.junos.junos_facts.send_request')
        self.send_request = self.mock_send_request.start()

    def tearDown(self):
        self.mock_send_request.stop()

    def load_fixtures(self, commands=None, format='text', changed=False):
        def load_from_file(*args, **kwargs):
            module, element = args

            if element.text:
                path = str(element.text)
            else:
                path = RPC_CLI_MAP[str(element.tag)]

            filename = path.replace(' ', '_')
            filename = '%s_%s.txt' % (filename, format)
            return load_fixture(filename)

        self.send_request.side_effect = load_from_file

    def test_junos_get_facts(self):
        set_module_args(dict())
        result = self.execute_module(format='xml')
        facts = result['ansible_facts']

        self.assertEqual(facts['ansible_net_hostname'], 'vsrx01')
        self.assertTrue('em0' in facts['ansible_net_interfaces'])
        self.assertEqual(facts['ansible_net_interfaces']['em0']['type'], 'Ethernet')
        self.assertEqual(facts['ansible_net_memtotal_mb'], 983500)
        self.assertEqual(facts['ansible_net_filesystems'][0], '/dev/vtbd0s1a')
        self.assertTrue('ansible_net_config' not in facts)

    def test_junos_get_facts_subset_config_set(self):
        self.get_config.return_value = load_fixture('get_configuration_rpc_reply.txt')
        set_module_args(dict(gather_subset='config', config_format='set'))
        result = self.execute_module(format='xml')
        facts = result['ansible_facts']

        self.assertTrue('ansible_net_config' in facts)
        self.assertTrue(facts['ansible_net_config'].startswith('set'))
        self.assertEqual(facts['ansible_net_hostname'], 'vsrx01')
        self.assertTrue('ansible_net_interfaces' not in facts)

    def test_junos_get_facts_subset_list(self):
        set_module_args(dict(gather_subset=['hardware', 'interfaces']))
        result = self.execute_module(format='xml')
        facts = result['ansible_facts']

        self.assertTrue('ansible_net_config' not in facts)
        self.assertEqual(facts['ansible_net_interfaces']['em0']['oper-status'], 'up')
        self.assertEqual(facts['ansible_net_memfree_mb'], 200684)

    def test_junos_get_facts_wrong_subset(self):
        set_module_args(dict(gather_subset=['hardware', 'interfaces', 'test']))
        result = self.execute_module(format='xml', failed=True)

        self.assertTrue(result['msg'].startswith('Subset must be one'))
