from bucko.registry import Registry


def test_init():
    registry = Registry('http://registry.example.com')
    assert registry
