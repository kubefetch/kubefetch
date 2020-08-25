#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# (c) 2015, Brian Coca <bcoca@ansible.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['stableinterface'],
                    'supported_by': 'community'}


# This is a modification of @bcoca's `svc` module

DOCUMENTATION = '''
---
module: runit
author: "James Sumners (@jsumners)"
version_added: "2.3"
short_description:  Manage runit services.
description:
    - Controls runit services on remote hosts using the sv utility.
options:
    name:
        required: true
        description:
            - Name of the service to manage.
    state:
        required: false
        choices: [ started, stopped, restarted, killed, reloaded, once ]
        description:
            - C(started)/C(stopped) are idempotent actions that will not run
              commands unless necessary.  C(restarted) will always bounce the
              service (sv restart) and C(killed) will always bounce the service (sv force-stop).
              C(reloaded) will send a HUP (sv reload).
              C(once) will run a normally downed sv once (sv once), not really
              an idempotent operation.
    enabled:
        required: false
        choices: [ "yes", "no" ]
        description:
            - Wheater the service is enabled or not, if disabled it also implies stopped.
    service_dir:
        required: false
        default: /var/service
        description:
            - directory runsv watches for services
    service_src:
        required: false
        default: /etc/sv
        description:
            - directory where services are defined, the source of symlinks to service_dir.
'''

EXAMPLES = '''
# Example action to start sv dnscache, if not running
 - runit:
    name: dnscache
    state: started

# Example action to stop sv dnscache, if running
 - runit:
    name: dnscache
    state: stopped

# Example action to kill sv dnscache, in all cases
 - runit:
    name: dnscache
    state: killed

# Example action to restart sv dnscache, in all cases
 - runit:
    name: dnscache
    state: restarted

# Example action to reload sv dnscache, in all cases
 - runit:
    name: dnscache
    state: reloaded

# Example using alt sv directory location
 - runit:
    name: dnscache
    state: reloaded
    service_dir: /run/service
'''

import os
import re
import traceback

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_native


def _load_dist_subclass(cls, *args, **kwargs):
    '''
    Used for derivative implementations
    '''
    subclass = None

    distro = kwargs['module'].params['distro']

    # get the most specific superclass for this platform
    if distro is not None:
        for sc in cls.__subclasses__():
            if sc.distro is not None and sc.distro == distro:
                subclass = sc
    if subclass is None:
        subclass = cls

    return super(cls, subclass).__new__(subclass)

class Sv(object):
    """
    Main class that handles daemontools, can be subclassed and overridden in case
    we want to use a 'derivative' like encore, s6, etc
    """


    #def __new__(cls, *args, **kwargs):
    #    return _load_dist_subclass(cls, args, kwargs)



    def __init__(self, module):
        self.extra_paths = [ ]
        self.report_vars = ['state', 'enabled', 'svc_full', 'src_full', 'pid', 'duration', 'full_state']

        self.module         = module

        self.name           = module.params['name']
        self.service_dir    = module.params['service_dir']
        self.service_src    = module.params['service_src']
        self.enabled        = None
        self.full_state     = None
        self.state          = None
        self.pid            = None
        self.duration       = None

        self.svc_cmd        = module.get_bin_path('sv', opt_dirs=self.extra_paths)
        self.svstat_cmd     = module.get_bin_path('sv', opt_dirs=self.extra_paths)
        self.svc_full = '/'.join([ self.service_dir, self.name ])
        self.src_full = '/'.join([ self.service_src, self.name ])

        self.enabled = os.path.lexists(self.svc_full)
        if self.enabled:
            self.get_status()
        else:
            self.state = 'stopped'


    def enable(self):
        if os.path.exists(self.src_full):
            try:
                os.symlink(self.src_full, self.svc_full)
            except OSError as e:
                self.module.fail_json(path=self.src_full, msg='Error while linking: %s' % to_native(e))
        else:
            self.module.fail_json(msg="Could not find source for service to enable (%s)." % self.src_full)

    def disable(self):
        self.execute_command([self.svc_cmd,'force-stop',self.src_full])
        try:
            os.unlink(self.svc_full)
        except OSError as e:
            self.module.fail_json(path=self.svc_full, msg='Error while unlinking: %s' % to_native(e))

    def get_status(self):
        (rc, out, err) = self.execute_command([self.svstat_cmd, 'status', self.svc_full])

        if err is not None and err:
            self.full_state = self.state = err
        else:
            self.full_state = out

            m = re.search('\(pid (\d+)\)', out)
            if m:
                self.pid = m.group(1)

            m = re.search(' (\d+)s', out)
            if m:
                self.duration = m.group(1)

            if re.search('run:', out):
                self.state = 'started'
            elif re.search('down:', out):
                self.state = 'stopped'
            else:
                self.state = 'unknown'
                return

    def started(self):
        return self.start()

    def start(self):
        return self.execute_command([self.svc_cmd, 'start', self.svc_full])

    def stopped(self):
        return self.stop()

    def stop(self):
        return self.execute_command([self.svc_cmd, 'stop', self.svc_full])

    def once(self):
        return self.execute_command([self.svc_cmd, 'once', self.svc_full])

    def reloaded(self):
        return self.reload()

    def reload(self):
        return self.execute_command([self.svc_cmd, 'reload', self.svc_full])

    def restarted(self):
        return self.restart()

    def restart(self):
        return self.execute_command([self.svc_cmd, 'restart', self.svc_full])

    def killed(self):
        return self.kill()

    def kill(self):
        return self.execute_command([self.svc_cmd, 'force-stop', self.svc_full])

    def execute_command(self, cmd):
        try:
            (rc, out, err) = self.module.run_command(' '.join(cmd))
        except Exception as e:
            self.module.fail_json(msg="failed to execute: %s" % to_native(e), exception=traceback.format_exc())
        return (rc, out, err)

    def report(self):
        self.get_status()
        states = {}
        for k in self.report_vars:
            states[k] = self.__dict__[k]
        return states

# ===========================================
# Main control flow

def main():
    module = AnsibleModule(
        argument_spec = dict(
            name = dict(required=True),
            state = dict(choices=['started', 'stopped', 'restarted', 'killed', 'reloaded', 'once']),
            enabled = dict(required=False, type='bool'),
            dist = dict(required=False, default='runit'),
            service_dir = dict(required=False, default='/var/service'),
            service_src = dict(required=False, default='/etc/sv'),
        ),
        supports_check_mode=True,
    )

    module.run_command_environ_update = dict(LANG='C', LC_ALL='C', LC_MESSAGES='C', LC_CTYPE='C')

    state = module.params['state']
    enabled = module.params['enabled']

    sv = Sv(module)
    changed = False
    orig_state = sv.report()

    if enabled is not None and enabled != sv.enabled:
        changed = True
        if not module.check_mode:
            try:
                if enabled:
                    sv.enable()
                else:
                    sv.disable()
            except (OSError, IOError) as e:
                module.fail_json(msg="Could not change service link: %s" % to_native(e), exception=traceback.format_exc())

    if state is not None and state != sv.state:
        changed = True
        if not module.check_mode:
            getattr(sv,state)()

    module.exit_json(changed=changed, sv=sv.report())


if __name__ == '__main__':
    main()
