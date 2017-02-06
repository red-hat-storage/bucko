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


@pytest.fixture
def repocompose():
    return RepoCompose(FIXTURES_DIR, {'f000000d': '/etc/RPM-GPG-KEY-f00d'})


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
                    'MYPRODUCT-2.1-RHEL-7-Tools']
        assert config.sections() == expected

    def test_with_base_product(self, repocompose):
        # Set url, so the base_product will be present in the .repo file:
        repocompose.info.base_product.url = 'http://example.com/foo'
        path = repocompose.write_yum_repo_file()
        config = ConfigParser.RawConfigParser()
        config.read(path)
        assert 'rhel-7' in config.sections()
        assert config.get('rhel-7', 'gpgcheck') == '0'

    def test_with_base_product_gpgkey(self, repocompose):
        # Set gpgkey, so the base_product will be present in the .repo file:
        repocompose.info.base_product.url = 'http://example.com/foo'
        repocompose.info.base_product.gpgkey = 'f000000d'
        path = repocompose.write_yum_repo_file()
        config = ConfigParser.RawConfigParser()
        config.read(path)
        assert config.get('rhel-7', 'gpgcheck') == '1'
        assert config.get('rhel-7', 'gpgkey') == '/etc/RPM-GPG-KEY-f00d'
