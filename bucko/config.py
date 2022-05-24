import os
try:
    import configparser
    ConfigParserError = configparser.Error
except ImportError:
    import ConfigParser
    ConfigParserError = ConfigParser.Error
try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser


def load():
    """ Load a bucko configuration file and return a ConfigParser object. """
    configp = ConfigParser()
    configp.read(['bucko.conf', os.path.expanduser('~/.bucko.conf')])
    return configp


def lookup(configp, section, option, fatal=True):
    """ Gracefully (or not) look up an option from a ConfigParser section. """
    try:
        return configp.get(section, option)
    except ConfigParserError as e:
        if fatal:
            raise SystemExit('Problem parsing .bucko.conf: %s' % e.message)


def get_repo_urls(configp, section):
    """
    Return a set of URLs for this configparser section.

    If this section does not exist, return an empty set.

    :param str section: eg. 'ceph-3.0-rhel-7-base'
    :returns: set of URLs for Yum .repo files
    """
    urls = set()
    if section not in configp.sections():
        return urls
    items = configp.items(section)
    for key, url in items:
        if not key.startswith('repo'):
            continue
        # Sanity-check that this value looks like a .repo file.
        if not url.endswith('.repo'):
            raise RuntimeError('%s does not look like a .repo file' % url)
        urls.add(url)
    return urls
