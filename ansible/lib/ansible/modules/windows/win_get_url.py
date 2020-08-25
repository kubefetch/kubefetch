#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2014, Paul Durivage <paul.durivage@rackspace.com>, and others
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

# this is a windows documentation stub.  actual code lives in the .ps1
# file of the same name

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['stableinterface'],
                    'supported_by': 'core'}

DOCUMENTATION = r'''
---
module: win_get_url
version_added: "1.7"
short_description: Fetches a file from a given URL
description:
- Fetches a file from a URL and saves it locally.
- For non-Windows targets, use the M(get_url) module instead.
author:
- Paul Durivage (@angstwad)
- Takeshi Kuramochi (tksarah)
options:
  url:
    description:
    - The full URL of a file to download.
    required: yes
  dest:
    description:
    - The location to save the file at the URL.
    - Be sure to include a filename and extension as appropriate.
    required: yes
  force:
    description:
    - If C(yes), will always download the file. If C(no), will only
      download the file if it does not exist or the remote file has been
      modified more recently than the local file.
    - This works by sending an http HEAD request to retrieve last modified
      time of the requested resource, so for this to work, the remote web
      server must support HEAD requests.
    type: bool
    default: 'yes'
    version_added: "2.0"
  headers:
    description:
    - Add custom HTTP headers to a request (as a dictionary).
    version_added: '2.4'
  url_username:
    description:
    - Basic authentication username.
    aliases: [ username ]
  url_password:
    description:
    - Basic authentication password.
    aliases: [ password ]
  skip_certificate_validation:
    description:
    - This option is deprecated since v2.4, please use C(validate_certs) instead.
    - If C(yes), SSL certificates will not be validated. This should only be used
      on personally controlled sites using self-signed certificates.
    type: bool
    default: 'no'
  validate_certs:
    description:
    - If C(no), SSL certificates will not be validated. This should only be used
      on personally controlled sites using self-signed certificates.
    - If C(skip_certificate_validation) was set, it overrides this option.
    type: bool
    default: 'yes'
    version_added: '2.4'
  proxy_url:
    description:
    - The full URL of the proxy server to download through.
    version_added: "2.0"
  proxy_username:
    description:
    - Proxy authentication username.
    version_added: "2.0"
  proxy_password:
    description:
    - Proxy authentication password.
    version_added: "2.0"
  use_proxy:
    description:
    - If C(no), it will not use a proxy, even if one is defined in an environment
      variable on the target hosts.
    type: bool
    default: 'yes'
    version_added: '2.4'
  timeout:
    description:
    - Timeout in seconds for URL request.
    default: 10
    version_added : '2.4'
notes:
 - For non-Windows targets, use the M(get_url) module instead.
'''

EXAMPLES = r'''
- name: Download earthrise.jpg to specified path
  win_get_url:
    url: http://www.example.com/earthrise.jpg
    dest: C:\Users\RandomUser\earthrise.jpg

- name: Download earthrise.jpg to specified path only if modified
  win_get_url:
    url: http://www.example.com/earthrise.jpg
    dest: C:\Users\RandomUser\earthrise.jpg
    force: no

- name: Download earthrise.jpg to specified path through a proxy server.
  win_get_url:
    url: http://www.example.com/earthrise.jpg
    dest: C:\Users\RandomUser\earthrise.jpg
    proxy_url: http://10.0.0.1:8080
    proxy_username: username
    proxy_password: password
'''

RETURN = r'''
dest:
    description: destination file/path
    returned: always
    type: string
    sample: C:\Users\RandomUser\earthrise.jpg
url:
    description: requested url
    returned: always
    type: string
    sample: http://www.example.com/earthrise.jpg
msg:
    description: Error message, or HTTP status message from web-server
    returned: always
    type: string
    sample: OK
status_code:
    description: HTTP status code
    returned: always
    type: int
    sample: 200
'''
