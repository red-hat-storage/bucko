import os
import productmd
import pytest
import bucko
try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(TESTS_DIR, 'fixtures')


def test_version():
    assert bucko.__version__


class TestComposeUrlFromEnv(object):
    # Note: when we assert "is None", that effectively means we want the user
    # to specify a "--compose" on the commandline.
    def test_no_env(self, monkeypatch):
        monkeypatch.delenv('COMPOSE_URL', raising=False)
        monkeypatch.delenv('CI_MESSAGE', raising=False)
        assert bucko.compose_url_from_env() is None

    def test_blank(self, monkeypatch):
        monkeypatch.setenv('COMPOSE_URL', '')
        monkeypatch.setenv('CI_MESSAGE', '')
        assert bucko.compose_url_from_env() is None

    def test_compose_url(self, monkeypatch):
        monkeypatch.setenv('COMPOSE_URL', 'http://foo')
        monkeypatch.setenv('CI_MESSAGE', '')
        assert bucko.compose_url_from_env() == 'http://foo'

    def test_compose_ci_message(self, monkeypatch):
        monkeypatch.setenv('COMPOSE_URL', 'http://donotuse')
        monkeypatch.setenv('CI_MESSAGE', '{"compose_url": "http://foo"}')
        assert bucko.compose_url_from_env() == 'http://foo'

    def test_distgit_ci_message(self, monkeypatch):
        tmpl = 'http://foo/%(branch)s/latest-RHCEPH-%(major)s-%(distro)s'
        monkeypatch.setenv('COMPOSE_URL', tmpl)
        monkeypatch.setenv('CI_MESSAGE', '{"branch": "ceph-3.0-rhel-7"}')
        expected = 'http://foo/ceph-3.0-rhel-7/latest-RHCEPH-3-RHEL-7'
        assert bucko.compose_url_from_env() == expected


class TestGetPublisher(object):
    @pytest.fixture
    def config(self):
        config = ConfigParser()
        config.add_section('publish')
        config.set('publish', 'push', 'file:///mypath')
        config.set('publish', 'http', 'http://example.com/mypath')
        return config

    def test_get_publisher(self, config):
        p = bucko.get_publisher(config)
        assert isinstance(p, bucko.Publisher)
        assert p.push_url == 'file:///mypath'
        assert p.http_url == 'http://example.com/mypath'


class TestGetCompose(object):
    @pytest.fixture
    def config(self):
        config = ConfigParser()
        config.add_section('keys')
        return config

    def test_get_compose(self, config):
        c = bucko.get_compose(FIXTURES_DIR, config)
        assert isinstance(c, bucko.RepoCompose)


class TestGetBranch(object):
    @pytest.fixture
    def compose(self):
        compose_obj = productmd.compose.Compose(FIXTURES_DIR)
        return compose_obj

    def test_get_branch_basic(self, compose):
        branch = bucko.get_branch(compose)
        assert branch == 'myproduct-2.1-rhel-7'

    def test_get_branch_rhel_8(self, compose):
        compose.info.base_product.version = '8'
        branch = bucko.get_branch(compose)
        assert branch == 'myproduct-2.1-rhel-8'


class FakeKojiBuilder(object):
    """ Dummy KojiBuilder module """
    def __init__(self, *args, **kw):
        pass

    def build_container(*args, **kw):
        return 1234

    def watch_task(*args, **kw):
        pass

    def get_repositories(*args, **kw):
        return ['http://registry.example.com/foo']


class TestBuildContainer(object):
    @pytest.fixture
    def config(self):
        config = ConfigParser()
        config.add_section('koji')
        config.set('koji', 'hub', 'dummyhub')
        config.set('koji', 'web', 'dummyweb')
        config.set('koji', 'krbservice', 'dummykrbservice')
        config.set('koji', 'scm', 'git://example.com')
        config.set('koji', 'target', 'foo-rhel-7-candidate')
        return config

    def test_build_container(self, config, monkeypatch):
        monkeypatch.setattr('bucko.KojiBuilder', FakeKojiBuilder)
        repo_url = 'http://example.com/example.repo'
        branch = 'foo-3.0-rhel-7'
        parent_image = None
        results = bucko.build_container(repo_url, branch, parent_image, config)
        assert results['koji_task'] == 1234
        assert results['repository'] == 'http://registry.example.com/foo'
