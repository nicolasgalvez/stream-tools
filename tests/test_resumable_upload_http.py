"""The client's Http must not follow 308s (VGM-89).

YouTube's resumable upload answers each chunk but the last with 308. Treating
that as a redirect truncated every upload larger than one chunk.
"""

from unittest.mock import MagicMock, patch

from stream_tools.client import YouTubeLiveClient


def built_http():
    """The httplib2.Http the client hands to googleapiclient."""
    with patch("stream_tools.client.build") as build:
        _ = YouTubeLiveClient(MagicMock()).youtube
    return build.call_args.kwargs["http"].http


def test_the_http_the_client_builds_does_not_treat_308_as_a_redirect():
    assert 308 not in built_http().redirect_codes


def test_real_redirects_are_still_followed():
    assert {301, 302, 303, 307} <= built_http().redirect_codes
