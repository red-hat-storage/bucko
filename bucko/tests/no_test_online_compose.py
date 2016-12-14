import os
import re
from bucko.online_compose import OnlineCompose
import productmd.compose
import httpretty

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(TESTS_DIR, 'fixtures')


class TestOnlineComposeTrivial(object):
    """ Test simple mechanics """
    def test_inheritance(self):
        assert issubclass(OnlineCompose, productmd.compose.Compose)

    def test_constructor(self):
        c = OnlineCompose('http://example.noexist/mycompose')
        assert c.path == 'http://example.noexist/mycompose'


class TestOnlineComposeRequests(object):
    """ Test loading with HTTP """

    @classmethod
    def setup_class(cls):
        httpretty.enable()
        httpretty.HTTPretty.allow_net_connect = False
        httpretty.register_uri(httpretty.GET,
                               re.compile('example.noexist/mycompose/.*'),
                               body=cls._request_callback,
                               content_type='text/json')

    @classmethod
    def teardown_class(cls):
        httpretty.disable()
        httpretty.reset()

    @classmethod
    def _request_callback(cls, request, uri, headers):
        fixture = os.path.join(FIXTURES_DIR, 'metadata', os.path.basename(uri))
        try:
            body = open(fixture).read()
            return (200, headers, body)
        except IOError:
            return (404, headers, 'could not find %s' % fixture)

    def test_info(self):
        c = OnlineCompose('http://example.noexist/mycompose/')
        assert c.info
        assert c.info.base_product.short == 'RHEL'

    def test_images(self):
        c = OnlineCompose('http://example.noexist/mycompose/')
        assert c.images

    def test_rpms(self):
        c = OnlineCompose('http://example.noexist/mycompose/')
        assert c.rpms
