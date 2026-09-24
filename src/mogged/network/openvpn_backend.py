import base64
import logging
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Callable, Dict, Optional

from mogged.constants import CONNECT_TIMEOUT_SEC, STATUS_CONNECTED, STATUS_CONNECTING, STATUS_DISCONNECTED
from mogged.network.dns_manager import DNSManager
from mogged.network.split_tunnel import get_discord_split_directives
from mogged.network.vpn_backend import VPNBackend
from mogged.security.binary_verify import BinaryVerifier

logger = logging.getLogger("Mogged.Network.OpenVPNBackend")

class OpenVPNBackend(VPNBackend):

    def __init__(self, openvpn_bin_path: Optional[Path] = None) -> None:
        self.openvpn_bin = openvpn_bin_path or self._discover_openvpn()
        self.process: Optional[subprocess.Popen] = None
        self.active_config_path: Optional[str] = None
        self.active_auth_path: Optional[str] = None
        self._stop_requested = False
        self._connected = False
        self._verifier = BinaryVerifier()

    def _discover_openvpn(self) -> Optional[Path]:
        candidates = [
            Path("bin") / "openvpn.exe",
            Path(__file__).resolve().parent.parent.parent.parent / "bin" / "openvpn.exe",
            Path(sys.executable).parent / "bin" / "openvpn.exe",
            Path(sys.executable).parent / "openvpn.exe",
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "OpenVPN" / "bin" / "openvpn.exe",
        ]
        if hasattr(sys, "_MEIPASS"):
            candidates.insert(0, Path(sys._MEIPASS) / "bin" / "openvpn.exe")
        for cand in candidates:
            if cand.is_file():
                return cand.resolve()
        return None

    def is_connected(self) -> bool:
        return self._connected and self.process is not None and self.process.poll() is None

    def prepare_config(self, ovpn_base64: str, mode: str = "full") -> str:
        raw_text = base64.b64decode(ovpn_base64).decode("utf-8", errors="ignore")
        lines = []
        for line in raw_text.splitlines():
            clean = line.strip()
            if mode == "discord" and (clean.startswith("redirect-gateway") or clean.startswith("route-gateway")):
                continue
            if clean.startswith("auth-user-pass") or clean.startswith("#auth-user-pass") or clean.startswith(";auth-user-pass"):
                continue
            lines.append(line)

        auth_fd, auth_path = tempfile.mkstemp(suffix=".txt", prefix="mogged_auth_")
        with os.fdopen(auth_fd, "w", encoding="utf-8") as f:
            f.write("vpn\nvpn\n")
        self.active_auth_path = auth_path
        auth_path_escaped = auth_path.replace("\\", "/")

        directives = [
            "",
            "nobind",
            "persist-key",
            "persist-tun",
            "verb 3",
            "resolv-retry 2",
            "connect-timeout 20",
            "hand-window 20",
            "server-poll-timeout 8",
            "mssfix 1360",
            "tun-mtu 1500",
            "sndbuf 524288",
            "rcvbuf 524288",
            "block-ipv6",
            f'auth-user-pass "{auth_path_escaped}"',
            "auth-nocache",
            "auth-retry nointeract",
        ]

        if mode == "full":
            directives.append("redirect-gateway def1")
            directives.extend(DNSManager.get_openvpn_dns_directives())
        elif mode == "discord":
            directives.extend(get_discord_split_directives())

        final_content = "\n".join(lines) + "\n" + "\n".join(directives) + "\n"

        fd, config_path = tempfile.mkstemp(suffix=".ovpn", prefix="mogged_sec_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(final_content)
        return config_path

    def connect(
        self,
        server: Dict[str, Any],
        mode: str = "full",
        on_status: Optional[Callable[[str, str], None]] = None,
    ) -> bool:
        if not self.openvpn_bin or not self.openvpn_bin.is_file():
            logger.error("Executável openvpn.exe não localizado.")
            return False

        try:
            self._verifier.verify_file(self.openvpn_bin)
        except Exception as e:
            logger.error(f"Falha de integridade do binário OpenVPN: {e}")
            return False

        self._kill_process()
        self._stop_requested = False
        self._connected = False

        try:
            self.active_config_path = self.prepare_config(server["ovpn_config_b64"], mode=mode)
            bin_dir = str(self.openvpn_bin.parent)
            env = os.environ.copy()
            env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")

            cmd = [str(self.openvpn_bin), "--config", self.active_config_path]
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=bin_dir,
                env=env,
                creationflags=creationflags,
            )

            q: queue.Queue = queue.Queue()

            def _reader():
                try:
                    for line in iter(self.process.stdout.readline, ""):
                        q.put(line)
                except Exception:
                    pass
                q.put(None)

            reader_thread = threading.Thread(target=_reader, daemon=True)
            reader_thread.start()

            start_time = time.time()
            handshake_success = False

            while not self._stop_requested:
                try:
                    line = q.get(timeout=0.2)
                except queue.Empty:
                    line = None

                if line is not None:
                    line_str = line.strip()
                    if line_str:
                        logger.debug(f"[OpenVPN] {line_str}")
                        if "Initialization Sequence Completed" in line_str:
                            handshake_success = True
                            self._connected = True
                            if on_status:
                                on_status(STATUS_CONNECTED, f"Conectado ({mode})")
                            break
                        if "TLS: Initial packet from" in line_str and on_status:
                            on_status(STATUS_CONNECTING, "Handshake TLS...")
                        elif "Peer Connection Initiated" in line_str and on_status:
                            on_status(STATUS_CONNECTING, "Configurando tunel...")
                        if any(
                            err in line_str
                            for err in (
                                "AUTH_FAILED",
                                "TLS Error",
                                "Cannot resolve host",
                                "Connection refused",
                                "Connection timed out",
                                "Exiting due to fatal error",
                                "SIGUSR1",
                                "SIGTERM",
                            )
                        ):
                            logger.warning(f"Erro no handshake: {line_str[:100]}")
                            break

                if time.time() - start_time > CONNECT_TIMEOUT_SEC:
                    logger.warning("Tempo limite esgotado no handshake OpenVPN.")
                    break

                if self.process is not None and self.process.poll() is not None:
                    break

            if not handshake_success:
                self._kill_process()
                self._cleanup_temp_file()
                return False

            while not self._stop_requested and self.process is not None and self.process.poll() is None:
                try:
                    line = q.get(timeout=0.5)
                    if line is None:
                        break
                except queue.Empty:
                    continue

            self._kill_process()
            self._cleanup_temp_file()
            self._connected = False
            return True

        except Exception as e:
            logger.error(f"Exceção durante conexão OpenVPN: {e}")
            self._kill_process()
            self._cleanup_temp_file()
            self._connected = False
            return False

    def _kill_process(self) -> None:
        proc = self.process
        self.process = None
        self._connected = False
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "openvpn.exe", "/T"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                timeout=5,
            )
        except Exception:
            pass
        if proc is not None:
            try:
                proc.wait(timeout=4)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def disconnect(self) -> None:
        self._stop_requested = True
        self._kill_process()
        DNSManager.flush_dns()
        self._cleanup_temp_file()

    def _cleanup_temp_file(self) -> None:
        path = self.active_config_path
        self.active_config_path = None
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
        auth_path = self.active_auth_path
        self.active_auth_path = None
        if auth_path and os.path.exists(auth_path):
            try:
                os.remove(auth_path)
            except Exception:
                pass
