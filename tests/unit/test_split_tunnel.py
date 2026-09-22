"""Testes unitários para o módulo de Split-Tunneling do Discord."""

from unittest.mock import patch
from mogged.network.split_tunnel import (
    FALLBACK_DISCORD_IPS,
    get_discord_split_directives,
    resolve_discord_ips,
)


def test_resolve_discord_ips_success():
    fake_dns = {
        "discord.com": (None, None, ["162.159.135.232"]),
        "gateway.discord.gg": (None, None, ["162.159.136.232"]),
    }

    def mock_gethost(domain):
        if domain in fake_dns:
            return fake_dns[domain]
        raise OSError("DNS not mocked")

    with patch("socket.gethostbyname_ex", side_effect=mock_gethost):
        ips = resolve_discord_ips(force=True)
        assert "162.159.135.232" in ips
        assert "162.159.136.232" in ips


def test_resolve_discord_ips_fallback_on_dns_failure():
    with patch("socket.gethostbyname_ex", side_effect=OSError("Offline")):
        # Forçar sem cache prévio
        with patch("mogged.network.split_tunnel._cached_ips", set()):
            ips = resolve_discord_ips(force=True)
            assert ips == FALLBACK_DISCORD_IPS


def test_get_discord_split_directives_structure():
    directives = get_discord_split_directives()
    assert "route-nopull" in directives
    # Deve conter rotas formatadas "route <network> <netmask>"
    route_lines = [line for line in directives if line.startswith("route ")]
    assert len(route_lines) > 5
    for r in route_lines:
        parts = r.split()
        assert len(parts) == 3
