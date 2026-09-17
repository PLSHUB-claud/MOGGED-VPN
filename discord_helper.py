import glob
import logging
import os
import subprocess
import time
from typing import Optional
logger = logging.getLogger('MoggedVPN.DiscordHelper')

def find_discord_executable() -> Optional[str]:
    local_app_data = os.environ.get('LOCALAPPDATA', '')
    if not local_app_data:
        return None
    update_exe = os.path.join(local_app_data, 'Discord', 'Update.exe')
    if os.path.isfile(update_exe):
        return update_exe
    pattern = os.path.join(local_app_data, 'Discord', 'app-*', 'Discord.exe')
    matches = glob.glob(pattern)
    if matches:
        matches.sort(reverse=True)
        return matches[0]
    return None

def is_discord_running() -> bool:
    try:
        output = subprocess.check_output(['tasklist', '/FI', 'IMAGENAME eq Discord.exe'], text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return 'Discord.exe' in output
    except Exception:
        return False

def restart_discord() -> bool:
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'Discord.exe'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        time.sleep(1)
        exe = find_discord_executable()
        if not exe:
            return False
        if 'Update.exe' in exe:
            cmd = [exe, '--processStart', 'Discord.exe']
        else:
            cmd = [exe]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return True
    except Exception as e:
        logger.error(f'Erro ao reiniciar Discord: {e}')
        return False
