import requests
from bucko.registry import Registry


def test_init():
    registry = Registry('http://registry.example.com')
    assert registry


def test_find_realm_service_red_hat_registry_proxy():
    registry = Registry('http://registry.example.com')
    response = requests.Response()
    # Red Hat's registry-proxy has a simple Bearer value.
    response.headers = {
      'WWW-Authenticate': 'Bearer realm="https://registry.example.com/v2/auth"'
    }
    realm, service = registry.find_realm_service(response)
    assert realm == 'https://registry.example.com/v2/auth'
    assert service is None


def test_find_realm_service_icr():
    # IBM's cp.icr.io
    registry = Registry('http://registry.example.com')
    response = requests.Response()
    response.headers = {
      'WWW-Authenticate': 'Bearer realm="https://registry.example.com/oauth/token",service="registry",scope="repository:cp/samplerepo:pull'
    }
    realm, service = registry.find_realm_service(response)
    assert realm == 'https://registry.example.com/oauth/token'
    assert service == 'registry'
