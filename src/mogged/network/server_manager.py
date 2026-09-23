from concurrent.futures import ThreadPoolExecutor
import logging
import socket
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from mogged.network.server_fetcher import ServerFetcher
from mogged.network.server_validator import is_valid_public_ip

logger = logging.getLogger("Mogged.Network.ServerManager")

class ServerManager:

    def __init__(self, fetcher: Optional[ServerFetcher] = None, max_workers: int = 8) -> None:
        self.fetcher = fetcher or ServerFetcher()
        self.max_workers = max_workers
        self.servers: List[Dict[str, Any]] = []
        self.failure_counts: Dict[str, int] = {}
        self.blacklist: Set[str] = set()
        self.latency_cache: Dict[str, Tuple[float, float]] = {}

    def load_servers(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        self.servers = self.fetcher.fetch(force_refresh=force_refresh)
        return self.servers

    def probe_server(self, server: Dict[str, Any], timeout: float = 1.0) -> Tuple[Dict[str, Any], bool, float]:
        ip = server.get("ip", "")
        port = int(server.get("port", 443))
        proto = str(server.get("protocol", "tcp")).lower()

        if not is_valid_public_ip(ip):
            return (server, False, 9999.0)

        t0 = time.time()
        if proto == "tcp":
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(timeout)
                    sock.connect((ip, port))
                rtt = (time.time() - t0) * 1000.0
                return (server, True, rtt)
            except Exception:
                return (server, False, 9999.0)
        else:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.settimeout(timeout)
                    sock.connect((ip, port))
                    sock.send(b"\x38\x00\x00\x00\x00\x00\x00\x00\x00")
                api_ping = float(server.get("ping", 300))
                return (server, api_ping < 900, api_ping)
            except Exception:
                return (server, False, 9999.0)

    def health_check(self, candidates: List[Dict[str, Any]], timeout: float = 1.0) -> List[Dict[str, Any]]:
        if not candidates:
            return []

        active_candidates = [s for s in candidates if s.get("id") not in self.blacklist]
        pool = active_candidates if active_candidates else candidates
        to_probe = pool[:10]
        remaining = pool[10:]

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            probe_results = list(executor.map(lambda s: self.probe_server(s, timeout=timeout), to_probe))

        alive: List[Dict[str, Any]] = []
        dead: List[Dict[str, Any]] = []

        now = time.time()
        for srv, is_alive, rtt in probe_results:
            srv_id = srv.get("id", "")
            if is_alive:
                self.record_success(srv_id)
                self.latency_cache[srv_id] = (rtt, now)
                srv_copy = dict(srv)
                srv_copy["live_rtt"] = rtt
                alive.append(srv_copy)
            else:
                self.record_failure(srv_id)
                dead.append(srv)

        alive.sort(key=lambda s: (s.get("live_rtt", 9999.0), -s.get("speed_mbps", 0.0)))
        return alive + remaining if alive else remaining + dead

    def get_best_server(self, country_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.servers:
            self.load_servers()

        candidates = list(self.servers)
        if country_code:
            filtered = [s for s in candidates if s.get("country_short") == country_code.upper()]
            if filtered:
                candidates = filtered

        candidates.sort(key=lambda s: (-s.get("speed_mbps", 0.0), s.get("ping", 999)))
        checked = self.health_check(candidates, timeout=0.85)
        return checked[0] if checked else (candidates[0] if candidates else None)

    def get_fallback_candidates(self, country_code: str, exclude_server_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self.servers:
            self.load_servers()

        same_country = [
            s for s in self.servers
            if s.get("country_short") == country_code.upper()
            and s.get("id") != exclude_server_id
            and s.get("id") not in self.blacklist
        ]
        same_country.sort(key=lambda s: (-s.get("speed_mbps", 0.0), s.get("ping", 999)))

        candidates = list(same_country[:2])
        if len(candidates) < 2:
            global_nodes = [
                s for s in self.servers
                if s.get("id") != exclude_server_id
                and s.get("id") not in self.blacklist
                and s not in candidates
            ]
            global_nodes.sort(key=lambda s: (-s.get("speed_mbps", 0.0), s.get("ping", 999)))
            candidates.extend(global_nodes[: 3 - len(candidates)])

        return candidates

    def record_failure(self, server_id: str) -> None:
        if not server_id:
            return
        count = self.failure_counts.get(server_id, 0) + 1
        self.failure_counts[server_id] = count
        if count >= 3:
            self.blacklist.add(server_id)
            logger.warning(f"Servidor {server_id} adicionado a blacklist temporaria apos {count} falhas.")

    def record_success(self, server_id: str) -> None:
        if not server_id:
            return
        self.failure_counts[server_id] = 0
        if server_id in self.blacklist:
            self.blacklist.remove(server_id)

    def get_countries(self) -> List[Dict[str, Any]]:
        if not self.servers:
            self.load_servers()

        grouped: Dict[str, Dict[str, Any]] = {}
        for s in self.servers:
            code = s.get("country_short", "")
            if not code:
                continue
            if code not in grouped:
                grouped[code] = {
                    "code": code,
                    "name": s.get("country_long", "Unknown"),
                    "flag": s.get("flag", "🌐"),
                    "server_count": 0,
                    "best_ping": 9999,
                    "max_speed": 0.0,
                }
            grouped[code]["server_count"] += 1
            ping = s.get("ping", 9999)
            if 0 < ping < grouped[code]["best_ping"]:
                grouped[code]["best_ping"] = ping
            speed = s.get("speed_mbps", 0.0)
            if speed > grouped[code]["max_speed"]:
                grouped[code]["max_speed"] = speed

        res = list(grouped.values())
        res.sort(key=lambda x: (-x["server_count"], -x["max_speed"], x["name"].lower()))
        return res
