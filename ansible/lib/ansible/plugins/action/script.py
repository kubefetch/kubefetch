# (c) 2012, Michael DeHaan <michael.dehaan@gmail.com>
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

import os
import re
import shlex

from ansible.errors import AnsibleError
from ansible.module_utils._text import to_bytes, to_native, to_text
from ansible.plugins.action import ActionBase
from ansible.plugins.shell.powershell import exec_wrapper


class ActionModule(ActionBase):
    TRANSFERS_FILES = True

    # On Windows platform, absolute paths begin with a (back)slash
    # after chopping off a potential drive letter.
    windows_absolute_path_detection = re.compile(r'^(?:[a-zA-Z]\:)?(\\|\/)')

    def run(self, tmp=None, task_vars=None):
        ''' handler for file transfer operations '''
        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)

        if not tmp:
            tmp = self._make_tmp_path()

        creates = self._task.args.get('creates')
        if creates:
            # do not run the command if the line contains creates=filename
            # and the filename already exists. This allows idempotence
            # of command executions.
            if self._remote_file_exists(creates):
                self._remove_tmp_path(tmp)
                return dict(skipped=True, msg=("skipped, since %s exists" % creates))

        removes = self._task.args.get('removes')
        if removes:
            # do not run the command if the line contains removes=filename
            # and the filename does not exist. This allows idempotence
            # of command executions.
            if not self._remote_file_exists(removes):
                self._remove_tmp_path(tmp)
                return dict(skipped=True, msg=("skipped, since %s does not exist" % removes))

        # The chdir must be absolute, because a relative path would rely on
        # remote node behaviour & user config.
        chdir = self._task.args.get('chdir')
        if chdir:
            # Powershell is the only Windows-path aware shell
            if self._connection._shell.SHELL_FAMILY == 'powershell' and \
                    not self.windows_absolute_path_detection.matches(chdir):
                return dict(failed=True, msg='chdir %s must be an absolute path for a Windows remote node' % chdir)
            # Every other shell is unix-path-aware.
            if self._connection._shell.SHELL_FAMILY != 'powershell' and not chdir.startswith('/'):
                return dict(failed=True, msg='chdir %s must be an absolute path for a Unix-aware remote node' % chdir)

        # Split out the script as the first item in raw_params using
        # shlex.split() in order to support paths and files with spaces in the name.
        # Any arguments passed to the script will be added back later.
        raw_params = to_native(self._task.args.get('_raw_params', ''), errors='surrogate_or_strict')
        parts = [to_text(s, errors='surrogate_or_strict') for s in shlex.split(raw_params.strip())]
        source = parts[0]

        try:
            source = self._loader.get_real_file(self._find_needle('files', source), decrypt=self._task.args.get('decrypt', True))
        except AnsibleError as e:
            return dict(failed=True, msg=to_native(e))

        if not self._play_context.check_mode:
            # transfer the file to a remote tmp location
            tmp_src = self._connection._shell.join_path(tmp, os.path.basename(source))

            # Convert raw_params to text for the purpose of replacing the script since
            # parts and tmp_src are both unicode strings and raw_params will be different
            # depending on Python version.
            #
            # Once everything is encoded consistently, replace the script path on the remote
            # system with the remainder of the raw_params. This preserves quoting in parameters
            # that would have been removed by shlex.split().
            target_command = to_text(raw_params).strip().replace(parts[0], tmp_src)

            self._transfer_file(source, tmp_src)

            # set file permissions, more permissive when the copy is done as a different user
            self._fixup_perms2((tmp, tmp_src), execute=True)

            # add preparation steps to one ssh roundtrip executing the script
            env_dict = dict()
            env_string = self._compute_environment_string(env_dict)
            script_cmd = ' '.join([env_string, target_command])

        if self._play_context.check_mode:
            result['changed'] = True
            self._remove_tmp_path(tmp)
            return result

        script_cmd = self._connection._shell.wrap_for_exec(script_cmd)

        exec_data = None
        # HACK: come up with a sane way to pass around env outside the command
        if self._connection.transport == "winrm":
            pay = self._connection._create_raw_wrapper_payload(script_cmd,
                                                               env_dict)
            exec_data = exec_wrapper.replace(b"$json_raw = ''",
                                             b"$json_raw = @'\r\n%s\r\n'@"
                                             % to_bytes(pay))
            script_cmd = "-"

        result.update(self._low_level_execute_command(cmd=script_cmd, in_data=exec_data, sudoable=True, chdir=chdir))

        # clean up after
        self._remove_tmp_path(tmp)

        result['changed'] = True

        if 'rc' in result and result['rc'] != 0:
            result['failed'] = True
            result['msg'] = 'non-zero return code'

        return result
