import posixpath
from bucko.publisher import Publisher


PUSH_URL = 'sftp://example.noexist/var/www/html'
HTTP_URL = 'http://example.noexist/'


class FakeSSHClient(object):
    """ Dummy Paramiko client where everything is a no-op """
    def __getattr__(self, name):
        return lambda *args, **kw: None

    def open_sftp(self, *args):
        return FakeSFTPClient()


class FakeSFTPClient(object):
    """ Dummy paramiko.sftp_client.SFTPClient where everything is a no-op """
    def __getattr__(self, name):
        return lambda *args, **kw: None


class TestPublisher(object):
    def test_constructor(self):
        p = Publisher(PUSH_URL, HTTP_URL)
        assert isinstance(p, Publisher)
        assert p.push_url == PUSH_URL
        assert p.http_url == HTTP_URL

    def test_sftp(self, monkeypatch):
        """ Test publishing with an sftp:// URL """
        monkeypatch.setattr('bucko.publisher.SSHClient', FakeSSHClient)
        p = Publisher(PUSH_URL, HTTP_URL)
        result = p.publish('test.repo')
        assert result == posixpath.join(HTTP_URL, 'test.repo')

    def test_fs(self, tmpdir):
        """ Test publishing with a file:// URL """
        repo_file = tmpdir.join('test.repo').ensure()
        push_url = 'file://%s' % tmpdir.mkdir('dest')
        p = Publisher(push_url, HTTP_URL)
        result = p.publish(str(repo_file))
        assert result == posixpath.join(HTTP_URL, 'test.repo')
        # Ensure the file exists at this destination location on disk
        assert tmpdir.join('dest').join('test.repo').exists()
