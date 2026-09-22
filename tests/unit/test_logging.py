"""Testes unitários para o sistema de logging seguro e redaction."""

from mogged.logging_config import redact_sensitive


def test_redact_public_ips():
    sample = "Conexão aberta para 203.0.113.195 na porta 443"
    redacted = redact_sensitive(sample)
    assert "203.0.113.195" not in redacted
    assert "[REDACTED_IP]" in redacted


def test_preserve_localhost_ips():
    sample = "Ouvindo em 127.0.0.1 e 0.0.0.0"
    redacted = redact_sensitive(sample)
    assert "127.0.0.1" in redacted
    assert "0.0.0.0" in redacted


def test_redact_certificates():
    sample = (
        "Certificado recebido:\n"
        "-----BEGIN CERTIFICATE-----\n"
        "MIIDXTCCAkWgAwIBAgIJAL9Z...\n"
        "-----END CERTIFICATE-----"
    )
    redacted = redact_sensitive(sample)
    assert "MIIDXTCCAkWgAwIBAgIJAL9Z" not in redacted
    assert "[REDACTED_CERTIFICATE]" in redacted


def test_redact_tokens_and_passwords():
    sample = "Autenticado com token: secret_abc12345 e password='my_password_xyz'"
    redacted = redact_sensitive(sample)
    assert "secret_abc12345" not in redacted
    assert "my_password_xyz" not in redacted
    assert "[REDACTED]" in redacted
