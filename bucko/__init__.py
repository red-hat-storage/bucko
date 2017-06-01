import argparse
from pprint import pformat
import tempfile
import json
import os
from .log import log
from bucko.repo_compose import RepoCompose
from bucko.publisher import Publisher
from bucko.koji_builder import KojiBuilder
try:
    from configparser import ConfigParser
except ImportError:
    import ConfigParser


__version__ = '1.0.0'

__all__ = ['log']


def compose_url_from_env():
    """
    Parse COMPOSE_URL and CI_MESSAGE environment variables for a URL.

    If we can't find a URL, return None.

    Exact rules:
      1. Search the JSON in CI_MESSAGE first, return COMPOSE_URL key.
      2. If CI_MESSAGE is not valid JSON, or lacks COMPOSE_URL key, fall back
         to using the COMPOSE_URL environment variable. The assumption here is
         that this is a by-hand Jenkins job.
      3. If COMPOSE_URL env var is empty (or undefined), return None.
    """
    compose_url = os.environ.get('COMPOSE_URL', '')
    if compose_url == '':
        compose_url = None
    try:
        msg = json.loads(os.environ.get('CI_MESSAGE', ''))
    except ValueError:
        # No CI_MESSAGE JSON. Falling back to COMPOSE_URL environment var
        return compose_url
    log.info('Parsing CI_MESSAGE: %s' % pformat(msg))
    try:
        return msg['COMPOSE_URL']
    except KeyError:
        # CI_MESSAGE JSON lacks COMPOSE_URL. Falling back to COMPOSE_URL envvar
        return compose_url


def config():
    """ Load a bucko configuration file and return a ConfigParser object. """
    configp = ConfigParser.RawConfigParser()
    configp.read(['bucko.conf', os.path.expanduser('~/.bucko.conf')])
    return configp


def get_publisher(configp):
    """ Look up the push url and http url from a ConfigParser object. """
    try:
        push_url = configp.get('publish', 'push')
        http_url = configp.get('publish', 'http')
    except ConfigParser.Error as e:
        raise SystemExit('Problem parsing bucko.conf: %s' % e.message)
    return Publisher(push_url, http_url)


def get_base_product_config(configp):
    """ Look up the url and gpgkey from a ConfigParser object. """
    try:
        url = configp.get('base_product', 'url')
    except ConfigParser.Error as e:
        raise SystemExit('Problem parsing .bucko.conf: %s' % e.message)
    try:
        gpgkey = configp.get('base_product', 'gpgkey')
    except ConfigParser.Error:
        gpgkey = None
    return (url, gpgkey)


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
            for key, value in kwargs.iteritems():
                props.write(key.upper() + '=' + value + "\n")


def get_compose(compose_url, configp):
    """ Construct a RepoCompose object. """
    keys = dict(configp.items('keys'))
    c = RepoCompose(compose_url, keys)
    # Sanity-check that this is a layered product compose.
    if not c.info.release.is_layered:
        raise RuntimeError('%s must be layered' % c.info.release.short)
    (base_product_url, base_product_gpgkey) = get_base_product_config(configp)
    # Store extra base_product attrs within our ComposeInfo.BaseProduct.
    # c.write_yum_repo_file() will use these.
    c.info.base_product.url = base_product_url
    c.info.base_product.gpgkey = base_product_gpgkey
    return c


def build_container(repo_url, configp):
    """ Build a container with Koji. """
    kconf = dict(configp.items('koji'))
    koji = KojiBuilder(hub=kconf['hub'],
                       web=kconf['web'],
                       krbservice=kconf['krbservice'])
    log.info('Building container at %s' % kconf['hub'])
    task_id = koji.build_container(scm=kconf['scm'],
                                   target=kconf['target'],
                                   repos=[repo_url])
    # Show information to the console.
    koji.watch_task(task_id)
    # Return information about this build.
    return {'koji_task': task_id,
            'repositories': koji.get_repositories(task_id)}


def parse_args():
    """ Return parsed cmdline arguments. """
    parser = argparse.ArgumentParser()
    parser.add_argument('--compose', required=False,
                        default=compose_url_from_env(),
                        help='HTTP(S) URL to a Distill/Pungi compose.')
    return parser.parse_args()


def main():
    """ Scratch-build a container for an HTTP-accessible compose. """
    args = parse_args()

    if args.compose is None:
        err = 'Please set the CI_MESSAGE env var or use --compose arg'
        raise SystemExit(err)
    compose_url = args.compose

    # Load config file
    configp = config()

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

    # Do a Koji build
    metadata = build_container(repo_url, configp)

    # Store and publish our information about this build
    metadata['compose_url'] = compose_url
    metadata['compose_id'] = c.info.compose.id
    json_file = write_metadata_file(c.info.compose.id + '-osbs.json',
                                    **metadata)
    json_url = p.publish(json_file)
    log.info('OSBS JSON data at %s' % json_url)
    write_props_file(compose_id=c.info.compose.id,
                     json_url=json_url)


class BuckoError(Exception):
    pass
