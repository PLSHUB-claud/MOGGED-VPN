import logging
import os
import subprocess
import sys
from typing import Optional

logger = logging.getLogger("Mogged.Network.KillSwitch")

RULE_NAME = "MoggedVPN_KillSwitch_Discord"

class KillSwitch:

    def __init__(self, discord_exe_path: Optional[str] = None) -> None:
        self.discord_exe_path = discord_exe_path
        self._is_active = False

    def enable(self, discord_path: Optional[str] = None) -> bool:
        if sys.platform != "win32":
            return True

        target_exe = discord_path or self.discord_exe_path
        if not target_exe or not os.path.isfile(target_exe):
            logger.warning("Caminho do Discord não configurado para o Kill Switch.")
            return False

        self.cleanup()

        cmd = [
            "netsh",
            "advfirewall",
            "firewall",
            "add",
            "rule",
            f"name={RULE_NAME}",
            "dir=out",
            "action=block",
            f"program={target_exe}",
            "enable=yes",
            "description=Bloqueio de seguranca do Mogged VPN",
        ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if res.returncode == 0:
                self._is_active = True
                logger.info(f"Kill Switch ativado com sucesso para: {target_exe}")
                return True
            logger.error(f"Falha ao ativar regra do Kill Switch: {res.stderr}")
            return False
        except Exception as e:
            logger.error(f"Exceção ao criar regra de Kill Switch: {e}")
            return False

    def disable(self) -> bool:
        self._is_active = False
        return self.cleanup()

    @staticmethod
    def cleanup() -> bool:
        if sys.platform != "win32":
            return True

        cmd = [
            "netsh",
            "advfirewall",
            "firewall",
            "delete",
            "rule",
            f"name={RULE_NAME}",
        ]
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            logger.debug("Regras de Kill Switch limpas.")
            return True
        except Exception as e:
            logger.debug(f"Aviso ao limpar regras do Kill Switch: {e}")
            return False
