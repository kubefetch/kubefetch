# Copyright (c) 2018 Matt Martz <matt@sivel.net>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import pytest

from ansible.executor.module_common import modify_module
from ansible.module_utils.six import PY2


FAKE_OLD_MODULE = b'''#!/usr/bin/python
import sys
print('{"result": "%s"}' % sys.executable)
'''


@pytest.fixture
def fake_old_module_open(mocker):
    m = mocker.mock_open(read_data=FAKE_OLD_MODULE)
    if PY2:
        mocker.patch('__builtin__.open', m)
    else:
        mocker.patch('builtins.open', m)


def test_shebang(fake_old_module_open):
    (data, style, shebang) = modify_module('fake_module', 'fake_path', {})
    assert shebang == '#!/usr/bin/python'


def test_shebang_task_vars(fake_old_module_open):
    task_vars = {
        'ansible_python_interpreter': '/usr/bin/python3'
    }

    (data, style, shebang) = modify_module('fake_module', 'fake_path', {}, task_vars=task_vars)
    assert shebang == '#!/usr/bin/python3'
