import logging
import os
from pathlib import Path
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
from typing import Any, Dict, List, Optional
import urllib.request

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk

from mogged.constants import (
    APP_HEIGHT,
    APP_VERSION,
    APP_WIDTH,
    MODE_DISCORD,
    MODE_FULL,
    STATUS_CONNECTED,
    STATUS_CONNECTING,
    STATUS_DISCONNECTED,
    STATUS_ERROR,
)
from mogged.discord.process_manager import DiscordProcessManager
from mogged.network.server_fetcher import ServerFetcher
from mogged.network.server_manager import ServerManager
from mogged.network.server_validator import ServerValidator
from mogged.network.vpn_manager import VPNManager
from mogged.storage.secure_store import SecureStore
from mogged.ui.tray import TrayManager

logger = logging.getLogger("Mogged.UI.MainWindow")

def get_font(size: int = 12, bold: bool = False) -> ImageFont.ImageFont:
    try:
        font_name = "segoeuib.ttf" if bold else "segoeui.ttf"
        return ImageFont.truetype(font_name, size)
    except Exception:
        try:
            font_name = "arialbd.ttf" if bold else "arial.ttf"
            return ImageFont.truetype(font_name, size)
        except Exception:
            return ImageFont.load_default()

def create_glossy_button_image(
    width: int,
    height: int,
    text: str,
    is_active: bool = False,
    is_main: bool = False,
    is_connected: bool = False,
    is_connecting: bool = False,
    is_hover: bool = False,
) -> Image.Image:
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    radius = 12 if not is_main else 14
    if is_connected:
        fill = (65, 12, 12, 245) if not is_hover else (85, 15, 15, 255)
        border = (239, 68, 68, 240)
        top_gleam = (255, 140, 140, 240)
    elif is_connecting:
        fill = (55, 35, 12, 245) if not is_hover else (75, 45, 15, 255)
        border = (245, 158, 11, 240)
        top_gleam = (255, 210, 110, 240)
    elif is_main:
        fill = (14, 14, 20, 250) if not is_hover else (30, 30, 42, 255)
        border = (255, 255, 255, 240) if not is_hover else (255, 255, 255, 255)
        top_gleam = (255, 255, 255, 255)
    elif is_active:
        fill = (32, 32, 44, 245) if not is_hover else (45, 45, 60, 255)
        border = (255, 255, 255, 210)
        top_gleam = (255, 255, 255, 240)
    else:
        fill = (14, 14, 20, 200) if not is_hover else (28, 28, 38, 230)
        border = (255, 255, 255, 80) if not is_hover else (255, 255, 255, 160)
        top_gleam = (255, 255, 255, 150) if not is_hover else (255, 255, 255, 220)

    draw.rounded_rectangle([1, 1, width - 2, height - 2], radius=radius, fill=fill, outline=border, width=1)
    draw.line([radius + 2, 2, width - radius - 2, 2], fill=top_gleam, width=1)

    font_size = 14 if is_main else 12
    font = get_font(font_size, bold=True)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (width - tw) // 2
    ty = (height - th) // 2 - 2
    text_color = (
        (255, 255, 255, 255)
        if (is_active or is_main or is_connected or is_connecting or is_hover)
        else (175, 180, 195, 255)
    )
    draw.text((tx, ty), text, fill=text_color, font=font)
    return im

def bezier_points(p0, p1, p2, steps=30):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        pts.append((x, y))
    return pts

def create_eye_button_image(width=56, height=36, slashed=True, is_hover=False):
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    radius = 12
    fill = (14, 14, 20, 200) if not is_hover else (28, 28, 38, 235)
    border = (255, 255, 255, 120) if not is_hover else (255, 255, 255, 220)
    top_gleam = (255, 255, 255, 180) if not is_hover else (255, 255, 255, 250)
    draw.rounded_rectangle([1, 1, width - 2, height - 2], radius=radius, fill=fill, outline=border, width=1)
    draw.line([radius + 2, 2, width - radius - 2, 2], fill=top_gleam, width=1)

    scale = 4
    ew = 11 * scale
    eh = 7 * scale
    cx = width // 2 * scale
    cy = height // 2 * scale
    icon_im = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    idraw = ImageDraw.Draw(icon_im)
    color = (255, 255, 255, 255)
    pts_upper = bezier_points((cx - ew, cy), (cx, cy - eh), (cx + ew, cy))
    idraw.line(pts_upper, fill=color, width=int(1.8 * scale))
    pts_lower = bezier_points((cx - ew, cy), (cx, cy + eh), (cx + ew, cy))
    idraw.line(pts_lower, fill=color, width=int(1.8 * scale))
    pr = 2.8 * scale
    idraw.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=color)
    if slashed:
        idraw.line(
            [(cx - ew - 2 * scale, cy - eh - 1 * scale), (cx + ew + 2 * scale, cy + eh + 1 * scale)],
            fill=color,
            width=int(2.0 * scale),
        )
    icon_small = icon_im.resize((width, height), Image.Resampling.LANCZOS)
    return Image.alpha_composite(im, icon_small)

def create_reload_button_image(width=42, height=38, is_hover=False):
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    radius = 12
    fill = (14, 14, 20, 200) if not is_hover else (28, 28, 38, 235)
    border = (255, 255, 255, 120) if not is_hover else (255, 255, 255, 220)
    top_gleam = (255, 255, 255, 180) if not is_hover else (255, 255, 255, 250)
    draw.rounded_rectangle([1, 1, width - 2, height - 2], radius=radius, fill=fill, outline=border, width=1)
    draw.line([radius + 2, 2, width - radius - 2, 2], fill=top_gleam, width=1)

    scale = 4
    cx = width // 2 * scale
    cy = height // 2 * scale
    R = 8 * scale
    icon_im = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    idraw = ImageDraw.Draw(icon_im)
    color = (255, 255, 255, 255)
    box = [cx - R, cy - R, cx + R, cy + R]
    idraw.arc(box, start=35, end=190, fill=color, width=int(1.8 * scale))
    idraw.arc(box, start=215, end=370, fill=color, width=int(1.8 * scale))
    idraw.polygon(
        [(cx + R + 1 * scale, cy - 2 * scale), (cx + R - 4 * scale, cy - 8 * scale), (cx + R - 4 * scale, cy + 3 * scale)],
        fill=color,
    )
    idraw.polygon(
        [(cx - R - 1 * scale, cy + 2 * scale), (cx - R + 4 * scale, cy + 8 * scale), (cx - R + 4 * scale, cy - 3 * scale)],
        fill=color,
    )
    icon_small = icon_im.resize((width, height), Image.Resampling.LANCZOS)
    return Image.alpha_composite(im, icon_small)

def create_dropdown_bar_image(width, height, text, is_hover=False):
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    radius = 12
    fill = (16, 16, 24, 245) if not is_hover else (28, 28, 40, 255)
    border = (255, 255, 255, 180) if not is_hover else (255, 255, 255, 240)
    draw.rounded_rectangle([1, 1, width - 2, height - 2], radius=radius, fill=fill, outline=border, width=1)
    draw.line([radius + 2, 2, width - radius - 2, 2], fill=(255, 255, 255, 210), width=1)
    font = get_font(11, bold=True)
    draw.text((14, (height - 18) // 2), text, fill=(255, 255, 255, 255), font=font)
    arrow_x = width - 22
    arrow_y = height // 2 - 2
    draw.polygon([(arrow_x - 5, arrow_y), (arrow_x + 5, arrow_y), (arrow_x, arrow_y + 6)], fill=(255, 255, 255, 230))
    return im

class MainWindow:

    def __init__(self, root: tk.Tk, start_hidden: bool = False) -> None:
        self.root = root
        self.root.title("Mogged VPN")
        self.root.geometry(f"{APP_WIDTH}x{APP_HEIGHT}")
        self.root.minsize(APP_WIDTH, APP_HEIGHT)
        self.root.maxsize(APP_WIDTH, APP_HEIGHT)
        self.root.resizable(False, False)

        self._setup_window_styling()

        self.fetcher = ServerFetcher()
        self.server_manager = ServerManager(fetcher=self.fetcher)
        self.validator = ServerValidator()
        self.secure_store = SecureStore()
        self.vpn_manager = VPNManager(on_status_change=self._on_status_change)

        self.current_mode = MODE_FULL
        self.servers: List[Dict[str, Any]] = []
        self.countries: List[Dict[str, Any]] = []
        self.selected_country_code = ""
        self.selected_server: Optional[Dict[str, Any]] = None
        self.expanded_countries = set()
        self.selected_country_label = "Carregando servidores..."
        self.controls_hidden = False
        self.public_ip = "Verificando..."
        self.popup_menu: Optional[tk.Toplevel] = None
        self._connect_in_progress = False

        self.imgs: Dict[str, ImageTk.PhotoImage] = {}
        self._load_wallpaper()

        self.canvas = tk.Canvas(self.root, width=APP_WIDTH, height=APP_HEIGHT, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self._render_background()
        self._create_canvas_items()

        threading.Thread(target=self._fast_fetch_ip, daemon=True).start()
        threading.Thread(target=self._load_servers_thread, daemon=True).start()
        threading.Thread(target=self._check_updates_background, daemon=True).start()

        self.root.bind("<Key-h>", lambda e: self.toggle_controls())
        self.root.bind("<Key-H>", lambda e: self.toggle_controls())
        self.root.bind("<Button-1>", self._on_root_click)
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        self.tray = TrayManager(self)
        self.tray.start()

        if start_hidden:
            self.root.withdraw()

    def _setup_window_styling(self) -> None:
        from mogged.resource_helper import get_asset_path
        for name in ("transparent.ico", "app_icon.ico"):
            ico_path = get_asset_path(name)
            if ico_path.is_file():
                try:
                    self.root.iconbitmap(str(ico_path))
                    break
                except Exception:
                    pass

        if sys.platform == "win32":
            try:
                self.root.update_idletasks()
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
                dark = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(dark), ctypes.sizeof(dark))
            except Exception:
                pass

    def _load_wallpaper(self) -> None:
        from mogged.resource_helper import get_asset_path
        wp_path = get_asset_path("wallpaper.png")
        if wp_path.is_file():
            try:
                img = Image.open(wp_path).convert("RGBA")
            except Exception:
                img = Image.new("RGBA", (APP_WIDTH, APP_HEIGHT), (20, 25, 35, 255))
        else:
            img = Image.new("RGBA", (APP_WIDTH, APP_HEIGHT), (20, 25, 35, 255))
        if img.size != (APP_WIDTH, APP_HEIGHT):
            img = img.resize((APP_WIDTH, APP_HEIGHT), Image.Resampling.LANCZOS)
        self.base_wallpaper = img

    def _render_background(self) -> None:
        bg = self.base_wallpaper.copy()
        overlay = Image.new("RGBA", (APP_WIDTH, APP_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        p1 = [20, 16, 300, 52]
        crop1 = bg.crop(p1).filter(ImageFilter.GaussianBlur(10))
        bg.paste(crop1, p1)
        draw.rounded_rectangle(p1, radius=18, fill=(15, 20, 30, 140), outline=(255, 255, 255, 170), width=1)
        draw.line([p1[0] + 18, p1[1] + 1, p1[2] - 18, p1[1] + 1], fill=(255, 255, 255, 230), width=1)

        p2 = [312, 16, 530, 52]
        crop2 = bg.crop(p2).filter(ImageFilter.GaussianBlur(10))
        bg.paste(crop2, p2)
        draw.rounded_rectangle(p2, radius=18, fill=(15, 20, 30, 140), outline=(255, 255, 255, 170), width=1)
        draw.line([p2[0] + 18, p2[1] + 1, p2[2] - 18, p2[1] + 1], fill=(255, 255, 255, 230), width=1)

        if not self.controls_hidden:
            dock_box = [30, 465, 994, 558]
            dock_crop = bg.crop(dock_box).filter(ImageFilter.GaussianBlur(14))
            bg.paste(dock_crop, dock_box)
            draw.rounded_rectangle(dock_box, radius=22, fill=(15, 20, 32, 135), outline=(255, 255, 255, 175), width=2)
            draw.line([(dock_box[0] + 35, dock_box[1] + 1), (dock_box[2] - 35, dock_box[1] + 1)], fill=(255, 255, 255, 240), width=2)

            font_label = get_font(10, bold=True)
            draw.text((50, 477), "MODO DE CONEXÃO", fill=(255, 255, 255, 220), font=font_label)
            draw.text((305, 477), "LOCALIZAÇÃO DO SERVIDOR", fill=(255, 255, 255, 220), font=font_label)
            draw.text((645, 477), "DISCORD", fill=(255, 255, 255, 220), font=font_label)

        composite = Image.alpha_composite(bg, overlay)
        self.bg_tk = ImageTk.PhotoImage(composite)
        self.canvas.delete("bg_tag")
        self.canvas.create_image(0, 0, anchor="nw", image=self.bg_tk, tags="bg_tag")
        self.canvas.tag_lower("bg_tag")

    def _create_canvas_items(self) -> None:
        self.status_dot = self.canvas.create_oval(34, 29, 44, 39, fill="#94a3b8", outline="#ffffff", width=1)
        self.status_text = self.canvas.create_text(
            52, 34, text="Desconectado", anchor="w", fill="#ffffff", font=("Segoe UI", 10, "bold")
        )
        self.ip_text = self.canvas.create_text(
            328, 34, text=f"IP: {self.public_ip}", anchor="w", fill="#ffffff", font=("Segoe UI", 10, "bold")
        )

        self._update_eye_button(slashed=not self.controls_hidden)
        self._bind_button("btn_hide", self.toggle_controls)

        self._update_button_image("btn_pc", 115, 38, "Todo o PC", is_active=self.current_mode == MODE_FULL, x=107, y=517, tag_group="dock")
        self._bind_button("btn_pc", lambda: self.set_mode(MODE_FULL))

        self._update_button_image("btn_disc", 115, 38, "Discord", is_active=self.current_mode == MODE_DISCORD, x=228, y=517, tag_group="dock")
        self._bind_button("btn_disc", lambda: self.set_mode(MODE_DISCORD))

        self._update_dropdown_image()
        self.canvas.tag_bind("btn_dropdown", "<Button-1>", self._on_dropdown_click)
        self.canvas.tag_bind("btn_dropdown", "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind("btn_dropdown", "<Leave>", lambda e: self.canvas.config(cursor=""))

        self._update_reload_button()
        self._bind_button("btn_refresh", self._on_refresh_click)

        self._update_button_image("btn_restart_disc", 140, 38, "Reiniciar Discord", x=715, y=517, tag_group="dock")
        self._bind_button("btn_restart_disc", self._on_restart_discord)

        self._update_connect_button()
        self._bind_button("btn_connect", self._on_toggle_connect)

    def _update_button_image(
        self, name, width, height, text, is_active=False, is_main=False, is_connected=False, is_connecting=False, x=0, y=0, tag_group=""
    ) -> None:
        img = ImageTk.PhotoImage(
            create_glossy_button_image(
                width, height, text, is_active, is_main, is_connected, is_connecting, is_hover=False
            )
        )
        self.imgs[name] = img
        tags = (name, tag_group) if tag_group else (name,)
        item_id = self.canvas.find_withtag(name)
        if item_id:
            self.canvas.itemconfigure(item_id[0], image=img)
        else:
            self.canvas.create_image(x, y, image=img, tags=tags)

    def _bind_button(self, name: str, command) -> None:
        self.canvas.tag_bind(name, "<Button-1>", lambda e: command())
        self.canvas.tag_bind(name, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(name, "<Leave>", lambda e: self.canvas.config(cursor=""))

    def _update_eye_button(self, slashed=True, is_hover=False) -> None:
        img = ImageTk.PhotoImage(create_eye_button_image(56, 36, slashed=slashed, is_hover=is_hover))
        self.imgs["eye_btn"] = img
        item = self.canvas.find_withtag("btn_hide")
        if item:
            self.canvas.itemconfigure(item[0], image=img)
        else:
            self.canvas.create_image(974, 34, image=img, tags="btn_hide")

    def _update_reload_button(self, is_hover=False) -> None:
        img = ImageTk.PhotoImage(create_reload_button_image(42, 38, is_hover=is_hover))
        self.imgs["reload_btn"] = img
        item = self.canvas.find_withtag("btn_refresh")
        if item:
            self.canvas.itemconfigure(item[0], image=img)
        else:
            self.canvas.create_image(595, 517, image=img, tags=("btn_refresh", "dock"))

    def _update_dropdown_image(self, is_hover=False) -> None:
        img = ImageTk.PhotoImage(create_dropdown_bar_image(250, 38, self.selected_country_label, is_hover=is_hover))
        self.imgs["dropdown"] = img
        item = self.canvas.find_withtag("btn_dropdown")
        if item:
            self.canvas.itemconfigure(item[0], image=img)
        else:
            self.canvas.create_image(440, 517, image=img, tags=("btn_dropdown", "dock"))

    def _update_connect_button(self, is_hover=False) -> None:
        status = self.vpn_manager.status
        is_conn = status == STATUS_CONNECTED
        is_connecting = status == STATUS_CONNECTING
        text = "DESCONECTAR" if is_conn else "CANCELAR" if is_connecting else "CONECTAR"
        img = ImageTk.PhotoImage(
            create_glossy_button_image(
                160, 44, text, is_main=True, is_connected=is_conn, is_connecting=is_connecting, is_hover=is_hover
            )
        )
        self.imgs["connect_btn"] = img
        item = self.canvas.find_withtag("btn_connect")
        if item:
            self.canvas.itemconfigure(item[0], image=img)
        else:
            self.canvas.create_image(905, 517, image=img, tags=("btn_connect", "dock"))

    def set_mode(self, mode: str) -> None:
        self.current_mode = mode
        self._update_button_image("btn_pc", 115, 38, "Todo o PC", is_active=mode == MODE_FULL, x=107, y=517, tag_group="dock")
        self._update_button_image("btn_disc", 115, 38, "Discord", is_active=mode == MODE_DISCORD, x=228, y=517, tag_group="dock")

    def toggle_controls(self) -> None:
        self._close_popup()
        self.controls_hidden = not self.controls_hidden
        self._render_background()
        dock_items = self.canvas.find_withtag("dock")
        state = "hidden" if self.controls_hidden else "normal"
        for it in dock_items:
            self.canvas.itemconfigure(it, state=state)
        self._update_eye_button(slashed=not self.controls_hidden)

    def _on_root_click(self, event) -> None:
        if self.popup_menu:
            if hasattr(self, "_popup_open_time") and time.time() - self._popup_open_time < 0.2:
                return
            self._close_popup()

    def _close_popup(self) -> None:
        if self.popup_menu:
            self.popup_menu.destroy()
            self.popup_menu = None

    def _fast_fetch_ip(self) -> None:
        endpoints = ["https://api.ipify.org", "https://icanhazip.com", "https://checkip.amazonaws.com"]
        for url in endpoints:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "MoggedVPN/1.1"})
                with urllib.request.urlopen(req, timeout=2.5) as resp:  # nosec B310
                    ip = resp.read().decode("utf-8").strip()
                    if ip:
                        self.public_ip = ip
                        self.root.after(0, lambda: self.canvas.itemconfigure(self.ip_text, text=f"IP: {self.public_ip}"))
                        break
            except Exception:
                pass

    def _load_servers_thread(self, force_refresh: bool = False) -> None:
        try:
            self.servers = self.fetcher.fetch(force_refresh=force_refresh)
            self.server_manager.set_servers(self.servers)
            self._recalculate_countries()
            self.root.after(0, self._populate_countries)
        except Exception as e:
            logger.error(f"Erro ao carregar servidores: {e}")

    def _recalculate_countries(self) -> None:
        grouped: Dict[str, Dict[str, Any]] = {}
        for s in self.servers:
            code = s["country_short"]
            if code not in grouped:
                grouped[code] = {
                    "code": code,
                    "name": s["country_long"],
                    "flag": s["flag"],
                    "server_count": 0,
                    "best_ping": 9999,
                    "max_speed": 0.0,
                }
            grouped[code]["server_count"] += 1
            if 0 < s["ping"] < grouped[code]["best_ping"]:
                grouped[code]["best_ping"] = s["ping"]
            if s["speed_mbps"] > grouped[code]["max_speed"]:
                grouped[code]["max_speed"] = s["speed_mbps"]
        self.countries = sorted(
            list(grouped.values()),
            key=lambda x: (-x["server_count"], -x["max_speed"], x["name"].lower()),
        )

    def _populate_countries(self) -> None:
        if not self.countries:
            self.selected_country_label = "Nenhum servidor encontrado"
            self._update_dropdown_image()
            return

        preferred = self.secure_store.get("preferred_country_code")
        available_codes = {c["code"] for c in self.countries}

        if preferred and preferred in available_codes and not self.selected_country_code:
            self.selected_country_code = preferred
        elif not self.selected_country_code:
            self.selected_country_code = self.countries[0]["code"]

        for c in self.countries:
            if c["code"] == self.selected_country_code:
                p_str = f"{c['best_ping']}ms" if c["best_ping"] < 9000 else "N/A"
                self.selected_country_label = f"{c['name']}   ({c['server_count']} serv. • {p_str})"
                break
        self._update_dropdown_image()

    def _on_dropdown_click(self, event=None) -> None:
        if self.popup_menu:
            self._close_popup()
            return
        if not self.countries:
            return

        self._popup_open_time = time.time()
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        menu_w = 400
        menu_h = 350
        popup_x = root_x + 440 - menu_w // 2
        popup_y = root_y + 517 - menu_h - 26

        self.popup_menu = tk.Toplevel(self.root)
        self.popup_menu.overrideredirect(True)
        self.popup_menu.geometry(f"{menu_w}x{menu_h}+{popup_x}+{popup_y}")
        self.popup_menu.configure(bg="#0a0a0f")

        outer = tk.Frame(self.popup_menu, bg="#0a0a0f", bd=1, highlightbackground="#3b82f6", highlightthickness=1)
        outer.pack(fill="both", expand=True)

        from tkinter import ttk
        try:
            s = ttk.Style()
            s.theme_use("clam")
            s.configure(
                "Dark.Vertical.TScrollbar",
                gripcount=0,
                background="#2d3247",
                troughcolor="#0e1017",
                bordercolor="#0e1017",
                arrowcolor="#ffffff",
                arrowsize=11,
                width=12,
            )
            scroll = ttk.Scrollbar(outer, orient="vertical", style="Dark.Vertical.TScrollbar")
        except Exception:
            scroll = tk.Scrollbar(outer, orient="vertical")
        scroll.pack(side="right", fill="y")

        cv = tk.Canvas(outer, bg="#0e1017", highlightthickness=0)
        cv.pack(side="left", fill="both", expand=True)
        cv.configure(yscrollcommand=scroll.set)
        scroll.configure(command=cv.yview)

        scroll_frame = tk.Frame(cv, bg="#0e1017")
        cv.create_window((0, 0), window=scroll_frame, anchor="nw", width=menu_w - 22)

        def update_scroll(e=None):
            cv.configure(scrollregion=cv.bbox("all"))

        scroll_frame.bind("<Configure>", update_scroll)

        def on_mousewheel(e):
            cv.yview_scroll(int(-1 * (e.delta / 120)), "units")

        self.popup_menu.bind("<MouseWheel>", on_mousewheel)
        outer.bind("<MouseWheel>", on_mousewheel)
        cv.bind("<MouseWheel>", on_mousewheel)

        for c in self.countries:
            row = tk.Frame(scroll_frame, bg="#0e1017", height=32)
            row.pack(fill="x", padx=2, pady=1)

            p_str = f"{c['best_ping']}ms" if c["best_ping"] < 9000 else "N/A"
            txt = f"{c['flag']} {c['name']} ({c['server_count']} serv. • {p_str})"
            lbl = tk.Label(row, text=txt, bg="#0e1017", fg="#ffffff", font=("Segoe UI", 9, "bold"), anchor="w")
            lbl.pack(side="left", fill="both", expand=True, padx=8)

            def make_select(target_c):
                def _sel(e=None):
                    self.selected_country_code = target_c["code"]
                    try:
                        self.secure_store.set("preferred_country_code", self.selected_country_code)
                    except Exception:
                        pass
                    self.selected_server = None
                    p = f"{target_c['best_ping']}ms" if target_c["best_ping"] < 9000 else "N/A"
                    self.selected_country_label = f"{target_c['name']}   ({target_c['server_count']} serv. • {p})"
                    self._update_dropdown_image()
                    self._close_popup()
                return _sel

            sel_fn = make_select(c)
            row.bind("<Button-1>", sel_fn)
            lbl.bind("<Button-1>", sel_fn)

    def _on_refresh_click(self) -> None:
        self.selected_country_label = "Atualizando servidores..."
        self._update_dropdown_image()
        threading.Thread(target=self._load_servers_thread, args=(True,), daemon=True).start()

    def _on_restart_discord(self) -> None:
        self._update_button_image("btn_restart_disc", 140, 38, "Reiniciando...", x=715, y=517, tag_group="dock")

        def _run():
            try:
                DiscordProcessManager.restart()
                msg = "Reiniciado!"
            except Exception:
                msg = "Não Encontrado"
            self.root.after(0, lambda: self._update_button_image("btn_restart_disc", 140, 38, msg, x=715, y=517, tag_group="dock"))
            time.sleep(1.8)
            self.root.after(0, lambda: self._update_button_image("btn_restart_disc", 140, 38, "Reiniciar Discord", x=715, y=517, tag_group="dock"))

        threading.Thread(target=_run, daemon=True).start()

    def _on_toggle_connect(self) -> None:
        if self.vpn_manager.status in (STATUS_DISCONNECTED, STATUS_ERROR):
            if self._connect_in_progress:
                return
            self._connect_in_progress = True

            self.canvas.itemconfigure(self.status_dot, fill="#f59e0b")
            self.canvas.itemconfigure(self.status_text, text="Conectando...")
            self.canvas.itemconfigure(self.ip_text, text="IP: Conectando...")
            self._update_connect_button()

            def _async_conn():
                try:
                    self.root.after(0, lambda: self.canvas.itemconfigure(self.status_text, text="Testando servidores..."))
                    if not self.servers:
                        self.root.after(0, lambda: self.canvas.itemconfigure(self.status_text, text="Buscando servidores..."))
                        t_wait = time.time()
                        while not self.servers and (time.time() - t_wait < 6.0):
                            time.sleep(0.25)
                        if not self.servers:
                            self.servers = self.fetcher.fetch(force_refresh=False)
                            if not self.servers:
                                self.servers = self.fetcher.fetch(force_refresh=True)
                            if self.servers:
                                self.server_manager.set_servers(self.servers)
                                self._recalculate_countries()
                                self.root.after(0, self._populate_countries)

                    if not self.selected_country_code and self.countries:
                        self.selected_country_code = self.countries[0]["code"]

                    target_servers = [s for s in self.servers if s.get("country_short") == self.selected_country_code]
                    if not target_servers:
                        target_servers = list(self.servers)
                    if not target_servers:
                        self.root.after(0, lambda: self._apply_status(STATUS_ERROR, "Nenhum servidor disponível."))
                        return

                    checked_servers = self.server_manager.health_check(target_servers, timeout=1.5)
                    active_pool = checked_servers if checked_servers else target_servers
                    if active_pool and active_pool[0].get("live_rtt") is None:
                        global_cands = [s for s in self.servers if s.get("id") not in self.server_manager.blacklist]
                        global_cands.sort(key=lambda s: (-s.get("speed_mbps", 0.0), s.get("ping", 999)))
                        global_checked = self.server_manager.health_check(global_cands[:10], timeout=1.5)
                        if global_checked and any(s.get("live_rtt") is not None for s in global_checked):
                            active_pool = [s for s in global_checked if s.get("live_rtt") is not None]

                    target = active_pool[0]
                    raw_fallbacks = self.server_manager.get_fallback_candidates(self.selected_country_code, exclude_server_id=target.get("id"))
                    confirmed_fallbacks = [s for s in active_pool[1:3] if s.get("live_rtt") is not None and s.get("id") != target.get("id")]
                    for fb in raw_fallbacks:
                        if fb.get("id") != target.get("id") and not any(cf.get("id") == fb.get("id") for cf in confirmed_fallbacks):
                            confirmed_fallbacks.append(fb)

                    self.vpn_manager.connect(target, mode=self.current_mode, fallback_servers=confirmed_fallbacks)
                finally:
                    self._connect_in_progress = False

            threading.Thread(target=_async_conn, daemon=True).start()
        else:
            self.canvas.itemconfigure(self.ip_text, text="IP: Atualizando...")
            self.vpn_manager.disconnect()

    def _on_status_change(self, status: str, msg: str) -> None:
        self.root.after(0, lambda: self._apply_status(status, msg))

    def _apply_status(self, status: str, msg: str) -> None:
        self._update_connect_button()
        if status == STATUS_CONNECTED:
            self.canvas.itemconfigure(self.status_dot, fill="#22c55e")
            lbl = "Todo o PC" if self.vpn_manager.active_mode == MODE_FULL else "Discord"
            self.canvas.itemconfigure(self.status_text, text=f"Conectado ({lbl})")
            if self.selected_country_code:
                try:
                    self.secure_store.set("preferred_country_code", self.selected_country_code)
                except Exception:
                    pass
            if self.vpn_manager.active_server:
                srv_id = self.vpn_manager.active_server.get("id", "")
                self.server_manager.record_success(srv_id)
            threading.Thread(target=self._fast_fetch_ip, daemon=True).start()
        elif status == STATUS_CONNECTING:
            self.canvas.itemconfigure(self.status_dot, fill="#f59e0b")
            clean_msg = msg or "Conectando..."
            if len(clean_msg) > 22:
                clean_msg = clean_msg[:22] + "..."
            self.canvas.itemconfigure(self.status_text, text=clean_msg)
        elif status == STATUS_ERROR:
            self.canvas.itemconfigure(self.status_dot, fill="#ef4444")
            err_text = "Falha na Conexão" if ("Falha ao conectar" in (msg or "") or len(msg or "") > 22) else (msg or "Erro de Conexão")
            self.canvas.itemconfigure(self.status_text, text=err_text)
            if self.vpn_manager.active_server:
                srv_id = self.vpn_manager.active_server.get("id", "")
                self.server_manager.record_failure(srv_id)
        else:
            self.canvas.itemconfigure(self.status_dot, fill="#94a3b8")
            self.canvas.itemconfigure(self.status_text, text="Desconectado")
            threading.Thread(target=self._fast_fetch_ip, daemon=True).start()

        if self.tray:
            self.tray.update_status(status, msg)

    def minimize_to_tray(self) -> None:
        self._close_popup()
        self.root.withdraw()

    def restore_from_tray(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _check_updates_background(self) -> None:
        time.sleep(2.0)
        self.check_for_updates(quiet=True)

    def check_for_updates(self, quiet: bool = False) -> None:
        def _worker():
            try:
                from mogged.updates.updater import Updater
                updater = Updater()
                info = updater.check_for_updates()
                if info:
                    self.root.after(0, lambda: self._show_update_dialog(info))
                elif not quiet:
                    self.root.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Mogged VPN",
                            f"Você já está utilizando a versão mais recente (v{APP_VERSION}).",
                        ),
                    )
            except Exception as e:
                logger.debug(f"Erro ao verificar atualizações: {e}")
                if not quiet:
                    self.root.after(
                        0,
                        lambda: messagebox.showerror(
                            "Mogged VPN",
                            f"Não foi possível verificar atualizações no momento:\n{e}",
                        ),
                    )

        threading.Thread(target=_worker, daemon=True).start()

    def _show_update_dialog(self, info: Dict[str, Any]) -> None:
        from mogged.ui.update_dialog import UpdateDialog
        UpdateDialog(self.root, info, app_controller=self)

    def quit_app(self) -> None:
        self._close_popup()
        if self.tray:
            self.tray.stop()
        if self.vpn_manager.status in (STATUS_CONNECTING, STATUS_CONNECTED):
            self.vpn_manager.disconnect()
        try:
            self.root.destroy()
        except Exception:
            pass
        sys.exit(0)
