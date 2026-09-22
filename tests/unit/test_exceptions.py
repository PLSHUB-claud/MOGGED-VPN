"""Testes unitários para a hierarquia segura de exceções."""

import pytest
from mogged.exceptions import (
    MoggedError,
    NetworkError,
    VPNConnectionError,
    SecurityError,
    SignatureVerificationError,
    IntegrityCheckError,
)


def test_exception_hierarchy():
    err = VPNConnectionError("Falha ao conectar")
    assert isinstance(err, NetworkError)
    assert isinstance(err, MoggedError)

    sec_err = IntegrityCheckError("Hash incorreto")
    assert isinstance(sec_err, SecurityError)
    assert isinstance(sec_err, MoggedError)


def test_to_dict_sanitization():
    err = MoggedError(
        "Erro de autenticação",
        context={
            "user_id": 1234,
            "auth_token": "super_secret_token_123",
            "private_key": "-----BEGIN PRIVATE KEY-----xyz-----END PRIVATE KEY-----",
            "server_ip": "1.2.3.4",
        },
    )
    serialized = err.to_dict()

    assert serialized["error_type"] == "MoggedError"
    assert serialized["message"] == "Erro de autenticação"
    # Segredos devem estar redigidos
    assert serialized["context"]["auth_token"] == "[REDACTED]"
    assert serialized["context"]["private_key"] == "[REDACTED]"
    assert serialized["context"]["user_id"] == "1234"


def test_str_representation_does_not_leak_context():
    err = MoggedError("Mensagem pública", context={"secret_pass": "123456"})
    assert str(err) == "Mensagem pública"
    assert "123456" not in str(err)
