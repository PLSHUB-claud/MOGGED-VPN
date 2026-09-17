import base64
import csv
import json
import logging
import os
import time
import urllib.request
from typing import Optional, List, Dict, Any
from resource_helper import get_asset_path, get_writable_data_path
logger = logging.getLogger('MoggedVPN.Service')

def get_servers_cache_file() -> str:
    dest = get_writable_data_path('servers_cache.json')
    if not os.path.isfile(dest):
        bundled = get_asset_path('servers_cache.json')
        if os.path.isfile(bundled) and bundled != dest:
            try:
                import shutil
                shutil.copy2(bundled, dest)
            except Exception:
                return bundled
    return dest
CACHE_FILE = get_servers_cache_file()
API_URLS = ['http://www.vpngate.net/api/iphone/', 'https://www.vpngate.net/api/iphone/']
import re

def get_country_flag(code: str) -> str:
    if not code or len(code) != 2:
        return '🌐'
    try:
        return ''.join((chr(127397 + ord(c.upper())) for c in code))
    except Exception:
        return '🌐'

def clean_country_name(name: str) -> str:
    if not name:
        return 'Unknown'
    clean = re.sub('\\(LOCAL Name:.*?\\)', '', name, flags=re.IGNORECASE).strip()
    clean = re.sub('\\(.*?\\)', '', clean).strip()
    replacements = {'Korea Republic of': 'South Korea', 'Russian Federation': 'Russia', 'Viet Nam': 'Vietnam', 'Taiwan Province of China': 'Taiwan', 'Iran, Islamic Republic of': 'Iran', 'Moldova, Republic of': 'Moldova', 'United States': 'United States', 'United Kingdom': 'United Kingdom'}
    return replacements.get(clean, clean)

class VpnServerService:

    def __init__(self):
        self.servers: List[Dict[str, Any]] = []
        self.last_fetch_time: float = 0
        self.load_cache()

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.servers = data.get('servers', [])
                    self.last_fetch_time = data.get('timestamp', 0)
                    logger.info(f'Carregados {len(self.servers)} servidores do cache local.')
            except Exception as e:
                logger.warning(f'Erro ao carregar cache local: {e}')

    def save_cache(self):
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump({'timestamp': self.last_fetch_time, 'servers': self.servers}, f, ensure_ascii=False, separators=(',', ':'))
        except Exception as e:
            logger.warning(f'Erro ao salvar cache local: {e}')

    def fetch_servers(self, force_refresh: bool=False) -> List[Dict[str, Any]]:
        now = time.time()
        if not force_refresh and self.servers and (now - self.last_fetch_time < 600):
            return self.servers
        raw_csv = None
        for url in API_URLS:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) MoggedVPN/1.0'})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    raw_csv = resp.read().decode('utf-8', errors='ignore')
                    if raw_csv and 'HostName' in raw_csv:
                        break
            except Exception as e:
                logger.warning(f'Falha ao consultar {url}: {e}')
        if not raw_csv:
            logger.warning('Não foi possível atualizar servidores online. Usando cache.')
            return self.servers
        parsed_servers = []
        try:
            lines = [l.lstrip('#').strip() for l in raw_csv.splitlines() if l.strip() and (not l.startswith('*'))]
            reader = csv.DictReader(lines)
            idx = 1
            for row in reader:
                ip = row.get('IP', '').strip()
                country_long = clean_country_name(row.get('CountryLong', '').strip())
                country_short = row.get('CountryShort', '').strip().upper()
                ovpn_b64 = row.get('OpenVPN_ConfigData_Base64', '').strip()
                if not ip or not ovpn_b64:
                    continue
                try:
                    ping = int(row.get('Ping', 999))
                except ValueError:
                    ping = 999
                try:
                    speed_bps = int(row.get('Speed', 0))
                    speed_mbps = round(speed_bps / (1024 * 1024), 1)
                except ValueError:
                    speed_mbps = 0.0
                try:
                    sessions = int(row.get('NumVpnSessions', 0))
                except ValueError:
                    sessions = 0
                display_name = f'Node-{country_short}-{idx:02d}'
                idx += 1
                parsed_servers.append({'id': f'{country_short}-{ip}', 'name': display_name, 'ip': ip, 'country_long': country_long or 'Unknown', 'country_short': country_short, 'flag': get_country_flag(country_short), 'ping': ping, 'speed_mbps': speed_mbps, 'sessions': sessions, 'ovpn_config_b64': ovpn_b64})
            if parsed_servers:
                self.servers = parsed_servers
                self.last_fetch_time = now
                self.save_cache()
                logger.info(f'API atualizada com sucesso! {len(self.servers)} servidores encontrados.')
        except Exception as e:
            logger.error(f'Erro ao processar CSV de servidores: {e}')
        return self.servers

    def get_countries(self) -> List[Dict[str, Any]]:
        if not self.servers:
            self.fetch_servers()
        grouped: Dict[str, Dict[str, Any]] = {}
        for s in self.servers:
            code = s['country_short']
            name = s['country_long']
            flag = s['flag']
            if code not in grouped:
                grouped[code] = {'code': code, 'name': name, 'flag': flag, 'server_count': 0, 'best_ping': 9999, 'max_speed': 0.0}
            grouped[code]['server_count'] += 1
            if s['ping'] > 0 and s['ping'] < grouped[code]['best_ping']:
                grouped[code]['best_ping'] = s['ping']
            if s['speed_mbps'] > grouped[code]['max_speed']:
                grouped[code]['max_speed'] = s['speed_mbps']
        result = list(grouped.values())
        result.sort(key=lambda x: (-x['server_count'], -x['max_speed'], x['name'].lower()))
        return result

    def get_best_server(self, country_code: Optional[str]=None) -> Optional[Dict[str, Any]]:
        ranked = self.get_servers_ranked(country_code, probe_alive=True)
        return ranked[0] if ranked else None

    def get_servers_ranked(self, country_code: Optional[str]=None, probe_alive: bool=False) -> List[Dict[str, Any]]:
        if not self.servers:
            self.fetch_servers()
        candidates = list(self.servers)
        if country_code:
            candidates = [s for s in candidates if s['country_short'].upper() == country_code.upper()]
        if not candidates:
            return []

        def score(s):
            ping = s['ping'] if s['ping'] > 0 else 9999
            speed = s['speed_mbps']
            return (ping, -speed)
        candidates.sort(key=score)
        if not probe_alive or len(candidates) == 0:
            return candidates
        from concurrent.futures import ThreadPoolExecutor
        import socket
        to_probe = candidates[:10]
        remaining = candidates[10:]

        def probe_target(srv):
            ip = srv.get('ip', '')
            port = 443
            proto = 'tcp'
            try:
                cfg = base64.b64decode(srv.get('ovpn_config_b64', '')).decode('utf-8', errors='ignore')
                for line in cfg.splitlines():
                    ls = line.strip()
                    if ls.startswith('proto '):
                        proto = ls.split()[1].lower()
                    elif ls.startswith('remote '):
                        parts = ls.split()
                        if len(parts) >= 3:
                            port = int(parts[2])
            except Exception:
                pass
            t0 = time.time()
            if proto == 'tcp':
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.85)
                    sock.connect((ip, port))
                    sock.close()
                    rtt = (time.time() - t0) * 1000
                    return (srv, True, rtt)
                except Exception:
                    return (srv, False, 9999.0)
            else:
                return (srv, True, 500.0)
        try:
            with ThreadPoolExecutor(max_workers=8) as executor:
                probe_results = list(executor.map(probe_target, to_probe))
            alive_servers = []
            dead_servers = []
            for srv, is_alive, rtt in probe_results:
                if is_alive:
                    srv_copy = dict(srv)
                    srv_copy['live_rtt'] = rtt
                    alive_servers.append(srv_copy)
                else:
                    dead_servers.append(srv)
            alive_servers.sort(key=lambda s: (-s.get('speed_mbps', 0), s.get('live_rtt', 9999)))
            if alive_servers:
                return alive_servers + remaining
            return remaining if remaining else dead_servers
        except Exception as e:
            logger.warning(f'Erro no probe concorrente de servidores: {e}')
            return candidates
