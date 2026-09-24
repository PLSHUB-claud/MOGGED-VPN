"""Testes unitários para ServerFetcher — HTTPS estrito, limite 10MB, CSV, sanitização.

Todos os testes de rede são executados com mocks; nenhuma conexão real é realizada.
"""

import base64
import json
import time
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mogged.exceptions import ServerFetchError
from mogged.network.server_fetcher import (
    ServerFetcher,
    clean_country_name,
    get_country_flag,
)


# ---------------------------------------------------------------------------
# get_country_flag
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code, expected_prefix",
    [
        ("US", "🇺🇸"),
        ("BR", "🇧🇷"),
        ("JP", "🇯🇵"),
    ],
)
def test_get_country_flag_valid_codes(code: str, expected_prefix: str) -> None:
    assert get_country_flag(code) == expected_prefix


@pytest.mark.parametrize("bad_code", ["", "A", "USA", None])
def test_get_country_flag_returns_globe_for_invalid(bad_code: Any) -> None:
    """Only None, empty string, and strings with len != 2 trigger fallback."""
    assert get_country_flag(bad_code) == "🌐"


def test_get_country_flag_digit_code_produces_regional_indicators() -> None:
    """Codes with len==2 (even digits) produce regional indicator chars, not globe.
    This documents known behavior: function only guards len != 2, not alpha-only.
    """
    result = get_country_flag("12")
    # Should return regional indicator chars (not 🌐) — two codepoints from chr(127397+ord('1')) etc.
    assert result != "🌐"
    assert len(result) == 2  # two regional indicator emoji characters


# ---------------------------------------------------------------------------
# clean_country_name
# ---------------------------------------------------------------------------


def test_clean_country_name_removes_local_annotation() -> None:
    raw = "Japan (LOCAL Name: 日本)"
    result = clean_country_name(raw)
    assert "LOCAL" not in result
    assert "日本" not in result
    assert "Japan" in result


def test_clean_country_name_applies_replacements() -> None:
    assert clean_country_name("Korea Republic of") == "South Korea"
    assert clean_country_name("Russian Federation") == "Russia"
    assert clean_country_name("Viet Nam") == "Vietnam"


def test_clean_country_name_empty_returns_unknown() -> None:
    assert clean_country_name("") == "Unknown"
    assert clean_country_name(None) == "Unknown"  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ServerFetcher.fetch — REJEIÇÃO DE HTTP PURO
# ---------------------------------------------------------------------------


def test_fetch_rejects_plain_http_urls(tmp_path: Path) -> None:
    """Nenhuma URL http:// deve ser tentada — apenas https:// é permitido."""
    http_only_providers = [{"name": "bad", "url": "http://evil.com/api", "parser": "vpngate", "priority": 1}]
    with patch("mogged.network.server_fetcher.OPENVPN_PROVIDERS", http_only_providers):
        fetcher = ServerFetcher(cache_dir=tmp_path)
        with patch.object(fetcher, "load_cache", return_value=([], 0.0)):
            with pytest.raises(ServerFetchError):
                fetcher.fetch(force_refresh=True)


# ---------------------------------------------------------------------------
# ServerFetcher.fetch — LIMITE DE 10MB (proteção DoS de memória)
# ---------------------------------------------------------------------------


def _make_mock_resp(content: bytes) -> MagicMock:
    """Cria um mock de resposta HTTP que respeita a interface de context manager."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = content
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_fetch_reads_at_most_10mb(tmp_path: Path) -> None:
    """Verifica que resp.read(10 * 1024 * 1024) é chamado com exatamente 10 485 760 bytes."""
    csv_with_header = (
        "# comment\n"
        "HostName,IP,Score,Ping,Speed,CountryLong,CountryShort,"
        "NumVpnSessions,Uptime,TotalUsers,TotalTraffic,LogType,"
        "Operator,Message,OpenVPN_ConfigData_Base64\n"
    ).encode("utf-8")

    mock_resp = _make_mock_resp(csv_with_header)

    single_provider = [{"name": "vpngate", "url": "https://test.local/api", "parser": "vpngate", "priority": 1}]
    with patch("mogged.network.server_fetcher.OPENVPN_PROVIDERS", single_provider):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            fetcher = ServerFetcher(cache_dir=tmp_path)
            with patch.object(fetcher, "load_cache", return_value=([], 0.0)):
                try:
                    fetcher.fetch(force_refresh=True)
                except ServerFetchError:
                    pass

    mock_resp.read.assert_called_once_with(10 * 1024 * 1024)


# ---------------------------------------------------------------------------
# ServerFetcher.fetch — PARSING DE CSV VÁLIDO
# ---------------------------------------------------------------------------


def _build_valid_csv(ip: str = "45.33.32.156") -> bytes:
    """Monta um CSV mínimo mas válido que ServerFetcher consegue parsear.

    O formato real da API VPN Gate usa '#HostName,...' como cabeçalho
    (com prefixo '#'), que após lstrip('#') vira 'HostName,...'.
    Linhas que começam com '*' são ignoradas.
    """
    ovpn_cfg = (
        "client\ndev tun\nproto tcp\nremote 45.33.32.156 443\n"
        "cipher AES-256-CBC\n"
    )
    ovpn_b64 = base64.b64encode(ovpn_cfg.encode()).decode()

    csv_content = (
        "#HostName,IP,Score,Ping,Speed,CountryLong,CountryShort,"
        "NumVpnSessions,Uptime,TotalUsers,TotalTraffic,LogType,"
        "Operator,Message,OpenVPN_ConfigData_Base64\n"
        f"vpn.test,{ip},1234,35,1048576,United States,US,"
        f"10,99,1000,1073741824,2,Test,,{ovpn_b64}\n"
        "*\n"
    )
    return csv_content.encode("utf-8")


def test_fetch_parses_valid_csv(tmp_path: Path) -> None:
    """Verificar que ServerFetcher parse e devolve entrada CSV válida."""
    mock_resp = _make_mock_resp(_build_valid_csv())

    with patch("mogged.network.server_fetcher.VPN_GATE_API_URLS", ["https://test.local/api"]):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            fetcher = ServerFetcher(cache_dir=tmp_path)
            # Isolate from project-root bundled servers_cache.json
            with patch.object(fetcher, "load_cache", return_value=([], 0.0)):
                servers = fetcher.fetch(force_refresh=True)

    assert len(servers) >= 1
    s = servers[0]
    assert s["ip"] == "45.33.32.156"
    assert s["country_short"] == "US"
    assert s["country_long"] == "United States"
    assert s["protocol"] == "tcp"
    assert s["port"] == 443
    assert "ovpn_config_b64" in s


def test_fetch_skips_private_ips_in_csv(tmp_path: Path) -> None:
    """Entradas com IPs privados no CSV devem ser descartadas silenciosamente."""
    mock_resp = _make_mock_resp(_build_valid_csv(ip="192.168.1.1"))

    with patch("mogged.network.server_fetcher.VPN_GATE_API_URLS", ["https://test.local/api"]):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            fetcher = ServerFetcher(cache_dir=tmp_path)
            # Isolate from bundled cache so we actually hit the "no valid servers" path
            with patch.object(fetcher, "load_cache", return_value=([], 0.0)):
                with pytest.raises(ServerFetchError):
                    # IP privado → nenhum servidor válido → sem cache → exceção
                    fetcher.fetch(force_refresh=True)


# ---------------------------------------------------------------------------
# ServerFetcher — CACHE LOCAL
# ---------------------------------------------------------------------------


def test_fetch_returns_cache_when_fresh(tmp_path: Path) -> None:
    """Se o cache for recente (< 600s), não deve chamar a rede."""
    cached_data = {
        "timestamp": time.time(),  # fresquíssimo
        "servers": [{"ip": "8.8.8.8", "name": "cached", "port": 443, "protocol": "tcp"}],
    }
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cache_file = cache_dir / "servers_cache.json"
    cache_file.write_text(json.dumps(cached_data), encoding="utf-8")

    with patch("urllib.request.urlopen") as mock_urlopen:
        fetcher = ServerFetcher(cache_dir=cache_dir)
        result = fetcher.fetch(force_refresh=False)
        mock_urlopen.assert_not_called()

    assert result == cached_data["servers"]


def test_fetch_raises_when_no_servers_and_no_cache(tmp_path: Path) -> None:
    """Sem rede e sem cache deve lançar ServerFetchError."""
    with patch(
        "mogged.network.server_fetcher.VPN_GATE_API_URLS",
        ["https://nowhere.invalid/api"],
    ):
        with patch("urllib.request.urlopen", side_effect=OSError("no route")):
            fetcher = ServerFetcher(cache_dir=tmp_path)
            # Isolate from bundled servers_cache.json at project root
            with patch.object(fetcher, "load_cache", return_value=([], 0.0)):
                with pytest.raises(ServerFetchError):
                    fetcher.fetch(force_refresh=True)


# ---------------------------------------------------------------------------
# ServerFetcher — SANITIZAÇÃO DE DADOS
# ---------------------------------------------------------------------------


def test_server_name_does_not_contain_raw_ip(tmp_path: Path) -> None:
    """O campo 'name' deve usar formato 'Node-XX-NN', nunca o IP bruto."""
    mock_resp = _make_mock_resp(_build_valid_csv())

    with patch("mogged.network.server_fetcher.VPN_GATE_API_URLS", ["https://test.local/api"]):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            fetcher = ServerFetcher(cache_dir=tmp_path)
            with patch.object(fetcher, "load_cache", return_value=([], 0.0)):
                servers = fetcher.fetch(force_refresh=True)

    name = servers[0]["name"]
    assert "45.33.32.156" not in name
    assert name.startswith("Node-")


def test_save_and_load_cache_roundtrip(tmp_path: Path) -> None:
    """ServerFetcher.save_cache seguido de load_cache deve recuperar os mesmos dados."""
    cache_dir = tmp_path / "c"
    fetcher = ServerFetcher(cache_dir=cache_dir)
    servers = [{"ip": "1.2.3.4", "name": "test-node", "port": 443, "protocol": "tcp"}]
    fetcher.save_cache(servers)
    loaded, ts = fetcher.load_cache()
    assert loaded == servers
    assert ts > 0
