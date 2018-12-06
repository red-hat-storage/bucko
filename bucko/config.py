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
