from urllib.parse import urlparse
import base64
import os
import json
import posixpath
import requests
from bucko.build import Build

"""
Methods to interact with our container registry API
"""

# https://docs.docker.com/registry/spec/api/#detail

# Possibly affected by https://access.redhat.com/articles/6138332 ?


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

    def find_realm_service(self, response):
        """
        Parse the headers of this response for the realm URL and service name.

        :param Reponse response: requests.Response object
        :returns: two element tuple containing the realm URL and service name.
        """
        auth_header = response.headers['WWW-Authenticate']
        auth_type, bearer = auth_header.split(' ', 1)
        if auth_type != 'Bearer':
            raise ValueError('WWW-Authenticate: %s' % auth_header)
        realm = None
        service = None
        parts = bearer.split(',')
        for part in parts:
            if part.startswith('realm='):
                realm = part[6:].strip('"')
            if part.startswith('service='):
                service = part[8:].strip('"')
        return (realm, service)

    def store_token(self, realm, service, repository):
        """
        Get and store a JWT Bearer token for this repository.

        If we have a saved username+password from podman-login, we'll
        authenticate to the "realm" URL with that. If not, we will not perform
        any authentication to "realm", and we'll simply obtain an anonymous
        pull token.

        :param str realm: eg. "https://registry.example.com/oauth/token"
        :param str service: eg. "registry", or None
        :param str repository: eg. "cp/ibm-ceph/prometheus-node-exporter"
        """
        params = {'scope': f'repository:{repository}:pull'}
        if service:
            params['service'] = service
        r = self.session.get(realm, params=params, auth=self.auth)
        r.raise_for_status()
        data = r.json()
        token = data['token']
        self.tokens[repository] = token
        return token

    @property
    def auth(self):
        """ Returns HTTPBasicAuth if we have a saved credential, or None. """
        o = urlparse(self.baseurl)
        credential = self.load_credentials(o.hostname)
        if not credential:
            return None
        username, password = credential
        return requests.auth.HTTPBasicAuth(username, password)

    @property
    def authfile(self):
        # skopeo requires XDG_RUNTIME_DIR
        # https://github.com/containers/image/issues/1097
        # For simplicity we will require it also.
        if not os.getenv('XDG_RUNTIME_DIR'):
            return None
        return os.path.join(os.environ['XDG_RUNTIME_DIR'],
                            'containers', 'auth.json')

    def load_credentials(self, hostname):
        """
        Read credentials from podman's default location,
        ${XDG_RUNTIME_DIR}/containers/auth.json.

        See podman-login(1) and skopeo-login(1) for details.

        :returns: two-element list (the username and password), or None
        """
        if not self.authfile:
            return None
        try:
            with open(self.authfile) as f:
                data = json.load(f)
        except FileNotFoundError:
            return None
        auths = data.get('auths', {})
        settings = auths.get(hostname, {})
        auth = settings.get('auth')
        if not auth:
            return None
        username_password = base64.b64decode(auth).decode()
        return username_password.split(':', 1)

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
                (realm, service) = self.find_realm_service(r)
                self.store_token(realm, service, repository)
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
        labels = data['config']['Labels']
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
