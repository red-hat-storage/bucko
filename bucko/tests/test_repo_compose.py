import os
from bucko.repo_compose import RepoCompose
import productmd.compose
import pytest
try:
    from configparser import RawConfigParser
except ImportError:
    from ConfigParser import RawConfigParser

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(TESTS_DIR, 'fixtures')

INTERNAL_KEYS = {'f000000d': '/etc/RPM-GPG-KEY-f00d'}


@pytest.fixture
def repocompose():
    compose = RepoCompose(FIXTURES_DIR, INTERNAL_KEYS)
    return compose


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
        config = RawConfigParser()
        config.read(path)
        expected = ['MYPRODUCT-2.1-RHEL-7-MON',
                    'MYPRODUCT-2.1-RHEL-7-OSD',
                    'MYPRODUCT-2.1-RHEL-7-Tools']
        assert config.sections() == expected
