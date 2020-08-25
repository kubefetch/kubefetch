#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 Lenovo, Inc.
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
# Module to send conditional template to Lenovo Switches
# Lenovo Networking
#

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}


DOCUMENTATION = '''
---
module: cnos_conditional_template
author: "Dave Kasberg (@dkasberg)"
short_description: Manage switch configuration using templates based on condition on devices running Lenovo CNOS
description:
    - This module allows you to work with the running configuration of a switch. It provides a way to
     execute a set of CNOS commands on a switch by evaluating the current running configuration and
     executing the commands only if the specific settings have not been already configured.
     The configuration source can be a set of commands or a template written in the Jinja2 templating language.
     This module functions the same as the cnos_template module.
     The only exception is that the following inventory variable can be specified
     ["condition = <flag string>"]
     When this inventory variable is specified as the variable of a task, the template is executed for
     the network element that matches the flag string. Usually, templates are used when commands are the
     same across a group of network devices. When there is a requirement to skip the execution of the
     template on one or more devices, it is recommended to use this module.
     This module uses SSH to manage network device configuration.
     For more information about this module from Lenovo and customizing it usage for your
     use cases, please visit U(http://systemx.lenovofiles.com/help/index.jsp?topic=%2Fcom.lenovo.switchmgt.ansible.doc%2Fcnos_conditional_template.html)
version_added: "2.3"
extends_documentation_fragment: cnos
options:
    commandfile:
        description:
            - This specifies the path to the CNOS command file which needs to be applied. This usually
             comes from the commands folder. Generally this file is the output of the variables applied
             on a template file. So this command is preceded by a template module.
             The command file must contain the Ansible keyword {{ inventory_hostname }} and the condition
             flag in its filename to ensure that the command file is unique for each switch and condition.
             If this is omitted, the command file will be overwritten during iteration. For example,
             commandfile=./commands/clos_leaf_bgp_{{ inventory_hostname }}_LP21_commands.txt
        required: true
        default: Null
    condition:
        description:
            - If you specify condition=<flag string> in the inventory file against any device, the template
             execution is done for that device in case it matches the flag setting for that task.
        required: true
        default: Null
    flag:
        description:
            - If a task needs to be executed, you have to set the flag the same as it is specified in
             the inventory for that device.
        required: true
        default: Null
'''
EXAMPLES = '''
Tasks : The following are examples of using the module cnos_conditional_template. These are written in the main.yml file of the tasks directory.
---
- name: Applying CLI template on VLAG Tier1 Leaf Switch1
  cnos_conditional_template:
      host: "{{ inventory_hostname }}"
      username: "{{ hostvars[inventory_hostname]['username'] }}"
      password: "{{ hostvars[inventory_hostname]['password'] }}"
      deviceType: "{{ hostvars[inventory_hostname]['deviceType'] }}"
      outputfile: "./results/vlag_1tier_leaf_switch1_{{ inventory_hostname }}_output.txt"
      condition: "{{ hostvars[inventory_hostname]['condition']}}"
      flag: "leaf_switch1"
      commandfile: "./commands/vlag_1tier_leaf_switch1_{{ inventory_hostname }}_commands.txt"
      enablePassword: "anil"
      stp_mode1: "disable"
      port_range1: "17,18,29,30"
      portchannel_interface_number1: 1001
      portchannel_mode1: active
      slot_chassis_number1: 1/48
      switchport_mode1: trunk
'''
RETURN = '''
msg:
  description: Success or failure message
  returned: always
  type: string
  sample: "Template Applied."
'''

import sys
import paramiko
import time
import argparse
import socket
import array
import json
import time
import re
try:
    from ansible.module_utils import cnos
    HAS_LIB = True
except:
    HAS_LIB = False
from ansible.module_utils.basic import AnsibleModule
from collections import defaultdict


def main():
    module = AnsibleModule(
        argument_spec=dict(
            commandfile=dict(required=True),
            outputfile=dict(required=True),
            condition=dict(required=True),
            flag=dict(required=True),
            host=dict(required=True),
            deviceType=dict(required=True),
            username=dict(required=True),
            password=dict(required=True, no_log=True),
            enablePassword=dict(required=False, no_log=True),),
        supports_check_mode=False)

    username = module.params['username']
    password = module.params['password']
    enablePassword = module.params['enablePassword']
    condition = module.params['condition']
    flag = module.params['flag']
    commandfile = module.params['commandfile']
    deviceType = module.params['deviceType']
    outputfile = module.params['outputfile']
    hostIP = module.params['host']

    output = ""

    # Here comes the logic against which a template is
    # conditionally executed for right Network element.
    if (condition != flag):
        module.exit_json(changed=True, msg="Template Skipped for this value")
        return " "

    # Create instance of SSHClient object
    remote_conn_pre = paramiko.SSHClient()

    # Automatically add untrusted hosts (make sure okay for security policy in your environment)
    remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # initiate SSH connection with the switch
    remote_conn_pre.connect(hostIP, username=username, password=password)
    time.sleep(2)

    # Use invoke_shell to establish an 'interactive session'
    remote_conn = remote_conn_pre.invoke_shell()
    time.sleep(2)
    # Enable and enter configure terminal then send command
    output = output + cnos.waitForDeviceResponse("\n", ">", 2, remote_conn)

    output = output + cnos.enterEnableModeForDevice(enablePassword, 3, remote_conn)

    # Make terminal length = 0
    output = output + cnos.waitForDeviceResponse("terminal length 0\n", "#", 2, remote_conn)

    # Go to config mode
    output = output + cnos.waitForDeviceResponse("configure d\n", "(config)#", 2, remote_conn)
    # Send commands one by one
    #with open(commandfile, "r") as f:
    f = open(commandfile, "r")
    for line in f:
        # Omit the comment lines in template file
        if not line.startswith("#"):
            # cnos.debugOutput(line)
            command = line
            if not line.endswith("\n"):
                command = command+"\n"
            response = cnos.waitForDeviceResponse(command, "#", 2, remote_conn)
            errorMsg = cnos.checkOutputForError(response)
            output = output + response
            if(errorMsg is not None):
                break
            # To cater to Mufti case
    # Write to memory
    output = output + cnos.waitForDeviceResponse("save\n", "#", 3, remote_conn)

    # Write output to file
    file = open(outputfile, "a")
    file.write(output)
    file.close()

    # Logic to check when changes occur or not
    errorMsg = cnos.checkOutputForError(output)
    if(errorMsg is None):
        module.exit_json(changed=True, msg="Template Applied")
    else:
        module.fail_json(msg=errorMsg)

if __name__ == '__main__':
    main()
