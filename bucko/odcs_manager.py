from bucko.log import log
from odcs.client import odcs

ODCS_URL = 'https://odcs.engineering.redhat.com'


def generate(tag, arches):
    # On CLI:
    # odcs --quiet --redhat create-tag --arch "x86_64 ppc64le s390x" --sigkey none ceph-6.0-rhel-9-candidate
    # odcs --quiet --redhat create-tag --arch "x86_64 ppc64le s390x aarch64" --sigkey none ceph-8.0-rhel-9-candidate
    source = odcs.ComposeSourceTag(tag, sigkeys=[''])
    client = odcs.ODCS(ODCS_URL, auth_mech=odcs.AuthMech.Kerberos)
    compose = client.request_compose(source, arches=arches.split())
    log.info('waiting for %s to finish' % compose['toplevel_url'])
    result = client.wait_for_compose(compose['id'])
    if result['state_name'] != 'done':
        raise RuntimeError(result)
    return result['result_repofile']
