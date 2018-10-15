from bucko.build import Build


def test_init():
    build = Build('rhel-server-container', '7.5', '107')
    assert str(build) == 'rhel-server-container-7.5-107'
    assert build.name == 'rhel-server-container'
    assert build.version == '7.5'
    assert build.release == '107'
