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

    This class will obtain a read-only JWT in order to access our desired
    registry server API endpoints.

    Note, in Red Hat's registry-proxy implementation, a 401 error for a
    repository could indicate that the repository does not exist (ie, a 404).
    """

    def __init__(self, baseurl):
        if baseurl.endswith('/v2'):
            self.baseurl = baseurl
        else:
            self.baseurl = posixpath.join(baseurl, 'v2')
        self.session = requests.Session()
        headers = {
            'Accept': 'application/vnd.docker.distribution.manifest.v2+json'
        }
        self.session.headers.update(headers)
        self.tokens = {}

    def blob(self, repository, digest):
        """
        Get a blob by digest.

        :param str repository: eg "rhel7"
        :param str blob: digest to query, eg "sha256:123abcd..."
        """
        endpoint = 'blobs/%s' % digest
        r = self._get(repository, endpoint)
        return r.json()

    def config(self, repository, reference):
        """
        Return the config information for this image.

        :param str repository: repository we want to query eg. "rhel7"
        :param str reference: tag name in the repository, "7.5-ondeck"
        """
        manifest = self.manifest(repository, reference)
        manifest_digest = manifest['config']['digest']  # "sha256:123abcd..."
        config = self.blob(repository, manifest_digest)
        return config

    def find_realm_from_header(self, response):
        """
        Parse the headers of this response for the realm URL.

        :param Reponse response: requests.Response object
        :returns: realm URL
        """
        auth_header = response.headers['WWW-Authenticate']
        parts = auth_header.split(' ')
        if parts[0] != 'Bearer':
            raise ValueError('WWW-Authenticate: %s' % auth_header)
        for part in parts:
            if part.startswith('realm='):
                realm = part[6:].strip('"')
                return realm

    def store_token(self, realm, repository):
        """
        Get and store a token for this repo
        """
        auth_url = '%s?scope=repository:%s:pull' % (realm, repository)
        r = self.session.get(auth_url)
        r.raise_for_status()
        data = r.json()
        token = data['token']
        self.tokens[repository] = token
        return token

    def _get(self, repository, endpoint):
        """
        Get a docker distribution API endpoint URL.

        :param str repository: repository we want to query eg. "rhel7"
        :param str path: API endpoint for this repository, eg.
                         "manifests/7.5-ondeck"
        :returns: Response object
        """
        url = posixpath.join(self.baseurl, repository, endpoint)
        token = self.tokens.get(repository)
        if not token:
            r = self.session.get(url)
            if r.status_code == 401:
                realm = self.find_realm_from_header(r)
                self.store_token(realm, repository)
                return self._get(repository, endpoint)
        headers = {'Authorization': 'Bearer %s' % token}
        r = self.session.get(url, headers=headers)
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
        endpoint = 'manifests/%s' % reference
        r = self._get(repository, endpoint)
        return r.json()
