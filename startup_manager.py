import os
import sys
import winreg
import logging
logger = logging.getLogger('MoggedVPN.Startup')
APP_NAME = 'MoggedVPN'
REG_PATH = 'Software\\Microsoft\\Windows\\CurrentVersion\\Run'

def get_startup_command() -> str:
    if getattr(sys, 'frozen', False):
        exe_path = os.path.abspath(sys.executable)
        return f'"{exe_path}" --tray'
    else:
        python_exe = sys.executable
        pythonw_exe = os.path.join(os.path.dirname(python_exe), 'pythonw.exe')
        if not os.path.isfile(pythonw_exe):
            pythonw_exe = python_exe
        main_script = os.path.abspath(sys.argv[0])
        if not main_script.endswith('main.py'):
            cand = os.path.join(os.path.dirname(__file__), 'main.py')
            if os.path.isfile(cand):
                main_script = os.path.abspath(cand)
        return f'"{pythonw_exe}" "{main_script}" --tray'

def is_startup_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except Exception as e:
        logger.warning(f'Erro ao verificar registro de inicialização: {e}')
        return False

def enable_startup() -> bool:
    try:
        cmd = get_startup_command()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        logger.info(f'Inicialização com Windows ativada: {cmd}')
        return True
    except Exception as e:
        logger.error(f'Erro ao registrar inicialização no Windows: {e}')
        return False

def disable_startup() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, APP_NAME)
                logger.info('Inicialização com Windows desativada.')
            except FileNotFoundError:
                pass
        return True
    except Exception as e:
        logger.error(f'Erro ao remover inicialização no Windows: {e}')
        return False

def toggle_startup() -> bool:
    if is_startup_enabled():
        disable_startup()
        return False
    else:
        enable_startup()
        return True
