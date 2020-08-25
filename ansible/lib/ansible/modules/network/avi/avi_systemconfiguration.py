#!/usr/bin/python
#
# Created on Aug 25, 2016
# @author: Gaurav Rastogi (grastogi@avinetworks.com)
#          Eric Anderson (eanderson@avinetworks.com)
# module_check: supported
# Avi Version: 17.1.1
#
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
                    'supported_by': 'community'}

DOCUMENTATION = '''
---
module: avi_systemconfiguration
author: Gaurav Rastogi (grastogi@avinetworks.com)

short_description: Module for setup of SystemConfiguration Avi RESTful Object
description:
    - This module is used to configure SystemConfiguration object
    - more examples at U(https://github.com/avinetworks/devops)
requirements: [ avisdk ]
version_added: "2.3"
options:
    state:
        description:
            - The state that should be applied on the entity.
        default: present
        choices: ["absent","present"]
    admin_auth_configuration:
        description:
            - Adminauthconfiguration settings for systemconfiguration.
    dns_configuration:
        description:
            - Dnsconfiguration settings for systemconfiguration.
    dns_virtualservice_refs:
        description:
            - Dns virtualservices hosting fqdn records for applications across avi vantage.
            - If no virtualservices are provided, avi vantage will provide dns services for configured applications.
            - Switching back to avi vantage from dns virtualservices is not allowed.
            - It is a reference to an object of type virtualservice.
    docker_mode:
        description:
            - Boolean flag to set docker_mode.
            - Default value when not specified in API or module is interpreted by Avi Controller as False.
    email_configuration:
        description:
            - Emailconfiguration settings for systemconfiguration.
    global_tenant_config:
        description:
            - Tenantconfiguration settings for systemconfiguration.
    linux_configuration:
        description:
            - Linuxconfiguration settings for systemconfiguration.
    mgmt_ip_access_control:
        description:
            - Configure ip access control for controller to restrict open access.
    ntp_configuration:
        description:
            - Ntpconfiguration settings for systemconfiguration.
    portal_configuration:
        description:
            - Portalconfiguration settings for systemconfiguration.
    proxy_configuration:
        description:
            - Proxyconfiguration settings for systemconfiguration.
    snmp_configuration:
        description:
            - Snmpconfiguration settings for systemconfiguration.
    ssh_ciphers:
        description:
            - Allowed ciphers list for ssh to the management interface on the controller and service engines.
            - If this is not specified, all the default ciphers are allowed.
            - Ssh -q cipher provides the list of default ciphers supported.
    ssh_hmacs:
        description:
            - Allowed hmac list for ssh to the management interface on the controller and service engines.
            - If this is not specified, all the default hmacs are allowed.
            - Ssh -q mac provides the list of default hmacs supported.
    url:
        description:
            - Avi controller URL of the object.
    uuid:
        description:
            - Unique object identifier of the object.
extends_documentation_fragment:
    - avi
'''

EXAMPLES = """
- name: Example to create SystemConfiguration object
  avi_systemconfiguration:
    controller: 10.10.25.42
    username: admin
    password: something
    state: present
    name: sample_systemconfiguration
"""

RETURN = '''
obj:
    description: SystemConfiguration (api/systemconfiguration) object
    returned: success, changed
    type: dict
'''

from ansible.module_utils.basic import AnsibleModule
try:
    from ansible.module_utils.avi import (
        avi_common_argument_spec, HAS_AVI, avi_ansible_api)
except ImportError:
    HAS_AVI = False


def main():
    argument_specs = dict(
        state=dict(default='present',
                   choices=['absent', 'present']),
        admin_auth_configuration=dict(type='dict',),
        dns_configuration=dict(type='dict',),
        dns_virtualservice_refs=dict(type='list',),
        docker_mode=dict(type='bool',),
        email_configuration=dict(type='dict',),
        global_tenant_config=dict(type='dict',),
        linux_configuration=dict(type='dict',),
        mgmt_ip_access_control=dict(type='dict',),
        ntp_configuration=dict(type='dict',),
        portal_configuration=dict(type='dict',),
        proxy_configuration=dict(type='dict',),
        snmp_configuration=dict(type='dict',),
        ssh_ciphers=dict(type='list',),
        ssh_hmacs=dict(type='list',),
        url=dict(type='str',),
        uuid=dict(type='str',),
    )
    argument_specs.update(avi_common_argument_spec())
    module = AnsibleModule(
        argument_spec=argument_specs, supports_check_mode=True)
    if not HAS_AVI:
        return module.fail_json(msg=(
            'Avi python API SDK (avisdk>=17.1) is not installed. '
            'For more details visit https://github.com/avinetworks/sdk.'))
    return avi_ansible_api(module, 'systemconfiguration',
                           set([]))

if __name__ == '__main__':
    main()
