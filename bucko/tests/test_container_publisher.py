from bucko.container_publisher import ContainerPublisher

HOST = 'registry.example.com'
TOKEN = 'abc123'


class CheckOutputRecorder(object):
    """ Simple recorder for monkeypatching. """
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        return b''


def test_constructor():
    p = ContainerPublisher(HOST, TOKEN)
    assert isinstance(p, ContainerPublisher)
    assert p.host == HOST
    assert p.token == TOKEN


def test_publish(monkeypatch):
    recorder = CheckOutputRecorder()
    monkeypatch.setattr('subprocess.check_output', recorder)
    p = ContainerPublisher(HOST, TOKEN)
    source_image = 'registry.example.com/ceph/ceph:foo'
    namespace = 'ceph'
    repository = 'ceph-4.0-rhel-8'
    tag = 'latest'
    p.publish(source_image, namespace, repository, tag)
    expected = [
        ('sudo', 'REGISTRY_AUTH_FILE=/run/containers/0/auth.json', 'podman',
         'login', '-p', 'abc123', '-u', 'unused', 'registry.example.com'),
        ('sudo', 'skopeo', 'copy',
         'docker://registry.example.com/ceph/ceph:foo',
         'docker://registry.example.com/ceph/ceph-4.0-rhel-8:latest'),
        ('sudo', 'REGISTRY_AUTH_FILE=/run/containers/0/auth.json', 'podman',
         'logout', 'registry.example.com'),
    ]
    assert recorder.calls
    assert recorder.calls == expected
