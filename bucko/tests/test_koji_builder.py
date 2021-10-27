import koji
from types import SimpleNamespace
from bucko.koji_builder import KojiBuilder
from collections import defaultdict


class FakeKoji(object):
    """ Dummy koji module """
    TASK_STATES = koji.TASK_STATES
    config = SimpleNamespace(
        server='dummyhub',
        weburl='dummyweb',
        authtype='kerberos',
        cert='',
    )

    @staticmethod
    def ClientSession(baseurl, opts):
        return FakeClientSession(baseurl, opts)

    @classmethod
    def get_profile_module(cls, profile):
        return cls


class FakeClientSession(object):
    """ Dummy koji.ClientSession """
    logged_in = False
    tasks_waited = defaultdict(int)

    def __init__(self, baseurl, opts):
        self.opts = opts

    def __getattr__(self, name):
        return lambda *args, **kw: None

    def gssapi_login(self, *args, **kw):
        self.logged_in = True

    def getAPIVersion(self):
        return 1

    def getBuildTarget(self, target):
        return {}

    def buildContainer(self, *args, **kw):
        return 1234

    def getTaskInfo(self, id_, request=False):
        """ Return 'OPEN' state the first couple of times, then 'CLOSED'. """
        task = {'host_id': None}
        self.tasks_waited[id_] += 1
        if self.tasks_waited[id_] < 5:
            task['state'] = koji.TASK_STATES['OPEN']
        else:
            task['state'] = koji.TASK_STATES['CLOSED']
        return task

    def getTaskChildren(self, id_):
        return []

    def getTaskResult(self, id_):
        """ Return a non-scratch buildContainer task result """
        return {
            'koji_builds': [1234],  # list of koji build IDs
        }

    def listTags(self, build):
        """ Return a list of tags for a build """
        return [
            {'name': 'ceph-candidate'},
        ]


class TestKojiBuilder(object):
    def test_constructor(self, monkeypatch):
        monkeypatch.setattr('bucko.koji_builder.koji', FakeKoji)
        k = KojiBuilder('koji')
        assert isinstance(k, KojiBuilder)

    def test_ensure_logged_in(self, monkeypatch):
        """ Test ensure_logged_in() """
        monkeypatch.setattr('bucko.koji_builder.koji', FakeKoji)
        k = KojiBuilder('koji')
        k.ensure_logged_in()
        assert k.session.logged_in is True

    def test_build_container(self, monkeypatch):
        monkeypatch.setattr('bucko.koji_builder.koji', FakeKoji)
        k = KojiBuilder('koji')
        scm = 'git://example.com/containers/rhceph#origin/ceph-4.0-rhel-8'
        target = 'ceph-4.0-rhel-8-containers-candidate'
        result = k.build_container(scm, target, 'ceph-4.0-rhel-8', [])
        assert result == 1234

    def test_watch_task(self, monkeypatch, capsys):
        monkeypatch.setattr('bucko.koji_builder.koji', FakeKoji)
        k = KojiBuilder('koji')
        k.watch_task(1234, interval=0)
        out, _ = capsys.readouterr()
        assert 'Watching Koji task dummyweb/taskinfo?taskID=1234' in out

    def test_untag_task_result(self, monkeypatch, capsys):
        monkeypatch.setattr('bucko.koji_builder.koji', FakeKoji)
        k = KojiBuilder('koji')
        k.untag_task_result(12345)
        out, _ = capsys.readouterr()
        expected = """\
Checking dummyweb/buildinfo?buildID=1234 for tags to untag
Untagging dummyweb/buildinfo?buildID=1234 from ceph-candidate
"""
        assert out == expected
