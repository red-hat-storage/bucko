import sys
import subprocess
from bucko.log import log
import backoff


"""
Publish container images to a registry with skopeo and podman.
"""

PY2 = sys.version_info[0] == 2


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
        :returns: the destination (str)
        """
        source = 'docker://%s' % source_image
        tmpl = 'docker://{host}/{namespace}/{repository}:{tag}'
        destination = tmpl.format(host=self.host,
                                  namespace=namespace,
                                  repository=repository,
                                  tag=tag)
        self.login()
        self.copy(source, destination)
        self.logout()
        return destination[9:]

    @backoff.on_exception(backoff.expo,
                          subprocess.CalledProcessError,
                          max_tries=3)
    def copy(self, source, destination):
        """
        Run "skopeo copy" with retries.

        Sometimes "skopeo copy" will fail with "read: connection reset by
        peer", so we should retry the copy operation a couple times.
        """
        skopeo('copy', source, destination)

    def login(self):
        # Don't print the password string to the log.
        log.info('+ sudo podman login -p **** -u unused %s', self.host)
        try:
            podman('login', '-p', self.token, '-u', 'unused', self.host,
                   log_cmd=False, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            if PY2:
                output = e.output
            else:
                output = e.output.decode('utf-8')
            log.error(output)
            raise SystemExit(e.returncode)

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
    args = ('sudo', 'podman') + args
    return cmd(*args, **kwargs)


def skopeo(*args, **kwargs):
    """ Run a priv skopeo shell command, optionally returning the output """
    args = ('sudo', 'skopeo') + args
    return cmd(*args, **kwargs)
