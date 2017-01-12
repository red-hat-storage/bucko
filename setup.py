# -*- coding: utf-8 -*-
import subprocess
try:
    from setuptools import setup, find_packages, Command
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages, Command
import re


def read_module_contents():
    with open('bucko/__init__.py') as bucko_init:
        return bucko_init.read()

module_file = read_module_contents()
metadata = dict(re.findall("__([a-z]+)__\s*=\s*'([^']+)'", module_file))
long_description = open('README.rst').read()
version = metadata['version']


class BumpCommand(Command):
    """ Bump the __version__ number and commit all changes. """

    user_options = [('version=', 'v', 'version number to use')]

    def initialize_options(self):
        new_version = metadata['version'].split('.')
        new_version[-1] = str(int(new_version[-1]) + 1)  # Bump the final part
        self.version = ".".join(new_version)

    def finalize_options(self):
        pass

    def run(self):

        try:
            print('old version: %s  new version: %s' %
                  (metadata['version'], self.version))
            raw_input('Press enter to confirm, or ctrl-c to exit >')
        except KeyboardInterrupt:
            raise SystemExit("\nNot proceeding")

        old = "__version__ = '%s'" % metadata['version']
        new = "__version__ = '%s'" % self.version

        module_file = read_module_contents()
        with open('bucko/__init__.py', 'w') as fileh:
            fileh.write(module_file.replace(old, new))

        # Commit everything with a standard commit message
        cmd = ['git', 'commit', '-a', '-m', 'version %s' % self.version]
        print(' '.join(cmd))
        subprocess.check_call(cmd)


class ReleaseCommand(Command):
    """ Tag and push a new release. """

    user_options = [('sign', 's', 'GPG-sign the Git tag and release files')]

    def initialize_options(self):
        self.sign = False

    def finalize_options(self):
        pass

    def run(self):
        # Create Git tag
        tag_name = 'v%s' % version
        cmd = ['git', 'tag', '-a', tag_name, '-m', 'version %s' % version]
        if self.sign:
            cmd.append('-s')
        print(' '.join(cmd))
        subprocess.check_call(cmd)

        # Push Git tag to origin remote
        cmd = ['git', 'push', 'origin', tag_name]
        print(' '.join(cmd))
        subprocess.check_call(cmd)

        # Push package to pypi
        # cmd = ['python', 'setup.py', 'sdist', 'upload']
        # if self.sign:
        #    cmd.append('--sign')
        # print(' '.join(cmd))
        # subprocess.check_call(cmd)

        # Push master to the remote
        cmd = ['git', 'push', 'origin', 'master']
        print(' '.join(cmd))
        subprocess.check_call(cmd)


setup(
    name='bucko',
    version=version,
    description='Build Unified Containers',
    long_description=long_description,
    author='Ken Dreyer',
    author_email='kdreyer@redhat.com',
    scripts=['bin/bucko'],
    license='GPLv2',
    include_package_data=True,
    install_requires=[
        # 'koji', it's a requirement, but we can't specify it here. :(
        'paramiko',
        'productmd>=1.3',
    ],
    tests_require=[
        'pytest',
        'httpretty',
    ],
    packages=find_packages(exclude=['ez_setup']),
    cmdclass={'bump': BumpCommand, 'release': ReleaseCommand},
)
