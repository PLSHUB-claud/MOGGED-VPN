import logging
import os
import sys
import tkinter as tk
from vpn_engine import is_admin, elevate_admin
from resource_helper import get_writable_data_path
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
log_path = get_writable_data_path('mogged_vpn.log')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] (%(name)s) %(message)s', handlers=[logging.FileHandler(log_path, encoding='utf-8'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger('VPN.Main')

def main():
    logger.info('Iniciando VPN nativo...')
    start_hidden = '--tray' in sys.argv or '--minimized' in sys.argv
    if not start_hidden and (not is_admin()):
        logger.info('Solicitando permissão de Administrador...')
        elevated = elevate_admin()
        if elevated:
            return
    from native_app import NativeVpnApp
    root = tk.Tk()
    if start_hidden:
        root.withdraw()
    app = NativeVpnApp(root, start_hidden=start_hidden)
    root.protocol('WM_DELETE_WINDOW', app.minimize_to_tray)
    root.mainloop()
if __name__ == '__main__':
    main()
