import posixpath
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse
import os
import paramiko
import shutil

"""
Publish files to a "push URL", and retrieve them via an "HTTP URL".

The "push URL" can be a file:// URL for local testing or an sftp:// URL for
publishing to a remote web server.
"""

import logging
paramiko.util.get_logger("paramiko.transport").setLevel(logging.DEBUG)
paramiko.util.get_logger("paramiko").setLevel(logging.DEBUG)


class Publisher(object):
    def __init__(self, push_url, http_url):
        self.push_url = push_url
        self.http_url = http_url

    def publish(self, file_):
        o = urlparse(self.push_url)
        if o.scheme == 'sftp':
            self._ssh_publish(file_)
        elif o.scheme == 'file':
            self._fs_publish(file_)
        else:
            err = 'push_url must be an sftp:// or file:// URL'
            raise NotImplementedError(err)
        return posixpath.join(self.http_url, os.path.basename(file_))

    def _ssh_publish(self, file_):
        """ Publish a file to an SFTP server. """
        url = urlparse(self.push_url)
        destfile = os.path.join(url.path, os.path.basename(file_))
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        # ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(url.netloc.split('@')[-1], username=url.username)

        sftp = ssh.open_sftp()
        sftp.put(file_, destfile)
        sftp.close()
        ssh.close()

    def _fs_publish(self, file_):
        url = urlparse(self.push_url)
        destfile = os.path.join(url.path, os.path.basename(file_))
        shutil.copy(file_, destfile)
