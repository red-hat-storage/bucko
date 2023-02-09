from bucko.log import log
from odcs.client import odcs

# TODO: determine the arches dynamically from the
# ceph-6.0-rhel-9-containers-candidate target tag, like OSBS does.
ARCHES = ['x86_64', 'ppc64le', 's390x']
ODCS_URL = 'https://odcs.engineering.redhat.com'


def generate(tag):
    # On CLI:
    # odcs --quiet --redhat create-tag --arch "x86_64 ppc64le s390x" --sigkey none ceph-6.0-rhel-9-candidate
    source = odcs.ComposeSourceTag(tag, sigkeys=[''])
    client = odcs.ODCS(ODCS_URL, auth_mech=odcs.AuthMech.Kerberos)
    compose = client.request_compose(source, arches=ARCHES)
    log.info('waiting for %s to finish' % compose['toplevel_url'])
    result = client.wait_for_compose(compose['id'])
    if result['state_name'] != 'done':
        raise RuntimeError(result)
    return result['result_repofile']
