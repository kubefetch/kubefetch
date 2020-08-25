#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2017, Ansible by Red Hat, inc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'network'}


DOCUMENTATION = """
---
module: junos_netconf
version_added: "2.1"
author: "Peter Sprygada (@privateip)"
short_description: Configures the Junos Netconf system service
description:
  - This module provides an abstraction that enables and configures
    the netconf system service running on Junos devices.  This module
    can be used to easily enable the Netconf API. Netconf provides
    a programmatic interface for working with configuration and state
    resources as defined in RFC 6242.
extends_documentation_fragment: junos
options:
  netconf_port:
    description:
      - This argument specifies the port the netconf service should
        listen on for SSH connections.  The default port as defined
        in RFC 6242 is 830.
    required: false
    default: 830
    aliases: ['listens_on']
    version_added: "2.2"
  state:
    description:
      - Specifies the state of the C(junos_netconf) resource on
        the remote device.  If the I(state) argument is set to
        I(present) the netconf service will be configured.  If the
        I(state) argument is set to I(absent) the netconf service
        will be removed from the configuration.
    required: false
    default: present
    choices: ['present', 'absent']
notes:
  - Tested against vSRX JUNOS version 15.1X49-D15.4, vqfx-10000 JUNOS Version 15.1X53-D60.4.
"""

EXAMPLES = """
- name: enable netconf service on port 830
  junos_netconf:
    listens_on: 830
    state: present

- name: disable netconf service
  junos_netconf:
    state: absent
"""

RETURN = """
commands:
  description: Returns the command sent to the remote device
  returned: when changed is True
  type: str
  sample: 'set system services netconf ssh port 830'
"""
import re

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import exec_command
from ansible.module_utils.junos import junos_argument_spec, check_args
from ansible.module_utils.junos import commit_configuration, discard_changes
from ansible.module_utils.network_common import to_list
from ansible.module_utils.six import iteritems

USE_PERSISTENT_CONNECTION = True


def map_obj_to_commands(updates, module):
    want, have = updates
    commands = list()

    if want['state'] == 'absent':
        if have['state'] == 'present':
            commands.append('delete system services netconf')
    else:
        if have['state'] == 'absent' or want['netconf_port'] != have.get('netconf_port'):
            commands.append(
                'set system services netconf ssh port %s' % want['netconf_port']
            )

    return commands


def parse_port(config):
    match = re.search(r'port (\d+)', config)
    if match:
        return int(match.group(1))


def map_config_to_obj(module):
    cmd = 'show configuration system services netconf'
    rc, out, err = exec_command(module, cmd)
    if rc != 0:
        module.fail_json(msg='unable to retrieve current config', stderr=err)
    config = str(out).strip()

    obj = {'state': 'absent'}
    if 'ssh' in config:
        obj.update({
            'state': 'present',
            'netconf_port': parse_port(config)
        })
    return obj


def validate_netconf_port(value, module):
    if not 1 <= value <= 65535:
        module.fail_json(msg='netconf_port must be between 1 and 65535')


def map_params_to_obj(module):
    obj = {
        'netconf_port': module.params['netconf_port'],
        'state': module.params['state']
    }

    for key, value in iteritems(obj):
        # validate the param value (if validator func exists)
        validator = globals().get('validate_%s' % key)
        if callable(validator):
            validator(value, module)

    return obj


def load_config(module, config, commit=False):

    exec_command(module, 'configure')

    for item in to_list(config):
        rc, out, err = exec_command(module, item)
        if rc != 0:
            module.fail_json(msg=str(err))

    exec_command(module, 'top')
    rc, diff, err = exec_command(module, 'show | compare')

    if diff:
        if commit:
            exec_command(module, 'commit and-quit')
        else:
            for cmd in ['rollback 0', 'exit']:
                exec_command(module, cmd)

    return str(diff).strip()


def main():
    """main entry point for module execution
    """
    argument_spec = dict(
        netconf_port=dict(type='int', default=830, aliases=['listens_on']),
        state=dict(default='present', choices=['present', 'absent']),
    )

    argument_spec.update(junos_argument_spec)

    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=True)

    warnings = list()
    check_args(module, warnings)

    result = {'changed': False, 'warnings': warnings}

    want = map_params_to_obj(module)
    have = map_config_to_obj(module)

    commands = map_obj_to_commands((want, have), module)
    result['commands'] = commands

    if commands:
        commit = not module.check_mode
        diff = load_config(module, commands, commit=commit)
        if diff:
            if module._diff:
                result['diff'] = {'prepared': diff}
            result['changed'] = True

    module.exit_json(**result)


if __name__ == '__main__':
    main()
