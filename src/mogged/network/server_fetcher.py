import base64
import csv
import json
import logging
import os
from pathlib import Path
import re
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
import urllib.parse

from mogged.constants import (
    OPENVPN_PROVIDERS,
    SERVER_FETCH_TIMEOUT_SEC,
    VPN_GATE_API_URLS,
)
from mogged.exceptions import ServerFetchError
from mogged.network.server_validator import is_valid_public_ip

logger = logging.getLogger("Mogged.Network.ServerFetcher")


def get_country_flag(code: str) -> str:
    if not code or len(code) != 2:
        return "🌐"
    try:
        return "".join(chr(127397 + ord(c.upper())) for c in code)
    except Exception:
        return "🌐"


def clean_country_name(name: str) -> str:
    if not name:
        return "Unknown"
    clean = re.sub(r"\(LOCAL Name:.*?\)", "", name, flags=re.IGNORECASE).strip()
    clean = re.sub(r"\(.*?\)", "", clean).strip()
    replacements = {
        "Korea Republic of": "South Korea",
        "Russian Federation": "Russia",
        "Viet Nam": "Vietnam",
        "Taiwan Province of China": "Taiwan",
        "Iran, Islamic Republic of": "Iran",
        "Moldova, Republic of": "Moldova",
    }
    return replacements.get(clean, clean)


def _parse_ovpn_meta(ovpn_b64: str) -> Tuple[int, str]:
    port = 443
    protocol = "tcp"
    try:
        cfg = base64.b64decode(ovpn_b64).decode("utf-8", errors="ignore")
        for line in cfg.splitlines():
            ls = line.strip()
            if ls.startswith("proto "):
                protocol = ls.split()[1].lower()
            elif ls.startswith("remote "):
                parts = ls.split()
                if len(parts) >= 3:
                    port = int(parts[2])
    except Exception:
        pass
    return port, protocol


def _http_get(url: str, timeout: float = SERVER_FETCH_TIMEOUT_SEC, max_bytes: int = 10 * 1024 * 1024) -> Optional[bytes]:
    if not url.startswith("https://"):
        logger.warning(f"URL rejeitada (não HTTPS): {url}")
        return None
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "MoggedVPN-SecureClient/1.1.0",
                "Accept": "*/*",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            return resp.read(max_bytes)
    except Exception as e:
        logger.warning(f"HTTP GET falhou para {url}: {e}")
        return None


def _build_server_entry(
    ip: str,
    country_short: str,
    country_long: str,
    ovpn_b64: str,
    ping: int = 999,
    speed_mbps: float = 0.0,
    sessions: int = 0,
    idx: int = 1,
    source: str = "vpngate",
) -> Dict[str, Any]:
    port, protocol = _parse_ovpn_meta(ovpn_b64)
    return {
        "id": f"{country_short}-{ip}-{source}",
        "name": f"Node-{country_short}-{idx:02d}",
        "ip": ip,
        "port": port,
        "protocol": protocol,
        "country_long": country_long or "Unknown",
        "country_short": country_short,
        "flag": get_country_flag(country_short),
        "ping": ping,
        "speed_mbps": speed_mbps,
        "sessions": sessions,
        "ovpn_config_b64": ovpn_b64,
        "source": source,
    }


class _VpnGateParser:
    def parse(self, raw: bytes, source_name: str = "vpngate") -> List[Dict[str, Any]]:
        text = raw.decode("utf-8", errors="ignore")
        lines = [
            l.lstrip("#").strip()
            for l in text.splitlines()
            if l.strip() and not l.startswith("*")
        ]
        reader = csv.DictReader(lines)
        servers: List[Dict[str, Any]] = []
        idx = 1
        for row in reader:
            ip = row.get("IP", "").strip()
            country_long = clean_country_name(row.get("CountryLong", "").strip())
            country_short = row.get("CountryShort", "").strip().upper()
            ovpn_b64 = row.get("OpenVPN_ConfigData_Base64", "").strip()

            if not is_valid_public_ip(ip) or not ovpn_b64:
                continue

            try:
                ping = int(row.get("Ping", 999))
            except (ValueError, TypeError):
                ping = 999

            try:
                speed_bps = int(row.get("Speed", 0))
                speed_mbps = round(speed_bps / (1024 * 1024), 1)
            except (ValueError, TypeError):
                speed_mbps = 0.0

            try:
                sessions = int(row.get("NumVpnSessions", 0))
            except (ValueError, TypeError):
                sessions = 0

            servers.append(
                _build_server_entry(
                    ip=ip,
                    country_short=country_short,
                    country_long=country_long,
                    ovpn_b64=ovpn_b64,
                    ping=ping,
                    speed_mbps=speed_mbps,
                    sessions=sessions,
                    idx=idx,
                    source=source_name,
                )
            )
            idx += 1
        return servers


class _AutoOvpnJsonParser:
    def parse(self, raw: bytes, source_name: str = "auto_ovpn") -> List[Dict[str, Any]]:
        try:
            payload = json.loads(raw.decode("utf-8", errors="ignore"))
        except Exception as e:
            logger.warning(f"auto_ovpn: falha ao parsear JSON: {e}")
            return []

        if isinstance(payload, list) and len(payload) > 0 and isinstance(payload[0], dict):
            raw_servers = payload[0].get("servers", [])
        elif isinstance(payload, dict):
            raw_servers = payload.get("servers", [])
        else:
            return []

        if not isinstance(raw_servers, list):
            return []

        servers: List[Dict[str, Any]] = []
        idx = 1
        for row in raw_servers:
            if not isinstance(row, dict):
                continue
            ip = str(row.get("ip", "")).strip()
            country_long = clean_country_name(str(row.get("countrylong", "")).strip())
            country_short = str(row.get("countryshort", "")).strip().upper()
            ovpn_b64 = str(row.get("openvpn_configdata_base64", "")).strip()

            if not is_valid_public_ip(ip) or not ovpn_b64:
                continue

            try:
                ping = int(row.get("ping", 999))
            except (ValueError, TypeError):
                ping = 999

            try:
                speed_bps = int(row.get("speed", 0))
                speed_mbps = round(speed_bps / (1024 * 1024), 1)
            except (ValueError, TypeError):
                speed_mbps = 0.0

            try:
                sessions = int(row.get("numvpnsessions", 0))
            except (ValueError, TypeError):
                sessions = 0

            servers.append(
                _build_server_entry(
                    ip=ip,
                    country_short=country_short,
                    country_long=country_long,
                    ovpn_b64=ovpn_b64,
                    ping=ping,
                    speed_mbps=speed_mbps,
                    sessions=sessions,
                    idx=idx,
                    source=source_name,
                )
            )
            idx += 1
        return servers


_AutoOvpnParser = _AutoOvpnJsonParser

_PARSERS = {
    "vpngate": _VpnGateParser(),
    "auto_ovpn": _AutoOvpnJsonParser(),
}


class ServerFetcher:

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        if cache_dir is None:
            local_appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
            self.cache_dir = Path(local_appdata) / "MoggedVPN" / "cache"
        else:
            self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "servers_cache.json"

    def _ensure_server_metadata(self, servers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for s in servers:
            if "port" not in s or "protocol" not in s:
                ovpn_b64 = s.get("ovpn_config_b64", "")
                port, protocol = _parse_ovpn_meta(ovpn_b64) if ovpn_b64 else (443, "tcp")
                s["port"] = port
                s["protocol"] = protocol
        return servers

    def load_cache(self) -> Tuple[List[Dict[str, Any]], float]:
        if not self.cache_file.is_file():
            candidates = [
                Path("servers_cache.json"),
                Path(__file__).resolve().parent.parent.parent.parent / "servers_cache.json",
                Path(sys.executable).parent / "servers_cache.json",
            ]
            if hasattr(sys, "_MEIPASS"):
                candidates.insert(0, Path(sys._MEIPASS) / "servers_cache.json")

            for bundled in candidates:
                if bundled.is_file():
                    try:
                        with open(bundled, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            srvs = self._ensure_server_metadata(data.get("servers", []))
                            return srvs, float(data.get("timestamp", 0))
                    except Exception as e:
                        logger.warning(f"Erro ao carregar cache bundled: {e}")
            return [], 0.0

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                srvs = self._ensure_server_metadata(data.get("servers", []))
                return srvs, float(data.get("timestamp", 0))
        except Exception as e:
            logger.warning(f"Falha ao ler cache de servidores: {e}")
            return [], 0.0

    def save_cache(self, servers: List[Dict[str, Any]]) -> None:
        try:
            payload = {"timestamp": time.time(), "servers": servers}
            temp_file = self.cache_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            temp_file.replace(self.cache_file)
        except Exception as e:
            logger.warning(f"Falha ao salvar cache de servidores: {e}")

    def _fetch_provider(self, provider: Dict[str, Any]) -> List[Dict[str, Any]]:
        name = provider["name"]
        url = provider["url"]
        parser_key = provider["parser"]
        parser = _PARSERS.get(parser_key)

        if not parser:
            logger.warning(f"Parser '{parser_key}' não encontrado para provider '{name}'")
            return []

        logger.info(f"Buscando servidores via '{name}': {url}")
        raw = _http_get(url, timeout=SERVER_FETCH_TIMEOUT_SEC)
        if not raw:
            return []

        try:
            servers = parser.parse(raw, source_name=name)
            logger.info(f"Provider '{name}': {len(servers)} servidores obtidos")
            return servers
        except Exception as e:
            logger.warning(f"Provider '{name}' falhou ao parsear: {e}")
            return []

    def fetch(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        cached_servers, last_time = self.load_cache()
        now = time.time()

        if not force_refresh and cached_servers and (now - last_time < 180):
            return cached_servers

        providers = sorted(OPENVPN_PROVIDERS, key=lambda p: p.get("priority", 99))

        all_servers: List[Dict[str, Any]] = []
        seen_ips = set()

        results: Dict[str, List[Dict[str, Any]]] = {}
        threads = []

        def _worker(prov):
            results[prov["name"]] = self._fetch_provider(prov)

        for provider in providers:
            t = threading.Thread(target=_worker, args=(provider,), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=SERVER_FETCH_TIMEOUT_SEC + 10)

        for provider in providers:
            for srv in results.get(provider["name"], []):
                ip = srv.get("ip", "")
                if ip and ip not in seen_ips:
                    seen_ips.add(ip)
                    all_servers.append(srv)

        if all_servers:
            logger.info(f"Total de servidores únicos carregados: {len(all_servers)}")
            self.save_cache(all_servers)
            return all_servers

        if cached_servers:
            logger.warning("Todos os providers falharam. Usando cache.")
            return cached_servers

        raise ServerFetchError("Não foi possível obter servidores e não há cache válido.")
