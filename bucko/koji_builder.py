import posixpath
import koji
import time
from koji_cli.lib import activate_session

""" Use the Koji API to build a container image """


class KojiBuilder(object):
    """ Simple Koji client that can barely build a container image. """

    def __init__(self, profile):
        self.profile = profile
        mykoji = koji.get_profile_module(profile)
        opts = vars(mykoji.config)
        self.session = mykoji.ClientSession(mykoji.config.server, opts)

    def ensure_logged_in(self):
        """ Log in if we are not already logged in """
        if not self.session.logged_in:
            self.session.opts['noauth'] = False
            # Log in ("activate") this session:
            # Note: this can raise SystemExit if there is a problem, eg with
            # Kerberos:
            activate_session(self.session, self.session.opts)

    def build_container(self, scm, target, branch, repos, scratch=True,
                        koji_parent_build=None):
        """ Build a container in Koji

        :param str scm: dist-git SCM.
                        Eg. 'git://example.com/foo#origin/foo-rhel-7'
        :param str target: Koji build target.
                           Eg. 'foo-rhel-7-containers-candidate'
        :param str branch: dist-git branch. Eg. 'foo-rhel-7'
        :param list repos: URLs to Yum .repo files.
        :param bool scratch: Whether to scratch-build this container
                             (default: True).
        :param str koji_parent_build: Override the "FROM" line in the
                                      Dockerfile with a custom base image.
                                      Eg. 'rhel-server-container-7.5-107'.
                                      (default: no overriding).
        :returns int: a Koji task ID
        """
        self.ensure_logged_in()

        # Verify we can build containers with this Koji instance:
        if 'buildContainer' not in self.session.system.listMethods():
            server = self.session.opts['server']
            msg = '%s does not support buildContainer' % server
            raise RuntimeError(msg)

        # Sanity-check build target name:
        if self.session.getBuildTarget(target) is None:
            server = self.session.opts['server']
            msg = 'Build Target %s is not present in %s' % (target, server)
            raise RuntimeError(msg)

        config = {'scratch': scratch,
                  'yum_repourls': list(repos),
                  'git_branch': branch,
                  'signing_intent': 'unsigned'}
        if koji_parent_build:
            config['koji_parent_build'] = str(koji_parent_build)

        return self.session.buildContainer(scm, target, config, priority=None)

    def watch_task(self, id_, interval=5):
        """ Watch a Koji task ID, printing its state transitions to STDOUT """
        weburl = self.session.opts['weburl']
        url = posixpath.join(weburl, 'taskinfo?taskID=%s' % id_)
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
