import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable, Dict, Optional

from mogged.constants import STATUS_CONNECTED, STATUS_CONNECTING, STATUS_DISCONNECTED
from mogged.network.dns_manager import DNSManager
from mogged.network.vpn_backend import VPNBackend
from mogged.security.binary_verify import BinaryVerifier

logger = logging.getLogger("Mogged.Network.WireGuardBackend")

class WireGuardBackend(VPNBackend):

    def __init__(self, wireguard_bin_path: Optional[Path] = None) -> None:
        self.wireguard_bin = wireguard_bin_path or self._discover_wireguard()
        self.process: Optional[subprocess.Popen] = None
        self.active_config_path: Optional[str] = None
        self._connected = False
        self._stop_requested = False
        self._verifier = BinaryVerifier()

    def _discover_wireguard(self) -> Optional[Path]:
        candidates = [
            Path("bin") / "wireguard.exe",
            Path(__file__).resolve().parent.parent.parent.parent / "bin" / "wireguard.exe",
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "WireGuard" / "wireguard.exe",
        ]
        for cand in candidates:
            if cand.is_file():
                return cand.resolve()
        return None

    def is_connected(self) -> bool:
        return self._connected and (self.process is None or self.process.poll() is None)

    def prepare_config(self, server: Dict[str, Any], mode: str = "full") -> str:
        private_key = server.get("client_private_key", "CLIENT_PRIVKEY_PLACEHOLDER")
        address = server.get("client_ip", "10.66.66.2/32")
        dns_servers = "1.1.1.1, 9.9.9.9"
        peer_pubkey = server.get("peer_public_key", "SERVER_PUBKEY_PLACEHOLDER")
        endpoint = f"{server.get('ip', '127.0.0.1')}:{server.get('port', 51820)}"
        allowed_ips = "0.0.0.0/0, ::/0" if mode == "full" else "104.16.0.0/12, 162.158.0.0/15"

        lines = [
            "[Interface]",
            f"PrivateKey = {private_key}",
            f"Address = {address}",
            f"DNS = {dns_servers}",
            "",
            "[Peer]",
            f"PublicKey = {peer_pubkey}",
            f"Endpoint = {endpoint}",
            f"AllowedIPs = {allowed_ips}",
            "PersistentKeepalive = 25",
        ]

        fd, config_path = tempfile.mkstemp(suffix=".conf", prefix="mogged_wg_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return config_path

    def connect(
        self,
        server: Dict[str, Any],
        mode: str = "full",
        on_status: Optional[Callable[[str, str], None]] = None,
    ) -> bool:
        if not self.wireguard_bin or not self.wireguard_bin.is_file():
            logger.warning("Executável wireguard.exe não encontrado. Operação não suportada.")
            return False

        self._stop_requested = False
        try:
            self.active_config_path = self.prepare_config(server, mode=mode)
            cmd = [str(self.wireguard_bin), "/installtunnelservice", self.active_config_path]
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=creationflags,
                timeout=10,
            )
            if res.returncode == 0:
                self._connected = True
                if on_status:
                    on_status(STATUS_CONNECTED, f"Conectado via WireGuard ({mode})")
                return True
            else:
                logger.error(f"Erro ao inicializar serviço de túnel WireGuard: {res.stderr}")
                return False
        except Exception as e:
            logger.error(f"Exceção ao conectar WireGuard: {e}")
            self.disconnect()
            return False

    def disconnect(self) -> None:
        self._stop_requested = True
        if self.wireguard_bin and self.active_config_path:
            tunnel_name = Path(self.active_config_path).stem
            cmd = [str(self.wireguard_bin), "/uninstalltunnelservice", tunnel_name]
            try:
                subprocess.run(
                    cmd,
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    timeout=5,
                )
            except Exception:
                pass

        self._connected = False
        DNSManager.flush_dns()
        if self.active_config_path and os.path.exists(self.active_config_path):
            try:
                os.remove(self.active_config_path)
            except Exception:
                pass
        self.active_config_path = None
