# This code is part of Ansible, but is an independent component.
# This particular file snippet, and this file snippet only, is BSD licensed.
# Modules you write using this snippet, which is embedded dynamically by Ansible
# still belong to the author of the module, and may assign their own license
# to the complete work.
#
# Copyright (c), Gaurav Rastogi <grastogi@avinetworks.com>, 2017
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# This module initially matched the namespace of network module avi. However,
# that causes namespace import error when other modules from avi namespaces
# are imported. Added import of absolute_import to avoid import collisions for
# avi.sdk.

from __future__ import absolute_import
import os
from pkg_resources import parse_version

HAS_AVI = True
try:
    import avi.sdk
    sdk_version = getattr(avi.sdk, '__version__', None)
    if ((sdk_version is None) or (sdk_version and (parse_version(sdk_version) < parse_version('17.1')))):
        # It allows the __version__ to be '' as that value is used in development builds
        raise ImportError
    from avi.sdk.utils.ansible_utils import avi_ansible_api
except ImportError:
    HAS_AVI = False


def avi_common_argument_spec():
    """
    Returns common arguments for all Avi modules
    :return: dict
    """
    return dict(
        controller=dict(default=os.environ.get('AVI_CONTROLLER', '')),
        username=dict(default=os.environ.get('AVI_USERNAME', '')),
        password=dict(default=os.environ.get('AVI_PASSWORD', ''), no_log=True),
        tenant=dict(default='admin'),
        tenant_uuid=dict(default=''),
        api_version=dict(default='16.4'))


def ansible_return(module, rsp, changed, req=None, existing_obj=None):
    """
    Helper function to return the right ansible return based on the error code and
    changed status.
    :param module: AnsibleModule
    :param rsp: ApiResponse object returned from ApiSession.
    :param changed: Whether something changed in this module.
    :param req: Dict data for Avi API call.
    :param existing_obj: Dict representing current HTTP resource in Avi Controller.

    Returns: specific ansible module exit function
    """
    if rsp.status_code > 299:
        return module.fail_json(msg='Error %d Msg %s req: %s' % (
            rsp.status_code, rsp.text, req))
    if changed and existing_obj:
        return module.exit_json(
            changed=changed, obj=rsp.json(), old_obj=existing_obj)
    return module.exit_json(changed=changed, obj=rsp.json())
