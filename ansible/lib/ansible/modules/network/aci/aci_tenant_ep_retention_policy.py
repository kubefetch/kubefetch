#!/usr/bin/python
# -*- coding: utf-8 -*-

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = r'''
---
module: aci_tenant_ep_retention_policy
short_description: Manage End Point (EP) retention protocol policies on Cisco ACI fabrics (fv:EpRetPol)
description:
- Manage End Point (EP) retention protocol policies on Cisco ACI fabrics.
- More information from the internal APIC class
  I(fv:EpRetPol) at U(https://developer.cisco.com/media/mim-ref/MO-fvEpRetPol.html).
author:
- Swetha Chunduri (@schunduri)
- Dag Wieers (@dagwieers)
- Jacob McGill (@jmcgill298)
version_added: '2.4'
requirements:
- ACI Fabric 1.0(3f)+
notes:
- The C(tenant) used must exist before using this module in your playbook.
  The M(aci_tenant) module can be used for this.
options:
  tenant:
    description:
    - The name of an existing tenant.
    aliases: [ tenant_name ]
  epr_policy:
    description:
    - The name of the end point retention policy.
    aliases: [ epr_name, name ]
  bounce_age:
    description:
    - Bounce Entry Aging Interval (range 150secs - 65535secs)
    - 0 is used for infinite.
    default: 630
  bounce_trigger:
    description:
    - Determines if the bounce entries are installed by RARP Flood or COOP Protocol.
    - The APIC defaults new End Point Retention Policies to C(coop).
    default: coop
  hold_interval:
    description:
    - Hold Interval (range 5secs - 65535secs).
    default: 300
  local_ep_interval:
    description:
    - Local end point Aging Interval (range 120secs - 65535secs).
    - 0 is used for infinite.
    default: 900
  remote_ep_interval:
    description:
    - Remote end point Aging Interval (range 120secs - 65535secs).
    - O is used for infinite.
    default: 300
  move_frequency:
    description:
    - Move frequency per second (range 0secs - 65535secs).
    - 0 is used for none.
    default: 256
  description:
    description:
    - Description for the End point rentention policy.
    aliases: [ descr ]
  state:
    description:
    - Use C(present) or C(absent) for adding or removing.
    - Use C(query) for listing an object or multiple objects.
    choices: [ absent, present, query ]
    default: present
extends_documentation_fragment: aci
'''

EXAMPLES = r'''
- name: Add a new EPR policy
  aci_epr_policy:
    hostname: apic
    username: admin
    password: SomeSecretPassword
    tenant: production
    epr_policy: EPRPol1
    bounce_age: 630
    hold_interval: 300
    local_ep_interval: 900
    remote_ep_interval: 300
    move_frequency: 256
    description: test
    state: present

- name: Remove an EPR policy
  aci_epr_policy:
    hostname: apic
    username: admin
    password: SomeSecretPassword
    tenant: production
    epr_policy: EPRPol1
    state: absent

- name: Query an EPR policy
  aci_epr_policy:
    hostname: apic
    username: admin
    password: SomeSecretPassword
    tenant: production
    epr_policy: EPRPol1
    state: query

- name: Query all EPR policies
  aci_epr_policy:
    hostname: apic
    username: admin
    password: SomeSecretPassword
    state: query
'''

RETURN = r'''
#
'''

from ansible.module_utils.aci import ACIModule, aci_argument_spec
from ansible.module_utils.basic import AnsibleModule

BOUNCE_TRIG_MAPPING = dict(coop='protocol', rarp='rarp-flood')


def main():
    argument_spec = aci_argument_spec
    argument_spec.update(
        tenant=dict(type='str', aliases=['tenant_name']),  # not required for querying all EPRs
        epr_policy=dict(type='str', aliases=['epr_name', 'name']),
        bounce_age=dict(type='int'),
        bounce_trigger=dict(type='str', choices=['coop', 'flood']),
        hold_interval=dict(type='int'),
        local_ep_interval=dict(type='int'),
        remote_ep_interval=dict(type='int'),
        description=dict(type='str', aliases=['descr']),
        move_frequency=dict(type='int'),
        state=dict(type='str', default='present', choices=['absent', 'present', 'query']),
        method=dict(type='str', choices=['delete', 'get', 'post'], aliases=['action'], removed_in_version='2.6'),  # Deprecated starting from v2.6
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ['state', 'absent', ['epr_policy', 'tenant']],
            ['state', 'present', ['epr_policy', 'tenant']],
        ],
    )

    epr_policy = module.params['epr_policy']
    bounce_age = module.params['bounce_age']
    if bounce_age is not None and bounce_age != 0 and bounce_age not in range(150, 65536):
        module.fail_json(msg="The bounce_age must be a value of 0 or between 150 and 65535")
    if bounce_age == 0:
        bounce_age = 'infinite'
    bounce_trigger = module.params['bounce_trigger']
    if bounce_trigger is not None:
        bounce_trigger = BOUNCE_TRIG_MAPPING[bounce_trigger]
    description = module.params['description']
    hold_interval = module.params['hold_interval']
    if hold_interval is not None and hold_interval not in range(5, 65536):
        module.fail_json(msg="The hold_interval must be a value between 5 and 65535")
    local_ep_interval = module.params['local_ep_interval']
    if local_ep_interval is not None and local_ep_interval != 0 and local_ep_interval not in range(120, 65536):
        module.fail_json(msg="The local_ep_interval must be a value of 0 or between 120 and 65535")
    if local_ep_interval == 0:
        local_ep_interval = "infinite"
    move_frequency = module.params['move_frequency']
    if move_frequency is not None and move_frequency not in range(65536):
        module.fail_json(msg="The move_frequency must be a value between 0 and 65535")
    if move_frequency == 0:
        move_frequency = "none"
    remote_ep_interval = module.params['remote_ep_interval']
    if remote_ep_interval is not None and remote_ep_interval not in range(120, 65536):
        module.fail_json(msg="The remote_ep_interval must be a value of 0 or between 120 and 65535")
    if remote_ep_interval == 0:
        remote_ep_interval = "infinite"
    state = module.params['state']

    aci = ACIModule(module)
    aci.construct_url(root_class='tenant', subclass_1='epr_policy')
    aci.get_existing()

    if state == 'present':
        # filter out module parameters with null values
        aci.payload(
            aci_class='fvEpRetPol',
            class_config=dict(
                name=epr_policy,
                descr=description,
                bounceAgeIntvl=bounce_age,
                bounceTrig=bounce_trigger,
                holdIntvl=hold_interval,
                localEpAgeIntvl=local_ep_interval,
                remoteEpAgeIntvl=remote_ep_interval,
                moveFreq=move_frequency,
            ),
        )

        # Generate config diff which will be used as POST request body
        aci.get_diff(aci_class='fvEpRetPol')

        # Submit changes if module not in check_mode and the proposed is different than existing
        aci.post_config()

    elif state == 'absent':
        aci.delete_config()

    module.exit_json(**aci.result)


if __name__ == "__main__":
    main()
