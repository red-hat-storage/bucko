import posixpath
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse
import os
import paramiko
import shutil
import boto3

"""
Publish files to a "push URL", and retrieve them via an "HTTP URL".

The "push URL" can be a file:// URL for local testing or an sftp:// URL for
publishing to a remote web server.
"""


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
        elif o.scheme == 's3':
            self._s3_publish(file_)
        else:
            err = 'push_url must be an sftp://, file://, or s3:// URL'
            raise NotImplementedError(err)
        return posixpath.join(self.http_url, os.path.basename(file_))

    def _ssh_publish(self, file_):
        """ Publish a file to an SFTP server. """
        url = urlparse(self.push_url)
        destfile = os.path.join(url.path, os.path.basename(file_))
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        host = url.netloc.split('@')[-1]
        # ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=url.username)

        sftp = ssh.open_sftp()
        sftp.put(file_, destfile)
        sftp.close()
        ssh.close()

    def _fs_publish(self, file_):
        url = urlparse(self.push_url)
        destfile = os.path.join(url.path, os.path.basename(file_))
        shutil.copy(file_, destfile)

    def _s3_publish(self, file_):
        """ Publish a file to an s3 server. """
        # Must set these env variables:
        assert os.environ['AWS_ACCESS_KEY_ID']
        assert os.environ['AWS_SECRET_ACCESS_KEY']
        s3 = boto3.client('s3', endpoint_url=os.environ['AWS_ENDPOINT_URL'])
        url = urlparse(self.push_url)
        bucket = url.netloc
        object_name = os.path.basename(file_)
        s3.upload_file(
            file_, bucket, object_name,
            ExtraArgs={'ContentType': 'text/plain'},
        )
