"""Testes unitários para o VPNManager."""

import time
from unittest.mock import MagicMock, patch
from mogged.constants import (
    STATUS_CONNECTED,
    STATUS_CONNECTING,
    STATUS_DISCONNECTED,
    STATUS_ERROR,
)
from mogged.network.vpn_manager import VPNManager


def test_vpn_manager_initial_state():
    mgr = VPNManager()
    assert mgr.status == STATUS_DISCONNECTED
    assert mgr.connected_since is None


def test_vpn_manager_status_updates():
    status_events = []
    mgr = VPNManager(on_status_change=lambda st, msg: status_events.append((st, msg)))

    mgr._set_status(STATUS_CONNECTING, "Tentando...")
    assert mgr.status == STATUS_CONNECTING

    mgr._set_status(STATUS_CONNECTED, "Conectado")
    assert mgr.status == STATUS_CONNECTED
    assert mgr.connected_since is not None

    mgr._set_status(STATUS_DISCONNECTED, "Desconectado")
    assert mgr.status == STATUS_DISCONNECTED
    assert mgr.connected_since is None

    assert len(status_events) == 3


def test_vpn_manager_connect_fallback_success():
    fake_backend = MagicMock()
    # Primeiro servidor falha, segundo tem sucesso
    fake_backend.connect.side_effect = [False, True]

    mgr = VPNManager(backend=fake_backend)

    srv1 = {"id": "srv1", "ip": "1.1.1.1", "country_long": "Node 1"}
    srv2 = {"id": "srv2", "ip": "2.2.2.2", "country_long": "Node 2"}

    # Mock time.sleep para teste veloz
    with patch("time.sleep", return_value=None):
        mgr.connect(srv1, mode="full", fallback_servers=[srv2])
        if mgr._monitor_thread:
            mgr._monitor_thread.join(timeout=2)

    assert fake_backend.connect.call_count == 2
    assert mgr.active_server == srv2


def test_vpn_manager_disconnect():
    fake_backend = MagicMock()
    mgr = VPNManager(backend=fake_backend)
    mgr.disconnect()
    fake_backend.disconnect.assert_called_once()
    assert mgr.status == STATUS_DISCONNECTED
