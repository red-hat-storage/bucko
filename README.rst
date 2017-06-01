``bucko`` - Build Unified COntainers
====================================

A tool to build a single container from all variants of a signed `Pungi
<https://pagure.io/pungi/>`_ compose.

You can use this to automatically scratch-build unified containers from
composes as part of a CI system (ie Jenkins).

Example: specifying a compose URL on the command-line
-----------------------------------------------------

Ensure you have a Kerberos credential, and then run ``bucko --compose``::

    kinit kdreyer@REDHAT.COM

    bucko --compose http://example.com/MYCOMPOSE-1234.t.0/

Example: running unattended
---------------------------

Let's say Jenkins sets a ``COMPOSE_URL`` environment variable for us::

    echo $COMPOSE_URL
    http://example/MYCOMPOSE-1234.t.0/

Bucko will parse this environment var if we don't specify a ``--compose``
argument on the command line. We just need a keytab for authentication, and
we're set::

    k5start -U -f /etc/my-jenkins.keytab -- bucko

Example: running unattended from CI_MESSAGE JSON
------------------------------------------------

Let's say Jenkins sets a more complicated environment variable for us.
``CI_MESSAGE`` contains JSON data with the COMPOSE_URL embedded in it::

    echo $CI_MESSAGE
    {"COMPOSE_URL": "http://example/MYCOMPOSE-1234.t.0/"}

As long as ``CI_MESSAGE`` is valid JSON and has a ``"COMPOSE_URL"`` key
defined in the message, Bucko will parse the compose URL from ``CI_MESSAGE``
for us::

    k5start -U -f /etc/my-jenkins.keytab -- bucko

How it works
------------
Bucko does the following actions:

1. Query the compose's metadata to discover all the variants in a compose.
2. Construct a Yum .repo file with all the compose's variants.
3. Publish the .repo file to a web server (ie, to a local filesystem location,
   or a remote SSH server).
4. Initiate a Brew build with this .repo file on the web server.

Integration with Pungi
----------------------

Eventually some or all of bucko's functionality may be implemented in Pungi
itself. See the following:

* https://github.com/release-engineering/productmd/issues/41
  - productmd support for querying directly via HTTP (In productmd v1.3)
* https://pagure.io/pungi/issue/485 - metadata for scratch builds (will be
  released in the next Pungi release after v4.1.13)
* https://pagure.io/pungi/issue/486 - unified containers (In Pungi v4.1.12)
* https://pagure.io/pungi/issue/487 - GPG verification during container build
  (In Pungi v4.1.12)

Command-line arguments
----------------------

* ``--compose`` HTTP(S) URL to a Distill/Pungi compose. If unspecified, this
  program will parse the ``COMPOSE_URL`` and ``CI_MESSAGE`` environment
  variables for this information.

Configuration file
------------------

Some settings should be specified in a ``bucko.conf`` configuration file.

bucko will search for a ``bucko.conf`` in the current working directory,
falling back to ``$HOME/.bucko.conf``.

Sample ``bucko.conf`` contents::

    [publish]
    # sftp:// or --file:// location to publish the .repo file.
    push = sftp:///home/remote/kdreyer/public_html/osbs

    #  HTTP(S) URL to the publish directory for OSBS to contact.
    http = http://example.com/~kdreyer/osbs

    [koji]
    hub = https://koji.fedoraproject.org/kojihub
    web = http://koji.fedoraproject.org/koji
    scm = git://example.com/rpms/rhceph-rhel7-docker#origin/ceph-2-rhel-7
    target = ceph-2-rhel-7-docker-candidate
    krbservice = brewhub

    [keys]
    # List any extra keys here. For example, an internal signing key:
    f000000d = http://internal.example.com/keys/RPM-GPG-KEY-internal-custom

    [base_product]
    # HTTP URL to RHEL 7 Server content
    url = http://example.com/content/dist/rhel/server/7/7Server/$basearch/os/
    gpgkey = fd431d51
