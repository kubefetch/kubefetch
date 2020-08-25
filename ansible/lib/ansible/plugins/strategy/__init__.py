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

import functools
import os
import threading
import time

from collections import deque
from multiprocessing import Lock
from jinja2.exceptions import UndefinedError

from ansible import constants as C
from ansible.errors import AnsibleError, AnsibleParserError, AnsibleUndefinedVariable
from ansible.executor import action_write_locks
from ansible.executor.process.worker import WorkerProcess
from ansible.executor.task_result import TaskResult
from ansible.inventory.host import Host
from ansible.module_utils.six.moves import queue as Queue
from ansible.module_utils.six import iteritems, string_types
from ansible.module_utils._text import to_text
from ansible.playbook.helpers import load_list_of_blocks
from ansible.playbook.included_file import IncludedFile
from ansible.playbook.task_include import TaskInclude
from ansible.playbook.role_include import IncludeRole
from ansible.plugins.loader import action_loader, connection_loader, filter_loader, lookup_loader, module_loader, test_loader
from ansible.template import Templar
from ansible.utils.vars import combine_vars
from ansible.vars.manager import strip_internal_keys


try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

__all__ = ['StrategyBase']


class StrategySentinel:
    pass


# TODO: this should probably be in the plugins/__init__.py, with
#       a smarter mechanism to set all of the attributes based on
#       the loaders created there
class SharedPluginLoaderObj:
    '''
    A simple object to make pass the various plugin loaders to
    the forked processes over the queue easier
    '''
    def __init__(self):
        self.action_loader = action_loader
        self.connection_loader = connection_loader
        self.filter_loader = filter_loader
        self.test_loader = test_loader
        self.lookup_loader = lookup_loader
        self.module_loader = module_loader

_sentinel = StrategySentinel()


def results_thread_main(strategy):
    while True:
        try:
            result = strategy._final_q.get()
            if isinstance(result, StrategySentinel):
                break
            else:
                strategy._results_lock.acquire()
                strategy._results.append(result)
                strategy._results_lock.release()
        except (IOError, EOFError):
            break
        except Queue.Empty:
            pass


def debug_closure(func):
    """
    A stub reimplementation of the debug_closure used in devel, required
    for a later fix that built on top of the work done to move debugging
    into StrategyBase.
    """
    @functools.wraps(func)
    def inner(self, iterator, one_pass=False, max_passes=None):
        _processed_results = []
        results = func(self, iterator, one_pass=one_pass, max_passes=max_passes)
        for result in results:
            task = result._task
            host = result._host
            _queued_task_args = self._queued_task_cache.pop((host.name, task._uuid), None)
            _processed_results.append(result)
        return _processed_results
    return inner


class StrategyBase:

    '''
    This is the base class for strategy plugins, which contains some common
    code useful to all strategies like running handlers, cleanup actions, etc.
    '''

    def __init__(self, tqm):
        self._tqm = tqm
        self._inventory = tqm.get_inventory()
        self._workers = tqm.get_workers()
        self._notified_handlers = tqm._notified_handlers
        self._listening_handlers = tqm._listening_handlers
        self._variable_manager = tqm.get_variable_manager()
        self._loader = tqm.get_loader()
        self._final_q = tqm._final_q
        self._step = getattr(tqm._options, 'step', False)
        self._diff = getattr(tqm._options, 'diff', False)

        # the task cache is a dictionary of tuples of (host.name, task._uuid)
        # used to find the original task object of in-flight tasks and to store
        # the task args/vars and play context info used to queue the task.
        self._queued_task_cache = {}

        # Backwards compat: self._display isn't really needed, just import the global display and use that.
        self._display = display

        # internal counters
        self._pending_results = 0
        self._cur_worker = 0

        # this dictionary is used to keep track of hosts that have
        # outstanding tasks still in queue
        self._blocked_hosts = dict()

        self._results = deque()
        self._results_lock = threading.Condition(threading.Lock())

        # create the result processing thread for reading results in the background
        self._results_thread = threading.Thread(target=results_thread_main, args=(self,))
        self._results_thread.daemon = True
        self._results_thread.start()

    def cleanup(self):
        self._final_q.put(_sentinel)
        self._results_thread.join()

    def run(self, iterator, play_context, result=0):
        # execute one more pass through the iterator without peeking, to
        # make sure that all of the hosts are advanced to their final task.
        # This should be safe, as everything should be ITERATING_COMPLETE by
        # this point, though the strategy may not advance the hosts itself.
        [iterator.get_next_task_for_host(host) for host in self._inventory.get_hosts(iterator._play.hosts) if host.name not in self._tqm._unreachable_hosts]

        # save the failed/unreachable hosts, as the run_handlers()
        # method will clear that information during its execution
        failed_hosts = iterator.get_failed_hosts()
        unreachable_hosts = self._tqm._unreachable_hosts.keys()

        display.debug("running handlers")
        handler_result = self.run_handlers(iterator, play_context)
        if isinstance(handler_result, bool) and not handler_result:
            result |= self._tqm.RUN_ERROR
        elif not handler_result:
            result |= handler_result

        # now update with the hosts (if any) that failed or were
        # unreachable during the handler execution phase
        failed_hosts = set(failed_hosts).union(iterator.get_failed_hosts())
        unreachable_hosts = set(unreachable_hosts).union(self._tqm._unreachable_hosts.keys())

        # return the appropriate code, depending on the status hosts after the run
        if not isinstance(result, bool) and result != self._tqm.RUN_OK:
            return result
        elif len(unreachable_hosts) > 0:
            return self._tqm.RUN_UNREACHABLE_HOSTS
        elif len(failed_hosts) > 0:
            return self._tqm.RUN_FAILED_HOSTS
        else:
            return self._tqm.RUN_OK

    def get_hosts_remaining(self, play):
        return [host for host in self._inventory.get_hosts(play.hosts)
                if host.name not in self._tqm._failed_hosts and host.name not in self._tqm._unreachable_hosts]

    def get_failed_hosts(self, play):
        return [host for host in self._inventory.get_hosts(play.hosts) if host.name in self._tqm._failed_hosts]

    def add_tqm_variables(self, vars, play):
        '''
        Base class method to add extra variables/information to the list of task
        vars sent through the executor engine regarding the task queue manager state.
        '''
        vars['ansible_current_hosts'] = [h.name for h in self.get_hosts_remaining(play)]
        vars['ansible_failed_hosts'] = [h.name for h in self.get_failed_hosts(play)]

    def _queue_task(self, host, task, task_vars, play_context):
        ''' handles queueing the task up to be sent to a worker '''

        display.debug("entering _queue_task() for %s/%s" % (host.name, task.action))

        # Add a write lock for tasks.
        # Maybe this should be added somewhere further up the call stack but
        # this is the earliest in the code where we have task (1) extracted
        # into its own variable and (2) there's only a single code path
        # leading to the module being run.  This is called by three
        # functions: __init__.py::_do_handler_run(), linear.py::run(), and
        # free.py::run() so we'd have to add to all three to do it there.
        # The next common higher level is __init__.py::run() and that has
        # tasks inside of play_iterator so we'd have to extract them to do it
        # there.

        if task.action not in action_write_locks.action_write_locks:
            display.debug('Creating lock for %s' % task.action)
            action_write_locks.action_write_locks[task.action] = Lock()

        # and then queue the new task
        try:

            # create a dummy object with plugin loaders set as an easier
            # way to share them with the forked processes
            shared_loader_obj = SharedPluginLoaderObj()

            queued = False
            starting_worker = self._cur_worker
            while True:
                (worker_prc, rslt_q) = self._workers[self._cur_worker]
                if worker_prc is None or not worker_prc.is_alive():
                    self._queued_task_cache[(host.name, task._uuid)] = {
                        'host': host,
                        'task': task,
                        'task_vars': task_vars,
                        'play_context': play_context
                    }

                    worker_prc = WorkerProcess(self._final_q, task_vars, host, task, play_context, self._loader, self._variable_manager, shared_loader_obj)
                    self._workers[self._cur_worker][0] = worker_prc
                    worker_prc.start()
                    display.debug("worker is %d (out of %d available)" % (self._cur_worker + 1, len(self._workers)))
                    queued = True
                self._cur_worker += 1
                if self._cur_worker >= len(self._workers):
                    self._cur_worker = 0
                if queued:
                    break
                elif self._cur_worker == starting_worker:
                    time.sleep(0.0001)

            self._pending_results += 1
        except (EOFError, IOError, AssertionError) as e:
            # most likely an abort
            display.debug("got an error while queuing: %s" % e)
            return
        display.debug("exiting _queue_task() for %s/%s" % (host.name, task.action))

    def get_task_hosts(self, iterator, task_host, task):
        if task.run_once:
            host_list = [host for host in self._inventory.get_hosts(iterator._play.hosts) if host.name not in self._tqm._unreachable_hosts]
        else:
            host_list = [task_host]
        return host_list

    def get_delegated_hosts(self, result, task):
        host_name = result.get('_ansible_delegated_vars', {}).get('ansible_delegated_host', None)
        if host_name is not None:
            actual_host = self._inventory.get_host(host_name)
            if actual_host is None:
                actual_host = Host(name=host_name)
        else:
            actual_host = Host(name=task.delegate_to)

        return [actual_host]

    @debug_closure
    def _process_pending_results(self, iterator, one_pass=False, max_passes=None):
        '''
        Reads results off the final queue and takes appropriate action
        based on the result (executing callbacks, updating state, etc.).
        '''

        ret_results = []

        def get_original_host(host_name):
            # FIXME: this should not need x2 _inventory
            host_name = to_text(host_name)
            if host_name in self._inventory.hosts:
                return self._inventory.hosts[host_name]
            else:
                return self._inventory.get_host(host_name)

        def search_handler_blocks_by_name(handler_name, handler_blocks):
            for handler_block in handler_blocks:
                for handler_task in handler_block.block:
                    if handler_task.name:
                        handler_vars = self._variable_manager.get_vars(play=iterator._play, task=handler_task)
                        templar = Templar(loader=self._loader, variables=handler_vars)
                        try:
                            # first we check with the full result of get_name(), which may
                            # include the role name (if the handler is from a role). If that
                            # is not found, we resort to the simple name field, which doesn't
                            # have anything extra added to it.
                            target_handler_name = templar.template(handler_task.name)
                            if target_handler_name == handler_name:
                                return handler_task
                            else:
                                target_handler_name = templar.template(handler_task.get_name())
                                if target_handler_name == handler_name:
                                    return handler_task
                        except (UndefinedError, AnsibleUndefinedVariable):
                            # We skip this handler due to the fact that it may be using
                            # a variable in the name that was conditionally included via
                            # set_fact or some other method, and we don't want to error
                            # out unnecessarily
                            continue
            return None

        def search_handler_blocks_by_uuid(handler_uuid, handler_blocks):
            for handler_block in handler_blocks:
                for handler_task in handler_block.block:
                    if handler_uuid == handler_task._uuid:
                        return handler_task
            return None

        def parent_handler_match(target_handler, handler_name):
            if target_handler:
                if isinstance(target_handler, (TaskInclude, IncludeRole)):
                    try:
                        handler_vars = self._variable_manager.get_vars(play=iterator._play, task=target_handler)
                        templar = Templar(loader=self._loader, variables=handler_vars)
                        target_handler_name = templar.template(target_handler.name)
                        if target_handler_name == handler_name:
                            return True
                        else:
                            target_handler_name = templar.template(target_handler.get_name())
                            if target_handler_name == handler_name:
                                return True
                    except (UndefinedError, AnsibleUndefinedVariable):
                        pass
                return parent_handler_match(target_handler._parent, handler_name)
            else:
                return False

        cur_pass = 0
        while True:
            try:
                self._results_lock.acquire()
                task_result = self._results.popleft()
            except IndexError:
                break
            finally:
                self._results_lock.release()

            # get the original host and task. We then assign them to the TaskResult for use in callbacks/etc.
            original_host = get_original_host(task_result._host)
            queue_cache_entry = (original_host.name, task_result._task)
            found_task = self._queued_task_cache.get(queue_cache_entry)['task']
            original_task = found_task.copy(exclude_parent=True, exclude_tasks=True)
            original_task._parent = found_task._parent
            original_task.from_attrs(task_result._task_fields)

            task_result._host = original_host
            task_result._task = original_task

            # get the correct loop var for use later
            if original_task.loop_control:
                loop_var = original_task.loop_control.loop_var or 'item'
            else:
                loop_var = 'item'

            # send callbacks for 'non final' results
            if '_ansible_retry' in task_result._result:
                self._tqm.send_callback('v2_runner_retry', task_result)
                continue
            elif '_ansible_item_result' in task_result._result:
                if task_result.is_failed() or task_result.is_unreachable():
                    self._tqm.send_callback('v2_runner_item_on_failed', task_result)
                elif task_result.is_skipped():
                    self._tqm.send_callback('v2_runner_item_on_skipped', task_result)
                else:
                    if 'diff' in task_result._result:
                        if self._diff:
                            self._tqm.send_callback('v2_on_file_diff', task_result)
                    self._tqm.send_callback('v2_runner_item_on_ok', task_result)
                continue

            if original_task.register:
                host_list = self.get_task_hosts(iterator, original_host, original_task)

                clean_copy = strip_internal_keys(task_result._result)
                if 'invocation' in clean_copy:
                    del clean_copy['invocation']

                for target_host in host_list:
                    self._variable_manager.set_nonpersistent_facts(target_host, {original_task.register: clean_copy})

            # all host status messages contain 2 entries: (msg, task_result)
            role_ran = False
            if task_result.is_failed():
                role_ran = True
                ignore_errors = original_task.ignore_errors
                if not ignore_errors:
                    display.debug("marking %s as failed" % original_host.name)
                    if original_task.run_once:
                        # if we're using run_once, we have to fail every host here
                        for h in self._inventory.get_hosts(iterator._play.hosts):
                            if h.name not in self._tqm._unreachable_hosts:
                                state, _ = iterator.get_next_task_for_host(h, peek=True)
                                iterator.mark_host_failed(h)
                                state, new_task = iterator.get_next_task_for_host(h, peek=True)
                    else:
                        iterator.mark_host_failed(original_host)

                    # increment the failed count for this host
                    self._tqm._stats.increment('failures', original_host.name)

                    # grab the current state and if we're iterating on the rescue portion
                    # of a block then we save the failed task in a special var for use
                    # within the rescue/always
                    state, _ = iterator.get_next_task_for_host(original_host, peek=True)

                    if iterator.is_failed(original_host) and state and state.run_state == iterator.ITERATING_COMPLETE:
                        self._tqm._failed_hosts[original_host.name] = True

                    if state and state.run_state == iterator.ITERATING_RESCUE:
                        self._variable_manager.set_nonpersistent_facts(
                            original_host,
                            dict(
                                ansible_failed_task=original_task.serialize(),
                                ansible_failed_result=task_result._result,
                            ),
                        )
                else:
                    self._tqm._stats.increment('ok', original_host.name)
                    if 'changed' in task_result._result and task_result._result['changed']:
                        self._tqm._stats.increment('changed', original_host.name)
                self._tqm.send_callback('v2_runner_on_failed', task_result, ignore_errors=ignore_errors)
            elif task_result.is_unreachable():
                self._tqm._unreachable_hosts[original_host.name] = True
                iterator._play._removed_hosts.append(original_host.name)
                self._tqm._stats.increment('dark', original_host.name)
                self._tqm.send_callback('v2_runner_on_unreachable', task_result)
            elif task_result.is_skipped():
                self._tqm._stats.increment('skipped', original_host.name)
                self._tqm.send_callback('v2_runner_on_skipped', task_result)
            else:
                role_ran = True

                if original_task.loop:
                    # this task had a loop, and has more than one result, so
                    # loop over all of them instead of a single result
                    result_items = task_result._result.get('results', [])
                else:
                    result_items = [task_result._result]

                for result_item in result_items:
                    if '_ansible_notify' in result_item:
                        if task_result.is_changed():
                            # The shared dictionary for notified handlers is a proxy, which
                            # does not detect when sub-objects within the proxy are modified.
                            # So, per the docs, we reassign the list so the proxy picks up and
                            # notifies all other threads
                            for handler_name in result_item['_ansible_notify']:
                                found = False
                                # Find the handler using the above helper.  First we look up the
                                # dependency chain of the current task (if it's from a role), otherwise
                                # we just look through the list of handlers in the current play/all
                                # roles and use the first one that matches the notify name
                                target_handler = search_handler_blocks_by_name(handler_name, iterator._play.handlers)
                                if target_handler is not None:
                                    found = True
                                    if target_handler._uuid not in self._notified_handlers:
                                        self._notified_handlers[target_handler._uuid] = []
                                    if original_host not in self._notified_handlers[target_handler._uuid]:
                                        self._notified_handlers[target_handler._uuid].append(original_host)
                                        # FIXME: should this be a callback?
                                        display.vv("NOTIFIED HANDLER %s" % (handler_name,))
                                else:
                                    # As there may be more than one handler with the notified name as the
                                    # parent, so we just keep track of whether or not we found one at all
                                    for target_handler_uuid in self._notified_handlers:
                                        target_handler = search_handler_blocks_by_uuid(target_handler_uuid, iterator._play.handlers)
                                        if target_handler and parent_handler_match(target_handler, handler_name):
                                            found = True
                                            if original_host not in self._notified_handlers[target_handler._uuid]:
                                                self._notified_handlers[target_handler._uuid].append(original_host)
                                                display.vv("NOTIFIED HANDLER %s" % (target_handler.get_name(),))

                                if handler_name in self._listening_handlers:
                                    for listening_handler_uuid in self._listening_handlers[handler_name]:
                                        listening_handler = search_handler_blocks_by_uuid(listening_handler_uuid, iterator._play.handlers)
                                        if listening_handler is not None:
                                            found = True
                                        else:
                                            continue
                                        if original_host not in self._notified_handlers[listening_handler._uuid]:
                                            self._notified_handlers[listening_handler._uuid].append(original_host)
                                            display.vv("NOTIFIED HANDLER %s" % (listening_handler.get_name(),))

                                # and if none were found, then we raise an error
                                if not found:
                                    msg = ("The requested handler '%s' was not found in either the main handlers list nor in the listening "
                                           "handlers list" % handler_name)
                                    if C.ERROR_ON_MISSING_HANDLER:
                                        raise AnsibleError(msg)
                                    else:
                                        display.warning(msg)

                    if 'add_host' in result_item:
                        # this task added a new host (add_host module)
                        new_host_info = result_item.get('add_host', dict())
                        self._add_host(new_host_info, iterator)

                    elif 'add_group' in result_item:
                        # this task added a new group (group_by module)
                        self._add_group(original_host, result_item)

                    if 'ansible_facts' in result_item:

                        # if delegated fact and we are delegating facts, we need to change target host for them
                        if original_task.delegate_to is not None and original_task.delegate_facts:
                            host_list = self.get_delegated_hosts(result_item, original_task)
                        else:
                            host_list = self.get_task_hosts(iterator, original_host, original_task)

                        if original_task.action == 'include_vars':
                            for (var_name, var_value) in iteritems(result_item['ansible_facts']):
                                # find the host we're actually referring too here, which may
                                # be a host that is not really in inventory at all
                                for target_host in host_list:
                                    self._variable_manager.set_host_variable(target_host, var_name, var_value)
                        else:
                            cacheable = result_item.pop('ansible_facts_cacheable', True)
                            for target_host in host_list:
                                if cacheable:
                                    self._variable_manager.set_host_facts(target_host, result_item['ansible_facts'].copy())

                                # If we are setting a fact, it should populate non_persistent_facts as well
                                self._variable_manager.set_nonpersistent_facts(target_host, result_item['ansible_facts'].copy())

                    if 'ansible_stats' in result_item and 'data' in result_item['ansible_stats'] and result_item['ansible_stats']['data']:

                        if 'per_host' not in result_item['ansible_stats'] or result_item['ansible_stats']['per_host']:
                            host_list = self.get_task_hosts(iterator, original_host, original_task)
                        else:
                            host_list = [None]

                        data = result_item['ansible_stats']['data']
                        aggregate = 'aggregate' in result_item['ansible_stats'] and result_item['ansible_stats']['aggregate']
                        for myhost in host_list:
                            for k in data.keys():
                                if aggregate:
                                    self._tqm._stats.update_custom_stats(k, data[k], myhost)
                                else:
                                    self._tqm._stats.set_custom_stats(k, data[k], myhost)

                if 'diff' in task_result._result:
                    if self._diff:
                        self._tqm.send_callback('v2_on_file_diff', task_result)

                if not isinstance(original_task, TaskInclude):
                    self._tqm._stats.increment('ok', original_host.name)
                    if 'changed' in task_result._result and task_result._result['changed']:
                        self._tqm._stats.increment('changed', original_host.name)

                # finally, send the ok for this task
                self._tqm.send_callback('v2_runner_on_ok', task_result)

            self._pending_results -= 1
            if original_host.name in self._blocked_hosts:
                del self._blocked_hosts[original_host.name]

            # If this is a role task, mark the parent role as being run (if
            # the task was ok or failed, but not skipped or unreachable)
            if original_task._role is not None and role_ran:  # TODO:  and original_task.action != 'include_role':?
                # lookup the role in the ROLE_CACHE to make sure we're dealing
                # with the correct object and mark it as executed
                for (entry, role_obj) in iteritems(iterator._play.ROLE_CACHE[original_task._role._role_name]):
                    if role_obj._uuid == original_task._role._uuid:
                        role_obj._had_task_run[original_host.name] = True

            ret_results.append(task_result)

            if one_pass or max_passes is not None and (cur_pass + 1) >= max_passes:
                break

            cur_pass += 1

        return ret_results

    def _wait_on_pending_results(self, iterator):
        '''
        Wait for the shared counter to drop to zero, using a short sleep
        between checks to ensure we don't spin lock
        '''

        ret_results = []

        display.debug("waiting for pending results...")
        while self._pending_results > 0 and not self._tqm._terminated:

            if self._tqm.has_dead_workers():
                raise AnsibleError("A worker was found in a dead state")

            results = self._process_pending_results(iterator)
            ret_results.extend(results)
            if self._pending_results > 0:
                time.sleep(C.DEFAULT_INTERNAL_POLL_INTERVAL)

        display.debug("no more pending results, returning what we have")

        return ret_results

    def _add_host(self, host_info, iterator):
        '''
        Helper function to add a new host to inventory based on a task result.
        '''

        if host_info:
            host_name = host_info.get('host_name')

            # Check if host in inventory, add if not
            if host_name not in self._inventory.hosts:
                self._inventory.add_host(host_name, 'all')
            new_host = self._inventory.hosts.get(host_name)

            # Set/update the vars for this host
            new_host.vars = combine_vars(new_host.get_vars(), host_info.get('host_vars', dict()))

            new_groups = host_info.get('groups', [])
            for group_name in new_groups:
                if group_name not in self._inventory.groups:
                    self._inventory.add_group(group_name)
                new_group = self._inventory.groups[group_name]
                new_group.add_host(self._inventory.hosts[host_name])

            # reconcile inventory, ensures inventory rules are followed
            self._inventory.reconcile_inventory()

    def _add_group(self, host, result_item):
        '''
        Helper function to add a group (if it does not exist), and to assign the
        specified host to that group.
        '''

        changed = False

        # the host here is from the executor side, which means it was a
        # serialized/cloned copy and we'll need to look up the proper
        # host object from the master inventory
        real_host = self._inventory.hosts[host.name]
        group_name = result_item.get('add_group')
        parent_group_names = result_item.get('parent_groups', [])

        for name in [group_name] + parent_group_names:
            if name not in self._inventory.groups:
                # create the new group and add it to inventory
                self._inventory.add_group(name)
                changed = True
        group = self._inventory.groups[group_name]
        for parent_group_name in parent_group_names:
            parent_group = self._inventory.groups[parent_group_name]
            parent_group.add_child_group(group)

        if real_host.name not in group.get_hosts():
            group.add_host(real_host)
            changed = True

        if group_name not in host.get_groups():
            real_host.add_group(group)
            changed = True

        if changed:
            self._inventory.reconcile_inventory()

        return changed

    def _copy_included_file(self, included_file):
        '''
        A proven safe and performant way to create a copy of an included file
        '''
        ti_copy = included_file._task.copy(exclude_parent=True)
        ti_copy._parent = included_file._task._parent

        temp_vars = ti_copy.vars.copy()
        temp_vars.update(included_file._args)

        ti_copy.vars = temp_vars

        return ti_copy

    def _load_included_file(self, included_file, iterator, is_handler=False):
        '''
        Loads an included YAML file of tasks, applying the optional set of variables.
        '''

        display.debug("loading included file: %s" % included_file._filename)
        try:
            data = self._loader.load_from_file(included_file._filename)
            if data is None:
                return []
            elif not isinstance(data, list):
                raise AnsibleError("included task files must contain a list of tasks")

            ti_copy = self._copy_included_file(included_file)
            # pop tags out of the include args, if they were specified there, and assign
            # them to the include. If the include already had tags specified, we raise an
            # error so that users know not to specify them both ways
            tags = included_file._task.vars.pop('tags', [])
            if isinstance(tags, string_types):
                tags = tags.split(',')
            if len(tags) > 0:
                if len(included_file._task.tags) > 0:
                    raise AnsibleParserError("Include tasks should not specify tags in more than one way (both via args and directly on the task). "
                                             "Mixing tag specify styles is prohibited for whole import hierarchy, not only for single import statement",
                                             obj=included_file._task._ds)
                display.deprecated("You should not specify tags in the include parameters. All tags should be specified using the task-level option")
                included_file._task.tags = tags

            block_list = load_list_of_blocks(
                data,
                play=iterator._play,
                parent_block=None,
                task_include=ti_copy,
                role=included_file._task._role,
                use_handlers=is_handler,
                loader=self._loader,
                variable_manager=self._variable_manager,
            )

            # since we skip incrementing the stats when the task result is
            # first processed, we do so now for each host in the list
            for host in included_file._hosts:
                self._tqm._stats.increment('ok', host.name)

        except AnsibleError as e:
            # mark all of the hosts including this file as failed, send callbacks,
            # and increment the stats for this host
            for host in included_file._hosts:
                tr = TaskResult(host=host, task=included_file._task, return_data=dict(failed=True, reason=to_text(e)))
                iterator.mark_host_failed(host)
                self._tqm._failed_hosts[host.name] = True
                self._tqm._stats.increment('failures', host.name)
                self._tqm.send_callback('v2_runner_on_failed', tr)
            return []

        # finally, send the callback and return the list of blocks loaded
        self._tqm.send_callback('v2_playbook_on_include', included_file)
        display.debug("done processing included file")
        return block_list

    def run_handlers(self, iterator, play_context):
        '''
        Runs handlers on those hosts which have been notified.
        '''

        result = self._tqm.RUN_OK

        for handler_block in iterator._play.handlers:
            # FIXME: handlers need to support the rescue/always portions of blocks too,
            #        but this may take some work in the iterator and gets tricky when
            #        we consider the ability of meta tasks to flush handlers
            for handler in handler_block.block:
                if handler._uuid in self._notified_handlers and len(self._notified_handlers[handler._uuid]):
                    result = self._do_handler_run(handler, handler.get_name(), iterator=iterator, play_context=play_context)
                    if not result:
                        break
        return result

    def _do_handler_run(self, handler, handler_name, iterator, play_context, notified_hosts=None):

        # FIXME: need to use iterator.get_failed_hosts() instead?
        # if not len(self.get_hosts_remaining(iterator._play)):
        #     self._tqm.send_callback('v2_playbook_on_no_hosts_remaining')
        #     result = False
        #     break
        saved_name = handler.name
        handler.name = handler_name
        self._tqm.send_callback('v2_playbook_on_handler_task_start', handler)
        handler.name = saved_name

        if notified_hosts is None:
            notified_hosts = self._notified_handlers[handler._uuid]

        run_once = False
        try:
            action = action_loader.get(handler.action, class_only=True)
            if handler.run_once or getattr(action, 'BYPASS_HOST_LOOP', False):
                run_once = True
        except KeyError:
            # we don't care here, because the action may simply not have a
            # corresponding action plugin
            pass

        host_results = []
        for host in notified_hosts:
            if not handler.has_triggered(host) and (not iterator.is_failed(host) or play_context.force_handlers):
                task_vars = self._variable_manager.get_vars(play=iterator._play, host=host, task=handler)
                self.add_tqm_variables(task_vars, play=iterator._play)
                self._queue_task(host, handler, task_vars, play_context)
                if run_once:
                    break

        # collect the results from the handler run
        host_results = self._wait_on_pending_results(iterator)

        try:
            included_files = IncludedFile.process_include_results(
                host_results,
                self._tqm,
                iterator=iterator,
                inventory=self._inventory,
                loader=self._loader,
                variable_manager=self._variable_manager
            )
        except AnsibleError as e:
            return False

        result = True
        if len(included_files) > 0:
            for included_file in included_files:
                try:
                    new_blocks = self._load_included_file(included_file, iterator=iterator, is_handler=True)
                    # for every task in each block brought in by the include, add the list
                    # of hosts which included the file to the notified_handlers dict
                    for block in new_blocks:
                        iterator._play.handlers.append(block)
                        iterator.cache_block_tasks(block)
                        for task in block.block:
                            result = self._do_handler_run(
                                handler=task,
                                handler_name=None,
                                iterator=iterator,
                                play_context=play_context,
                                notified_hosts=included_file._hosts[:],
                            )
                            if not result:
                                break
                except AnsibleError as e:
                    for host in included_file._hosts:
                        iterator.mark_host_failed(host)
                        self._tqm._failed_hosts[host.name] = True
                    display.warning(str(e))
                    continue

        # wipe the notification list
        self._notified_handlers[handler._uuid] = []
        display.debug("done running handlers, result is: %s" % result)
        return result

    def _take_step(self, task, host=None):

        ret = False
        msg = u'Perform task: %s ' % task
        if host:
            msg += u'on %s ' % host
        msg += u'(N)o/(y)es/(c)ontinue: '
        resp = display.prompt(msg)

        if resp.lower() in ['y', 'yes']:
            display.debug("User ran task")
            ret = True
        elif resp.lower() in ['c', 'continue']:
            display.debug("User ran task and canceled step mode")
            self._step = False
            ret = True
        else:
            display.debug("User skipped task")

        display.banner(msg)

        return ret

    def _execute_meta(self, task, play_context, iterator, target_host):

        # meta tasks store their args in the _raw_params field of args,
        # since they do not use k=v pairs, so get that
        meta_action = task.args.get('_raw_params')

        # FIXME(s):
        # * raise an error or show a warning when a conditional is used
        #   on a meta task that doesn't support them

        def _evaluate_conditional(h):
            all_vars = self._variable_manager.get_vars(play=iterator._play, host=h, task=task)
            templar = Templar(loader=self._loader, variables=all_vars)
            return task.evaluate_conditional(templar, all_vars)

        skipped = False
        msg = ''
        if meta_action == 'noop':
            # FIXME: issue a callback for the noop here?
            msg = "noop"
        elif meta_action == 'flush_handlers':
            self.run_handlers(iterator, play_context)
            msg = "ran handlers"
        elif meta_action == 'refresh_inventory':
            self._inventory.refresh_inventory()
            msg = "inventory successfully refreshed"
        elif meta_action == 'clear_facts':
            if _evaluate_conditional(target_host):
                for host in self._inventory.get_hosts(iterator._play.hosts):
                    hostname = host.get_name()
                    self._variable_manager.clear_facts(hostname)
                msg = "facts cleared"
            else:
                skipped = True
        elif meta_action == 'clear_host_errors':
            if _evaluate_conditional(target_host):
                for host in self._inventory.get_hosts(iterator._play.hosts):
                    self._tqm._failed_hosts.pop(host.name, False)
                    self._tqm._unreachable_hosts.pop(host.name, False)
                    iterator._host_states[host.name].fail_state = iterator.FAILED_NONE
                msg = "cleared host errors"
            else:
                skipped = True
        elif meta_action == 'end_play':
            if _evaluate_conditional(target_host):
                for host in self._inventory.get_hosts(iterator._play.hosts):
                    if host.name not in self._tqm._unreachable_hosts:
                        iterator._host_states[host.name].run_state = iterator.ITERATING_COMPLETE
                msg = "ending play"
        elif meta_action == 'reset_connection':
            connection = connection_loader.get(play_context.connection, play_context, os.devnull)
            play_context.set_options_from_plugin(connection)
            if connection:
                connection.reset()
                msg = 'reset connection'
            else:
                msg = 'no connection, nothing to reset'
        else:
            raise AnsibleError("invalid meta action requested: %s" % meta_action, obj=task._ds)

        result = {'msg': msg}
        if skipped:
            result['skipped'] = True
        else:
            result['changed'] = False

        display.vv("META: %s" % msg)

        return [TaskResult(target_host, task, result)]

    def get_hosts_left(self, iterator):
        ''' returns list of available hosts for this iterator by filtering out unreachables '''

        hosts_left = []
        for host in self._inventory.get_hosts(iterator._play.hosts, order=iterator._play.order):
            if host.name not in self._tqm._unreachable_hosts:
                hosts_left.append(host)
        return hosts_left
