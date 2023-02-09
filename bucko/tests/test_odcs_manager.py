from odcs.client.odcs import ComposeSourceTag
from bucko import odcs_manager
from unittest.mock import patch


@patch('bucko.odcs_manager.odcs.ODCS.request_compose',
       return_value={'id': 1, 'toplevel_url': 'http://example.com/'})
@patch('bucko.odcs_manager.odcs.ODCS.wait_for_compose',
       return_value={'state_name': 'done',
                     'result_repofile': 'https://example.com/example.repo'})
def test_generate(mock_wait, mock_request):
    result = odcs_manager.generate('ceph-6.0-rhel-9-candidate')
    assert result == 'https://example.com/example.repo'

    mock_request.assert_called_once()
    # py36 compat for .call_args properties:
    mock_request.call_args.args = mock_request.call_args[0]
    mock_request.call_args.kwargs = mock_request.call_args[1]
    source = mock_request.call_args.args[0]
    assert isinstance(source, ComposeSourceTag)
    kwargs = mock_request.call_args.kwargs
    assert kwargs == {'arches': ['x86_64', 'ppc64le', 's390x']}
