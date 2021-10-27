import posixpath
import koji
from koji_cli.lib import activate_session
from koji_cli.lib import watch_tasks

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
        print('Watching Koji task %s' % url)
        task_result = watch_tasks(self.session, [id_], poll_interval=interval)
        if task_result != 0:
            raise RuntimeError('failed buildContainer task')

    def get_repositories(self, id_):
        """ Get the list of repositories for a container task. """
        result = self.session.getTaskResult(id_)
        return result['repositories']

    def untag_task_result(self, task_id):
        """ Untag the builds from this buildContainer task. """
        result = self.session.getTaskResult(task_id)
        build_ids = result['koji_builds']
        for build_id in build_ids:
            build_id = int(build_id)  # koji returns strs for some reason
            weburl = self.session.opts['weburl']
            url = posixpath.join(weburl, 'buildinfo?buildID=%s' % build_id)
            print('Checking %s for tags to untag' % url)
            tags = self.session.listTags(build=build_id)
            if tags:
                self.ensure_logged_in()
            for tag in tags:
                tag_name = tag['name']
                print('Untagging %s from %s' % (url, tag_name))
                self.session.untagBuild(tag_name, build_id, strict=False)
