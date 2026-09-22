import logging
import os
import subprocess
import sys
from typing import List

logger = logging.getLogger("Mogged.Network.DNSManager")

SAFE_DNS_SERVERS = ["1.1.1.1", "1.0.0.1", "9.9.9.9"]

class DNSManager:

    @staticmethod
    def get_openvpn_dns_directives() -> List[str]:
        directives = [
            "# --- DNS LEAK PREVENTION ---",
            "block-outside-dns",
        ]
        for dns in SAFE_DNS_SERVERS:
            directives.append(f"dhcp-option DNS {dns}")
        return directives

    @staticmethod
    def flush_dns() -> bool:
        if sys.platform != "win32":
            return True

        try:
            subprocess.run(
                ["ipconfig", "/flushdns"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                timeout=5,
            )
            logger.debug("Cache DNS limpo com sucesso.")
            return True
        except Exception as e:
            logger.warning(f"Erro ao executar flushdns: {e}")
            return False
