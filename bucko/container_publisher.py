import sys
import subprocess
from bucko.log import log


"""
Publish container images to a registry with skopeo and podman.
"""

PY2 = sys.version_info[0] == 2

# Skopeo expects to read the credential from /run/containers.
# We have to force newer versions of podman to write to this location.
# https://bugzilla.redhat.com/show_bug.cgi?id=1800815
REGISTRY_AUTH_FILE_ENV='REGISTRY_AUTH_FILE=/run/containers/0/auth.json'

class ContainerPublisher(object):
    def __init__(self, host, token):
        self.host = host
        self.token = token

    def publish(self, source_image, namespace, repository, tag):
        """
        Copy a container to a namespace/repository:tag

        :param str source_image: the source image to copy
        :param str namespace: the namespace in the dest repo, eg "ceph"
        :param str repository: the destination repo, eg "ceph-4.0-rhel-8"
        :param str tag: the tag for this destionation repo, eg "latest"
        :returns: the destination (str) or None if the copy failed.
        """
        source = 'docker://%s' % source_image
        tmpl = 'docker://{host}/{namespace}/{repository}:{tag}'
        destination = tmpl.format(host=self.host,
                                  namespace=namespace,
                                  repository=repository,
                                  tag=tag)
        success = self.login() and self.copy(source, destination)
        self.logout()
        if success:
            return destination[9:]

    def copy(self, source, destination):
        """
        Run "skopeo copy" to publish this image to a destination.

        Sometimes "skopeo copy" will fail with "read: connection reset by
        peer" or "Error writing blob ...: unexpected EOF" (eg. INC1518133).

        :returns: True if the copy succeeded, False if the copy failed.
        """
        try:
            skopeo('copy', source, destination)
            return True
        except subprocess.CalledProcessError as e:
            if PY2:
                output = e.output
            else:
                output = e.output.decode('utf-8')
            log.warning('"skopeo copy" failed with exit code %d', e.returncode)
            log.warning(output)
        return False

    def login(self):
        """
        Run "podman login" to authenticate for copy().

        Sometimes "podman login" will fail with "invalid username/password",
        even if the token is correct.

        :returns: True if the login succeeded, False if the login failed.
        """
        # Don't print the password string to the log.
        log.info('+ sudo podman %s login -p **** -u unused %s',
                 REGISTRY_AUTH_FILE_ENV, self.host)
        try:
            podman('login', '-p', self.token, '-u', 'unused', self.host,
                   log_cmd=False, stderr=subprocess.STDOUT)
            return True
        except subprocess.CalledProcessError as e:
            if PY2:
                output = e.output
            else:
                output = e.output.decode('utf-8')
            log.warning('"podman login" failed with exit code %d', e.returncode)
            log.warning(output)
            return False

    def logout(self):
        podman('logout', self.host)


def cmd(*args, **kwargs):
    """ Run a command, with logging, returning the output """
    log_cmd = kwargs.pop('log_cmd', True)
    if log_cmd:
        log.info('+ ' + ' '.join(args))
    output = subprocess.check_output(args, **kwargs)
    if PY2:
        return output
    return output.decode('utf-8')


def podman(*args, **kwargs):
    """ Run a priv podman shell command, optionally returning the output """
    args = ('sudo', REGISTRY_AUTH_FILE_ENV, 'podman') + args
    return cmd(*args, **kwargs)


def skopeo(*args, **kwargs):
    """ Run a priv skopeo shell command, optionally returning the output """
    args = ('sudo', 'skopeo') + args
    return cmd(*args, **kwargs)
