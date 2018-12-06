import os
import posixpath
import tempfile
import productmd.compose
try:
    from configparser import RawConfigParser
except ImportError:
    from ConfigParser import RawConfigParser

# Default set of GPG signing keys:
GPG_KEYS = {
    # From https://access.redhat.com/security/team/key
    # Red Hat GA signing key
    'fd431d51': 'file:///etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release',
    # Red Hat Beta signing key
    'f21541eb': 'file:///etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-beta',
}


class RepoCompose(productmd.compose.Compose):
    """ An online compose for which we will write a yum .repo file. """

    def __init__(self, path, keys={}):
        super(RepoCompose, self).__init__(path)
        # Sanity-check that this is a layered product compose.
        if not self.info.release.is_layered:
            raise RuntimeError('%s must be layered' % self.info.release.short)
        # Dict of possible GPG signing keys:
        self.keys = GPG_KEYS.copy()
        self.keys.update(keys)

    def get_variant_url(self, v, arch):
        return posixpath.join(self.compose_path, v.paths.repository[arch])

    def get_variant_gpg_key(self, v, arch):
        """
        Return the self.keys (path) to a key for this variant.

        :returns str: the gpg key path, eg. 'file:///etc/pki/rpm-gpg/FOO'
        :returns None: if all RPMs are unsigned
        :raises: ``RuntimeError``, if some of the RPMs are signed+unsigned, or
                 if signed by multiple keys.
        """
        key = None
        for pkg in self.rpms.rpms[str(v)][arch].values():
            for pkgfile in pkg.values():
                # This code assumes that one of the following cases is true:
                #  A. None of the RPMs are GPG-signed
                #  B. All of the RPMs are GPG-signed by one single key
                if key is None and pkgfile['sigkey'] is not None:
                    key = pkgfile['sigkey']
                if key is not None and pkgfile['sigkey'] is None:
                    raise RuntimeError('%s is unsigned' % pkgfile['path'])
                if key is not None and key != pkgfile['sigkey']:
                    raise RuntimeError('multiple keys found: %s and %s' %
                                       (key, pkgfile['sigkey']))
        if key is None:
            return None
        return self.keys[key]

    def write_yum_repo_file(self, arch='x86_64'):
        """ Write a Yum .repo file into a temporary directory.

        :returns str: the filename path, eg. '/tmp/foo.compose/MYCOMPOSE.repo'
        """
        filename = '%s.repo' % self.info.compose.id
        filename = os.path.join(tempfile.mkdtemp(suffix='.compose'), filename)
        config = RawConfigParser()
        try:
            variants = self.info.get_variants(arch=arch)
        except AttributeError:
            # Bug in productmd here with the arch parameter?
            #   "AttributeError: 'Variants' object has no attribute 'arches'"
            # https://github.com/release-engineering/productmd/issues/65
            # Workaround: filter the variants manually
            variants = []
            for v in self.info.get_variants():
                if arch in v.arches:
                    variants.append(v)

        for v in variants:
            name = '%s-%s' % (self.info.get_release_id(), v.uid)
            url = self.get_variant_url(v, arch)
            gpgkey = self.get_variant_gpg_key(v, arch)
            config.add_section(name)
            config.set(name, 'name', self.info.compose.id + ' ' + v.uid)
            config.set(name, 'baseurl', url)
            config.set(name, 'enabled', 1)
            config.set(name, 'gpgcheck', 0)
            if gpgkey is not None:
                config.set(name, 'gpgcheck', 1)
                config.set(name, 'gpgkey', gpgkey)

        with open(filename, 'w') as configfile:
            config.write(configfile)
        return filename
