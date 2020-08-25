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
module: aci_bd_subnet
short_description: Manage Subnets on Cisco ACI fabrics (fv:Subnet)
description:
- Manage Subnets on Cisco ACI fabrics.
- More information from the internal APIC class
  I(fv:Subnet) at U(https://developer.cisco.com/media/mim-ref/MO-fvSubnet.html).
author:
- Swetha Chunduri (@schunduri)
- Dag Wieers (@dagwieers)
- Jacob McGill (@jmcgill298)
version_added: '2.4'
requirements:
- ACI Fabric 1.0(3f)+
notes:
- The C(gateway) parameter is the root key used to access the Subnet (not name), so the C(gateway)
  is required when the state is C(absent) or C(present).
- The C(tenant) and C(bd) used must exist before using this module in your playbook.
  The M(aci_tenant) module and M(aci_bd) can be used for these.
options:
  bd:
    description:
    - The name of the Bridge Domain.
  description:
    description:
    - The description for the Subnet.
  enable_vip:
    description:
    - Determines if the Subnet should be treated as a VIP; used when the BD is extended to multiple sites.
    - The APIC defaults new Subnets to C(no).
    choices: [ no, yes ]
    default: no
  gateway:
    description:
    - The IPv4 or IPv6 gateway address for the Subnet.
    aliases: [ gateway_ip ]
  mask:
    description:
    - The subnet mask for the Subnet.
    - This is the number assocated with CIDR notation.
    choices: [ Any 0 to 32 for IPv4 Addresses, 0-128 for IPv6 Addresses  ]
    aliases: [ subnet_mask ]
  nd_prefix_policy:
    description:
    - The IPv6 Neighbor Discovery Prefix Policy to associate with the Subnet.
  preferred:
    description:
    - Determines if the Subnet is preferred over all available Subnets. Only one Subnet per Address Family (IPv4/IPv6).
      can be preferred in the Bridge Domain.
    - The APIC defaults new Subnets to C(no).
    choices: [ no, yes ]
    default: no
  route_profile:
    description:
    - The Route Profile to the associate with the Subnet.
  route_profile_l3_out:
    description:
    - The L3 Out that contains the assocated Route Profile.
  scope:
    description:
    - Determines if scope of the Subnet.
    - The private option only allows communication with hosts in the same VRF.
    - The public option allows the Subnet to be advertised outside of the ACI Fabric, and allows communication with
      hosts in other VRFs.
    - The shared option limits communication to hosts in either the same VRF or the shared VRF.
    - The APIC defaults new Subnets to C(private).
    choices: [ private, public, shared ]
    default: private
  subnet_control:
    description:
    - Determines the Subnet's Control State.
    - The querier_ip option is used to treat the gateway_ip as an IGMP querier source IP.
    - The nd_ra option is used to treate the gateway_ip address as a Neighbor Discovery Router Advertisement Prefix.
    - The no_gw option is used to remove default gateway functionality from the gateway address.
    - The APIC defaults new Subnets to C(nd_ra).
    choices: [ nd_ra, no_gw, querier_ip, unspecified ]
    default: nd_ra
  subnet_name:
    description:
    - The name of the Subnet.
    aliases: [ name ]
  tenant:
    description:
    - The name of the Tenant.
    aliases: [ tenant_name ]
'''

EXAMPLES = r''' # '''

RETURN = r''' # '''

SUBNET_CONTROL_MAPPING = dict(nd_ra='nd', no_gw='no-default-gateway', querier_ip='querier', unspecified='')


from ansible.module_utils.aci import ACIModule, aci_argument_spec
from ansible.module_utils.basic import AnsibleModule


def main():
    argument_spec = aci_argument_spec
    argument_spec.update(
        bd=dict(type='str', aliases=['bd_name']),
        description=dict(type='str', aliases=['descr']),
        enable_vip=dict(type='str', choices=['no', 'yes']),
        gateway=dict(type='str', aliases=['gateway_ip']),
        mask=dict(type='int', aliases=['subnet_mask']),
        subnet_name=dict(type='str', aliases=['name']),
        nd_prefix_policy=dict(type='str'),
        preferred=dict(type='str', choices=['no', 'yes']),
        route_profile=dict(type='str'),
        route_profile_l3_out=dict(type='str'),
        scope=dict(type='str', choices=['private', 'public', 'shared']),
        subnet_control=dict(type='str', choices=['nd_ra', 'no_gw', 'querier_ip', 'unspecified']),
        state=dict(type='str', default='present', choices=['absent', 'present', 'query']),
        tenant=dict(type='str', aliases=['tenant_name']),
        method=dict(type='str', choices=['delete', 'get', 'post'], aliases=['action'], removed_in_version='2.6'),  # Deprecated starting from v2.6
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_together=[['gateway', 'mask']],
        required_if=[
            ['state', 'present', ['bd', 'gateway', 'mask', 'tenant']],
            ['state', 'absent', ['bd', 'gateway', 'mask', 'tenant']],
        ],
    )

    description = module.params['description']
    enable_vip = module.params['enable_vip']
    gateway = module.params['gateway']
    mask = module.params['mask']
    if mask is not None and mask not in range(0, 129):
        # TODO: split checkes between IPv4 and IPv6 Addresses
        module.fail_json(msg='Valid Subnet Masks are 0 to 32 for IPv4 Addresses and 0 to 128 for IPv6 addresses')
    subnet_name = module.params['subnet_name']
    nd_prefix_policy = module.params['nd_prefix_policy']
    preferred = module.params['preferred']
    route_profile = module.params['route_profile']
    route_profile_l3_out = module.params['route_profile_l3_out']
    scope = module.params['scope']
    state = module.params['state']
    subnet_control = module.params['subnet_control']
    if subnet_control:
        subnet_control = SUBNET_CONTROL_MAPPING[subnet_control]

    # Construct gateway_addr and add to module.params for constructing URL
    if gateway is not None and mask is not None:
        gateway_addr = '{}/{}'.format(gateway, str(mask))
        module.params['gateway_addr'] = gateway_addr

    aci = ACIModule(module)
    aci.construct_url(
        root_class='tenant', subclass_1='bd', subclass_2='gateway_addr',
        child_classes=['fvRsBDSubnetToProfile', 'fvRsNdPfxPol'],
    )
    aci.get_existing()

    if state == 'present':
        # Filter out module params with null values
        aci.payload(
            aci_class='fvSubnet',
            class_config=dict(
                ctrl=subnet_control,
                descr=description,
                ip=gateway_addr,
                name=subnet_name,
                preferred=preferred,
                scope=scope,
                virtual=enable_vip,
            ),
            child_configs=[
                {'fvRsBDSubnetToProfile': {'attributes': {'tnL3extOutName': route_profile_l3_out, 'tnRtctrlProfileName': route_profile}}},
                {'fvRsNdPfxPol': {'attributes': {'tnNdPfxPolName': nd_prefix_policy}}},
            ],
        )

        # Generate config diff which will be used as POST request body
        aci.get_diff(aci_class='fvSubnet')

        # Submit changes if module not in check_mode and the proposed is different than existing
        aci.post_config()

    elif state == 'absent':
        aci.delete_config()

    # Remove gateway_addr used to form URL from module.params
    module.params.pop("gateway_addr", None)

    module.exit_json(**aci.result)


if __name__ == "__main__":
    main()
