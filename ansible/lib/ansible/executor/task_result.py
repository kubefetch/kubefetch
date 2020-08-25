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

from copy import deepcopy

from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import strip_internal_keys

_IGNORE = tuple()
_PRESERVE = ('attempts', 'changed', 'retries', 'failed', 'unreachable', 'skipped')


class TaskResult:
    '''
    This class is responsible for interpreting the resulting data
    from an executed task, and provides helper methods for determining
    the result of a given task.
    '''

    def __init__(self, host, task, return_data, task_fields=None):
        self._host = host
        self._task = task

        if isinstance(return_data, dict):
            self._result = return_data.copy()
        else:
            self._result = DataLoader().load(return_data)

        if task_fields is None:
            self._task_fields = dict()
        else:
            self._task_fields = task_fields

    @property
    def task_name(self):
        return self._task_fields.get('name', None) or self._task.get_name()

    def is_changed(self):
        return self._check_key('changed')

    def is_skipped(self):
        # loop results
        if 'results' in self._result:
            results = self._result['results']
            # Loop tasks are only considered skipped if all items were skipped.
            # some squashed results (eg, yum) are not dicts and can't be skipped individually
            if results and all(isinstance(res, dict) and res.get('skipped', False) for res in results):
                return True

        # regular tasks and squashed non-dict results
        return self._result.get('skipped', False)

    def is_failed(self):
        if 'failed_when_result' in self._result or \
           'results' in self._result and True in [True for x in self._result['results'] if 'failed_when_result' in x]:
            return self._check_key('failed_when_result')
        else:
            return self._check_key('failed')

    def is_unreachable(self):
        return self._check_key('unreachable')

    def _check_key(self, key):
        '''get a specific key from the result or it's items'''

        if isinstance(self._result, dict) and key in self._result:
            return self._result.get(key, False)
        else:
            flag = False
            for res in self._result.get('results', []):
                if isinstance(res, dict):
                    flag |= res.get(key, False)
            return flag

    def clean_copy(self):

        ''' returns 'clean' taskresult object '''

        # FIXME: clean task_fields, _task and _host copies
        result = TaskResult(self._host, self._task, {}, self._task_fields)

        # statuses are already reflected on the event type
        if result._task and result._task.action in ['debug']:
            # debug is verbose by default to display vars, no need to add invocation
            ignore = _IGNORE + ('invocation',)
        else:
            ignore = _IGNORE

        if self._task.no_log or self._result.get('_ansible_no_log', False):
            x = {"censored": "the output has been hidden due to the fact that 'no_log: true' was specified for this result"}
            for preserve in _PRESERVE:
                if preserve in self._result:
                    x[preserve] = self._result[preserve]
            result._result = x
        elif self._result:
            result._result = deepcopy(self._result)

            # actualy remove
            for remove_key in ignore:
                if remove_key in result._result:
                    del result._result[remove_key]

            # remove almost ALL internal keys, keep ones relevant to callback
            strip_internal_keys(result._result, exceptions=('_ansible_verbose_always', '_ansible_item_label', '_ansible_no_log'))

        return result
