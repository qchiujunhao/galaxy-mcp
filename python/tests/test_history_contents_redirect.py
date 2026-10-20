"""get_history_contents sends the API key, so its contents request never follows a redirect."""

from unittest.mock import patch

import pytest
import responses

from .test_helpers import galaxy_state, get_history_contents_fn

GALAXY = "http://localhost:8080/api"
CONTENTS = f"{GALAXY}/histories/h1/contents"


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_is_an_error_and_not_followed(mock_galaxy_instance, status):
    location = "https://attacker.example/steal"
    with responses.RequestsMock(assert_all_requests_are_fired=False) as galaxy:
        galaxy.get(CONTENTS, status=status, headers={"Location": location})
        galaxy.get(location, json={"contents": [], "stats": {"total_matches": 0}})
        with patch.dict(galaxy_state, {"connected": True, "gi": mock_galaxy_instance}):
            with pytest.raises(ValueError, match=f"HTTP {status} \\(redirects are not followed\\)"):
                get_history_contents_fn("h1")
        # One request, to Galaxy, carrying the key; nothing to the redirect target.
        assert [c.request.url.split("?")[0] for c in galaxy.calls] == [CONTENTS]
        assert galaxy.calls[0].request.headers["x-api-key"] == "test_key"


def test_a_plain_answer_still_reads(mock_galaxy_instance):
    with responses.RequestsMock() as galaxy:
        galaxy.get(CONTENTS, json={"contents": [], "stats": {"total_matches": 0}})
        with patch.dict(galaxy_state, {"connected": True, "gi": mock_galaxy_instance}):
            result = get_history_contents_fn("h1")
    assert result.success is True
    assert result.data["contents"] == []
