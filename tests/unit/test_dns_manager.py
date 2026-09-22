"""Testes unitários para DNSManager — diretivas OpenVPN, flush DNS.

flush_dns() requer Windows e usa ipconfig, portanto testes de plataforma
são marcados com skipif adequado.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from mogged.network.dns_manager import DNSManager, SAFE_DNS_SERVERS


# ---------------------------------------------------------------------------
# get_openvpn_dns_directives
# ---------------------------------------------------------------------------


def test_directives_include_block_outside_dns() -> None:
    """A diretiva 'block-outside-dns' deve estar presente para prevenir DNS leaks."""
    directives = DNSManager.get_openvpn_dns_directives()
    assert "block-outside-dns" in directives


def test_directives_include_all_safe_dns_servers() -> None:
    """Cada servidor DNS seguro deve aparecer como dhcp-option DNS na lista."""
    directives = DNSManager.get_openvpn_dns_directives()
    for dns in SAFE_DNS_SERVERS:
        assert f"dhcp-option DNS {dns}" in directives


def test_directives_returns_list_of_strings() -> None:
    directives = DNSManager.get_openvpn_dns_directives()
    assert isinstance(directives, list)
    assert all(isinstance(d, str) for d in directives)


def test_directives_no_plain_http() -> None:
    """Nenhuma diretiva deve referenciar URLs http:// inseguras."""
    for d in DNSManager.get_openvpn_dns_directives():
        assert "http://" not in d


def test_directives_have_minimum_length() -> None:
    """Deve haver pelo menos 2 entradas (block-outside-dns + ao menos 1 DNS)."""
    assert len(DNSManager.get_openvpn_dns_directives()) >= 2


# ---------------------------------------------------------------------------
# SAFE_DNS_SERVERS — validação dos IPs
# ---------------------------------------------------------------------------


def test_safe_dns_servers_are_valid_public_ips() -> None:
    """Os servidores DNS configurados não devem ser IPs privados ou reservados."""
    import ipaddress

    for dns in SAFE_DNS_SERVERS:
        ip = ipaddress.ip_address(dns)
        assert not ip.is_private
        assert not ip.is_loopback
        assert not ip.is_link_local


# ---------------------------------------------------------------------------
# flush_dns — Windows
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="flush_dns só executa no Windows")
def test_flush_dns_returns_true_on_success() -> None:
    """Quando ipconfig /flushdns retorna código 0, flush_dns() deve retornar True."""
    mock_result = MagicMock()
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = DNSManager.flush_dns()

    assert result is True
    mock_run.assert_called_once()
    # Verificar que não usou shell=True
    call_kwargs = mock_run.call_args
    assert call_kwargs.kwargs.get("shell") is not True


@pytest.mark.skipif(sys.platform != "win32", reason="flush_dns só executa no Windows")
def test_flush_dns_returns_false_on_exception() -> None:
    """Se subprocess.run lançar exceção, flush_dns() deve retornar False sem propagar."""
    with patch("subprocess.run", side_effect=OSError("acesso negado")):
        result = DNSManager.flush_dns()

    assert result is False


def test_flush_dns_returns_true_on_non_windows() -> None:
    """Em plataformas não-Windows, flush_dns() deve retornar True sem fazer nada."""
    with patch("sys.platform", "linux"):
        result = DNSManager.flush_dns()
    assert result is True


def test_flush_dns_does_not_use_shell_true() -> None:
    """Garantir que subprocess.run nunca é chamado com shell=True (regra de segurança)."""
    if sys.platform != "win32":
        pytest.skip("Verificação de shell=True apenas relevante no Windows")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        DNSManager.flush_dns()

    for call in mock_run.call_args_list:
        assert call.kwargs.get("shell") is not True
