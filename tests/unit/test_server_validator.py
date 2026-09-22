"""Testes unitários para a validação estrita de IPs e servidores."""

import pytest
from mogged.network.server_validator import is_valid_public_ip, ServerValidator


@pytest.mark.parametrize(
    "invalid_ip",
    [
        "127.0.0.1",          # Loopback
        "10.0.0.5",           # RFC 1918 Privado
        "192.168.0.1",        # RFC 1918 Privado
        "172.16.50.1",        # RFC 1918 Privado
        "169.254.169.254",    # Link-local / Metadata AWS/Azure
        "100.64.0.1",         # CGNAT
        "224.0.0.1",          # Multicast
        "0.0.0.0",            # Reservado
        "255.255.255.255",    # Broadcast
        "not_an_ip",          # String inválida
        "::1",                # IPv6 Loopback
    ],
)
def test_reject_private_and_reserved_ips(invalid_ip):
    assert is_valid_public_ip(invalid_ip) is False


@pytest.mark.parametrize(
    "valid_ip",
    [
        "8.8.8.8",
        "1.1.1.1",
        "9.9.9.9",
        "142.250.190.46",
    ],
)
def test_accept_valid_public_ips(valid_ip):
    assert is_valid_public_ip(valid_ip) is True


def test_server_validator_filters_invalid_candidates():
    validator = ServerValidator()
    candidates = [
        {"id": "1", "ip": "192.168.1.100", "country_short": "US"},
        {"id": "2", "ip": "169.254.169.254", "country_short": "BR"},
        {"id": "3", "ip": "8.8.8.8", "country_short": "US"},
        {"id": "4", "ip": "127.0.0.1", "country_short": "JP"},
    ]

    filtered = validator.filter_valid_servers(candidates)
    assert len(filtered) == 1
    assert filtered[0]["ip"] == "8.8.8.8"
