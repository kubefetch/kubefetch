#!/usr/bin/python
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

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'network'}


DOCUMENTATION = """
---
module: eos_config
version_added: "2.1"
author: "Peter Sprygada (@privateip)"
short_description: Manage Arista EOS configuration sections
description:
  - Arista EOS configurations use a simple block indent file syntax
    for segmenting configuration into sections.  This module provides
    an implementation for working with EOS configuration sections in
    a deterministic way.  This module works with either CLI or eAPI
    transports.
extends_documentation_fragment: eos
notes:
  - Tested against EOS 4.15
options:
  lines:
    description:
      - The ordered set of commands that should be configured in the
        section.  The commands must be the exact same commands as found
        in the device running-config.  Be sure to note the configuration
        command syntax as some commands are automatically modified by the
        device config parser.
    required: false
    default: null
  parents:
    description:
      - The ordered set of parents that uniquely identify the section
        the commands should be checked against.  If the parents argument
        is omitted, the commands are checked against the set of top
        level or global commands.
    required: false
    default: null
  src:
    description:
      - The I(src) argument provides a path to the configuration file
        to load into the remote system.  The path can either be a full
        system path to the configuration file if the value starts with /
        or relative to the root of the implemented role or playbook.
        This argument is mutually exclusive with the I(lines) and
        I(parents) arguments. It can be a Jinja2 template as well.
        src file must have same indentation as a live switch config.
        Arista EOS device config has 3 spaces indentation.
    required: false
    default: null
    version_added: "2.2"
  before:
    description:
      - The ordered set of commands to push on to the command stack if
        a change needs to be made.  This allows the playbook designer
        the opportunity to perform configuration commands prior to pushing
        any changes without affecting how the set of commands are matched
        against the system.
    required: false
    default: null
  after:
    description:
      - The ordered set of commands to append to the end of the command
        stack if a change needs to be made.  Just like with I(before) this
        allows the playbook designer to append a set of commands to be
        executed after the command set.
    required: false
    default: null
  match:
    description:
      - Instructs the module on the way to perform the matching of
        the set of commands against the current device config.  If
        match is set to I(line), commands are matched line by line.  If
        match is set to I(strict), command lines are matched with respect
        to position.  If match is set to I(exact), command lines
        must be an equal match.  Finally, if match is set to I(none), the
        module will not attempt to compare the source configuration with
        the running configuration on the remote device.
    required: false
    default: line
    choices: ['line', 'strict', 'exact', 'none']
  replace:
    description:
      - Instructs the module on the way to perform the configuration
        on the device.  If the replace argument is set to I(line) then
        the modified lines are pushed to the device in configuration
        mode.  If the replace argument is set to I(block) then the entire
        command block is pushed to the device in configuration mode if any
        line is not correct.
    required: false
    default: line
    choices: ['line', 'block', 'config']
  force:
    description:
      - The force argument instructs the module to not consider the
        current devices running-config.  When set to true, this will
        cause the module to push the contents of I(src) into the device
        without first checking if already configured.
      - Note this argument should be considered deprecated.  To achieve
        the equivalent, set the C(match=none) which is idempotent.  This argument
        will be removed in a future release.
    required: false
    default: false
    type: bool
  backup:
    description:
      - This argument will cause the module to create a full backup of
        the current C(running-config) from the remote device before any
        changes are made.  The backup file is written to the C(backup)
        folder in the playbook root directory.  If the directory does not
        exist, it is created.
    required: false
    default: no
    type: bool
    version_added: "2.2"
  running_config:
    description:
      - The module, by default, will connect to the remote device and
        retrieve the current running-config to use as a base for comparing
        against the contents of source.  There are times when it is not
        desirable to have the task get the current running-config for
        every task in a playbook.  The I(running_config) argument allows the
        implementer to pass in the configuration to use as the base
        config for this module.
    required: false
    default: null
    aliases: ['config']
    version_added: "2.4"
  defaults:
    description:
      - The I(defaults) argument will influence how the running-config
        is collected from the device.  When the value is set to true,
        the command used to collect the running-config is append with
        the all keyword.  When the value is set to false, the command
        is issued without the all keyword
    required: false
    default: false
    type: bool
    version_added: "2.2"
  save:
    description:
      - The C(save) argument instructs the module to save the
        running-config to startup-config.  This operation is performed
        after any changes are made to the current running config.  If
        no changes are made, the configuration is still saved to the
        startup config.  This option will always cause the module to
        return changed.
      - This option is deprecated as of Ansible 2.4, use C(save_when)
    required: false
    default: false
    type: bool
    version_added: "2.2"
  save_when:
    description:
      - When changes are made to the device running-configuration, the
        changes are not copied to non-volatile storage by default.  Using
        this argument will change that before.  If the argument is set to
        I(always), then the running-config will always be copied to the
        startup-config and the I(modified) flag will always be set to
        True.  If the argument is set to I(modified), then the running-config
        will only be copied to the startup-config if it has changed since
        the last save to startup-config.  If the argument is set to
        I(never), the running-config will never be copied to the
        startup-config
    required: false
    default: never
    choices: ['always', 'never', 'modified']
    version_added: "2.4"
  diff_against:
    description:
      - When using the C(ansible-playbook --diff) command line argument
        the module can generate diffs against different sources.
      - When this option is configure as I(startup), the module will return
        the diff of the running-config against the startup-config.
      - When this option is configured as I(intended), the module will
        return the diff of the running-config against the configuration
        provided in the C(intended_config) argument.
      - When this option is configured as I(running), the module will
        return the before and after diff of the running-config with respect
        to any changes made to the device configuration.
      - When this option is configured as C(session), the diff returned will
        be based on the configuration session.
    required: false
    default: session
    choices: ['startup', 'running', 'intended', 'session']
    version_added: "2.4"
  diff_ignore_lines:
    description:
      - Use this argument to specify one or more lines that should be
        ignored during the diff.  This is used for lines in the configuration
        that are automatically updated by the system.  This argument takes
        a list of regular expressions or exact line matches.
    required: false
    version_added: "2.4"
  intended_config:
    description:
      - The C(intended_config) provides the master configuration that
        the node should conform to and is used to check the final
        running-config against.   This argument will not modify any settings
        on the remote device and is strictly used to check the compliance
        of the current device's configuration against.  When specifying this
        argument, the task should also modify the C(diff_against) value and
        set it to I(intended).
    required: false
    version_added: "2.4"
"""

EXAMPLES = """
- name: configure top level settings
  eos_config:
    lines: hostname {{ inventory_hostname }}

- name: diff against a provided master config
  eos_config:
    diff_against: config
    config: "{{ lookup('file', 'master.cfg') }}"

- name: load an acl into the device
  eos_config:
    lines:
      - 10 permit ip 1.1.1.1/32 any log
      - 20 permit ip 2.2.2.2/32 any log
      - 30 permit ip 3.3.3.3/32 any log
      - 40 permit ip 4.4.4.4/32 any log
    parents: ip access-list test
    before: no ip access-list test
    replace: block

- name: load configuration from file
  eos_config:
    src: eos.cfg

- name: diff the running config against a master config
  eos_config:
    diff_against: intended
    intended_config: "{{ lookup('file', 'master.cfg') }}"
"""

RETURN = """
commands:
  description: The set of commands that will be pushed to the remote device
  returned: always
  type: list
  sample: ['hostname switch01', 'interface Ethernet1', 'no shutdown']
updates:
  description: The set of commands that will be pushed to the remote device
  returned: always
  type: list
  sample: ['hostname switch01', 'interface Ethernet1', 'no shutdown']
backup_path:
  description: The full path to the backup file
  returned: when backup is yes
  type: string
  sample: /playbooks/ansible/backup/eos_config.2016-07-16@22:28:34
"""
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.netcfg import NetworkConfig, dumps
from ansible.module_utils.eos import get_config, load_config
from ansible.module_utils.eos import run_commands
from ansible.module_utils.eos import eos_argument_spec
from ansible.module_utils.eos import check_args


def get_candidate(module):
    candidate = NetworkConfig(indent=3)
    if module.params['src']:
        candidate.load(module.params['src'])
    elif module.params['lines']:
        parents = module.params['parents'] or list()
        candidate.add(module.params['lines'], parents=parents)
    return candidate


def get_running_config(module, config=None):
    contents = module.params['running_config']
    if not contents:
        if config:
            contents = config
        else:
            flags = []
            if module.params['defaults']:
                flags.append('all')
            contents = get_config(module, flags=flags)
    return NetworkConfig(indent=3, contents=contents)


def main():
    """ main entry point for module execution
    """
    argument_spec = dict(
        src=dict(type='path'),

        lines=dict(aliases=['commands'], type='list'),
        parents=dict(type='list'),

        before=dict(type='list'),
        after=dict(type='list'),

        match=dict(default='line', choices=['line', 'strict', 'exact', 'none']),
        replace=dict(default='line', choices=['line', 'block', 'config']),

        defaults=dict(type='bool', default=False),
        backup=dict(type='bool', default=False),

        save_when=dict(choices=['always', 'never', 'modified'], default='never'),

        diff_against=dict(choices=['startup', 'session', 'intended', 'running'], default='session'),
        diff_ignore_lines=dict(type='list'),

        running_config=dict(aliases=['config']),
        intended_config=dict(),

        # save is deprecated as of ans2.4, use save_when instead
        save=dict(default=False, type='bool', removed_in_version='2.4'),

        # force argument deprecated in ans2.2
        force=dict(default=False, type='bool', removed_in_version='2.2')
    )

    argument_spec.update(eos_argument_spec)

    mutually_exclusive = [('lines', 'src'),
                          ('save', 'save_when')]

    required_if = [('match', 'strict', ['lines']),
                   ('match', 'exact', ['lines']),
                   ('replace', 'block', ['lines']),
                   ('replace', 'config', ['src']),
                   ('diff_against', 'intended', ['intended_config'])]

    module = AnsibleModule(argument_spec=argument_spec,
                           mutually_exclusive=mutually_exclusive,
                           required_if=required_if,
                           supports_check_mode=True)

    warnings = list()
    check_args(module, warnings)

    result = {'changed': False}
    if warnings:
        result['warnings'] = warnings

    config = None

    if module.params['backup'] or (module._diff and module.params['diff_against'] == 'running'):
        contents = get_config(module)
        config = NetworkConfig(indent=3, contents=contents)
        if module.params['backup']:
            result['__backup__'] = contents

    if any((module.params['src'], module.params['lines'])):
        match = module.params['match']
        replace = module.params['replace']

        candidate = get_candidate(module)

        if match != 'none' and replace != 'config':
            config_text = get_running_config(module)
            config = NetworkConfig(indent=3, contents=config_text)
            path = module.params['parents']
            configobjs = candidate.difference(config, match=match, replace=replace, path=path)
        else:
            configobjs = candidate.items

        if configobjs:
            commands = dumps(configobjs, 'commands').split('\n')

            if module.params['before']:
                commands[:0] = module.params['before']

            if module.params['after']:
                commands.extend(module.params['after'])

            result['commands'] = commands
            result['updates'] = commands

            replace = module.params['replace'] == 'config'
            commit = not module.check_mode

            response = load_config(module, commands, replace=replace, commit=commit)

            if 'diff' in response and module.params['diff_against'] == 'session':
                result['diff'] = {'prepared': response['diff']}

            if 'session' in response:
                result['session'] = response['session']

            result['changed'] = True


    running_config = None
    startup_config = None

    diff_ignore_lines = module.params['diff_ignore_lines']

    if module.params['save_when'] != 'never':
        output = run_commands(module, [{'command': 'show running-config', 'output': 'text'},
                                       {'command': 'show startup-config', 'output': 'text'}])

        running_config = NetworkConfig(indent=1, contents=output[0], ignore_lines=diff_ignore_lines)
        startup_config = NetworkConfig(indent=1, contents=output[1], ignore_lines=diff_ignore_lines)

        if running_config.sha1 != startup_config.sha1 or module.params['save_when'] == 'always':
            result['changed'] = True
            if not module.check_mode:
                cmd = {'command': 'copy running-config startup-config', 'output': 'text'}
                run_commands(module, [cmd])
            else:
                module.warn('Skipping command `copy running-config startup-config` '
                            'due to check_mode.  Configuration not copied to '
                            'non-volatile storage')

    if module._diff:
        if not running_config:
            output = run_commands(module, {'command': 'show running-config', 'output': 'text'})
            contents = output[0]
        else:
            contents = running_config.config_text

        # recreate the object in order to process diff_ignore_lines
        running_config = NetworkConfig(indent=1, contents=contents, ignore_lines=diff_ignore_lines)

        if module.params['diff_against'] == 'running':
            if module.check_mode:
                module.warn("unable to perform diff against running-config due to check mode")
                contents = None
            else:
                contents = config.config_text

        elif module.params['diff_against'] == 'startup':
            if not startup_config:
                output = run_commands(module, {'command': 'show startup-config', 'output': 'text'})
                contents = output[0]
            else:
                contents = startup_config.config_text

        elif module.params['diff_against'] == 'intended':
            contents = module.params['intended_config']

        if contents is not None:
            base_config = NetworkConfig(indent=1, contents=contents, ignore_lines=diff_ignore_lines)

            if running_config.sha1 != base_config.sha1:
                if module.params['diff_against'] == 'intended':
                    before = running_config
                    after = base_config
                elif module.params['diff_against'] in ('startup', 'running'):
                    before = base_config
                    after = running_config

                result.update({
                    'changed': True,
                    'diff': {'before': str(before), 'after': str(after)}
                })

    module.exit_json(**result)


if __name__ == '__main__':
    main()
