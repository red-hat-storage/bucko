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
        if os.getenv('REGISTRY_AUTH_FILE'):
            return os.environ['REGISTRY_AUTH_FILE']
        # skopeo requires XDG_RUNTIME_DIR if REGISTRY_AUTH_FILE is unset,
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

    @property
    def lookaside(self):
        """
        Read the lookaside (or sigstore) URL from /etc/containers/registry.d/

        See
        https://github.com/containers/image/blob/main/docs/signature-protocols.md
        for details. This used to be called "sigstore" in RHEL 8.

        Example:
        https://registry.redhat.io/containers/sigstore/

        :returns: the sigstore URL string, or None
        """
        # bucko's main use-case does not exercise the signature codepaths yet.
        # For flexibility and simplicity, I'm importing this dependency here,
        # so you only need to install PyYAML if you're checking signatures.
        import yaml
        o = urlparse(self.baseurl)
        hostname = o.hostname
        conf = f'/etc/containers/registries.d/{hostname}.yaml'
        try:
            with open(conf) as f:
                data = yaml.safe_load(f)
        except FileNotFoundError:
            return None
        docker = data.get('docker')
        if not docker:
            return None
        host = docker.get(hostname)
        if not host:
            return None
        lookaside = host.get('lookaside')
        if lookaside:
            return lookaside
        return host.get('sigstore')

    def _get(self, repository, endpoint, additional_headers={}):
        """
        Get a docker distribution API endpoint URL.

        :param str repository: repository we want to query eg. "rhel7"
        :param str path: API endpoint for this repository, eg.
                         "manifests/7.5-ondeck"
        :param dict additional_headers: Add these headers to the request
        :returns: Response object
        """
        url = posixpath.join(self.baseurl, repository, endpoint)
        token = self.tokens.get(repository)
        if not token:
            r = self.session.get(url)
            if r.status_code == 401:
                (realm, service) = self.find_realm_service(r)
                self.store_token(realm, service, repository)
                return self._get(repository, endpoint, additional_headers)
        headers = {'Authorization': 'Bearer %s' % token}
        headers.update(additional_headers)
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

    def signatures(self, image):
        """
        Return the GPG signature data for this image.

        See
        https://github.com/containers/image/blob/main/docs/containers-signature.5.md
        and
        https://github.com/containers/image/blob/main/docs/signature-protocols.md

        :param str image: image name, eg. "cp/ibm-ceph/ceph-5-rhel8:latest"
        :returns: list of signatures for this image's manifest sha256 digest.
                  Note that one manifest digest can have multiple tags.
        """
        # Lots of duplicated code here...
        (repository, reference) = image.split(':', 1)
        manifests = self.manifest(repository, reference, manifest_list=True)
        for manifest in manifests['manifests']:
            platform = manifest['platform']
            # hard-coding so we only return signatures for one arch...
            if platform['architecture'] != 'amd64':
                continue
            digest = manifest['digest']

        signatures = []
        if self.lookaside:
            # Use that URL + /signature-1, 2, 3, etc. until you hit a 404.
            # The resulting data is the gpg-signed JSON blob.
            template = posixpath.join(
                self.lookaside,
                repository + '@' + digest.replace(':', '='),
                'signature-{index}'
            )
            index = 1
            MAX_SIGNATURES = 25  # sanity circuit breaker
            while index < MAX_SIGNATURES:
                url = template.format(index=index)
                response = self.session.get(url)
                if response.ok:
                    signatures.append(response.content)
                    index += 1
                else:
                    break
        else:
            # No /etc/containers/registries.d for this host.
            # Query the default "extensions" URL on this registry.
            token = self.tokens[repository]
            headers = {'Authorization': 'Bearer %s' % token}
            baseurl = self.baseurl.replace('/v2', '/extensions/v2')
            url = posixpath.join(baseurl, repository, 'signatures', digest)
            r = self.session.get(url, headers=headers)
            if r.status_code == 404:
                return []
            r.raise_for_status()
            data = r.json()
            for entry in data['signatures']:
                # "content" is the base64-encoded GPG binary blob.
                signature = base64.b64decode(entry['content'])
                signatures.append(signature)
        return signatures

    def signature_payloads(self, image):
        """
        Return the JSON document payloads that GPG has signed.

        Ignores GPG signature validity and simply returns the data.

        :returns: list of dicts, one per signature/ref
        """
        # Pipe each binary file thru /usr/bin/gpg to read the contents
        # on STDOUT and view the signature info on STDERR
        # Or, run gpg --verify /tmp/myfile to only verify the signature.
        payloads = []
        from subprocess import Popen, PIPE
        signatures = self.signatures(image)
        for signature in signatures:
            p = Popen(['gpg'], stdout=PIPE, stdin=PIPE, stderr=PIPE)
            stdout_data = p.communicate(input=signature)[0]
            string = stdout_data.decode()
            payload = json.loads(string)
            payloads.append(payload)
        return payloads

    def signature_references(self, image):
        """
        Return all the docker refs (tags) that are signed for this container
        image.

        Ignores GPG signature validity and simply returns the list of refs.

        :returns: list of docker refs (str)
        """
        signatures = self.signature_payloads(image)  # bucko.build.Build
        return [s['critical']['identity']['docker-reference']
                for s in signatures]

    def manifest(self, repository, reference, manifest_list=False):
        """
        Get the manifest information about this image.

        :param str repository: repository to query, eg "rhel7"
        :param str reference: tag name in the repository, "7.5-ondeck"
        :param bool manifest_list: return the "fat manifests", see
                                   https://docs.docker.com/registry/spec/manifest-v2-2/
        """
        endpoint = 'manifests/%s' % reference
        additional_headers = {}
        if manifest_list:
            additional_headers['Accept'] = 'application/vnd.docker.distribution.manifest.list.v2+json'
        r = self._get(repository, endpoint, additional_headers)
        return r.json()
