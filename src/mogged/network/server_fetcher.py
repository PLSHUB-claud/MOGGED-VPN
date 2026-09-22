import base64
import csv
import json
import logging
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.request

from mogged.constants import VPN_GATE_API_URLS
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

class ServerFetcher:

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        if cache_dir is None:
            local_appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
            self.cache_dir = Path(local_appdata) / "MoggedVPN" / "cache"
        else:
            self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "servers_cache.json"

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
                            return data.get("servers", []), float(data.get("timestamp", 0))
                    except Exception as e:
                        logger.warning(f"Erro ao carregar cache bundled: {e}")
            return [], 0.0

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("servers", []), float(data.get("timestamp", 0))
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

    def fetch(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        cached_servers, last_time = self.load_cache()
        now = time.time()

        if not force_refresh and cached_servers and (now - last_time < 600):
            return cached_servers

        raw_csv: Optional[str] = None
        for url in VPN_GATE_API_URLS:
            if not url.startswith("https://"):
                continue
            try:
                logger.info(f"Buscando servidores via HTTPS: {url}")
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "MoggedVPN-SecureClient/1.1.0"},
                )
                with urllib.request.urlopen(req, timeout=10.0) as resp:  # nosec B310
                    content = resp.read(10 * 1024 * 1024)
                    raw_csv = content.decode("utf-8", errors="ignore")
                    if raw_csv and "HostName" in raw_csv:
                        break
            except Exception as e:
                logger.warning(f"Erro ao acessar {url}: {e}")

        if not raw_csv:
            if cached_servers:
                logger.warning("Falha na consulta HTTPS. Utilizando cache seguro.")
                return cached_servers
            raise ServerFetchError("Não foi possível obter servidores e não há cache válido.")

        parsed_servers: List[Dict[str, Any]] = []
        try:
            lines = [
                l.lstrip("#").strip()
                for l in raw_csv.splitlines()
                if l.strip() and not l.startswith("*")
            ]
            reader = csv.DictReader(lines)
            idx = 1
            for row in reader:
                ip = row.get("IP", "").strip()
                country_long = clean_country_name(row.get("CountryLong", "").strip())
                country_short = row.get("CountryShort", "").strip().upper()
                ovpn_b64 = row.get("OpenVPN_ConfigData_Base64", "").strip()

                if not is_valid_public_ip(ip) or not ovpn_b64:
                    continue

                port = 443
                protocol = "tcp"
                try:
                    cfg_text = base64.b64decode(ovpn_b64).decode("utf-8", errors="ignore")
                    for line in cfg_text.splitlines():
                        line_s = line.strip()
                        if line_s.startswith("proto "):
                            protocol = line_s.split()[1].lower()
                        elif line_s.startswith("remote "):
                            parts = line_s.split()
                            if len(parts) >= 3:
                                port = int(parts[2])
                except Exception:
                    pass

                try:
                    ping = int(row.get("Ping", 999))
                except ValueError:
                    ping = 999

                try:
                    speed_bps = int(row.get("Speed", 0))
                    speed_mbps = round(speed_bps / (1024 * 1024), 1)
                except ValueError:
                    speed_mbps = 0.0

                try:
                    sessions = int(row.get("NumVpnSessions", 0))
                except ValueError:
                    sessions = 0

                display_name = f"Node-{country_short}-{idx:02d}"
                idx += 1

                parsed_servers.append(
                    {
                        "id": f"{country_short}-{ip}",
                        "name": display_name,
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
                    }
                )

            if parsed_servers:
                self.save_cache(parsed_servers)
                logger.info(f"API atualizada: {len(parsed_servers)} servidores válidos.")
                return parsed_servers
            elif cached_servers:
                return cached_servers
            raise ServerFetchError("Nenhum servidor público válido encontrado no CSV.")
        except Exception as e:
            logger.error(f"Erro ao processar dados CSV: {e}")
            if cached_servers:
                return cached_servers
            raise ServerFetchError(f"Erro no processamento da lista de servidores: {e}")
