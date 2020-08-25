#!/usr/bin/python
# -*- coding: utf-8 -*-
# (c) 2017, Daniel Korn <korndaniel1@gmail.com>
# (c) 2017, Yaacov Zamir <yzamir@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}


DOCUMENTATION = '''
module: manageiq_provider
short_description: Management of provider in ManageIQ.
extends_documentation_fragment: manageiq
version_added: '2.4'
author: Daniel Korn (@dkorn)
description:
  - The manageiq_provider module supports adding, updating, and deleting provider in ManageIQ.

options:
  state:
    description:
      - absent - provider should not exist, present - provider should be, valid - provider authentication should be valid.
    required: False
    choices: ['absent', 'present']
    default: 'present'
  name:
    description: The provider's name.
    required: true
  type:
    description: The provider's type.
    required: true
    choices: ['Openshift', 'Amazon']
  zone:
    description: The ManageIQ zone name that will manage the provider.
    required: false
    default: 'default'
  provider_region:
    description: The provider region name to connect to (e.g. AWS region for Amazon).
    required: false
    default: null

  provider:
    required: false
    description: Default endpoint connection information, required if state is true.
    default: null
    suboptions:
      hostname:
        description: The provider's api hostname.
        required: true
      port:
        description: The provider's api port.
        required: false
      userid:
        required: false
        default: null
        description: Provider's api endpoint authentication userid. defaults to None.
      password:
        required: false
        default: null
        description: Provider's api endpoint authentication password. defaults to None.
      auth_key:
        required: false
        default: null
        description: Provider's api endpoint authentication bearer token. defaults to None.
      verify_ssl:
        required: false
        default: true
        description: Whether SSL certificates should be verified for HTTPS requests (deprecated). defaults to True.
      security_protocol:
        required: false
        default: None
        choices: ['ssl-with-validation','ssl-with-validation-custom-ca','ssl-without-validation']
        description: How SSL certificates should be used for HTTPS requests. defaults to None.
      certificate_authority:
        required: false
        default: null
        description: The CA bundle string with custom certificates. defaults to None.

  metrics:
    required: false
    description: Metrics endpoint connection information.
    default: null
    suboptions:
      hostname:
        description: The provider's api hostname.
        required: true
      port:
        description: The provider's api port.
        required: false
      userid:
        required: false
        default: null
        description: Provider's api endpoint authentication userid. defaults to None.
      password:
        required: false
        default: null
        description: Provider's api endpoint authentication password. defaults to None.
      auth_key:
        required: false
        default: null
        description: Provider's api endpoint authentication bearer token. defaults to None.
      verify_ssl:
        required: false
        default: true
        description: Whether SSL certificates should be verified for HTTPS requests (deprecated). defaults to True.
      security_protocol:
        required: false
        default: None
        choices: ['ssl-with-validation','ssl-with-validation-custom-ca','ssl-without-validation']
        description: How SSL certificates should be used for HTTPS requests. defaults to None.
      certificate_authority:
        required: false
        default: null
        description: The CA bundle string with custom certificates. defaults to None.

  alerts:
    required: false
    description: Alerts endpoint connection information.
    default: null
    suboptions:
      hostname:
        description: The provider's api hostname.
        required: true
      port:
        description: The provider's api port.
        required: false
      userid:
        required: false
        default: null
        description: Provider's api endpoint authentication userid. defaults to None.
      password:
        required: false
        default: null
        description: Provider's api endpoint authentication password. defaults to None.
      auth_key:
        required: false
        default: null
        description: Provider's api endpoint authentication bearer token. defaults to None.
      verify_ssl:
        required: false
        default: true
        description: Whether SSL certificates should be verified for HTTPS requests (deprecated). defaults to True.
      security_protocol:
        required: false
        default: None
        choices: ['ssl-with-validation','ssl-with-validation-custom-ca','ssl-without-validation']
        description: How SSL certificates should be used for HTTPS requests. defaults to None.
      certificate_authority:
        required: false
        default: null
        description: The CA bundle string with custom certificates. defaults to None.
'''

EXAMPLES = '''
  - name: Create a new provider in ManageIQ ('Hawkular' metrics)
    manageiq_provider:
      name: 'EngLab'
      type: 'OpenShift'
      provider:
        auth_key: 'topSecret'
        hostname: 'example.com'
        port: 8443
        verify_ssl: False
      metrics:
        role: 'hawkular'
        hostname: 'example.com'
        port: 443
        verify_ssl: False
      manageiq_connection:
        url: 'http://127.0.0.1:3000'
        username: 'admin'
        password: 'smartvm'
        verify_ssl: False

  - name: Update an existing provider named 'EngLab' (defaults to 'Prometheus' metrics)
    manageiq_provider:
      name: 'EngLab'
      type: 'Openshift'
      provider:
        auth_key: 'verySecret'
        hostname: 'next.example.com'
        port: 8443
        verify_ssl: False
      metrics:
        hostname: 'next.example.com'
        port: 443
        verify_ssl: False
      manageiq_connection:
        url: 'http://127.0.0.1:3000'
        username: 'admin'
        password: 'smartvm'
        verify_ssl: False

  - name: Delete a provider in ManageIQ
    manageiq_provider:
      state: 'absent'
      name: 'EngLab'
      manageiq_connection:
        url: 'http://127.0.0.1:3000'
        username: 'admin'
        password: 'smartvm'
        verify_ssl: False

  - name: Create a new Amazon provider in ManageIQ using token authentication
    manageiq_provider:
      name: 'EngAmazon'
      type: 'Amazon'
      provider_region: 'us-east-1'
      provider:
        hostname: 'amazon.example.com'
        userid: 'hello'
        password: 'world'
      manageiq_connection:
        url: 'http://127.0.0.1:3000'
        token: 'VeryLongToken'
        verify_ssl: False

'''

RETURN = '''
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.manageiq import ManageIQ, manageiq_argument_spec


def supported_providers():
    return dict(
        Openshift=dict(
            class_name='ManageIQ::Providers::Openshift::ContainerManager',
            authtype='bearer',
            default_role='default',
            metrics_role='prometheus',
        ),
        Amazon=dict(
            class_name='ManageIQ::Providers::Amazon::CloudManager',
        ),
    )


def endpoint_list_spec():
    return dict(
        provider=dict(type='dict', options=endpoint_argument_spec()),
        metrics=dict(type='dict', options=endpoint_argument_spec()),
        alerts=dict(type='dict', options=endpoint_argument_spec()),
    )


def endpoint_argument_spec():
    return dict(
        role=dict(),
        hostname=dict(required=True),
        port=dict(type='int'),
        verify_ssl=dict(default=True, type='bool'),
        certificate_authority=dict(),
        security_protocol=dict(
            choices=[
                'ssl-with-validation',
                'ssl-with-validation-custom-ca',
                'ssl-without-validation',
            ],
        ),
        userid=dict(),
        password=dict(no_log=True),
        auth_key=dict(no_log=True),
    )


def delete_nulls(h):
    """ Remove null entries from a hash

    Returns:
        a hash without nulls
    """
    if isinstance(h, list):
        return map(delete_nulls, h)
    if isinstance(h, dict):
        return dict((k, delete_nulls(v)) for k, v in h.items() if v is not None)

    return h


class ManageIQProvider(object):
    """
        Object to execute provider management operations in manageiq.
    """

    def __init__(self, manageiq):
        self.manageiq = manageiq

        self.module = self.manageiq.module
        self.api_url = self.manageiq.api_url
        self.client = self.manageiq.client

    def class_name_to_type(self, class_name):
        """ Convert class_name to type

        Returns:
            the type
        """
        out = [k for k, v in supported_providers().items() if v['class_name'] == class_name]
        if len(out) == 1:
            return out[0]

        return None

    def zone_id(self, name):
        """ Search for zone id by zone name.

        Returns:
            the zone id, or send a module Fail signal if zone not found.
        """
        zone = self.manageiq.find_collection_resource_by('zones', name=name)
        if not zone:  # zone doesn't exist
            self.module.fail_json(
                msg="zone %s does not exist in manageiq" % (name))

        return zone['id']

    def provider(self, name):
        """ Search for provider object by name.

        Returns:
            the provider, or None if provider not found.
        """
        return self.manageiq.find_collection_resource_by('providers', name=name)

    def build_connection_configurations(self, provider_type, endpoints):
        """ Build "connection_configurations" objects from
        requested endpoints provided by user

        Returns:
            the user requested provider endpoints list
        """
        connection_configurations = []
        endpoint_keys = endpoint_list_spec().keys()
        provider_defaults = supported_providers().get(provider_type, {})

        # get endpoint defaults
        endpoint = endpoints.get('provider')
        default_auth_key = endpoint.get('auth_key')

        # build a connection_configuration object for each endpoint
        for endpoint_key in endpoint_keys:
            endpoint = endpoints.get(endpoint_key)
            if endpoint:
                # get role and authtype
                role = endpoint.get('role') or provider_defaults.get(endpoint_key + '_role', 'default')
                if role == 'default':
                    authtype = provider_defaults.get('authtype', role)
                else:
                    authtype = role

                # set a connection_configuration
                connection_configurations.append({
                    'endpoint': {
                        'role': role,
                        'hostname': endpoint.get('hostname'),
                        'port': endpoint.get('port'),
                        'verify_ssl': [0, 1][endpoint.get('verify_ssl', True)],
                        'security_protocol': endpoint.get('security_protocol'),
                        'certificate_authority': endpoint.get('certificate_authority'),
                    },
                    'authentication': {
                        'authtype': authtype,
                        'userid': endpoint.get('userid'),
                        'password': endpoint.get('password'),
                        'auth_key': endpoint.get('auth_key', default_auth_key),
                    }
                })

        return connection_configurations

    def delete_provider(self, provider):
        """ Deletes a provider from manageiq.

        Returns:
            a short message describing the operation executed.
        """
        try:
            url = '%s/providers/%s' % (self.api_url, provider['id'])
            result = self.client.post(url, action='delete')
        except Exception as e:
            self.module.fail_json(msg="failed to delete provider %s: %s" % (provider['name'], str(e)))

        return dict(changed=True, msg=result['message'])

    def edit_provider(self, provider, name, provider_type, endpoints, zone_id, provider_region):
        """ Edit a user from manageiq.

        Returns:
            a short message describing the operation executed.
        """
        url = '%s/providers/%s' % (self.api_url, provider['id'])

        resource = dict(
            name=name,
            zone={'id': zone_id},
            provider_region=provider_region,
            connection_configurations=endpoints,
        )

        # NOTE: we do not check for diff's between requested and current
        #       provider, we always submit endpoints with password or auth_keys,
        #       since we can not compare with current password or auth_key,
        #       every edit request is sent to ManageIQ API without compareing
        #       it to current state.

        # clean nulls, we do not send nulls to the api
        resource = delete_nulls(resource)

        # try to update provider
        try:
            result = self.client.post(url, action='edit', resource=resource)
        except Exception as e:
            self.module.fail_json(msg="failed to update provider %s: %s" % (provider['name'], str(e)))

        return dict(
            changed=True,
            msg="successfully updated the provider %s: %s" % (provider['name'], result))

    def create_provider(self, name, provider_type, endpoints, zone_id, provider_region):
        """ Creates the user in manageiq.

        Returns:
            the created user id, name, created_on timestamp,
            updated_on timestamp, userid and current_group_id.
        """
        # clean nulls, we do not send nulls to the api
        endpoints = delete_nulls(endpoints)

        # try to create a new provider
        try:
            url = '%s/providers' % (self.api_url)
            result = self.client.post(
                url,
                name=name,
                type=supported_providers()[provider_type]['class_name'],
                zone={'id': zone_id},
                provider_region=provider_region,
                connection_configurations=endpoints,
            )
        except Exception as e:
            self.module.fail_json(msg="failed to create provider %s: %s" % (name, str(e)))

        return dict(
            changed=True,
            msg="successfully created the provider %s: %s" % (name, result['results']))


def main():
    zone_id = None
    endpoints = []
    argument_spec = dict(
        manageiq_connection=dict(required=True, type='dict',
                                 options=manageiq_argument_spec()),
        state=dict(choices=['absent', 'present'], default='present'),
        name=dict(required=True),
        zone=dict(default='default'),
        provider_region=dict(),
        type=dict(choices=supported_providers().keys()),
    )
    # add the endpoint arguments to the arguments
    argument_spec.update(endpoint_list_spec())

    module = AnsibleModule(
        argument_spec=argument_spec,
        required_if=[
            ('state', 'present', ['provider'])],
    )

    name = module.params['name']
    zone_name = module.params['zone']
    provider_type = module.params['type']
    raw_endpoints = module.params
    provider_region = module.params['provider_region']
    state = module.params['state']

    manageiq = ManageIQ(module)
    manageiq_provider = ManageIQProvider(manageiq)

    provider = manageiq_provider.provider(name)

    # provider should not exist
    if state == "absent":
        # if we have a provider, delete it
        if provider:
            res_args = manageiq_provider.delete_provider(provider)
        # if we do not have a provider, nothing to do
        else:
            res_args = dict(
                changed=False,
                msg="provider %s: does not exist in manageiq" % (name))

    # provider should exist
    if state == "present":
        # get data user did not explicitly give
        if zone_name:
            zone_id = manageiq_provider.zone_id(zone_name)

        # if we do not have a provider_type, use the current provider_type
        if provider and not provider_type:
            provider_type = manageiq_provider.class_name_to_type(provider['type'])

        # check supported_providers types
        if not provider_type:
            manageiq_provider.module.fail_json(
                msg="missing required argument: provider_type")

        # check supported_providers types
        if provider_type not in supported_providers().keys():
            manageiq_provider.module.fail_json(
                msg="provider_type %s is not supported" % (provider_type))

        # build "connection_configurations" objects from user requsted endpoints
        # "provider" is a required endpoint, if we have it, we have endpoints
        if raw_endpoints.get("provider"):
            endpoints = manageiq_provider.build_connection_configurations(provider_type, raw_endpoints)

        # if we have a provider, edit it
        if provider:
            res_args = manageiq_provider.edit_provider(provider, name, provider_type, endpoints, zone_id, provider_region)
        # if we do not have a provider, create it
        else:
            res_args = manageiq_provider.create_provider(name, provider_type, endpoints, zone_id, provider_region)

    module.exit_json(**res_args)


if __name__ == "__main__":
    main()
