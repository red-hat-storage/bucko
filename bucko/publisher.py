import posixpath
from urlparse import urlparse
import os
from paramiko import SSHClient
import shutil


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
        ssh = SSHClient()
        ssh.load_system_host_keys()
        # ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(url.netloc, username=url.username)

        sftp = ssh.open_sftp()
        sftp.put(file_, destfile)
        sftp.close()
        ssh.close()

    def _fs_publish(self, file_):
        url = urlparse(self.push_url)
        destfile = os.path.join(url.path, os.path.basename(file_))
        shutil.copy(file_, destfile)
