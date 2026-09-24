from concurrent.futures import ThreadPoolExecutor
import ipaddress
import logging
import socket
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Mogged.Network.ServerValidator")

def is_valid_public_ip(ip_str: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_str.strip())
    except ValueError:
        return False

    if ip_obj.version != 4:
        return False

    if hasattr(ip_obj, "is_global") and not ip_obj.is_global:
        return False

    if (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    ):
        return False

    special_networks = (
        ipaddress.IPv4Network("0.0.0.0/8"),
        ipaddress.IPv4Network("100.64.0.0/10"),
        ipaddress.IPv4Network("192.0.0.0/24"),
        ipaddress.IPv4Network("192.0.2.0/24"),
        ipaddress.IPv4Network("192.88.99.0/24"),
        ipaddress.IPv4Network("198.18.0.0/15"),
        ipaddress.IPv4Network("198.51.100.0/24"),
        ipaddress.IPv4Network("203.0.113.0/24"),
        ipaddress.IPv4Network("240.0.0.0/4"),
        ipaddress.IPv4Network("255.255.255.255/32"),
    )
    for net in special_networks:
        if ip_obj in net:
            return False

    return True

def probe_server_connectivity(
    server: Dict[str, Any], timeout: float = 1.0
) -> Tuple[Dict[str, Any], bool, float]:
    ip = server.get("ip", "")
    port = server.get("port", 443)
    proto = server.get("protocol", "tcp").lower()

    if not is_valid_public_ip(ip):
        return (server, False, 9999.0)

    if proto == "tcp":
        t0 = time.time()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect((ip, int(port)))
            rtt = (time.time() - t0) * 1000.0
            return (server, True, rtt)
        except Exception:
            return (server, False, 9999.0)
    else:
        api_ping = float(server.get("ping", 500))
        return (server, api_ping < 1000, api_ping)

class ServerValidator:

    def __init__(self, max_workers: int = 8) -> None:
        self.max_workers = max_workers

    def filter_valid_servers(self, servers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        valid = []
        for s in servers:
            ip = s.get("ip", "")
            if is_valid_public_ip(ip):
                valid.append(s)
            else:
                logger.warning(f"Servidor descartado por IP inseguro/inválido: {ip}")
        return valid

    def probe_candidates(
        self, candidates: List[Dict[str, Any]], limit: int = 10
    ) -> List[Dict[str, Any]]:
        to_probe = candidates[:limit]
        remaining = candidates[limit:]

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = list(executor.map(probe_server_connectivity, to_probe))

        alive = []
        dead = []
        for srv, is_alive, rtt in results:
            if is_alive:
                srv_copy = dict(srv)
                srv_copy["live_rtt"] = rtt
                alive.append(srv_copy)
            else:
                dead.append(srv)

        alive.sort(key=lambda s: (-s.get("speed_mbps", 0), s.get("live_rtt", 9999)))
        return alive + remaining if alive else remaining + dead
