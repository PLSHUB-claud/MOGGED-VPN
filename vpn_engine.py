import base64
import ctypes
import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Callable, Optional, Dict, Any
from resource_helper import get_asset_path
from discord_routes import get_discord_openvpn_directives
logger = logging.getLogger('MoggedVPN.Engine')
STATUS_DISCONNECTED = 'DISCONNECTED'
STATUS_CONNECTING = 'CONNECTING'
STATUS_CONNECTED = 'CONNECTED'
STATUS_ERROR = 'ERROR'
OPENVPN_SEARCH_PATHS = ['C:\\Program Files\\OpenVPN\\bin\\openvpn.exe', 'C:\\Program Files (x86)\\OpenVPN\\bin\\openvpn.exe', 'C:\\Program Files\\Mullvad VPN\\resources\\openvpn.exe']

def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def elevate_admin():
    if is_admin():
        return False
    try:
        if getattr(sys, 'frozen', False):
            params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
            ret = ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, params, None, 1)
        else:
            script = os.path.abspath(sys.argv[0])
            params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
            ret = ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, f'"{script}" {params}', None, 1)
        if ret > 32:
            sys.exit(0)
    except Exception as e:
        logger.error(f'Erro ao solicitar privilégios de Administrador: {e}')
    return False

def find_openvpn_binary() -> Optional[str]:
    bundled = get_asset_path(os.path.join('bin', 'openvpn.exe'))
    if os.path.isfile(bundled):
        return os.path.abspath(bundled)
    if getattr(sys, 'frozen', False):
        local_exe = os.path.join(os.path.dirname(sys.executable), 'openvpn.exe')
        if os.path.isfile(local_exe):
            return os.path.abspath(local_exe)
        local_bin_exe = os.path.join(os.path.dirname(sys.executable), 'bin', 'openvpn.exe')
        if os.path.isfile(local_bin_exe):
            return os.path.abspath(local_bin_exe)
    for path in OPENVPN_SEARCH_PATHS:
        if os.path.isfile(path):
            return path
    which_path = shutil.which('openvpn')
    if which_path and os.path.isfile(which_path):
        return which_path
    return None

class VpnEngine:

    def __init__(self, on_status_change: Optional[Callable[[str, str], None]]=None):
        self.status = STATUS_DISCONNECTED
        self.on_status_change = on_status_change
        self.process: Optional[subprocess.Popen] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self.active_config_path: Optional[str] = None
        self.connected_since: Optional[float] = None
        self.active_server: Optional[Dict[str, Any]] = None
        self.active_mode: str = 'full'
        self._stop_requested = False
        self._connect_lock = threading.Lock()
        self.openvpn_bin = find_openvpn_binary()
        if not self.openvpn_bin:
            logger.warning('openvpn.exe não foi encontrado nos caminhos padrão.')

    def _update_status(self, new_status: str, message: str=''):
        self.status = new_status
        if new_status == STATUS_CONNECTED:
            self.connected_since = time.time()
        elif new_status in (STATUS_DISCONNECTED, STATUS_ERROR):
            self.connected_since = None
        logger.info(f'Status alterado para [{new_status}]: {message}')
        if self.on_status_change:
            try:
                self.on_status_change(new_status, message)
            except Exception as e:
                logger.error(f'Erro no callback de status: {e}')

    def prepare_config(self, ovpn_base64: str, mode: str='full') -> str:
        raw_text = base64.b64decode(ovpn_base64).decode('utf-8', errors='ignore')
        lines = []
        for line in raw_text.splitlines():
            clean = line.strip()
            if mode == 'discord' and (clean.startswith('redirect-gateway') or clean.startswith('route-gateway')):
                continue
            lines.append(line)
        custom_directives = ['', '# --- MOGGED VPN CONNECTION OPTIONS ---', 'nobind', 'persist-key', 'persist-tun', 'verb 3', 'resolv-retry 2', 'connect-timeout 10', 'hand-window 12', 'server-poll-timeout 8', 'mssfix 1360', 'sndbuf 524288', 'rcvbuf 524288', 'windows-driver wintun']
        if mode == 'full':
            custom_directives.extend(['redirect-gateway def1', 'dhcp-option DNS 1.1.1.1', 'dhcp-option DNS 8.8.8.8'])
        elif mode == 'discord':
            custom_directives.extend(get_discord_openvpn_directives())
        final_config = '\n'.join(lines) + '\n' + '\n'.join(custom_directives) + '\n'
        fd, config_path = tempfile.mkstemp(suffix='.ovpn', prefix='mogged_vpn_')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(final_config)
        return config_path

    def connect(self, server: Dict[str, Any], mode: str='full', fallback_servers: list=None):
        with self._connect_lock:
            if self.status in (STATUS_CONNECTING, STATUS_CONNECTED):
                self.disconnect()

            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=5.0)

            if self.monitor_thread is not None:
                time.sleep(1.5)

            if not self.openvpn_bin:
                self._update_status(STATUS_ERROR, 'OpenVPN executable not found.')
                return

            servers_to_try = [server]
            if fallback_servers:
                for fb in fallback_servers:
                    if fb['id'] != server['id'] and len(servers_to_try) < 3:
                        servers_to_try.append(fb)

            self._stop_requested = False
            self.active_mode = mode
            total = len(servers_to_try)

        def run_thread():
            for attempt, srv in enumerate(servers_to_try, 1):
                if self._stop_requested:
                    break
                self.active_server = srv
                curr_country = srv.get('country_long', 'Server')
                self._update_status(STATUS_CONNECTING, 'Connecting...')
                logger.info(f"Attempt {attempt}/{total}: {srv.get('ip', '?')} ({curr_country})")
                session_ran = self._run_server_connection(srv, mode)
                if session_ran:
                    return
                if self._stop_requested:
                    break
                if attempt < total:
                    next_srv = servers_to_try[attempt]
                    next_country = next_srv.get('country_long', 'Server')
                    logger.info(f"Server {srv.get('ip')} did not respond, auto-switching to candidate {attempt + 1}/{total} ({next_country})...")
                    for _ in range(20):
                        if self._stop_requested:
                            break
                        time.sleep(0.1)
            if not self._stop_requested:
                initial_country = server.get('country_long', 'Server')
                logger.error(f'Could not connect to {initial_country}. All candidates failed.')
                self._update_status(STATUS_ERROR, 'Connection Error')

        self.monitor_thread = threading.Thread(target=run_thread, daemon=True)
        self.monitor_thread.start()

    def _run_server_connection(self, server: Dict[str, Any], mode: str) -> bool:
        try:
            self._kill_process()
            self.active_config_path = self.prepare_config(server['ovpn_config_b64'], mode=mode)
            cmd = [self.openvpn_bin, '--config', self.active_config_path]
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            bin_dir = os.path.dirname(os.path.abspath(self.openvpn_bin))
            env = os.environ.copy()
            env['PATH'] = bin_dir + os.pathsep + env.get('PATH', '')
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, text=True, bufsize=1, cwd=bin_dir, env=env, creationflags=creationflags)
            q = queue.Queue()

            def reader():
                try:
                    for line in iter(self.process.stdout.readline, ''):
                        q.put(line)
                except Exception:
                    pass
                q.put(None)
            reader_thread = threading.Thread(target=reader, daemon=True)
            reader_thread.start()
            connection_successful = False
            start_time = time.time()
            CONNECT_TIMEOUT = 25.0
            while not self._stop_requested:
                try:
                    line = q.get(timeout=0.2)
                except queue.Empty:
                    line = None
                if line is not None:
                    line_str = line.strip()
                    if line_str:
                        logger.debug(f'[OpenVPN] {line_str}')
                        if 'Initialization Sequence Completed' in line_str:
                            connection_successful = True
                            mode_label = 'Entire PC' if mode == 'full' else 'Discord'
                            self._update_status(STATUS_CONNECTED, f'Connected successfully ({mode_label})')
                            break
                        if any((err in line_str for err in ['AUTH_FAILED', 'TLS Error', 'Cannot resolve host', 'Connection refused', 'Connection timed out', 'SIGTERM', 'process exiting', 'Exiting due to fatal error'])):
                            logger.warning(f'Server error during handshake: {line_str[:120]}')
                            break
                if time.time() - start_time > CONNECT_TIMEOUT:
                    logger.warning(f"Server {server.get('ip')} connection timeout after {CONNECT_TIMEOUT}s")
                    break
                if self.process.poll() is not None:
                    break
            if not connection_successful:
                self._kill_process()
                self._cleanup_temp_file()
                return False
            while not self._stop_requested and self.process.poll() is None:
                try:
                    line = q.get(timeout=0.5)
                    if line is None:
                        break
                except queue.Empty:
                    continue
            if not self._stop_requested:
                self._update_status(STATUS_DISCONNECTED, 'Disconnected.')
            self._kill_process()
            self._cleanup_temp_file()
            return True
        except Exception as e:
            logger.error(f'OpenVPN process exception: {e}')
            self._kill_process()
            self._cleanup_temp_file()
            return False

    def _kill_process(self):
        proc = self.process
        self.process = None
        if proc is None:
            return
        try:
            subprocess.run(
                ['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                timeout=5
            )
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        try:
            proc.wait(timeout=4)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def disconnect(self):
        if self.status == STATUS_DISCONNECTED and (not self.process):
            return
        self._stop_requested = True
        self._kill_process()
        try:
            subprocess.run(['ipconfig', '/flushdns'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except Exception:
            pass
        self._cleanup_temp_file()
        self._update_status(STATUS_DISCONNECTED, 'Disconnected.')

    def _cleanup_temp_file(self):
        path = self.active_config_path
        self.active_config_path = None
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
