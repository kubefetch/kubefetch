# (c) 2016 Red Hat Inc.
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

import json

from ansible.compat.tests.mock import patch
from ansible.modules.network.ios import ios_user
from .ios_module import TestIosModule, load_fixture, set_module_args


class TestIosUserModule(TestIosModule):

    module = ios_user

    def setUp(self):
        self.mock_get_config = patch('ansible.modules.network.ios.ios_user.get_config')
        self.get_config = self.mock_get_config.start()

        self.mock_load_config = patch('ansible.modules.network.ios.ios_user.load_config')
        self.load_config = self.mock_load_config.start()

    def tearDown(self):
        self.mock_get_config.stop()
        self.mock_load_config.stop()

    def load_fixtures(self, commands=None, transport='cli'):
        self.get_config.return_value = load_fixture('ios_user_config.cfg')
        self.load_config.return_value = dict(diff=None, session='session')

    def test_ios_user_create(self):
        set_module_args(dict(name='test', nopassword=True))
        result = self.execute_module(changed=True)
        self.assertEqual(result['commands'], ['username test nopassword'])

    def test_ios_user_delete(self):
        set_module_args(dict(name='ansible', state='absent'))
        result = self.execute_module(changed=True)
        cmd = json.loads(
            '{"answer": "y", ' +
            '"prompt": "This operation will remove all username related ' +
            'configurations with same name", "command": "no username ansible"}'
        )

        result_cmd = []
        for i in result['commands']:
            result_cmd.append(json.loads(i))

        self.assertEqual(result_cmd, [cmd])

    def test_ios_user_password(self):
        set_module_args(dict(name='ansible', configured_password='test'))
        result = self.execute_module(changed=True)
        self.assertEqual(result['commands'], ['username ansible secret test'])

    def test_ios_user_privilege(self):
        set_module_args(dict(name='ansible', privilege=15))
        result = self.execute_module(changed=True)
        self.assertEqual(result['commands'], ['username ansible privilege 15'])

    def test_ios_user_privilege_invalid(self):
        set_module_args(dict(name='ansible', privilege=25))
        self.execute_module(failed=True)

    def test_ios_user_purge(self):
        set_module_args(dict(purge=True))
        result = self.execute_module(changed=True)
        cmd = json.loads(
            '{"answer": "y", ' +
            '"prompt": "This operation will remove all username related ' +
            'configurations with same name", "command": "no username ansible"}'
        )

        result_cmd = []
        for i in result['commands']:
            result_cmd.append(json.loads(i))

        self.assertEqual(result_cmd, [cmd])

    def test_ios_user_view(self):
        set_module_args(dict(name='ansible', view='test'))
        result = self.execute_module(changed=True)
        self.assertEqual(result['commands'], ['username ansible view test'])

    def test_ios_user_update_password_changed(self):
        set_module_args(dict(name='test', configured_password='test', update_password='on_create'))
        result = self.execute_module(changed=True)
        self.assertEqual(result['commands'], ['username test secret test'])

    def test_ios_user_update_password_on_create_ok(self):
        set_module_args(dict(name='ansible', configured_password='test', update_password='on_create'))
        self.execute_module()

    def test_ios_user_update_password_always(self):
        set_module_args(dict(name='ansible', configured_password='test', update_password='always'))
        result = self.execute_module(changed=True)
        self.assertEqual(result['commands'], ['username ansible secret test'])
