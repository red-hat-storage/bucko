class Build(object):
    """
    Representation of a Koji build NVR.
    """
    def __init__(self, name, version, release):
        self.name = name
        self.version = version
        self.release = release

    @property
    def nvr(self):
        return '%s-%s-%s' % (self.name, self.version, self.release)

    def __str__(self):
        return self.nvr

    def __repr__(self):
        return 'Build(%s, %s, %s)' % (self.name, self.version, self.release)
