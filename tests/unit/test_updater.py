import hashlib
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from mogged.exceptions import UpdateDownloadError, UpdateVerificationError
from mogged.updates.updater import Updater, is_newer_version, parse_semver

def test_parse_semver():
    assert parse_semver("1.2.3") == (1, 2, 3)
    assert parse_semver("v2.0.1") == (2, 0, 1)
    with pytest.raises(ValueError):
        parse_semver("invalid_version")

def test_is_newer_version():
    assert is_newer_version("1.0.0", "1.0.1") is True
    assert is_newer_version("1.0.0", "2.0.0") is True
    assert is_newer_version("1.1.0", "1.1.0") is False
    assert is_newer_version("1.2.0", "1.1.9") is False

def test_check_for_updates_finds_new_release():
    updater = Updater(repo_owner="test", repo_name="test")
    fake_payload = json.dumps({"tag_name": "v9.9.9", "body": "Changelog text"}).encode("utf-8")

    mock_resp = io.BytesIO(fake_payload)
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=None)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        info = updater.check_for_updates()
        assert info is not None
        assert info["version"] == "v9.9.9"
        assert info["release_notes"] == "Changelog text"

def test_check_for_updates_raw_version_json():
    updater = Updater(repo_owner="test", repo_name="test")
    payload = json.dumps({
        "version": "2.0.0",
        "download_url": "https://example.com/MoggedVPN_Setup.exe",
        "changelog": "Versao 2.0 lancada",
        "sha256": "abc123"
    }).encode("utf-8")

    mock_resp = io.BytesIO(payload)
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=None)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        info = updater.check_for_updates()
        assert info is not None
        assert info["version"] == "2.0.0"
        assert info["download_url"] == "https://example.com/MoggedVPN_Setup.exe"
        assert info["release_notes"] == "Versao 2.0 lancada"
        assert info["sha256"] == "abc123"

def test_check_for_updates_no_newer_version():
    updater = Updater(repo_owner="test", repo_name="test")
    payload = json.dumps({"version": "1.0.0"}).encode("utf-8")

    mock_resp = io.BytesIO(payload)
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=None)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        info = updater.check_for_updates()
        assert info is None

def test_download_and_verify_rejects_http():
    updater = Updater()
    with pytest.raises(UpdateDownloadError) as exc_info:
        updater.download_and_verify("http://insecure.example.com/setup.exe", "fake_hash")
    assert "estritamente HTTPS" in str(exc_info.value)

def test_download_and_verify_hash_mismatch():
    updater = Updater(expected_publisher=None)
    payload = b"MALICIOUS_OR_CORRUPT_EXE_DATA"

    mock_resp = io.BytesIO(payload)
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=None)

    wrong_hash = "0" * 64
    with patch("urllib.request.urlopen", return_value=mock_resp):
        with pytest.raises(UpdateVerificationError) as exc_info:
            updater.download_and_verify("https://secure.example.com/setup.exe", wrong_hash)
        assert "Hash SHA-256 do instalador diverge" in str(exc_info.value)

def test_download_and_verify_success():
    updater = Updater(expected_publisher=None)
    payload = b"VALID_SIGNED_EXE_DATA"
    valid_hash = hashlib.sha256(payload).hexdigest()

    mock_resp = io.BytesIO(payload)
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=None)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        file_path = updater.download_and_verify("https://secure.example.com/setup.exe", valid_hash)
        assert file_path.is_file()
        assert file_path.read_bytes() == payload
        file_path.unlink()

def test_download_and_verify_with_progress_callback():
    updater = Updater(expected_publisher=None)
    payload = b"A" * 131072

    class MockRespWithHeaders(io.BytesIO):
        headers = {"Content-Length": str(len(payload))}

    mock_resp = MockRespWithHeaders(payload)
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=None)

    progress_reports = []

    def on_progress(percent, downloaded):
        progress_reports.append((percent, downloaded))

    with patch("urllib.request.urlopen", return_value=mock_resp):
        file_path = updater.download_and_verify(
            "https://secure.example.com/setup.exe",
            progress_callback=on_progress,
        )
        assert file_path.is_file()
        assert len(progress_reports) > 0
        assert progress_reports[-1][0] == 100
        file_path.unlink()
