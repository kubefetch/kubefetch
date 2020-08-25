# This code is part of Ansible, but is an independent component.
# This particular file snippet, and this file snippet only, is BSD licensed.
# Modules you write using this snippet, which is embedded dynamically by Ansible
# still belong to the author of the module, and may assign their own license
# to the complete work.
#
# (c) 2016 Red Hat Inc.
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
#
from ansible.module_utils._text import to_text
from ansible.module_utils.basic import env_fallback, return_values
from ansible.module_utils.network_common import to_list
from ansible.module_utils.connection import exec_command

_DEVICE_CONFIGS = {}

vyos_provider_spec = {
    'host': dict(),
    'port': dict(type='int'),

    'username': dict(fallback=(env_fallback, ['ANSIBLE_NET_USERNAME'])),
    'password': dict(fallback=(env_fallback, ['ANSIBLE_NET_PASSWORD']), no_log=True),
    'ssh_keyfile': dict(fallback=(env_fallback, ['ANSIBLE_NET_SSH_KEYFILE']), type='path'),

    'timeout': dict(type='int'),
}
vyos_argument_spec = {
    'provider': dict(type='dict', options=vyos_provider_spec),
}
vyos_argument_spec.update(vyos_provider_spec)


def get_argspec():
    return vyos_argument_spec


def check_args(module, warnings):
    for key in vyos_argument_spec:
        if module._name == 'vyos_user':
            if key not in ['password', 'provider'] and module.params[key]:
                warnings.append('argument %s has been deprecated and will be in a future version' % key)
        else:
            if key != 'provider' and module.params[key]:
                warnings.append('argument %s has been deprecated and will be removed in a future version' % key)


def get_config(module, target='commands'):
    cmd = ' '.join(['show configuration', target])

    try:
        return _DEVICE_CONFIGS[cmd]
    except KeyError:
        rc, out, err = exec_command(module, cmd)
        if rc != 0:
            module.fail_json(msg='unable to retrieve current config', stderr=to_text(err, errors='surrogate_or_strict'))
        cfg = to_text(out, errors='surrogate_or_strict').strip()
        _DEVICE_CONFIGS[cmd] = cfg
        return cfg


def run_commands(module, commands, check_rc=True):
    responses = list()
    for cmd in to_list(commands):
        rc, out, err = exec_command(module, cmd)
        if check_rc and rc != 0:
            module.fail_json(msg=to_text(err, errors='surrogate_or_strict'), rc=rc)
        responses.append(to_text(out, errors='surrogate_or_strict'))
    return responses


def load_config(module, commands, commit=False, comment=None):
    rc, out, err = exec_command(module, 'configure')
    if rc != 0:
        module.fail_json(msg='unable to enter configuration mode', output=to_text(err, errors='surrogate_or_strict'))

    for cmd in to_list(commands):
        rc, out, err = exec_command(module, cmd)
        if rc != 0:
            # discard any changes in case of failure
            exec_command(module, 'exit discard')
            module.fail_json(msg='configuration failed')

    diff = None
    if module._diff:
        rc, out, err = exec_command(module, 'compare')
        out = to_text(out, errors='surrogate_or_strict')
        if not out.startswith('No changes'):
            rc, out, err = exec_command(module, 'show')
            diff = to_text(out, errors='surrogate_or_strict').strip()

    if commit:
        cmd = 'commit'
        if comment:
            cmd += ' comment "%s"' % comment
        rc, out, err = exec_command(module, cmd)
        if rc != 0:
            # discard any changes in case of failure
            exec_command(module, 'exit discard')
            module.fail_json(msg='commit failed: %s' % err)

    if not commit:
        exec_command(module, 'exit discard')
    else:
        exec_command(module, 'exit')

    if diff:
        return diff
