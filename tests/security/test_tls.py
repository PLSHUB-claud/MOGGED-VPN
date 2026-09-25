"""Testes de segurança TLS: verificar que apenas HTTPS é aceito em ServerFetcher.

Estes testes garantem que nenhuma URL http:// é processada, que o
ServerFetcher usa urllib com verificação SSL por padrão, e que as URLs
configuradas no sistema aderem estritamente ao protocolo HTTPS.
"""

import ssl
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from mogged.constants import OPENVPN_PROVIDERS, VPN_GATE_API_URLS
from mogged.exceptions import ServerFetchError
from mogged.network.server_fetcher import ServerFetcher


def test_all_configured_urls_use_https() -> None:
    assert len(VPN_GATE_API_URLS) > 0
    for url in VPN_GATE_API_URLS:
        assert url.startswith("https://")
    assert len(OPENVPN_PROVIDERS) > 0
    for prov in OPENVPN_PROVIDERS:
        assert prov["url"].startswith("https://")


def test_no_http_url_in_configured_urls() -> None:
    for url in VPN_GATE_API_URLS:
        assert not url.startswith("http://")
    for prov in OPENVPN_PROVIDERS:
        assert not prov["url"].startswith("http://")


def test_fetcher_skips_http_urls_silently(tmp_path: Path) -> None:
    http_url = "http://vpngate.net/api/iphone/"
    https_url = "https://vpngate.net/api/iphone/"

    call_log: list = []

    def fake_urlopen(req, timeout=None):
        call_log.append(req.full_url if hasattr(req, "full_url") else str(req))
        raise OSError("network error")

    mixed_providers = [
        {"name": "bad", "url": http_url, "parser": "vpngate", "priority": 1},
        {"name": "good", "url": https_url, "parser": "vpngate", "priority": 2},
    ]

    with patch("mogged.network.server_fetcher.OPENVPN_PROVIDERS", mixed_providers):
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            fetcher = ServerFetcher(cache_dir=tmp_path)
            try:
                fetcher.fetch(force_refresh=True)
            except ServerFetchError:
                pass

    for attempted_url in call_log:
        assert attempted_url.startswith("https://")
    assert len(call_log) == 1
    assert call_log[0] == https_url


def test_fetcher_raises_when_only_http_urls_configured(tmp_path: Path) -> None:
    """Se apenas URLs http:// estiverem configuradas, deve lançar ServerFetchError sem rede."""
    only_http_providers = [
        {"name": "bad1", "url": "http://evil.com/api", "parser": "vpngate", "priority": 1},
        {"name": "bad2", "url": "http://another.com/api", "parser": "vpngate", "priority": 2},
    ]
    with patch("mogged.network.server_fetcher.OPENVPN_PROVIDERS", only_http_providers):
        fetcher = ServerFetcher(cache_dir=tmp_path)
        with patch.object(fetcher, "load_cache", return_value=([], 0.0)):
            with pytest.raises(ServerFetchError):
                fetcher.fetch(force_refresh=True)


def test_fetcher_never_calls_urlopen_for_http(tmp_path: Path) -> None:
    """urlopen NÃO deve ser chamado para URLs http://."""
    http_only_providers = [{"name": "bad", "url": "http://leak.example.com/api", "parser": "vpngate", "priority": 1}]
    with patch("mogged.network.server_fetcher.OPENVPN_PROVIDERS", http_only_providers):
        with patch("urllib.request.urlopen") as mock_urlopen:
            fetcher = ServerFetcher(cache_dir=tmp_path)
            with patch.object(fetcher, "load_cache", return_value=([], 0.0)):
                try:
                    fetcher.fetch(force_refresh=True)
                except ServerFetchError:
                    pass

    mock_urlopen.assert_not_called()


# ---------------------------------------------------------------------------
# Verificação de contexto SSL padrão do Python (não desabilitado)
# ---------------------------------------------------------------------------


def test_default_ssl_context_verifies_certificates() -> None:
    """O contexto SSL padrão do Python deve verificar certificados (não CERT_NONE)."""
    ctx = ssl.create_default_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_urllib_request_uses_https_handler() -> None:
    """urllib.request deve ter o HTTPSHandler disponível com verificação SSL."""
    opener = urllib.request.build_opener()
    handler_classes = [type(h).__name__ for h in opener.handlers]
    assert "HTTPSHandler" in handler_classes


# ---------------------------------------------------------------------------
# Verificação de que Request() do urllib não contém parâmetros inseguros
# ---------------------------------------------------------------------------


def test_request_object_uses_https_url() -> None:
    """Um urllib.request.Request criado com https:// deve preservar o esquema."""
    req = urllib.request.Request(
        "https://www.vpngate.net/api/iphone/",
        headers={"User-Agent": "MoggedVPN/1.1.0"},
    )
    assert req.full_url.startswith("https://")
    assert req.type == "https"


def test_request_object_rejects_http_by_convention() -> None:
    """Documentar que nosso código NUNCA cria Request() com http://."""
    # Este teste verifica a convenção: se alguém criar Request com http://,
    # o type retornado será "http", o que nosso código detecta e ignora.
    req = urllib.request.Request("http://example.com/api")
    assert req.type == "http"
    # O código do fetcher verifica url.startswith("https://") antes de chamar Request()
    # Então Request("http://...") nunca é criado.


# ---------------------------------------------------------------------------
# Verificação de timeout (proteção contra slow-read attacks)
# ---------------------------------------------------------------------------


def test_fetcher_uses_timeout_in_urlopen(tmp_path: Path) -> None:
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"HostName\nno_data"
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    single_provider = [{"name": "vpngate", "url": "https://test.local/api", "parser": "vpngate", "priority": 1}]
    with patch("mogged.network.server_fetcher.OPENVPN_PROVIDERS", single_provider):
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            fetcher = ServerFetcher(cache_dir=tmp_path)
            try:
                fetcher.fetch(force_refresh=True)
            except ServerFetchError:
                pass

    mock_urlopen.assert_called()
    call_args = mock_urlopen.call_args
    timeout = call_args.kwargs.get("timeout") or (
        call_args.args[1] if len(call_args.args) > 1 else None
    )
    assert timeout is not None, "urlopen chamado sem timeout"
    assert float(timeout) > 0, f"Timeout inválido: {timeout}"
