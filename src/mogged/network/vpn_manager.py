import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from mogged.constants import (
    MODE_DISCORD,
    MODE_FULL,
    STATUS_CONNECTED,
    STATUS_CONNECTING,
    STATUS_DISCONNECTED,
    STATUS_ERROR,
)
from mogged.network.kill_switch import KillSwitch
from mogged.network.openvpn_backend import OpenVPNBackend
from mogged.network.vpn_backend import VPNBackend

logger = logging.getLogger("Mogged.Network.VPNManager")

class VPNManager:

    def __init__(
        self,
        backend: Optional[VPNBackend] = None,
        on_status_change: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.backend = backend or OpenVPNBackend()
        self.on_status_change = on_status_change
        self._status = STATUS_DISCONNECTED
        self._status_lock = threading.Lock()
        self._connect_lock = threading.Lock()

        self.active_server: Optional[Dict[str, Any]] = None
        self.active_mode: str = MODE_FULL
        self.connected_since: Optional[float] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_requested = False

        self.kill_switch = KillSwitch()

    @property
    def status(self) -> str:
        with self._status_lock:
            return self._status

    def _set_status(self, new_status: str, msg: str = "") -> None:
        with self._status_lock:
            self._status = new_status
            if new_status == STATUS_CONNECTED:
                self.connected_since = time.time()
            elif new_status in (STATUS_DISCONNECTED, STATUS_ERROR):
                self.connected_since = None

        logger.info(f"Estado alterado para [{new_status}]: {msg}")
        if self.on_status_change:
            try:
                self.on_status_change(new_status, msg)
            except Exception as e:
                logger.error(f"Erro no callback de status: {e}")

    def connect(
        self,
        server: Dict[str, Any],
        mode: str = MODE_FULL,
        fallback_servers: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        with self._connect_lock:
            if self.status in (STATUS_CONNECTING, STATUS_CONNECTED):
                self.disconnect()

            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=5.0)

            time.sleep(1.2)

            self._stop_requested = False
            self.active_mode = mode

            candidates = [server]
            if fallback_servers:
                for fb in fallback_servers:
                    if fb["id"] != server["id"] and len(candidates) < 3:
                        candidates.append(fb)

            total = len(candidates)

        def _worker():
            for idx, srv in enumerate(candidates, 1):
                if self._stop_requested:
                    break

                self.active_server = srv
                curr_c = srv.get("country_long", "Server")
                self._set_status(STATUS_CONNECTING, "Conectando...")
                logger.info(f"Tentativa {idx}/{total}: {srv.get('ip')} ({curr_c})")

                success = self.backend.connect(
                    srv,
                    mode=mode,
                    on_status=self._set_status,
                )

                if success:
                    return

                if self._stop_requested:
                    break

                if idx < total:
                    next_s = candidates[idx]
                    logger.info(
                        f"Servidor {srv.get('ip')} falhou. Alternando para {idx + 1}/{total} "
                        f"({next_s.get('country_long')})..."
                    )
                    for _ in range(15):
                        if self._stop_requested:
                            break
                        time.sleep(0.1)

            if not self._stop_requested:
                self._set_status(STATUS_ERROR, "Falha ao conectar com todos os servidores.")

        self._monitor_thread = threading.Thread(target=_worker, daemon=True)
        self._monitor_thread.start()

    def disconnect(self) -> None:
        self._stop_requested = True
        self._set_status(STATUS_CONNECTING, "Desconectando...")
        self.backend.disconnect()
        self.kill_switch.disable()
        self._set_status(STATUS_DISCONNECTED, "Desconectado.")
