import ctypes
from ctypes import wintypes
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Optional

import psutil
from mogged.discord.paths import find_discord_executable
from mogged.exceptions import DiscordNotFoundError, DiscordRestartError

logger = logging.getLogger("Mogged.Discord.ProcessManager")

class DiscordProcessManager:

    @staticmethod
    def is_running() -> bool:
        if sys.platform != "win32":
            return False
        try:
            cmd = ["tasklist", "/FI", "IMAGENAME eq Discord.exe"]
            output = subprocess.check_output(
                cmd,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            return "Discord.exe" in output
        except Exception:
            return False

    @staticmethod
    def close_gracefully(timeout_sec: float = 3.0) -> bool:
        if sys.platform != "win32":
            return True

        user32 = ctypes.windll.user32
        WM_CLOSE = 0x0010

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        pid = wintypes.DWORD()

        def _enum_windows_cb(hwnd, _lparam):
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value:
                try:
                    p = psutil.Process(pid.value)
                    if p.name().lower() == "discord.exe":
                        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                except Exception:
                    pass
            return True

        user32.EnumWindows(WNDENUMPROC(_enum_windows_cb), 0)

        start = time.time()
        while time.time() - start < timeout_sec:
            if not DiscordProcessManager.is_running():
                logger.info("Discord encerrado graciosamente via WM_CLOSE.")
                return True
            time.sleep(0.3)

        logger.info("Encerrando instâncias restantes do Discord via taskkill.")
        subprocess.run(
            ["taskkill", "/F", "/IM", "Discord.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        time.sleep(0.5)
        return not DiscordProcessManager.is_running()

    @staticmethod
    def restart() -> bool:
        DiscordProcessManager.close_gracefully()
        time.sleep(1.0)

        exe = find_discord_executable()
        if not exe:
            logger.error("Executável do Discord não foi encontrado.")
            raise DiscordNotFoundError("Discord não localizado na máquina.")

        if "Update.exe" in str(exe):
            cmd = [str(exe), "--processStart", "Discord.exe"]
        else:
            cmd = [str(exe)]

        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            logger.info(f"Discord reiniciado com sucesso: {exe}")
            return True
        except Exception as e:
            logger.error(f"Erro ao reiniciar Discord: {e}")
            raise DiscordRestartError(f"Falha ao executar Discord: {e}")
