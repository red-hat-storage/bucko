import os
from bucko.repo_compose import RepoCompose
import productmd.compose
import pytest
try:
    from configparser import ConfigParser
except ImportError:
    import ConfigParser

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(TESTS_DIR, 'fixtures')

INTERNAL_KEYS = {'f000000d': '/etc/RPM-GPG-KEY-f00d'}


@pytest.fixture
def repocompose():
    compose = RepoCompose(FIXTURES_DIR, INTERNAL_KEYS)
    bp_url = 'http://example.com/foo'
    bp_gpgkey = None
    bp_extras = None
    compose.set_base_product(bp_url, bp_gpgkey, bp_extras)
    return compose


@pytest.fixture
def repocompose_bp_signed(repocompose):
    bp_url = 'http://example.com/foo'
    bp_gpgkey = 'f000000d'
    bp_extras = None
    repocompose.set_base_product(bp_url, bp_gpgkey, bp_extras)
    return repocompose


@pytest.fixture
def repocompose_extras(repocompose):
    bp_url = 'http://example.com/foo'
    bp_gpgkey = 'f000000d'
    bp_extras = 'http://example.com/foo-extras'
    repocompose.set_base_product(bp_url, bp_gpgkey, bp_extras)
    return repocompose


class TestRepoComposeTrivial(object):
    """ Test simple mechanics """
    def test_inheritance(self):
        assert issubclass(RepoCompose, productmd.compose.Compose)

    def test_constructor(self, repocompose):
        assert repocompose.compose_path

    def test_attributes(self, repocompose):
        assert repocompose.info.get_variants()


class TestRepoComposeVariantUrl(object):

    def test_get_variant_url(self, repocompose):
        variants = repocompose.info.get_variants()
        assert len(variants) > 0
        result = repocompose.get_variant_url(variants[0], 'x86_64')
        expected = os.path.join(FIXTURES_DIR, 'MON', 'x86_64', 'os')
        assert result == expected


class TestRepoComposeYumRepo(object):
    """ Test attributes """

    def test_file_exists(self, repocompose):
        path = repocompose.write_yum_repo_file()
        assert os.path.isfile(path)

    def test_file_contents(self, repocompose):
        path = repocompose.write_yum_repo_file()
        # Verify the contents with ConfigParser
        config = ConfigParser.RawConfigParser()
        config.read(path)
        expected = ['MYPRODUCT-2.1-RHEL-7-MON',
                    'MYPRODUCT-2.1-RHEL-7-OSD',
                    'MYPRODUCT-2.1-RHEL-7-Tools',
                    'rhel-7']
        assert config.sections() == expected

    def test_no_base_product_gpgkey(self, repocompose):
        # No gpgkey means gpgcheck should be 0 in the .repo file.
        assert repocompose.info.base_product.gpgkey is None
        path = repocompose.write_yum_repo_file()
        config = ConfigParser.RawConfigParser()
        config.read(path)
        assert config.get('rhel-7', 'gpgcheck') == '0'

    def test_base_product_gpgkey(self, repocompose_bp_signed):
        # gpgkey is set, so it will be present in the .repo file.
        path = repocompose_bp_signed.write_yum_repo_file()
        config = ConfigParser.RawConfigParser()
        config.read(path)
        assert config.get('rhel-7', 'gpgcheck') == '1'
        assert config.get('rhel-7', 'gpgkey') == '/etc/RPM-GPG-KEY-f00d'

    def test_base_product_extras(self, repocompose_extras):
        # extras is set, so it will be present in the .repo file.
        path = repocompose_extras.write_yum_repo_file()
        config = ConfigParser.RawConfigParser()
        config.read(path)
        assert config.get('rhel-7-extras', 'gpgcheck') == '1'
        assert config.get('rhel-7-extras', 'gpgkey') == '/etc/RPM-GPG-KEY-f00d'
