#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2012, Jan-Piet Mens <jpmens () gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

# see examples/playbooks/get_url.yml

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['stableinterface'],
                    'supported_by': 'core'}

DOCUMENTATION = r'''
---
module: get_url
short_description: Downloads files from HTTP, HTTPS, or FTP to node
description:
     - Downloads files from HTTP, HTTPS, or FTP to the remote server. The remote
       server I(must) have direct access to the remote resource.
     - By default, if an environment variable C(<protocol>_proxy) is set on
       the target host, requests will be sent through that proxy. This
       behaviour can be overridden by setting a variable for this task
       (see `setting the environment
       <http://docs.ansible.com/playbooks_environment.html>`_),
       or by using the use_proxy option.
     - HTTP redirects can redirect from HTTP to HTTPS so you should be sure that
       your proxy environment for both protocols is correct.
     - From Ansible 2.4 when run with C(--check), it will do a HEAD request to validate the URL but
       will not download the entire file or verify it against hashes.
     - For Windows targets, use the M(win_get_url) module instead.
version_added: '0.6'
options:
  url:
    description:
      - HTTP, HTTPS, or FTP URL in the form (http|https|ftp)://[user[:pass]]@host.domain[:port]/path
    required: true
  dest:
    description:
      - Absolute path of where to download the file to.
      - If C(dest) is a directory, either the server provided filename or, if
        none provided, the base name of the URL on the remote server will be
        used. If a directory, C(force) has no effect.
      - If C(dest) is a directory, the file will always be downloaded
        (regardless of the C(force) option), but replaced only if the contents changed..
    required: true
  tmp_dest:
    description:
      - Absolute path of where temporary file is downloaded to.
      - Defaults to C(TMPDIR), C(TEMP) or C(TMP) env variables or a platform specific value.
      - U(https://docs.python.org/2/library/tempfile.html#tempfile.tempdir)
    version_added: '2.1'
  force:
    description:
      - If C(yes) and C(dest) is not a directory, will download the file every
        time and replace the file if the contents change. If C(no), the file
        will only be downloaded if the destination does not exist. Generally
        should be C(yes) only for small local files.
      - Prior to 0.6, this module behaved as if C(yes) was the default.
    version_added: '0.7'
    default: 'no'
    type: bool
    aliases: [ thirsty ]
  backup:
    description:
      - Create a backup file including the timestamp information so you can get
        the original file back if you somehow clobbered it incorrectly.
    required: false
    default: 'no'
    type: bool
    version_added: '2.1'
  sha256sum:
    description:
      - If a SHA-256 checksum is passed to this parameter, the digest of the
        destination file will be calculated after it is downloaded to ensure
        its integrity and verify that the transfer completed successfully.
        This option is deprecated. Use C(checksum) instead.
    default: ''
    version_added: "1.3"
  checksum:
    description:
      - 'If a checksum is passed to this parameter, the digest of the
        destination file will be calculated after it is downloaded to ensure
        its integrity and verify that the transfer completed successfully.
        Format: <algorithm>:<checksum>, e.g. checksum="sha256:D98291AC[...]B6DC7B97"'
      - If you worry about portability, only the sha1 algorithm is available
        on all platforms and python versions.
      - The third party hashlib library can be installed for access to additional algorithms.
      - Additionally, if a checksum is passed to this parameter, and the file exist under
        the C(dest) location, the I(destination_checksum) would be calculated, and if
        checksum equals I(destination_checksum), the file download would be skipped
        (unless C(force) is true).
    default: ''
    version_added: "2.0"
  use_proxy:
    description:
      - if C(no), it will not use a proxy, even if one is defined in
        an environment variable on the target hosts.
    default: 'yes'
    type: bool
  validate_certs:
    description:
      - If C(no), SSL certificates will not be validated. This should only be used
        on personally controlled sites using self-signed certificates.
    default: 'yes'
    type: bool
  timeout:
    description:
      - Timeout in seconds for URL request.
    default: 10
    version_added: '1.8'
  headers:
    description:
        - Add custom HTTP headers to a request in the format "key:value,key:value".
    version_added: '2.0'
  url_username:
    description:
      - The username for use in HTTP basic authentication.
      - This parameter can be used without C(url_password) for sites that allow empty passwords.
    version_added: '1.6'
  url_password:
    description:
        - The password for use in HTTP basic authentication.
        - If the C(url_username) parameter is not specified, the C(url_password) parameter will not be used.
    version_added: '1.6'
  force_basic_auth:
    version_added: '2.0'
    description:
      - httplib2, the library used by the uri module only sends authentication information when a webservice
        responds to an initial request with a 401 status. Since some basic auth services do not properly
        send a 401, logins will fail. This option forces the sending of the Basic authentication header
        upon initial request.
    default: 'no'
    type: bool
  client_cert:
    description:
      - PEM formatted certificate chain file to be used for SSL client
        authentication. This file can also include the key as well, and if
        the key is included, C(client_key) is not required.
    version_added: '2.4'
  client_key:
    description:
      - PEM formatted file that contains your private key to be used for SSL
        client authentication. If C(client_cert) contains both the certificate
        and key, this option is not required.
    version_added: '2.4'
  others:
    description:
      - all arguments accepted by the M(file) module also work here
# informational: requirements for nodes
extends_documentation_fragment:
    - files
notes:
     - For Windows targets, use the M(win_get_url) module instead.
author:
- Jan-Piet Mens (@jpmens)
'''

EXAMPLES = r'''
- name: Download foo.conf
  get_url:
    url: http://example.com/path/file.conf
    dest: /etc/foo.conf
    mode: 0440

- name: Download file and force basic auth
  get_url:
    url: http://example.com/path/file.conf
    dest: /etc/foo.conf
    force_basic_auth: yes

- name: Download file with custom HTTP headers
  get_url:
    url: http://example.com/path/file.conf
    dest: /etc/foo.conf
    headers: 'key:value,key:value'

- name: Download file with check (sha256)
  get_url:
    url: http://example.com/path/file.conf
    dest: /etc/foo.conf
    checksum: sha256:b5bb9d8014a0f9b1d61e21e796d78dccdf1352f23cd32812f4850b878ae4944c

- name: Download file with check (md5)
  get_url:
    url: http://example.com/path/file.conf
    dest: /etc/foo.conf
    checksum: md5:66dffb5228a211e61d6d7ef4a86f5758

- name: Download file from a file path
  get_url:
    url: file:///tmp/afile.txt
    dest: /tmp/afilecopy.txt
'''

RETURN = r'''
backup_file:
    description: name of backup file created after download
    returned: changed and if backup=yes
    type: string
    sample: /path/to/file.txt.2015-02-12@22:09~
checksum_dest:
    description: sha1 checksum of the file after copy
    returned: success
    type: string
    sample: 6e642bb8dd5c2e027bf21dd923337cbb4214f827
checksum_src:
    description: sha1 checksum of the file
    returned: success
    type: string
    sample: 6e642bb8dd5c2e027bf21dd923337cbb4214f827
dest:
    description: destination file/path
    returned: success
    type: string
    sample: /path/to/file.txt
gid:
    description: group id of the file
    returned: success
    type: int
    sample: 100
group:
    description: group of the file
    returned: success
    type: string
    sample: "httpd"
md5sum:
    description: md5 checksum of the file after download
    returned: when supported
    type: string
    sample: "2a5aeecc61dc98c4d780b14b330e3282"
mode:
    description: permissions of the target
    returned: success
    type: string
    sample: "0644"
msg:
    description: the HTTP message from the request
    returned: always
    type: string
    sample: OK (unknown bytes)
owner:
    description: owner of the file
    returned: success
    type: string
    sample: httpd
secontext:
    description: the SELinux security context of the file
    returned: success
    type: string
    sample: unconfined_u:object_r:user_tmp_t:s0
size:
    description: size of the target
    returned: success
    type: int
    sample: 1220
src:
    description: source file used after download
    returned: changed
    type: string
    sample: /tmp/tmpAdFLdV
state:
    description: state of the target
    returned: success
    type: string
    sample: file
status:
    description: the HTTP status code from the request
    returned: always
    type: int
    sample: 200
uid:
    description: owner id of the file, after execution
    returned: success
    type: int
    sample: 100
url:
    description: the actual URL used for the request
    returned: always
    type: string
    sample: https://www.ansible.com/
'''

import datetime
import os
import re
import shutil
import tempfile
import traceback

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six.moves.urllib.parse import urlsplit
from ansible.module_utils._text import to_native
from ansible.module_utils.urls import fetch_url, url_argument_spec

# ==============================================================
# url handling


def url_filename(url):
    fn = os.path.basename(urlsplit(url)[2])
    if fn == '':
        return 'index.html'
    return fn


def url_get(module, url, dest, use_proxy, last_mod_time, force, timeout=10, headers=None, tmp_dest=''):
    """
    Download data from the url and store in a temporary file.

    Return (tempfile, info about the request)
    """
    if module.check_mode:
        method = 'HEAD'
    else:
        method = 'GET'

    rsp, info = fetch_url(module, url, use_proxy=use_proxy, force=force, last_mod_time=last_mod_time, timeout=timeout, headers=headers, method=method)

    if info['status'] == 304:
        module.exit_json(url=url, dest=dest, changed=False, msg=info.get('msg', ''))

    # Exceptions in fetch_url may result in a status -1, the ensures a proper error to the user in all cases
    if info['status'] == -1:
        module.fail_json(msg=info['msg'], url=url, dest=dest)

    if info['status'] != 200 and not url.startswith('file:/') and not (url.startswith('ftp:/') and info.get('msg', '').startswith('OK')):
        module.fail_json(msg="Request failed", status_code=info['status'], response=info['msg'], url=url, dest=dest)

    # create a temporary file and copy content to do checksum-based replacement
    if tmp_dest:
        # tmp_dest should be an existing dir
        tmp_dest_is_dir = os.path.isdir(tmp_dest)
        if not tmp_dest_is_dir:
            if os.path.exists(tmp_dest):
                module.fail_json(msg="%s is a file but should be a directory." % tmp_dest)
            else:
                module.fail_json(msg="%s directory does not exist." % tmp_dest)

        fd, tempname = tempfile.mkstemp(dir=tmp_dest)
    else:
        fd, tempname = tempfile.mkstemp()

    f = os.fdopen(fd, 'wb')
    try:
        shutil.copyfileobj(rsp, f)
    except Exception as e:
        os.remove(tempname)
        module.fail_json(msg="failed to create temporary content file: %s" % to_native(e),
                         exception=traceback.format_exc())
    f.close()
    rsp.close()
    return tempname, info


def extract_filename_from_headers(headers):
    """
    Extracts a filename from the given dict of HTTP headers.

    Looks for the content-disposition header and applies a regex.
    Returns the filename if successful, else None."""
    cont_disp_regex = 'attachment; ?filename="?([^"]+)'
    res = None

    if 'content-disposition' in headers:
        cont_disp = headers['content-disposition']
        match = re.match(cont_disp_regex, cont_disp)
        if match:
            res = match.group(1)
            # Try preventing any funny business.
            res = os.path.basename(res)

    return res


# ==============================================================
# main

def main():
    argument_spec = url_argument_spec()
    argument_spec.update(
        url=dict(type='str', required=True),
        dest=dict(type='path', required=True),
        backup=dict(type='bool'),
        sha256sum=dict(type='str', default=''),
        checksum=dict(type='str', default=''),
        timeout=dict(type='int', default=10),
        headers=dict(type='str'),
        tmp_dest=dict(type='path'),
    )

    module = AnsibleModule(
        # not checking because of daisy chain to file module
        argument_spec=argument_spec,
        add_file_common_args=True,
        supports_check_mode=True,
        mutually_exclusive=(['checksum', 'sha256sum']),
    )

    url = module.params['url']
    dest = module.params['dest']
    backup = module.params['backup']
    force = module.params['force']
    sha256sum = module.params['sha256sum']
    checksum = module.params['checksum']
    use_proxy = module.params['use_proxy']
    timeout = module.params['timeout']
    tmp_dest = module.params['tmp_dest']

    # Parse headers to dict
    if module.params['headers']:
        try:
            headers = dict(item.split(':', 1) for item in module.params['headers'].split(','))
        except:
            module.fail_json(msg="The header parameter requires a key:value,key:value syntax to be properly parsed.")
    else:
        headers = None

    dest_is_dir = os.path.isdir(dest)
    last_mod_time = None

    # workaround for usage of deprecated sha256sum parameter
    if sha256sum:
        checksum = 'sha256:%s' % (sha256sum)

    # checksum specified, parse for algorithm and checksum
    if checksum:
        try:
            algorithm, checksum = checksum.rsplit(':', 1)
            # Remove any non-alphanumeric characters, including the infamous
            # Unicode zero-width space
            checksum = re.sub(r'\W+', '', checksum).lower()
            # Ensure the checksum portion is a hexdigest
            int(checksum, 16)
        except ValueError:
            module.fail_json(msg="The checksum parameter has to be in format <algorithm>:<checksum>")

    if not dest_is_dir and os.path.exists(dest):
        checksum_mismatch = False

        # If the download is not forced and there is a checksum, allow
        # checksum match to skip the download.
        if not force and checksum != '':
            destination_checksum = module.digest_from_file(dest, algorithm)

            if checksum == destination_checksum:
                module.exit_json(msg="file already exists", dest=dest, url=url, changed=False)

            checksum_mismatch = True

        # Not forcing redownload, unless checksum does not match
        if not force and not checksum_mismatch:
            # allow file attribute changes
            module.params['path'] = dest
            file_args = module.load_file_common_arguments(module.params)
            file_args['path'] = dest
            changed = module.set_fs_attributes_if_different(file_args, False)

            if changed:
                module.exit_json(msg="file already exists but file attributes changed", dest=dest, url=url, changed=changed)
            module.exit_json(msg="file already exists", dest=dest, url=url, changed=changed)

        # If the file already exists, prepare the last modified time for the
        # request.
        mtime = os.path.getmtime(dest)
        last_mod_time = datetime.datetime.utcfromtimestamp(mtime)

        # If the checksum does not match we have to force the download
        # because last_mod_time may be newer than on remote
        if checksum_mismatch:
            force = True

    # download to tmpsrc
    tmpsrc, info = url_get(module, url, dest, use_proxy, last_mod_time, force, timeout, headers, tmp_dest)

    # Now the request has completed, we can finally generate the final
    # destination file name from the info dict.

    if dest_is_dir:
        filename = extract_filename_from_headers(info)
        if not filename:
            # Fall back to extracting the filename from the URL.
            # Pluck the URL from the info, since a redirect could have changed
            # it.
            filename = url_filename(info['url'])
        dest = os.path.join(dest, filename)

    checksum_src = None
    checksum_dest = None

    # If the remote URL exists, we're done with check mode
    if module.check_mode:
        os.remove(tmpsrc)
        res_args = dict(url=url, dest=dest, src=tmpsrc, changed=True, msg=info.get('msg', ''))
        module.exit_json(**res_args)

    # raise an error if there is no tmpsrc file
    if not os.path.exists(tmpsrc):
        os.remove(tmpsrc)
        module.fail_json(msg="Request failed", status_code=info['status'], response=info['msg'])
    if not os.access(tmpsrc, os.R_OK):
        os.remove(tmpsrc)
        module.fail_json(msg="Source %s is not readable" % (tmpsrc))
    checksum_src = module.sha1(tmpsrc)

    # check if there is no dest file
    if os.path.exists(dest):
        # raise an error if copy has no permission on dest
        if not os.access(dest, os.W_OK):
            os.remove(tmpsrc)
            module.fail_json(msg="Destination %s is not writable" % (dest))
        if not os.access(dest, os.R_OK):
            os.remove(tmpsrc)
            module.fail_json(msg="Destination %s is not readable" % (dest))
        checksum_dest = module.sha1(dest)
    else:
        if not os.path.exists(os.path.dirname(dest)):
            os.remove(tmpsrc)
            module.fail_json(msg="Destination %s does not exist" % (os.path.dirname(dest)))
        if not os.access(os.path.dirname(dest), os.W_OK):
            os.remove(tmpsrc)
            module.fail_json(msg="Destination %s is not writable" % (os.path.dirname(dest)))

    backup_file = None
    if checksum_src != checksum_dest:
        try:
            if backup:
                if os.path.exists(dest):
                    backup_file = module.backup_local(dest)
            module.atomic_move(tmpsrc, dest)
        except Exception as e:
            if os.path.exists(tmpsrc):
                os.remove(tmpsrc)
            module.fail_json(msg="failed to copy %s to %s: %s" % (tmpsrc, dest, to_native(e)),
                             exception=traceback.format_exc())
        changed = True
    else:
        changed = False

    if checksum != '':
        destination_checksum = module.digest_from_file(dest, algorithm)

        if checksum != destination_checksum:
            os.remove(dest)
            module.fail_json(msg="The checksum for %s did not match %s; it was %s." % (dest, checksum, destination_checksum))

    # allow file attribute changes
    module.params['path'] = dest
    file_args = module.load_file_common_arguments(module.params)
    file_args['path'] = dest
    changed = module.set_fs_attributes_if_different(file_args, changed)

    # Backwards compat only.  We'll return None on FIPS enabled systems
    try:
        md5sum = module.md5(dest)
    except ValueError:
        md5sum = None

    res_args = dict(
        url=url, dest=dest, src=tmpsrc, md5sum=md5sum, checksum_src=checksum_src,
        checksum_dest=checksum_dest, changed=changed, msg=info.get('msg', ''), status_code=info.get('status', '')
    )
    if backup_file:
        res_args['backup_file'] = backup_file

    # Mission complete
    module.exit_json(**res_args)


if __name__ == '__main__':
    main()
