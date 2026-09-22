"""Testes unitários abrangentes com mocks para OpenVPNBackend."""

import os
from pathlib import Path
import subprocess
import time
from unittest.mock import MagicMock, patch
import pytest

from mogged.constants import STATUS_CONNECTED
from mogged.network.openvpn_backend import OpenVPNBackend


@pytest.fixture
def mock_openvpn_bin(tmp_path: Path):
    fake_exe = tmp_path / "openvpn.exe"
    fake_exe.write_bytes(b"FAKE_OPENVPN_BINARY")
    return fake_exe


def test_prepare_config_full_mode(mock_openvpn_bin: Path):
    backend = OpenVPNBackend(openvpn_bin_path=mock_openvpn_bin)
    # ovpn config base64 de teste
    import base64
    sample_ovpn = base64.b64encode(b"client\ndev tun\nremote 8.8.8.8 1194").decode("utf-8")

    cfg_path = backend.prepare_config(sample_ovpn, mode="full")
    assert os.path.isfile(cfg_path)

    with open(cfg_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "redirect-gateway def1" in content
    assert "windows-driver wintun" in content
    assert "block-outside-dns" in content

    backend.active_config_path = cfg_path
    backend._cleanup_temp_file()
    assert not os.path.exists(cfg_path)


def test_prepare_config_discord_mode(mock_openvpn_bin: Path):
    backend = OpenVPNBackend(openvpn_bin_path=mock_openvpn_bin)
    import base64
    sample_ovpn = base64.b64encode(b"client\ndev tun\nredirect-gateway def1").decode("utf-8")

    cfg_path = backend.prepare_config(sample_ovpn, mode="discord")
    with open(cfg_path, "r", encoding="utf-8") as f:
        content = f.read()

    # No modo Discord, redirect-gateway original deve ser removido e route-nopull incluído
    assert "route-nopull" in content
    backend.active_config_path = cfg_path
    backend._cleanup_temp_file()


def test_connect_fails_if_binary_missing(tmp_path: Path):
    missing_bin = tmp_path / "non_existent_openvpn.exe"
    backend = OpenVPNBackend(openvpn_bin_path=missing_bin)
    server = {"id": "1", "ovpn_config_b64": "Y2xpZW50Cg=="}
    assert backend.connect(server) is False


def test_connect_handshake_success(mock_openvpn_bin: Path):
    backend = OpenVPNBackend(openvpn_bin_path=mock_openvpn_bin)
    # Bypass da verificação de integridade no mock
    backend._verifier.verify_file = MagicMock(return_value=True)

    fake_proc = MagicMock()
    fake_proc.pid = 12345
    fake_proc.stdout.readline.side_effect = [
        "OpenVPN 2.6.5\n",
        "Initialization Sequence Completed\n",
        "",
    ]
    fake_proc.poll.side_effect = [None, None, 0]

    status_calls = []

    def on_status(st, msg):
        status_calls.append((st, msg))

    import base64
    server = {"id": "1", "ovpn_config_b64": base64.b64encode(b"client").decode("utf-8")}

    with patch("subprocess.Popen", return_value=fake_proc):
        with patch.object(backend, "_kill_process") as mock_kill:
            result = backend.connect(server, mode="full", on_status=on_status)
            assert result is True
            assert any(st == STATUS_CONNECTED for st, _ in status_calls)


def test_connect_handshake_failure_tls_error(mock_openvpn_bin: Path):
    backend = OpenVPNBackend(openvpn_bin_path=mock_openvpn_bin)
    backend._verifier.verify_file = MagicMock(return_value=True)

    fake_proc = MagicMock()
    fake_proc.pid = 12346
    fake_proc.stdout.readline.side_effect = [
        "TLS Error: TLS handshake failed\n",
        "",
    ]
    fake_proc.poll.return_value = None

    import base64
    server = {"id": "1", "ovpn_config_b64": base64.b64encode(b"client").decode("utf-8")}

    with patch("subprocess.Popen", return_value=fake_proc):
        with patch.object(backend, "_kill_process"):
            result = backend.connect(server)
            assert result is False


def test_kill_process_by_pid_and_waits():
    backend = OpenVPNBackend()
    fake_proc = MagicMock()
    fake_proc.pid = 9999
    backend.process = fake_proc

    with patch("subprocess.run") as mock_run:
        backend._kill_process()
        assert backend.process is None
        fake_proc.wait.assert_called_once_with(timeout=4)
        mock_run.assert_called_once()
