import posixpath
import koji
import time

""" I have a dream that one day Koji will have a usuable API """


class KojiBuilder(object):
    """ Simple Koji client that can barely build a container image. """

    def __init__(self, hub, web, krbservice):
        self.hub = hub
        self.web = web
        opts = {'krbservice': krbservice}
        self.session = koji.ClientSession(hub, opts)

    def ensure_logged_in(self):
        """ Log in if we are not already logged in """
        if not self.session.logged_in:
            try:
                self.session.krb_login()
            except koji.krbV.Krb5Error as e:
                raise RuntimeError('Authentication failed: %s' % e.args[1])

    def build_container(self, scm, target, branch, repos, scratch=True):
        """ Build a container in Koji

        :param str scm: dist-git SCM.
                        Eg. 'git://example.com/foo#origin/foo-rhel-7'
        :param str target: Koji build target.
                           Eg. 'foo-rhel-7-containers-candidate'
        :param str branch: dist-git branch. Eg. 'foo-rhel-7'
        :param list repos: URLs to Yum .repo files.
        :returns int: a Koji task ID
        """
        self.ensure_logged_in()

        # Verify we can build containers with this Koji instance:
        if 'buildContainer' not in self.session.system.listMethods():
            msg = '%s does not support buildContainer' % self.hub
            raise RuntimeError(msg)

        # Sanity-check build target name:
        if self.session.getBuildTarget(target) is None:
            msg = 'Build Target %s is not present in %s' % (target, self.hub)
            raise RuntimeError(msg)

        config = {'scratch': scratch,
                  'yum_repourls': repos,
                  'git_branch': branch}

        return self.session.buildContainer(scm, target, config, priority=None)

    def watch_task(self, id_, interval=5):
        """ Watch a Koji task ID, printing its state transitions to STDOUT """
        url = posixpath.join(self.web, 'taskinfo?taskID=%s' % id_)
        task = KojiTask(id_, self.session)
        task.update()
        last_state = None
        print('Watching Koji task %s' % url)
        while not task.is_done():
            if last_state != task.state:
                last_state = task.state
                print('Task %s - %s' % (id_, task.state))
            time.sleep(interval)
            task.update()
        print('Task %s is done - %s' % (id_, task.state))

    def get_repositories(self, id_):
        """ Get the list of repositories for a container task. """
        result = self.session.getTaskResult(id_)
        return result['repositories']


class KojiTask(object):
    """ Inspired from TaskWatcher in /usr/bin/koji """
    def __init__(self, id_, session):
        self.id_ = id_
        self.session = session
        self.info = None

    def update(self):
        self.info = self.session.getTaskInfo(self.id_)
        if self.info is None:
            raise RuntimeError('No such task id %i' % self.id_)

    @property
    def state(self):
        """ Return the textual representation of this task's state. """
        if not self.info:
            return 'unknown'
        return koji.TASK_STATES[self.info['state']]

    def is_done(self):
        return (self.state in ('CLOSED', 'CANCELED', 'FAILED'))
