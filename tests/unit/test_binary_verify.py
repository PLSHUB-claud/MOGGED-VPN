"""Testes unitários para o subsistema de integridade de binários."""

from pathlib import Path
import pytest
from mogged.exceptions import IntegrityCheckError
from mogged.security.binary_verify import BinaryVerifier, calculate_sha256, verify_sha256


def test_calculate_and_verify_sha256(tmp_path: Path):
    dummy_file = tmp_path / "dummy_bin.exe"
    dummy_file.write_bytes(b"TEST_BINARY_CONTENT_MOGGED")

    expected_hash = calculate_sha256(dummy_file)
    assert len(expected_hash) == 64
    assert verify_sha256(dummy_file, expected_hash) is True


def test_hash_mismatch_raises_integrity_error(tmp_path: Path):
    dummy_file = tmp_path / "modified_bin.exe"
    dummy_file.write_bytes(b"AUTHENTIC_CONTENT")

    wrong_hash = "0" * 64
    with pytest.raises(IntegrityCheckError) as exc_info:
        verify_sha256(dummy_file, wrong_hash)

    assert "Hash SHA-256 divergente" in str(exc_info.value)


def test_missing_file_raises_integrity_error(tmp_path: Path):
    non_existent = tmp_path / "ghost.dll"
    with pytest.raises(IntegrityCheckError):
        verify_sha256(non_existent, "a" * 64)


def test_binary_verifier_with_manifest(tmp_path: Path):
    bin_file = tmp_path / "openvpn.exe"
    bin_file.write_bytes(b"OPENVPN_TEST_CONTENT")

    file_hash = calculate_sha256(bin_file)
    manifest = {"openvpn.exe": file_hash}

    verifier = BinaryVerifier(manifest=manifest)
    assert verifier.verify_file(bin_file) is True
    # Segunda chamada deve atingir o cache interno
    assert verifier.verify_file(bin_file) is True


def test_verify_authenticode_signature_valid(tmp_path: Path):
    from unittest.mock import MagicMock, patch
    from mogged.security.binary_verify import verify_authenticode_signature

    test_file = tmp_path / "valid.exe"
    test_file.write_bytes(b"DATA")

    mock_res = MagicMock()
    mock_res.stdout = "Valid|CN=OpenVPN Technologies, Inc., O=OpenVPN"

    with patch("subprocess.run", return_value=mock_res):
        assert verify_authenticode_signature(test_file, expected_publisher="OpenVPN") is True


def test_verify_authenticode_signature_wrong_publisher(tmp_path: Path):
    from unittest.mock import MagicMock, patch
    from mogged.security.binary_verify import verify_authenticode_signature

    test_file = tmp_path / "other.exe"
    test_file.write_bytes(b"DATA")

    mock_res = MagicMock()
    mock_res.stdout = "Valid|CN=Unknown Hacker, O=EvilCorp"

    with patch("subprocess.run", return_value=mock_res):
        assert verify_authenticode_signature(test_file, expected_publisher="OpenVPN") is False


def test_verify_authenticode_signature_invalid_status(tmp_path: Path):
    from unittest.mock import MagicMock, patch
    from mogged.security.binary_verify import verify_authenticode_signature

    test_file = tmp_path / "invalid.exe"
    test_file.write_bytes(b"DATA")

    mock_res = MagicMock()
    mock_res.stdout = "HashMismatch|"

    with patch("subprocess.run", return_value=mock_res):
        assert verify_authenticode_signature(test_file) is False


def test_verify_authenticode_missing_file():
    from mogged.exceptions import SignatureVerificationError
    from mogged.security.binary_verify import verify_authenticode_signature

    with pytest.raises(SignatureVerificationError):
        verify_authenticode_signature(Path("non_existent_path_xyz.exe"))

