import posixpath
import requests
from bucko.build import Build

"""
Methods to interact with our container registry API
"""

# https://docs.docker.com/registry/spec/api/#detail


class Registry(object):
    """
    Simple container registry client that query build NVRs.

    Note: This only supports a registry implementation that allows direct,
    anonymous HTTP(s) access (ie Pulp). Eventually we will need to add support
    for obtaining a read-only JWT in order to access our desired registry
    server API endpoints.
    """

    def __init__(self, baseurl):
        self.baseurl = baseurl
        self.session = requests.Session()
        headers = {
            'Accept': 'application/vnd.docker.distribution.manifest.v2+json'
        }
        self.session.headers.update(headers)

    def blob(self, repository, digest):
        """
        Get a blob by digest.

        :param str repository: eg "rhel7"
        :param str blob: digest to query, eg "sha256:123abcd..."
        """
        url = 'v2/%s/blobs/%s' % (repository, digest)
        r = self._get(url)
        return r.json()

    def config(self, repository, reference):
        """
        Return the config information for this image.

        :param str repository: eg "rhel7"
        :param str reference: tag name in the repository, "7.5-ondeck"
        """
        manifest = self.manifest(repository, reference)
        manifest_digest = manifest['config']['digest']  # "sha256:123abcd..."
        config = self.blob(repository, manifest_digest)
        return config

    def _get(self, path):
        """
        Get a docker distribution API endpoint URL.

        :param str path: API endpoint path to query, eg "v2/_catalog"
        :returns: Response object
        """
        url = posixpath.join(self.baseurl, path)
        r = self.session.get(url)
        r.raise_for_status()
        return r

    def build(self, image):
        """
        Return the Koji name-version-release information for this image.

        :param str image: image name, eg. "rhel7:7.5-ondeck"
        :returns: bucko.build.Build class
        """
        (repository, reference) = image.split(':', 1)
        # repository: image repository name, eg. "rhel7"
        # reference: tag name in the repository, eg. "7.5-ondeck"
        data = self.config(repository, reference)
        labels = data['container_config']['Labels']
        return Build(labels['com.redhat.component'],
                     labels['version'],
                     labels['release'])

    def manifest(self, repository, reference):
        """
        Get the manifest information about this image.

        :param str repository: repository to query, eg "rhel7"
        :param str reference: tag name in the repository, "7.5-ondeck"
        """
        url = 'v2/%s/manifests/%s' % (repository, reference)
        r = self._get(url)
        return r.json()
