import os
import pytest
from bucko import config
from bucko.config import ConfigParser

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(TESTS_DIR, 'fixtures')


@pytest.fixture()
def simple_configp():
    """ Minimal ConfigParser fixture with one simple setting. """
    cp = ConfigParser()
    # Set "foo=bar" in [testsection]
    cp.add_section('testsection')
    cp.set('testsection', 'foo', 'bar')
    return cp


@pytest.fixture()
def configp(monkeypatch):
    """ Our ConfigParser file from disk. """
    monkeypatch.setenv('HOME', FIXTURES_DIR)
    cp = config.load()
    return cp


def test_load(configp):
    assert isinstance(configp, ConfigParser)
    sections = configp.sections()
    assert sections


def test_lookup_present(simple_configp):
    result = config.lookup(simple_configp, 'testsection', 'foo')
    assert result == 'bar'


def test_lookup_fatal(simple_configp):
    with pytest.raises(SystemExit) as e:
        config.lookup(simple_configp, 'testsection', 'baz')
    assert 'bucko.conf' in str(e)


def test_lookup_nonfatal(simple_configp):
    result = config.lookup(simple_configp, 'testsection', 'baz', fatal=False)
    assert result is None


def test_get_repo_urls(configp):
    section = 'ceph-2-rhel-7-base'
    result = config.get_repo_urls(configp, section)
    expected = set(['http://example.com/repo1.repo',
                    'http://example.com/repo2.repo'])
    assert result == expected
