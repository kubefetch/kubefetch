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
from ansible.module_utils.network_common import to_list, ComplexList
from ansible.module_utils.connection import exec_command

_DEVICE_CONFIGS = {}

ios_provider_spec = {
    'host': dict(),
    'port': dict(type='int'),
    'username': dict(fallback=(env_fallback, ['ANSIBLE_NET_USERNAME'])),
    'password': dict(fallback=(env_fallback, ['ANSIBLE_NET_PASSWORD']), no_log=True),
    'ssh_keyfile': dict(fallback=(env_fallback, ['ANSIBLE_NET_SSH_KEYFILE']), type='path'),
    'authorize': dict(fallback=(env_fallback, ['ANSIBLE_NET_AUTHORIZE']), type='bool'),
    'auth_pass': dict(fallback=(env_fallback, ['ANSIBLE_NET_AUTH_PASS']), no_log=True),
    'timeout': dict(type='int'),
}
ios_argument_spec = {
    'provider': dict(type='dict', options=ios_provider_spec),
}
ios_argument_spec.update(ios_provider_spec)


def get_argspec():
    return ios_argument_spec


def check_args(module, warnings):
    for key in ios_argument_spec:
        if module._name == 'ios_user':
            if key not in ['password', 'provider', 'authorize'] and module.params[key]:
                warnings.append('argument %s has been deprecated and will be in a future version' % key)
        else:
            if key not in ['provider', 'authorize'] and module.params[key]:
                warnings.append('argument %s has been deprecated and will be removed in a future version' % key)


def get_defaults_flag(module):
    rc, out, err = exec_command(module, 'show running-config ?')
    out = to_text(out, errors='surrogate_then_replace')

    commands = set()
    for line in out.splitlines():
        if line.strip():
            commands.add(line.strip().split()[0])

    if 'all' in commands:
        return ['all']
    else:
        return ['full']


def get_config(module, flags=[]):
    cmd = 'show running-config '
    cmd += ' '.join(flags)
    cmd = cmd.strip()

    try:
        return _DEVICE_CONFIGS[cmd]
    except KeyError:
        rc, out, err = exec_command(module, cmd)
        if rc != 0:
            module.fail_json(msg='unable to retrieve current config', stderr=to_text(err, errors='surrogate_then_replace'))
        cfg = to_text(out, errors='surrogate_then_replace').strip()
        _DEVICE_CONFIGS[cmd] = cfg
        return cfg


def to_commands(module, commands):
    spec = {
        'command': dict(key=True),
        'prompt': dict(),
        'answer': dict()
    }
    transform = ComplexList(spec, module)
    return transform(commands)


def run_commands(module, commands, check_rc=True):
    responses = list()
    commands = to_commands(module, to_list(commands))
    for cmd in commands:
        cmd = module.jsonify(cmd)
        rc, out, err = exec_command(module, cmd)
        if check_rc and rc != 0:
            module.fail_json(msg=to_text(err, errors='surrogate_then_replace'), rc=rc)
        responses.append(to_text(out, errors='surrogate_then_replace'))
    return responses


def load_config(module, commands):

    rc, out, err = exec_command(module, 'configure terminal')
    if rc != 0:
        module.fail_json(msg='unable to enter configuration mode', err=to_text(out, errors='surrogate_then_replace'))

    for command in to_list(commands):
        if command == 'end':
            continue
        rc, out, err = exec_command(module, command)
        if rc != 0:
            module.fail_json(msg=to_text(err, errors='surrogate_then_replace'), command=command, rc=rc)

    exec_command(module, 'end')
