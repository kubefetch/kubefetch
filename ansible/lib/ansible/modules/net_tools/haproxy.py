#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2014, Ravi Bhure <ravibhure@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}


DOCUMENTATION = '''
---
module: haproxy
version_added: "1.9"
short_description: Enable, disable, and set weights for HAProxy backend servers using socket commands.
author: "Ravi Bhure (@ravibhure)"
description:
    - Enable, disable, drain and set weights for HAProxy backend servers using socket
      commands.
notes:
    - Enable, disable and drain commands are restricted and can only be issued on
      sockets configured for level 'admin'. For example, you can add the line
      'stats socket /var/run/haproxy.sock level admin' to the general section of
      haproxy.cfg. See U(http://haproxy.1wt.eu/download/1.5/doc/configuration.txt).
    - Depends on netcat (nc) being available; you need to install the appriate
      package for your operating system before this module can be used.
options:
  backend:
    description:
      - Name of the HAProxy backend pool.
    required: false
    default: auto-detected
  drain:
    description:
      - Wait until the server has no active connections or until the timeout
        determined by wait_interval and wait_retries is reached.  Continue only
        after the status changes to 'MAINT'.  This overrides the
        shutdown_sessions option.
    default: false
    version_added: "2.4"
  host:
    description:
      - Name of the backend host to change.
    required: true
    default: null
  shutdown_sessions:
    description:
      - When disabling a server, immediately terminate all the sessions attached
        to the specified server. This can be used to terminate long-running
        sessions after a server is put into maintenance mode. Overridden by the
        drain option.
    required: false
    default: false
  socket:
    description:
      - Path to the HAProxy socket file.
    required: false
    default: /var/run/haproxy.sock
  state:
    description:
      - Desired state of the provided backend host.
      - Note that C(drain) state was added in version 2.4. It is supported only by HAProxy version 1.5 or later,
        if used on versions < 1.5, it will be ignored.
    required: true
    default: null
    choices: [ "enabled", "disabled", "drain" ]
  fail_on_not_found:
    description:
      - Fail whenever trying to enable/disable a backend host that does not exist
    required: false
    default: false
    version_added: "2.2"
  wait:
    description:
      - Wait until the server reports a status of 'UP' when `state=enabled`,
        status of 'MAINT' when `state=disabled` or status of 'DRAIN' when `state=drain`
    required: false
    default: false
    version_added: "2.0"
  wait_interval:
    description:
      - Number of seconds to wait between retries.
    required: false
    default: 5
    version_added: "2.0"
  wait_retries:
    description:
      - Number of times to check for status after changing the state.
    required: false
    default: 25
    version_added: "2.0"
  weight:
    description:
      - The value passed in argument. If the value ends with the `%` sign, then
        the new weight will be relative to the initially configured weight.
        Relative weights are only permitted between 0 and 100% and absolute
        weights are permitted between 0 and 256.
    required: false
    default: null
'''

EXAMPLES = '''
# disable server in 'www' backend pool
- haproxy:
    state: disabled
    host: '{{ inventory_hostname }}'
    backend: www

# disable server without backend pool name (apply to all available backend pool)
- haproxy:
    state: disabled
    host: '{{ inventory_hostname }}'

# disable server, provide socket file
- haproxy:
    state: disabled
    host: '{{ inventory_hostname }}'
    socket: /var/run/haproxy.sock
    backend: www

# disable server, provide socket file, wait until status reports in maintenance
- haproxy:
    state: disabled
    host: '{{ inventory_hostname }}'
    socket: /var/run/haproxy.sock
    backend: www
    wait: yes

# Place server in drain mode, providing a socket file.  Then check the server's
# status every minute to see if it changes to maintenance mode, continuing if it
# does in an hour and failing otherwise.
- haproxy:
    state: disabled
    host: '{{ inventory_hostname }}'
    socket: /var/run/haproxy.sock
    backend: www
    wait: yes
    drain: yes
    wait_interval: 1
    wait_retries: 60

# disable backend server in 'www' backend pool and drop open sessions to it
- haproxy:
    state: disabled
    host: '{{ inventory_hostname }}'
    backend: www
    socket: /var/run/haproxy.sock
    shutdown_sessions: true

# disable server without backend pool name (apply to all available backend pool) but fail when the backend host is not found
- haproxy:
    state: disabled
    host: '{{ inventory_hostname }}'
    fail_on_not_found: yes

# enable server in 'www' backend pool
- haproxy:
    state: enabled
    host: '{{ inventory_hostname }}'
    backend: www

# enable server in 'www' backend pool wait until healthy
- haproxy:
    state: enabled
    host: '{{ inventory_hostname }}'
    backend: www
    wait: yes

# enable server in 'www' backend pool wait until healthy. Retry 10 times with intervals of 5 seconds to retrieve the health
- haproxy:
    state: enabled
    host: '{{ inventory_hostname }}'
    backend: www
    wait: yes
    wait_retries: 10
    wait_interval: 5

# enable server in 'www' backend pool with change server(s) weight
- haproxy:
    state: enabled
    host: '{{ inventory_hostname }}'
    socket: /var/run/haproxy.sock
    weight: 10
    backend: www

# set the server in 'www' backend pool to drain mode
- haproxy:
    state: drain
    host: '{{ inventory_hostname }}'
    socket: /var/run/haproxy.sock
    backend: www
'''

import csv
import socket
import time
from string import Template

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_bytes, to_text


DEFAULT_SOCKET_LOCATION = "/var/run/haproxy.sock"
RECV_SIZE = 1024
ACTION_CHOICES = ['enabled', 'disabled', 'drain']
WAIT_RETRIES = 25
WAIT_INTERVAL = 5


######################################################################
class TimeoutException(Exception):
    pass


class HAProxy(object):
    """
    Used for communicating with HAProxy through its local UNIX socket interface.
    Perform common tasks in Haproxy related to enable server and
    disable server.

    The complete set of external commands Haproxy handles is documented
    on their website:

    http://haproxy.1wt.eu/download/1.5/doc/configuration.txt#Unix Socket commands
    """

    def __init__(self, module):
        self.module = module

        self.state = self.module.params['state']
        self.host = self.module.params['host']
        self.backend = self.module.params['backend']
        self.weight = self.module.params['weight']
        self.socket = self.module.params['socket']
        self.shutdown_sessions = self.module.params['shutdown_sessions']
        self.fail_on_not_found = self.module.params['fail_on_not_found']
        self.wait = self.module.params['wait']
        self.wait_retries = self.module.params['wait_retries']
        self.wait_interval = self.module.params['wait_interval']
        self.drain = self.module.params['drain']
        self.command_results = {}

    def execute(self, cmd, timeout=200, capture_output=True):
        """
        Executes a HAProxy command by sending a message to a HAProxy's local
        UNIX socket and waiting up to 'timeout' milliseconds for the response.
        """
        self.client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.client.connect(self.socket)
        self.client.sendall(to_bytes('%s\n' % cmd))

        result = b''
        buf = b''
        buf = self.client.recv(RECV_SIZE)
        while buf:
            result += buf
            buf = self.client.recv(RECV_SIZE)
        result = to_text(result, errors='surrogate_or_strict')

        if capture_output:
            self.capture_command_output(cmd, result.strip())
        self.client.close()
        return result

    def capture_command_output(self, cmd, output):
        """
        Capture the output for a command
        """
        if 'command' not in self.command_results:
            self.command_results['command'] = []
        self.command_results['command'].append(cmd)
        if 'output' not in self.command_results:
            self.command_results['output'] = []
        self.command_results['output'].append(output)

    def discover_all_backends(self):
        """
        Discover all entries with svname = 'BACKEND' and return a list of their corresponding
        pxnames
        """
        data = self.execute('show stat', 200, False).lstrip('# ')
        r = csv.DictReader(data.splitlines())
        return tuple(map(lambda d: d['pxname'], filter(lambda d: d['svname'] == 'BACKEND', r)))

    def discover_version(self):
        """
        Attempt to extract the haproxy version.
        Return a tuple containing major and minor version.
        """
        data = self.execute('show info', 200, False)
        lines = data.splitlines()
        line = [x for x in lines if 'Version:' in x]
        try:
            version_values = line[0].partition(':')[2].strip().split('.', 3)
            version = (int(version_values[0]), int(version_values[1]))
        except (ValueError, TypeError, IndexError):
            version = None

        return version

    def execute_for_backends(self, cmd, pxname, svname, wait_for_status=None):
        """
        Run some command on the specified backends. If no backends are provided they will
        be discovered automatically (all backends)
        """
        # Discover backends if none are given
        if pxname is None:
            backends = self.discover_all_backends()
        else:
            backends = [pxname]

        # Run the command for each requested backend
        for backend in backends:
            # Fail when backends were not found
            state = self.get_state_for(backend, svname)
            if (self.fail_on_not_found) and state is None:
                self.module.fail_json(msg="The specified backend '%s/%s' was not found!" % (backend, svname))

            if state is not None:
                self.execute(Template(cmd).substitute(pxname=backend, svname=svname))
                if self.wait:
                    self.wait_until_status(backend, svname, wait_for_status)

    def get_state_for(self, pxname, svname):
        """
        Find the state of specific services. When pxname is not set, get all backends for a specific host.
        Returns a list of dictionaries containing the status and weight for those services.
        """
        data = self.execute('show stat', 200, False).lstrip('# ')
        r = csv.DictReader(data.splitlines())
        state = tuple(
            map(
                lambda d: {'status': d['status'], 'weight': d['weight'], 'scur': d['scur']},
                filter(lambda d: (pxname is None or d['pxname'] == pxname) and d['svname'] == svname, r)
            )
        )
        return state or None

    def wait_until_status(self, pxname, svname, status):
        """
        Wait for a service to reach the specified status. Try RETRIES times
        with INTERVAL seconds of sleep in between. If the service has not reached
        the expected status in that time, the module will fail. If the service was
        not found, the module will fail.
        """
        for i in range(1, self.wait_retries):
            state = self.get_state_for(pxname, svname)

            # We can assume there will only be 1 element in state because both svname and pxname are always set when we get here
            if state[0]['status'] == status:
                if not self.drain or (state[0]['scur'] == '0' and state == 'MAINT'):
                    return True
            else:
                time.sleep(self.wait_interval)

        self.module.fail_json(msg="server %s/%s not status '%s' after %d retries. Aborting." % (pxname, svname, status, self.wait_retries))

    def enabled(self, host, backend, weight):
        """
        Enabled action, marks server to UP and checks are re-enabled,
        also supports to get current weight for server (default) and
        set the weight for haproxy backend server when provides.
        """
        cmd = "get weight $pxname/$svname; enable server $pxname/$svname"
        if weight:
            cmd += "; set weight $pxname/$svname %s" % weight
        self.execute_for_backends(cmd, backend, host, 'UP')

    def disabled(self, host, backend, shutdown_sessions):
        """
        Disabled action, marks server to DOWN for maintenance. In this mode, no more checks will be
        performed on the server until it leaves maintenance,
        also it shutdown sessions while disabling backend host server.
        """
        cmd = "get weight $pxname/$svname; disable server $pxname/$svname"
        if shutdown_sessions:
            cmd += "; shutdown sessions server $pxname/$svname"
        self.execute_for_backends(cmd, backend, host, 'MAINT')

    def drain(self, host, backend, status='DRAIN'):
        """
        Drain action, sets the server to DRAIN mode.
        In this mode mode, the server will not accept any new connections
        other than those that are accepted via persistence.
        """
        haproxy_version = self.discover_version()

        # check if haproxy version suppots DRAIN state (starting with 1.5)
        if haproxy_version and (1, 5) <= haproxy_version:
            cmd = "set server $pxname/$svname state drain"
            self.execute_for_backends(cmd, backend, host, status)

    def act(self):
        """
        Figure out what you want to do from ansible, and then do it.
        """
        # Get the state before the run
        state_before = self.get_state_for(self.backend, self.host)
        self.command_results['state_before'] = state_before

        # toggle enable/disbale server
        if self.state == 'enabled':
            self.enabled(self.host, self.backend, self.weight)
        elif self.state == 'disabled' and self.drain:
            self.drain(self.host, self.backend, status='MAINT')
        elif self.state == 'disabled':
            self.disabled(self.host, self.backend, self.shutdown_sessions)
        elif self.state == 'drain':
            self.drain(self.host, self.backend)
        else:
            self.module.fail_json(msg="unknown state specified: '%s'" % self.state)

        # Get the state after the run
        state_after = self.get_state_for(self.backend, self.host)
        self.command_results['state_after'] = state_after

        # Report change status
        if state_before != state_after:
            self.command_results['changed'] = True
            self.module.exit_json(**self.command_results)
        else:
            self.command_results['changed'] = False
            self.module.exit_json(**self.command_results)


def main():

    # load ansible module object
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(required=True, default=None, choices=ACTION_CHOICES),
            host=dict(required=True, default=None),
            backend=dict(required=False, default=None),
            weight=dict(required=False, default=None),
            socket=dict(required=False, default=DEFAULT_SOCKET_LOCATION),
            shutdown_sessions=dict(required=False, default=False, type='bool'),
            fail_on_not_found=dict(required=False, default=False, type='bool'),
            wait=dict(required=False, default=False, type='bool'),
            wait_retries=dict(required=False, default=WAIT_RETRIES, type='int'),
            wait_interval=dict(required=False, default=WAIT_INTERVAL, type='int'),
            drain=dict(default=False, type='bool'),
        ),
    )

    if not socket:
        module.fail_json(msg="unable to locate haproxy socket")

    ansible_haproxy = HAProxy(module)
    ansible_haproxy.act()


if __name__ == '__main__':
    main()
