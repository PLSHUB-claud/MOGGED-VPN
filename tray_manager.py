import os
import sys
import logging
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item, Menu
import startup_manager
from resource_helper import get_asset_path
logger = logging.getLogger('MoggedVPN.Tray')

class TrayManager:

    def __init__(self, app):
        self.app = app
        self.icon = None
        self._setup_icon()

    def _get_icon_image(self):
        icon_path = get_asset_path('app_icon.ico')
        if os.path.isfile(icon_path):
            try:
                im = Image.open(icon_path)
                return im.resize((64, 64), Image.Resampling.LANCZOS)
            except Exception:
                pass
        im = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse([4, 4, 60, 60], fill=(14, 16, 23, 255), outline=(59, 130, 246, 255), width=3)
        d.polygon([(32, 16), (46, 22), (46, 36), (32, 48), (18, 36), (18, 22)], fill=(59, 130, 246, 255))
        return im

    def _setup_icon(self):
        im = self._get_icon_image()

        def on_open(icon, item):
            self.app.root.after(0, self.app.restore_from_tray)

        def on_toggle_startup(icon, item):
            startup_manager.toggle_startup()

        def is_startup_active(item):
            return startup_manager.is_startup_enabled()

        def on_toggle_connect(icon, item):
            self.app.root.after(0, self.app._on_toggle_connect)

        def get_status_text(item):
            status = getattr(self.app.engine, 'status', 'DISCONNECTED')
            mode = 'PC' if getattr(self.app, 'current_mode', 'full') == 'full' else 'Discord'
            if status == 'CONNECTED':
                c_code = getattr(self.app, 'selected_country_code', '')
                return f'Status: Connected ({c_code or mode})'
            elif status == 'CONNECTING':
                return 'Status: Connecting...'
            else:
                return 'Status: Disconnected'

        def on_exit(icon, item):
            self.app.root.after(0, self.app.quit_app)
        menu = Menu(item('Open Mogged VPN', on_open, default=True), Menu.SEPARATOR, item(get_status_text, None, enabled=False), item('Connect / Disconnect', on_toggle_connect), Menu.SEPARATOR, item('Start with Windows', on_toggle_startup, checked=is_startup_active), Menu.SEPARATOR, item('Exit', on_exit))
        self.icon = pystray.Icon('MoggedVPN', im, 'Mogged VPN', menu=menu)

    def start(self):
        if self.icon:
            try:
                self.icon.run_detached()
            except Exception as e:
                logger.error(f'Erro ao iniciar System Tray: {e}')

    def update_status(self, status, msg=''):
        if self.icon:
            self.icon.title = f'Mogged VPN - {status.capitalize()}'

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
