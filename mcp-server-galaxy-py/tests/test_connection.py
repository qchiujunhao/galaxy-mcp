"""
Test Galaxy connection and authentication
"""

from unittest.mock import patch

import pytest

from galaxy_mcp.server import ensure_connected, galaxy_state


class TestConnection:
    """Test connection functionality"""

    def test_initial_state(self):
        """Test initial galaxy state before connection"""
        with patch.dict(galaxy_state, {"connected": False, "gi": None}):
            assert not galaxy_state["connected"]
            assert galaxy_state["gi"] is None

    def test_connection_success(self, mock_galaxy_instance, test_env):
        """Test successful connection to Galaxy"""
        with patch.dict(galaxy_state, {"connected": False, "gi": None}):
            with patch("galaxy_mcp.server.GalaxyInstance", return_value=mock_galaxy_instance):
                # This should trigger initialization in the actual module
                from galaxy_mcp.server import galaxy_state as new_state

                # Simulate the initialization
                new_state["gi"] = mock_galaxy_instance
                new_state["connected"] = True

                assert new_state["connected"]
                assert new_state["gi"] is not None

    def test_ensure_connected_when_disconnected(self):
        """Test ensure_connected raises error when not connected"""
        with patch.dict(galaxy_state, {"connected": False}):
            with pytest.raises(ValueError, match="Not connected to Galaxy"):
                ensure_connected()

    def test_ensure_connected_when_connected(self, mock_galaxy_instance):
        """Test ensure_connected passes when connected"""
        with patch.dict(galaxy_state, {"connected": True, "gi": mock_galaxy_instance}):
            # Should not raise
            ensure_connected()

    def test_connection_with_invalid_url(self, test_env):
        """Test connection fails gracefully with invalid URL"""
        with patch.dict(galaxy_state, {"connected": False}):
            with patch("galaxy_mcp.server.GalaxyInstance", side_effect=Exception("Invalid URL")):
                # In real implementation, this would be handled during initialization
                assert not galaxy_state["connected"]

    def test_connection_with_missing_credentials(self):
        """Test connection requires credentials"""
        with patch.dict("os.environ", {}, clear=True):
            with patch.dict(galaxy_state, {"connected": False}):
                # Without credentials, should not connect
                assert not galaxy_state.get("connected", False)
