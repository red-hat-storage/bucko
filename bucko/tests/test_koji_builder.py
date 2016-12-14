import koji
from bucko.koji_builder import KojiBuilder
from collections import defaultdict


class FakeKoji(object):
    """ Dummy koji module where everything is a no-op """
    TASK_STATES = koji.TASK_STATES

    def __getattr__(self, name):
        return lambda *args, **kw: None

    @staticmethod
    def ClientSession(*args):
        return FakeClientSession()


class FakeSystem(object):
    """ Dummy koji.ClientSession.system """
    def listMethods(self):
        return ('buildContainer')


class FakeClientSession(object):
    """ Dummy koji.ClientSession """
    logged_in = False
    system = FakeSystem()
    tasks_waited = defaultdict(int)

    def __getattr__(self, name):
        return lambda *args, **kw: None

    def getBuildTarget(self, target):
        return {}

    def buildContainer(self, *args, **kw):
        return 1234

    def getTaskInfo(self, id_):
        """ Return 'OPEN' state the first couple of times, then 'CLOSED'. """
        self.tasks_waited[id_] += 1
        if self.tasks_waited[id_] < 5:
            return {'state': koji.TASK_STATES['OPEN']}
        else:
            return {'state': koji.TASK_STATES['CLOSED']}


class TestKojiBuilder(object):
    def test_constructor(self):
        k = KojiBuilder('dummyhub', 'dummyweb', 'brewhub')
        assert isinstance(k, KojiBuilder)

    def test_ensure_logged_in(self, monkeypatch):
        """ Test ensure_logged_in() """
        monkeypatch.setattr('bucko.koji_builder.koji', FakeKoji)
        k = KojiBuilder('dummyhub', 'dummyweb', 'brewhub')
        k.ensure_logged_in()

    def test_build_container(self, monkeypatch):
        monkeypatch.setattr('bucko.koji_builder.koji', FakeKoji)
        k = KojiBuilder('dummyhub', 'dummyweb', 'brewhub')
        scm = 'git://example.com/rpms/rhceph-rhel7-docker#origin/ceph-2-rhel-7'
        target = 'ceph-2-rhel-7-docker-candidate'
        result = k.build_container(scm, target, [])
        assert result == 1234

    def test_watch_task(self, monkeypatch, capsys):
        monkeypatch.setattr('bucko.koji_builder.koji', FakeKoji)
        k = KojiBuilder('dummyhub', 'dummyweb', 'brewhub')
        k.watch_task(1234, interval=0)
        out, _ = capsys.readouterr()
        assert 'Watching Koji task dummyweb/taskinfo?taskID=1234' in out
