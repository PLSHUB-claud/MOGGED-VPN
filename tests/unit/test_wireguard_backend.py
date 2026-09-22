"""Testes unitários para WireGuardBackend."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from mogged.constants import STATUS_CONNECTED
from mogged.network.wireguard_backend import WireGuardBackend


@pytest.fixture
def mock_wg_bin(tmp_path: Path):
    fake_exe = tmp_path / "wireguard.exe"
    fake_exe.write_bytes(b"FAKE_WIREGUARD_BIN")
    return fake_exe


def test_wireguard_prepare_config(mock_wg_bin: Path):
    backend = WireGuardBackend(wireguard_bin_path=mock_wg_bin)
    server = {
        "ip": "198.51.100.1",
        "port": 51820,
        "client_private_key": "c_priv_key",
        "peer_public_key": "p_pub_key",
    }
    cfg_path = backend.prepare_config(server, mode="full")
    assert os.path.isfile(cfg_path)

    with open(cfg_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "PrivateKey = c_priv_key" in content
    assert "PublicKey = p_pub_key" in content
    assert "Endpoint = 198.51.100.1:51820" in content

    backend.active_config_path = cfg_path
    backend.disconnect()
    assert not os.path.exists(cfg_path)


def test_wireguard_connect_fails_if_binary_missing(tmp_path: Path):
    missing_bin = tmp_path / "not_found_wg.exe"
    backend = WireGuardBackend(wireguard_bin_path=missing_bin)
    assert backend.connect({}) is False


def test_wireguard_connect_success(mock_wg_bin: Path):
    backend = WireGuardBackend(wireguard_bin_path=mock_wg_bin)
    server = {"ip": "1.2.3.4", "port": 51820}

    mock_res = MagicMock()
    mock_res.returncode = 0

    status_events = []

    def on_status(st, msg):
        status_events.append(st)

    with patch("subprocess.run", return_value=mock_res):
        res = backend.connect(server, mode="full", on_status=on_status)
        assert res is True
        assert backend.is_connected() is True
        assert STATUS_CONNECTED in status_events

    with patch("subprocess.run"):
        backend.disconnect()
        assert backend.is_connected() is False
