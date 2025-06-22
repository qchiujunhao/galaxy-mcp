"""
Test dataset-related operations
"""

from unittest.mock import patch

import pytest

from .test_helpers import download_dataset_fn, galaxy_state, get_dataset_details_fn, upload_file_fn


class TestDatasetOperations:
    """Test dataset operations"""

    def test_upload_file(self, mock_galaxy_instance):
        """Test file upload to history"""
        mock_galaxy_instance.tools.upload_file.return_value = {
            "outputs": [{"id": "new_dataset_1", "name": "test.txt"}]
        }

        with patch.dict(galaxy_state, {"connected": True, "gi": mock_galaxy_instance}):
            with patch("os.path.exists", return_value=True):
                result = upload_file_fn("/path/to/test.txt", "test_history_1")

                assert result["outputs"][0]["id"] == "new_dataset_1"
                assert result["outputs"][0]["name"] == "test.txt"
                mock_galaxy_instance.tools.upload_file.assert_called_once()

    def test_upload_file_not_found(self, mock_galaxy_instance):
        """Test upload with non-existent file"""
        with patch.dict(galaxy_state, {"connected": True, "gi": mock_galaxy_instance}):
            with patch("os.path.exists", return_value=False):
                with pytest.raises(ValueError, match="File not found"):
                    upload_file_fn("/nonexistent/file.txt", "test_history_1")

    def test_get_dataset_details_with_preview(self, mock_galaxy_instance):
        """Test getting dataset details with preview"""
        dataset_id = "dataset123"

        # Mock dataset info
        mock_dataset_info = {
            "id": dataset_id,
            "name": "test_data.txt",
            "state": "ok",
            "extension": "txt",
            "file_size": 1024,
        }

        # Mock dataset content for preview
        mock_content = b"line1\nline2\nline3\nline4\nline5\n"

        mock_galaxy_instance.datasets.show_dataset.return_value = mock_dataset_info
        mock_galaxy_instance.datasets.download_dataset.return_value = mock_content

        with patch.dict(galaxy_state, {"connected": True, "gi": mock_galaxy_instance}):
            result = get_dataset_details_fn(dataset_id, include_preview=True, preview_lines=3)

            assert result["dataset_id"] == dataset_id
            assert result["dataset"]["name"] == "test_data.txt"
            assert result["preview"]["lines"] == "line1\nline2\nline3"
            assert result["preview"]["total_lines"] == 6  # 5 lines + empty line at end
            assert result["preview"]["truncated"] is True

            mock_galaxy_instance.datasets.show_dataset.assert_called_once_with(dataset_id)

    def test_get_dataset_details_no_preview(self, mock_galaxy_instance):
        """Test getting dataset details without preview"""
        dataset_id = "dataset123"

        mock_dataset_info = {
            "id": dataset_id,
            "name": "test_data.txt",
            "state": "ok",
            "extension": "txt",
        }

        mock_galaxy_instance.datasets.show_dataset.return_value = mock_dataset_info

        with patch.dict(galaxy_state, {"connected": True, "gi": mock_galaxy_instance}):
            result = get_dataset_details_fn(dataset_id, include_preview=False)

            assert result["dataset_id"] == dataset_id
            assert result["dataset"]["name"] == "test_data.txt"
            assert "preview" not in result

            # Should not call download_dataset for preview
            mock_galaxy_instance.datasets.download_dataset.assert_not_called()

    def test_get_dataset_details_binary_file(self, mock_galaxy_instance):
        """Test getting dataset details with binary content"""
        dataset_id = "dataset123"

        mock_dataset_info = {
            "id": dataset_id,
            "name": "test_data.bin",
            "state": "ok",
            "extension": "bin",
        }

        # Binary content that can't be decoded as UTF-8
        mock_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00"

        mock_galaxy_instance.datasets.show_dataset.return_value = mock_dataset_info
        mock_galaxy_instance.datasets.download_dataset.return_value = mock_content

        with patch.dict(galaxy_state, {"connected": True, "gi": mock_galaxy_instance}):
            result = get_dataset_details_fn(dataset_id, include_preview=True)

            assert result["dataset_id"] == dataset_id
            assert "[Binary content" in result["preview"]["lines"]
            assert "hex:" in result["preview"]["lines"]

    def test_download_dataset_with_file_path(self, mock_galaxy_instance):
        """Test dataset download to specific file path"""
        dataset_id = "dataset123"
        file_path = "/tmp/test_download.txt"

        mock_dataset_info = {
            "id": dataset_id,
            "name": "test_data.txt",
            "state": "ok",
            "extension": "txt",
            "file_size": 1024,
        }

        mock_galaxy_instance.datasets.show_dataset.return_value = mock_dataset_info
        mock_galaxy_instance.datasets.download_dataset.return_value = file_path

        with patch.dict(galaxy_state, {"connected": True, "gi": mock_galaxy_instance}):
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getsize", return_value=1024):
                    result = download_dataset_fn(dataset_id, file_path=file_path)

                    assert result["dataset_id"] == dataset_id
                    assert result["file_path"] == file_path
                    assert result["file_size"] == 1024
                    assert result["dataset_info"]["name"] == "test_data.txt"

                    mock_galaxy_instance.datasets.download_dataset.assert_called_once_with(
                        dataset_id,
                        file_path=file_path,
                        use_default_filename=False,
                        require_ok_state=True,
                    )

    def test_download_dataset_default_filename(self, mock_galaxy_instance):
        """Test dataset download with default filename"""
        dataset_id = "dataset123"

        mock_dataset_info = {
            "id": dataset_id,
            "name": "test_data",
            "state": "ok",
            "extension": "txt",
            "file_size": 1024,
        }

        mock_content = b"test file content"

        mock_galaxy_instance.datasets.show_dataset.return_value = mock_dataset_info
        mock_galaxy_instance.datasets.download_dataset.return_value = mock_content

        with patch.dict(galaxy_state, {"connected": True, "gi": mock_galaxy_instance}):
            with patch("builtins.open", create=True) as mock_open:
                with patch("os.path.exists", return_value=True):
                    with patch("os.path.getsize", return_value=len(mock_content)):
                        result = download_dataset_fn(dataset_id)

                        assert result["dataset_id"] == dataset_id
                        assert result["file_path"] == "test_data.txt"
                        assert result["dataset_info"]["name"] == "test_data"

                        # Verify file was written
                        mock_open.assert_called_once_with("test_data.txt", "wb")

    def test_download_dataset_not_ok_state(self, mock_galaxy_instance):
        """Test download fails when dataset not in ok state"""
        dataset_id = "dataset123"

        mock_dataset_info = {
            "id": dataset_id,
            "name": "test_data.txt",
            "state": "running",
            "extension": "txt",
        }

        mock_galaxy_instance.datasets.show_dataset.return_value = mock_dataset_info

        with patch.dict(galaxy_state, {"connected": True, "gi": mock_galaxy_instance}):
            with pytest.raises(ValueError, match="Dataset .* is in state 'running', not 'ok'"):
                download_dataset_fn(dataset_id)

    def test_dataset_operations_not_connected(self):
        """Test dataset operations fail when not connected"""
        with patch.dict(galaxy_state, {"connected": False}):
            with pytest.raises(ValueError, match="Not connected to Galaxy"):
                upload_file_fn("/path/to/file.txt", "history_1")

            with pytest.raises(ValueError, match="Not connected to Galaxy"):
                get_dataset_details_fn("dataset123")

            with pytest.raises(ValueError, match="Not connected to Galaxy"):
                download_dataset_fn("dataset123")
