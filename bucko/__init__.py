import argparse
from pprint import pformat
import tempfile
import json
import os
from .log import log
from bucko import config
from bucko import odcs_manager
from bucko.container_publisher import ContainerPublisher
from bucko.repo_compose import RepoCompose
from bucko.publisher import Publisher
from bucko.koji_builder import KojiBuilder
from bucko.registry import Registry

__version__ = '1.0.0'

__all__ = ['log']


def parse_ci_message(msg, compose_url):
    """
    Parse CI_MESSAGE JSON data and return a compose URL according to our rules.

    :param         msg: ``dict`` of JSON data from CI_MESSAGE environment var
    :param compose_url: ``str`` COMPOSE_URL environment var (might be a format
                        string that we will interpolate from msg values.)
    :return: ``str`` compose URL.
    """
    log.info('Parsing CI_MESSAGE: %s' % pformat(msg))
    try:
        return msg['compose_url']
    except KeyError:
        log.info('CI_MESSAGE JSON lacks "compose_url" key.')
    # Not a product-build-done message?
    try:
        # Maybe CI_MESSAGE was a dist-git message?
        branch = msg['branch']
    except KeyError:
        log.info('CI_MESSAGE JSON lacks "branch" key.')
        log.info('Falling back to COMPOSE_URL env variable.')
        return compose_url
    # Parse our "branch" JSON key and interpolate values into the
    # COMPOSE_URL environment variable (format string).
    (_, version, distro) = branch.split('-', 2)
    major = int(float(version))
    distro_upper = distro.upper()
    result = compose_url % {'branch': branch,
                            'major': major,
                            'distro': distro,
                            'distro_upper': distro_upper}
    log.info('transformed %s format string to %s' % (compose_url, result))
    return result


def compose_url_from_env():
    """
    Parse COMPOSE_URL and CI_MESSAGE environment variables for a URL.

    If we can't find a URL, return None.

    Exact rules:
      1. Search the JSON in CI_MESSAGE first, return compose_url key.
           {"compose_url": "http://example.com/foo"}
      2. If the JSON lacks a compose_url key, search for a "branch" key
         instead. Parse that, and interpolate branch/major into the COMPOSE_URL
         env variable.
           {"branch": "ceph-3.0-rhel-7"}
           COMPOSE_URL=http://example.com/(branch)s/latest-RHCEPH-(major)s
      3. If CI_MESSAGE is not valid JSON, fall back to checking the COMPOSE_URL
         env var. The assumption here is that this is a manual Jenkins job run.
      4. If COMPOSE_URL env var is empty (or undefined), return None.
    """
    compose_url = os.environ.get('COMPOSE_URL', '')
    if compose_url == '':
        compose_url = None
    try:
        msg = json.loads(os.environ.get('CI_MESSAGE', ''))
    except ValueError:
        # No CI_MESSAGE JSON. Falling back to COMPOSE_URL environment var
        return compose_url
    return parse_ci_message(msg, compose_url)


def get_publisher(configp):
    """ Look up the push url and http url from a ConfigParser object. """
    push_url = config.lookup(configp, 'publish', 'push')
    http_url = config.lookup(configp, 'publish', 'http')
    return Publisher(push_url, http_url)


def get_container_publisher(configp):
    """ Look up the registry host and token from a ConfigParser object. """
    host = config.lookup(configp, 'publish', 'registry_host', fatal=False)
    if not host:
        return None
    token = config.lookup(configp, 'publish', 'registry_token', fatal=True)
    return ContainerPublisher(host, token)


def write_metadata_file(filename, **kwargs):
    """ Write metadata to a JSON file. """
    filename = os.path.join(tempfile.mkdtemp(suffix='.json'), filename)
    with open(filename, 'w') as f:
        json.dump(kwargs, f, sort_keys=True)
    return filename


def write_props_file(**kwargs):
    """ Write data into a .props file for Jenkins to read. """
    if 'WORKSPACE' in os.environ:
        log.info('WORKSPACE detected, writing osbs.props for Jenkins')
        props_path = os.path.join(os.environ['WORKSPACE'], 'osbs.props')
        with open(props_path, 'w') as props:
            for key, value in kwargs.items():
                props.write(key.upper() + '=' + str(value) + "\n")


def get_compose(compose_url, configp):
    """ Construct a RepoCompose object according to our ConfigParser. """
    keys = dict(configp.items('keys'))
    compose = RepoCompose(compose_url, keys)
    return compose


def get_branch(compose):
    """
    Return a dist-git branch name for this compose.

    Examples:
      "ceph-3.2-rhel-7"
      "ceph-4.0-rhel-8"
    """
    name = compose.info.release.short.lower()
    if name == 'rhceph':
        name = 'ceph'
    version = compose.info.release.version
    bp_short = compose.info.base_product.short.lower()  # "rhel"
    bp_version = compose.info.base_product.version  # "7" or "8"
    return '%s-%s-%s-%s' % (name, version, bp_short, bp_version)


def build_container(repo_urls, branch, parent_image, scratch, configp):
    """ Build a container with Koji. """
    kconf = dict(configp.items('koji', vars={'branch': branch}))
    koji = KojiBuilder(profile=kconf['profile'])
    parent = None
    if parent_image:
        registry_url = config.lookup(configp, 'registry', 'url')
        registry = Registry(registry_url)
        parent = registry.build(parent_image)  # bucko.build.Build
    log.info('Building container at %s' % koji.session.baseurl)
    task_id = koji.build_container(scm=kconf['scm'],
                                   target=kconf['target'],
                                   branch=branch,
                                   repos=repo_urls,
                                   scratch=scratch,
                                   koji_parent_build=parent)
    # Show information to the console.
    koji.watch_task(task_id)

    # Untag the build from the -candidate tag:
    # There's no "skip_tag" parameter for buildContainer, so we must
    # immediately untag it ourselves.
    # CLOUDBLD-5091 is the RFE to add skip-tag.
    if not scratch:
        koji.untag_task_result(task_id)

    # Return information about this build.
    result = {'koji_task': task_id}

    repositories = koji.get_repositories(task_id, kconf['target'])
    # "repository" (first in the list) is the OSBS unique tag.
    result['repository'] = repositories[0]
    result['repositories'] = repositories

    return result


def parse_args():
    """ Return parsed cmdline arguments. """
    parser = argparse.ArgumentParser()
    parser.add_argument('--compose', required=False,
                        default=compose_url_from_env(),
                        help='HTTP(S) URL to a product Pungi compose.')
    parser.add_argument('--scratch', default=True, action='store_true',
                        help='scratch-build container image')
    return parser.parse_args()


def main():
    """ Scratch-build a container for an HTTP-accessible compose. """
    args = parse_args()

    if args.compose is None:
        err = 'Please set the CI_MESSAGE env var or use --compose arg'
        raise SystemExit(err)
    compose_url = args.compose

    # Load config file
    configp = config.load()

    # Load compose
    c = get_compose(compose_url, configp)

    # Generate .repo file
    log.info('Generating .repo file for %s compose' % c.info.release.short)
    filename = c.write_yum_repo_file()

    # Publish the .repo file
    p = get_publisher(configp)
    log.info('Publishing .repo file to %s' % p.push_url)
    repo_url = p.publish(filename)
    log.info('Published %s' % repo_url)

    # Determine scm and brew target branch name
    branch = get_branch(c)

    # Determine other settings for this branch
    section = '%s-base' % branch  # eg "ceph-4.0-rhel-8-base"
    parent_image = config.lookup(configp, section, 'parent_image', fatal=False)
    if parent_image:
        log.info('parent_image configured: %s' % parent_image)
    repo_urls = config.get_repo_urls(configp, section)
    for url in repo_urls:
        log.info('Additional .repo configured: %s' % url)
    repo_urls.add(repo_url)

    odcs_tag = config.lookup(configp, section, 'odcs_tag', fatal=False)
    if odcs_tag:
        log.info('odcs_tag configured: %s' % odcs_tag)
        kconf = dict(configp.items('koji', vars={'branch': branch}))
        koji = KojiBuilder(profile=kconf['profile'])
        arches = koji.get_target_arches(kconf['target'])
        odcs_repo_url = odcs_manager.generate(odcs_tag, arches)
        log.info('Adding odcs repo url %s' % odcs_repo_url)
        repo_urls.add(odcs_repo_url)

    # Do a Koji build
    metadata = build_container(repo_urls, branch, parent_image, args.scratch,
                               configp)

    # Publish this Koji build to our registry
    container_pub = get_container_publisher(configp)
    if container_pub and 'repository' in metadata:
        source_image = metadata['repository']
        dest_namespace, _ = branch.split('-', 1)  # eg "ceph"
        _, unique_tag = source_image.split(':', 1)  # OSBS unique build tag
        for tag in ('latest', unique_tag):
            dest_repo = container_pub.publish(source_image,
                                              dest_namespace,
                                              branch,
                                              tag)
            if dest_repo:
                # Add the new location to metadata['repositories'] so that we
                # record it in the -osbs.json file below.
                metadata['repositories'].append(dest_repo)

    # Store and publish our information about this build
    metadata['compose_url'] = compose_url
    metadata['compose_id'] = c.info.compose.id
    json_file = write_metadata_file(c.info.compose.id + '-osbs.json',
                                    **metadata)
    json_url = p.publish(json_file)
    log.info('OSBS JSON data at %s' % json_url)
    write_props_file(**metadata)


class BuckoError(Exception):
    pass
