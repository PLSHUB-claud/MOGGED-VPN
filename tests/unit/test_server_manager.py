from unittest.mock import MagicMock, patch
import socket
import pytest

from mogged.network.server_manager import ServerManager

def test_server_manager_init():
    mock_fetcher = MagicMock()
    sm = ServerManager(fetcher=mock_fetcher)
    assert sm.servers == []
    assert len(sm.blacklist) == 0
    assert len(sm.failure_counts) == 0

def test_record_failure_and_blacklist():
    sm = ServerManager(fetcher=MagicMock())
    srv_id = "JP-1.2.3.4"
    assert srv_id not in sm.blacklist

    sm.record_failure(srv_id)
    assert sm.failure_counts[srv_id] == 1
    assert srv_id not in sm.blacklist

    sm.record_failure(srv_id)
    assert sm.failure_counts[srv_id] == 2
    assert srv_id not in sm.blacklist

    sm.record_failure(srv_id)
    assert sm.failure_counts[srv_id] == 3
    assert srv_id in sm.blacklist

    sm.record_success(srv_id)
    assert sm.failure_counts[srv_id] == 0
    assert srv_id not in sm.blacklist

def test_probe_server_tcp_success():
    sm = ServerManager(fetcher=MagicMock())
    server = {"id": "US-8.8.8.8", "ip": "8.8.8.8", "port": 443, "protocol": "tcp"}

    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value.__enter__.return_value = mock_sock
        srv, is_alive, rtt = sm.probe_server(server, timeout=0.5)

    assert is_alive is True
    assert rtt < 1000.0

def test_probe_server_tcp_failure():
    sm = ServerManager(fetcher=MagicMock())
    server = {"id": "US-8.8.8.8", "ip": "8.8.8.8", "port": 443, "protocol": "tcp"}

    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = socket.timeout("timed out")
        mock_sock_cls.return_value.__enter__.return_value = mock_sock
        srv, is_alive, rtt = sm.probe_server(server, timeout=0.5)

    assert is_alive is False
    assert rtt == 9999.0

def test_probe_server_invalid_ip():
    sm = ServerManager(fetcher=MagicMock())
    server = {"id": "INV-192.168.1.1", "ip": "192.168.1.1", "port": 443, "protocol": "tcp"}
    srv, is_alive, rtt = sm.probe_server(server, timeout=0.5)
    assert is_alive is False
    assert rtt == 9999.0

def test_health_check_ordering():
    sm = ServerManager(fetcher=MagicMock())
    servers = [
        {"id": "S1", "ip": "8.8.8.8", "port": 443, "protocol": "tcp", "speed_mbps": 100.0},
        {"id": "S2", "ip": "1.1.1.1", "port": 443, "protocol": "tcp", "speed_mbps": 50.0},
    ]

    def mock_probe(srv, timeout=1.0):
        if srv["id"] == "S1":
            return (srv, True, 120.0)
        return (srv, True, 25.0)

    with patch.object(sm, "probe_server", side_effect=mock_probe):
        checked = sm.health_check(servers)

    assert len(checked) == 2
    assert checked[0]["id"] == "S2"
    assert checked[0]["live_rtt"] == 25.0
    assert checked[1]["id"] == "S1"
    assert checked[1]["live_rtt"] == 120.0

def test_get_fallback_candidates():
    sm = ServerManager(fetcher=MagicMock())
    sm.servers = [
        {"id": "BR1", "country_short": "BR", "speed_mbps": 50.0, "ping": 20},
        {"id": "BR2", "country_short": "BR", "speed_mbps": 30.0, "ping": 30},
        {"id": "US1", "country_short": "US", "speed_mbps": 120.0, "ping": 100},
        {"id": "JP1", "country_short": "JP", "speed_mbps": 200.0, "ping": 250},
    ]

    fallbacks = sm.get_fallback_candidates("BR", exclude_server_id="BR1")
    assert len(fallbacks) >= 2
    assert fallbacks[0]["id"] == "BR2"
    assert fallbacks[1]["id"] in ("JP1", "US1")

def test_get_countries():
    sm = ServerManager(fetcher=MagicMock())
    sm.servers = [
        {"id": "BR1", "country_short": "BR", "country_long": "Brazil", "flag": "🇧🇷", "speed_mbps": 50.0, "ping": 20},
        {"id": "BR2", "country_short": "BR", "country_long": "Brazil", "flag": "🇧🇷", "speed_mbps": 80.0, "ping": 15},
        {"id": "US1", "country_short": "US", "country_long": "United States", "flag": "🇺🇸", "speed_mbps": 120.0, "ping": 100},
    ]

    countries = sm.get_countries()
    assert len(countries) == 2
    br = next(c for c in countries if c["code"] == "BR")
    assert br["server_count"] == 2
    assert br["best_ping"] == 15
    assert br["max_speed"] == 80.0
