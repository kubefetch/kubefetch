#
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
#
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import sys
import copy

from ansible import constants as C
from ansible.module_utils.basic import AnsibleFallbackNotFound
from ansible.module_utils.eos import ARGS_DEFAULT_VALUE, eos_argument_spec
from ansible.module_utils.six import iteritems
from ansible.plugins.action.normal import ActionModule as _ActionModule

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class ActionModule(_ActionModule):

    def run(self, tmp=None, task_vars=None):
        if self._play_context.connection != 'local':
            return dict(
                failed=True,
                msg='invalid connection specified, expected connection=local, '
                    'got %s' % self._play_context.connection
            )

        provider = self.load_provider()
        transport = provider['transport'] or 'cli'

        display.vvvv('connection transport is %s' % transport, self._play_context.remote_addr)

        if transport == 'cli':
            pc = copy.deepcopy(self._play_context)
            pc.connection = 'network_cli'
            pc.network_os = 'eos'
            pc.remote_addr = provider['host'] or self._play_context.remote_addr
            pc.port = int(provider['port'] or self._play_context.port or 22)
            pc.remote_user = provider['username'] or self._play_context.connection_user
            pc.password = provider['password'] or self._play_context.password
            pc.private_key_file = provider['ssh_keyfile'] or self._play_context.private_key_file
            pc.timeout = int(provider['timeout'] or C.PERSISTENT_COMMAND_TIMEOUT)
            pc.become = provider['authorize'] or False
            pc.become_pass = provider['auth_pass']

            display.vvv('using connection plugin %s' % pc.connection, pc.remote_addr)
            connection = self._shared_loader_obj.connection_loader.get('persistent', pc, sys.stdin)

            socket_path = connection.run()
            display.vvvv('socket_path: %s' % socket_path, pc.remote_addr)
            if not socket_path:
                return {'failed': True,
                        'msg': 'unable to open shell. Please see: ' +
                               'https://docs.ansible.com/ansible/network_debug_troubleshooting.html#unable-to-open-shell'}

            # make sure we are in the right cli context which should be
            # enable mode and not config module
            rc, out, err = connection.exec_command('prompt()')
            while '(config' in str(out):
                display.vvvv('wrong context, sending exit to device', self._play_context.remote_addr)
                connection.exec_command('exit')
                rc, out, err = connection.exec_command('prompt()')

            task_vars['ansible_socket'] = socket_path

        else:
            self._task.args['provider'] = ActionModule.eapi_implementation(provider, self._play_context)

        result = super(ActionModule, self).run(tmp, task_vars)
        return result

    @staticmethod
    def eapi_implementation(provider, play_context):
        provider['transport'] = 'eapi'

        if provider.get('host') is None:
            provider['host'] = play_context.remote_addr

        if provider.get('use_ssl') is None:
            provider['use_ssl'] = ARGS_DEFAULT_VALUE['use_ssl']

        if provider.get('port') is None:
            default_port = 443 if provider['use_ssl'] else 80
            provider['port'] = int(play_context.port or default_port)

        if provider.get('timeout') is None:
            provider['timeout'] = C.PERSISTENT_COMMAND_TIMEOUT

        if provider.get('username') is None:
            provider['username'] = play_context.connection_user

        if provider.get('password') is None:
            provider['password'] = play_context.password

        if provider.get('authorize') is None:
            provider['authorize'] = False

        if provider.get('validate_certs') is None:
            provider['validate_certs'] = ARGS_DEFAULT_VALUE['validate_certs']

        return provider

    def load_provider(self):
        provider = self._task.args.get('provider', {})
        for key, value in iteritems(eos_argument_spec):
            if key != 'provider' and key not in provider:
                if key in self._task.args:
                    provider[key] = self._task.args[key]
                elif 'fallback' in value:
                    provider[key] = self._fallback(value['fallback'])
                elif 'default' in value:
                    provider[key] = value['default']
                elif key not in provider:
                    provider[key] = None
        return provider

    def _fallback(self, fallback):
        strategy = fallback[0]
        args = []
        kwargs = {}

        for item in fallback[1:]:
            if isinstance(item, dict):
                kwargs = item
            else:
                args = item
        try:
            return strategy(*args, **kwargs)
        except AnsibleFallbackNotFound:
            pass
