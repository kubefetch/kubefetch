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

import re

from abc import ABCMeta, abstractmethod

from ansible.errors import AnsibleConnectionFailure
from ansible.module_utils.six import with_metaclass


class TerminalBase(with_metaclass(ABCMeta, object)):
    '''
    A base class for implementing cli connections

    .. note:: Unlike most of Ansible, nearly all strings in
        :class:`TerminalBase` plugins are byte strings.  This is because of
        how close to the underlying platform these plugins operate.  Remember
        to mark literal strings as byte string (``b"string"``) and to use
        :func:`~ansible.module_utils._text.to_bytes` and
        :func:`~ansible.module_utils._text.to_text` to avoid unexpected
        problems.
    '''

    #: compiled bytes regular expressions as stdout
    terminal_stdout_re = []

    #: compiled bytes regular expressions as stderr
    terminal_stderr_re = []

    #: compiled bytes regular expressions to remove ANSI codes
    ansi_re = [
        re.compile(br'(\x1b\[\?1h\x1b=)'),
        re.compile(br'\x08.')
    ]

    def __init__(self, connection):
        self._connection = connection

    def _exec_cli_command(self, cmd, check_rc=True):
        """
        Executes a CLI command on the device

        :arg cmd: Byte string consisting of the command to execute
        :kwarg check_rc: If True, the default, raise an
            :exc:`AnsibleConnectionFailure` if the return code from the
            command is nonzero
        :returns: A tuple of return code, stdout, and stderr from running the
            command.  stdout and stderr are both byte strings.
        """
        rc, out, err = self._connection.exec_command(cmd)
        if check_rc and rc != 0:
            raise AnsibleConnectionFailure(err)
        return rc, out, err

    def _get_prompt(self):
        """
        Returns the current prompt from the device

        :returns: A byte string of the prompt
        """
        for cmd in (b'\n', b'prompt()'):
            rc, out, err = self._exec_cli_command(cmd)
        return out

    def on_open_shell(self):
        """Called after the SSH session is established

        This method is called right after the invoke_shell() is called from
        the Paramiko SSHClient instance.  It provides an opportunity to setup
        terminal parameters such as disbling paging for instance.
        """
        pass

    def on_close_shell(self):
        """Called before the connection is closed

        This method gets called once the connection close has been requested
        but before the connection is actually closed.  It provides an
        opportunity to clean up any terminal resources before the shell is
        actually closed
        """
        pass

    def on_authorize(self, passwd=None):
        """Called when privilege escalation is requested

        :kwarg passwd: String containing the password

        This method is called when the privilege is requested to be elevated
        in the play context by setting become to True.  It is the responsibility
        of the terminal plugin to actually do the privilege escalation such
        as entering `enable` mode for instance
        """
        pass

    def on_deauthorize(self):
        """Called when privilege deescalation is requested

        This method is called when the privilege changed from escalated
        (become=True) to non escalated (become=False).  It is the responsibility
        of this method to actually perform the deauthorization procedure
        """
        pass
