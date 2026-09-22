import ipaddress
import logging
import socket
import time
from typing import List, Set

logger = logging.getLogger("Mogged.Network.SplitTunnel")

DISCORD_CIDRS = [
    "104.16.0.0/12",
    "162.158.0.0/15",
    "172.64.0.0/13",
    "35.186.224.0/19",
    "66.22.192.0/18",
    "195.62.89.0/24",
    "185.166.234.0/24",
    "208.8.38.0/24",
    "91.199.230.0/24",
    "64.71.8.96/29",
    "12.129.184.160/29",
    "143.244.32.0/19",
    "143.244.64.0/19",
    "163.114.128.0/20",
    "199.201.64.0/22",
    "138.128.136.0/21",
    "5.200.14.128/25",
]

DISCORD_DOMAINS = [
    "discord.com",
    "gateway.discord.gg",
    "cdn.discordapp.com",
    "media.discordapp.net",
    "latency.discord.media",
    "status.discord.com",
    "discord.gg",
    "discord.app",
    "discord.media",
    "discordapp.com",
    "discordapp.net",
    "dl.discordapp.net",
    "updates.discord.com",
    "router.discordapp.net",
    "voice.discord.media",
    "stream.discord.media",
    "rtc.discord.media",
]

FALLBACK_DISCORD_IPS: Set[str] = {
    "162.159.135.232",
    "162.159.136.232",
    "162.159.137.232",
    "162.159.138.232",
    "162.159.128.233",
}

_cached_ips: Set[str] = set()
_last_resolve_time: float = 0.0

def resolve_discord_ips(force: bool = False) -> Set[str]:
    global _cached_ips, _last_resolve_time
    now = time.time()
    if not force and _cached_ips and (now - _last_resolve_time < 3600):
        return _cached_ips

    resolved: Set[str] = set()
    for domain in DISCORD_DOMAINS:
        try:
            _, _, ips = socket.gethostbyname_ex(domain)
            for ip in ips:
                resolved.add(ip)
        except Exception as e:
            logger.debug(f"Não foi possível resolver {domain}: {e}")

    if resolved:
        _cached_ips = resolved
        _last_resolve_time = now
        return _cached_ips

    if _cached_ips:
        logger.warning("Resolução DNS falhou. Usando cache de IPs anterior do Discord.")
        return _cached_ips

    logger.warning("Resolução DNS indisponível e sem cache prévio. Utilizando sementes estáticas de fallback.")
    return set(FALLBACK_DISCORD_IPS)

def get_discord_split_directives() -> List[str]:
    directives = [
        "# --- DISCORD SPLIT-TUNNELING CONFIG ---",
        "route-nopull",
    ]

    networks = []
    for cidr in DISCORD_CIDRS:
        try:
            networks.append(ipaddress.IPv4Network(cidr, strict=False))
        except ValueError:
            continue

    for ip in resolve_discord_ips():
        try:
            ip_obj = ipaddress.IPv4Address(ip)
            if not ip_obj.is_private and not ip_obj.is_loopback:
                networks.append(ipaddress.IPv4Network(f"{ip}/32"))
        except ValueError:
            continue

    collapsed = list(ipaddress.collapse_addresses(networks))
    for net in collapsed:
        directives.append(f"route {net.network_address} {net.netmask}")

    directives.append("# --- FIM DISCORD CONFIG ---")
    return directives
