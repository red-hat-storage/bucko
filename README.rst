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

Example: running unattended from CI_MESSAGE JSON compose_url
------------------------------------------------------------

Let's say Jenkins sets a more complicated environment variable for us.
``CI_MESSAGE`` contains JSON data with the compose_url embedded in it::

    echo $CI_MESSAGE
    {"compose_url": "http://example/MYCOMPOSE-1234.t.0/"}

As long as ``CI_MESSAGE`` is valid JSON and has a ``"compose_url"`` key
defined in the message, Bucko will parse the compose URL from ``CI_MESSAGE``
for us::

    k5start -U -f /etc/my-jenkins.keytab -- bucko

Example: running unattended from CI_MESSAGE JSON without compose_url key
------------------------------------------------------------------------

Building on the previous example, let's say Jenkins sets ``CI_MESSAGE`` for us,
but that JSON data does not have a compose_url key. It just has a dist-git
branch name::

    echo $CI_MESSAGE
    {"branch": "ceph-3.0-rhel-7"}

In this instance, bucko will read that branch name and combine it with the
COMPOSE_URL environment variable when it is defined as a Python format string::

    echo $COMPOSE_URL
    http://example/%(branch)s/latest-RHCEPH-%(major)s-%(distro)s/

And the resulting compose Bucko looks for will be::

    http://example/ceph-3.0-rhel-7/latest-RHCEPH-3-RHEL-7/

How it works
------------
Bucko does the following actions:

1. Query the compose's metadata to discover all the variants in a compose.
2. Construct a Yum .repo file with all the compose's variants.
3. Publish the .repo file to a web server (ie, to a local filesystem location,
   or a remote SSH server).
4. Initiate a Brew build with this .repo file on the web server.

Side note: what is a "variant"?
-------------------------------

A "variant" is a slight difference in the package list for a product.

To use RHEL 7 as an example: "Server" is the main variant for RHEL 7,
almost to the point that when you and I think of RHEL 7, we think of
RHEL 7 Server. There is also "RHEL 7 Workstation", "RHEL 7 ComputeNode",
etc. These are separate variants of the RHEL 7 product.

A variant is a set of packages.

The list of packages in a variant may overlap (they often do overlap).

The set of packages differs between variants. The versions of the
packages are not different between variants.

Only the package lists differ.

The current variants for the RHCEPH product are "Mon", "OSD", and "Tools".

Why scratch build?
------------------

One reason bucko does scratch builds instead of real builds is because
it reduces confusion when it's time to ship.

* Scratch-built container == maybe not fully GPG-signed
* Real container build == must be GPG-signed with the GA key.

(Internally there is some initial work in the Errata Tool and MetaXOR to
automatically inspect RPM signatures within containers and ultimately
prevent non-GA-signed content from shipping live. This is still a work
in progress. One bug to watch is https://bugzilla.redhat.com/1590550 .)

Multi-arch, or lack thereof
---------------------------

By default, OSBS will build for all arches defined on Koji's build tag
associated with Koji's build target. OSBS's docs explain more about this at
https://osbs.readthedocs.io/en/latest/users.html?highlight=container.yaml#image-configuration

This means that when your Koji build target's build tag has ``Arches: ppc64le
x86_64`` set, OSBS will try to build containers for both of those arches.

By default, Bucko overrides this behavior and builds the container for x86_64
only. There is no support for altering bucko's behavior using the configuration
file at this time, because I don't need this currently.

Integration with Pungi
----------------------

Much of bucko's functionality has now been implemented in Pungi itself. See the
following:

* https://github.com/release-engineering/productmd/issues/41
  - productmd support for querying directly via HTTP (In productmd v1.3)
* https://pagure.io/pungi/issue/485 - metadata for scratch builds (In Pungi
  v4.1.14)
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
    # sftp:// or file:// location to publish the .repo file.
    push = sftp:///home/remote/kdreyer/public_html/osbs

    #  HTTP(S) URL to the publish directory for OSBS to contact.
    http = http://example.com/~kdreyer/osbs

    [koji]
    hub = https://koji.fedoraproject.org/kojihub
    web = http://koji.fedoraproject.org/koji
    scm = git://example.com/containers/rhceph-rhel7#origin/%(branch)s
    target = %(branch)s-containers-candidate
    krbservice = brewhub

    [keys]
    # List any extra keys here. For example, an internal signing key:
    f000000d = http://internal.example.com/keys/RPM-GPG-KEY-internal-custom

    [ceph-3.0-rhel-7-base]
    # HTTP URL to RHEL 7 Server content
    url = http://example.com/content/dist/rhel/server/7/7Server/$basearch/os/
    # This "extras" URL is optional. Add it if you need an "extras" repo
    # defined:
    extras = http://example.com/content/dist/rhel/server/7/7Server/$basearch/extras/os/
    gpgkey = fd431d51

Bucko will interpolate the ``%(branch)s`` format string according to the
compose's metadata. For example, bucko will choose a ``branch`` value of
``ceph-3.0-rhel-7`` when processing a ``RHCEPH 3.0`` compose.

The ``[*-base]`` sections are unique per branch. Please define one for each
branch you expect to use.
