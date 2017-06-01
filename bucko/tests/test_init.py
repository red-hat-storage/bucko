import os
import pytest
import bucko
try:
    from configparser import ConfigParser
except ImportError:
    import ConfigParser

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

    def test_ci_message(self, monkeypatch):
        monkeypatch.setenv('COMPOSE_URL', '')
        monkeypatch.setenv('CI_MESSAGE', '{"COMPOSE_URL": "http://foo"}')
        assert bucko.compose_url_from_env() == 'http://foo'


class TestGetPublisher(object):
    @pytest.fixture
    def config(self):
        config = ConfigParser.RawConfigParser()
        config.add_section('publish')
        config.set('publish', 'push', 'file:///mypath')
        config.set('publish', 'http', 'http:///example.com/mypath')
        return config

    def test_get_publisher(self, config):
        p = bucko.get_publisher(config)
        assert isinstance(p, bucko.Publisher)
        assert p.push_url == 'file:///mypath'
        assert p.http_url == 'http:///example.com/mypath'


class TestGetCompose(object):
    @pytest.fixture
    def config(self):
        config = ConfigParser.RawConfigParser()
        config.add_section('keys')
        config.add_section('base_product')
        config.set('base_product', 'url', 'http:///example.com/baseproduct')
        return config

    def test_get_compose(self, config):
        c = bucko.get_compose(FIXTURES_DIR, config)
        assert isinstance(c, bucko.RepoCompose)
        assert c.info.base_product.url == 'http:///example.com/baseproduct'


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
        config = ConfigParser.RawConfigParser()
        config.add_section('koji')
        config.set('koji', 'hub', 'dummyhub')
        config.set('koji', 'web', 'dummyweb')
        config.set('koji', 'krbservice', 'dummykrbservice')
        config.set('koji', 'scm', 'git://example.com')
        config.set('koji', 'target', 'foo-rhel-7-candidate')
        return config

    def test_build_container(self, config, monkeypatch):
        monkeypatch.setattr('bucko.KojiBuilder', FakeKojiBuilder)
        repo_url = 'http:///example.com/example.repo'
        results = bucko.build_container(repo_url, config)
        assert results['koji_task'] == 1234
        assert results['repositories'] == ['http://registry.example.com/foo']
