import logging
import os
from pathlib import Path
from PIL import Image, ImageDraw
import pystray
from pystray import Menu, MenuItem as item

logger = logging.getLogger("Mogged.UI.Tray")

class TrayManager:

    def __init__(self, app_controller) -> None:
        self.app = app_controller
        self.icon = None
        self._setup_icon()

    def _get_icon_image(self) -> Image.Image:
        from mogged.resource_helper import get_asset_path
        ico_file = get_asset_path("app_icon.ico")
        if ico_file.is_file():
            try:
                return Image.open(ico_file).resize((64, 64), Image.Resampling.LANCZOS)
            except Exception:
                pass

        im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse([4, 4, 60, 60], fill=(14, 16, 23, 255), outline=(59, 130, 246, 255), width=3)
        d.polygon([(32, 16), (46, 22), (46, 36), (32, 48), (18, 36), (18, 22)], fill=(59, 130, 246, 255))
        return im

    def _setup_icon(self) -> None:
        im = self._get_icon_image()

        def on_open(icon, item):
            self.app.root.after(0, self.app.restore_from_tray)

        def on_toggle_connect(icon, item):
            self.app.root.after(0, self.app._on_toggle_connect)

        def get_status_text(item):
            status = getattr(self.app.vpn_manager, "status", "DISCONNECTED")
            mode = getattr(self.app, "current_mode", "full").upper()
            return f"Status: {status} ({mode})"

        def on_check_updates(icon, item):
            self.app.root.after(0, lambda: self.app.check_for_updates(quiet=False))

        def on_exit(icon, item):
            self.app.root.after(0, self.app.quit_app)

        menu = Menu(
            item("Abrir Mogged VPN", on_open, default=True),
            Menu.SEPARATOR,
            item(get_status_text, None, enabled=False),
            item("Conectar / Desconectar", on_toggle_connect),
            item("Verificar Atualizações", on_check_updates),
            Menu.SEPARATOR,
            item("Sair", on_exit),
        )
        self.icon = pystray.Icon("MoggedVPN", im, "Mogged VPN", menu=menu)

    def start(self) -> None:
        if self.icon:
            try:
                self.icon.run_detached()
            except Exception as e:
                logger.error(f"Erro ao iniciar Tray Icon: {e}")

    def update_status(self, status: str, msg: str = "") -> None:
        if self.icon:
            self.icon.title = f"Mogged VPN - {status.capitalize()}"

    def stop(self) -> None:
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
