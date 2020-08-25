#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of Ansible

# (c) 2015, Jon Hawkesworth (@jhawkesworth) <figs@unity.demon.co.uk>
# Copyright (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['stableinterface'],
                    'supported_by': 'core'}


DOCUMENTATION = r'''
---
module: win_copy
version_added: '1.9.2'
short_description: Copies files to remote locations on windows hosts
description:
- The C(win_copy) module copies a file on the local box to remote windows locations.
- For non-Windows targets, use the M(copy) module instead.
options:
  content:
    description:
    - When used instead of C(src), sets the contents of a file directly to the
      specified value. This is for simple values, for anything complex or with
      formatting please switch to the template module.
    version_added: "2.3"
  dest:
    description:
    - Remote absolute path where the file should be copied to. If src is a
      directory, this must be a directory too.
    - Use \ for path separators or \\ when in "double quotes".
    - If C(dest) ends with \ then source or the contents of source will be
      copied to the directory without renaming.
    - If C(dest) is a nonexistent path, it will only be created if C(dest) ends
      with "/" or "\", or C(src) is a directory.
    - If C(src) and C(dest) are files and if the parent directory of C(dest)
      doesn't exist, then the task will fail.
    required: true
  force:
    version_added: "2.3"
    description:
    - If set to C(yes), the file will only be transferred if the content
      is different than destination.
    - If set to C(no), the file will only be transferred if the
      destination does not exist.
    - If set to C(no), no checksuming of the content is performed which can
      help improve performance on larger files.
    default: 'yes'
    type: bool
  local_follow:
    version_added: '2.4'
    description:
    - This flag indicates that filesystem links in the source tree, if they
      exist, should be followed.
    default: 'yes'
    type: bool
  remote_src:
    description:
    - If False, it will search for src at originating/master machine, if True
      it will go to the remote/target machine for the src.
    default: 'no'
    type: bool
    version_added: "2.3"
  src:
    description:
    - Local path to a file to copy to the remote server; can be absolute or
      relative.
    - If path is a directory, it is copied (including the source folder name)
      recursively to C(dest).
    - If path is a directory and ends with "/", only the inside contents of
      that directory are copied to the destination. Otherwise, if it does not
      end with "/", the directory itself with all contents is copied.
    - If path is a file and dest ends with "\", the file is copied to the
      folder with the same filename.
    required: true
notes:
- For non-Windows targets, use the M(copy) module instead.
- Currently win_copy does not support copying symbolic links from both local to
  remote and remote to remote.
- It is recommended that backslashes C(\) are used instead of C(/) when dealing
  with remote paths.
- Because win_copy runs over WinRM, it is not a very efficient transfer
  mechanism. If sending large files consider hosting them on a web service and
  using M(win_get_url) instead.
author:
- Jon Hawkesworth (@jhawkesworth)
- Jordan Borean (@jborean93)
'''

EXAMPLES = r'''
- name: Copy a single file
  win_copy:
    src: /srv/myfiles/foo.conf
    dest: c:\Temp\renamed-foo.conf

- name: Copy a single file keeping the filename
  win_copy:
    src: /src/myfiles/foo.conf
    dest: c:\temp\

- name: Copy folder to c:\temp (results in C:\Temp\temp_files)
  win_copy:
    src: files/temp_files
    dest: c:\Temp

- name: Copy folder contents recursively
  win_copy:
    src: files/temp_files/
    dest: c:\Temp

- name: Copy a single file where the source is on the remote host
  win_copy:
    src: C:\temp\foo.txt
    dest: C:\ansible\foo.txt
    remote_src: True

- name: Copy a folder recursively where the source is on the remote host
  win_copy:
    src: C:\temp
    dest: C:\ansible
    remote_src: True

- name: Set the contents of a file
  win_copy:
    dest: C:\temp\foo.txt
    content: abc123
'''

RETURN = r'''
dest:
    description: destination file/path
    returned: changed
    type: string
    sample: C:\Temp\
src:
    description: source file used for the copy on the target machine
    returned: changed
    type: string
    sample: /home/httpd/.ansible/tmp/ansible-tmp-1423796390.97-147729857856000/source
checksum:
    description: sha1 checksum of the file after running copy
    returned: success, src is a file
    type: string
    sample: 6e642bb8dd5c2e027bf21dd923337cbb4214f827
size:
    description: size of the target, after execution
    returned: changed, src is a file
    type: int
    sample: 1220
operation:
    description: whether a single file copy took place or a folder copy
    returned: success
    type: string
    sample: file_copy
original_basename:
    description: basename of the copied file
    returned: changed, src is a file
    type: string
    sample: foo.txt
'''
