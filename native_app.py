import json
import logging
import os
import sys
import threading
import time
import urllib.request
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageFilter, ImageFont
from vpn_service import VpnServerService
from vpn_engine import VpnEngine, STATUS_DISCONNECTED, STATUS_CONNECTING, STATUS_CONNECTED, STATUS_ERROR
from discord_helper import restart_discord
from resource_helper import get_asset_path
logger = logging.getLogger('VPN.NativeApp')
APP_WIDTH = 1024
APP_HEIGHT = 580

def get_font(size=12, bold=False):
    try:
        font_name = 'segoeuib.ttf' if bold else 'segoeui.ttf'
        return ImageFont.truetype(font_name, size)
    except Exception:
        try:
            font_name = 'arialbd.ttf' if bold else 'arial.ttf'
            return ImageFont.truetype(font_name, size)
        except Exception:
            return ImageFont.load_default()

def create_glossy_button_image(width, height, text, is_active=False, is_main=False, is_connected=False, is_connecting=False, is_hover=False):
    im = Image.new('RGBA', (width, height), (0, 0, 0, 0))
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
    text_color = (255, 255, 255, 255) if is_active or is_main or is_connected or is_connecting or is_hover else (175, 180, 195, 255)
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
    im = Image.new('RGBA', (width, height), (0, 0, 0, 0))
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
    icon_im = Image.new('RGBA', (width * scale, height * scale), (0, 0, 0, 0))
    idraw = ImageDraw.Draw(icon_im)
    color = (255, 255, 255, 255)
    pts_upper = bezier_points((cx - ew, cy), (cx, cy - eh), (cx + ew, cy))
    idraw.line(pts_upper, fill=color, width=int(1.8 * scale))
    pts_lower = bezier_points((cx - ew, cy), (cx, cy + eh), (cx + ew, cy))
    idraw.line(pts_lower, fill=color, width=int(1.8 * scale))
    pr = 2.8 * scale
    idraw.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=color)
    if slashed:
        idraw.line([(cx - ew - 2 * scale, cy - eh - 1 * scale), (cx + ew + 2 * scale, cy + eh + 1 * scale)], fill=color, width=int(2.0 * scale))
    icon_small = icon_im.resize((width, height), Image.Resampling.LANCZOS)
    im = Image.alpha_composite(im, icon_small)
    return im

def create_reload_button_image(width=42, height=38, is_hover=False):
    im = Image.new('RGBA', (width, height), (0, 0, 0, 0))
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
    icon_im = Image.new('RGBA', (width * scale, height * scale), (0, 0, 0, 0))
    idraw = ImageDraw.Draw(icon_im)
    color = (255, 255, 255, 255)
    box = [cx - R, cy - R, cx + R, cy + R]
    idraw.arc(box, start=35, end=190, fill=color, width=int(1.8 * scale))
    idraw.arc(box, start=215, end=370, fill=color, width=int(1.8 * scale))
    idraw.polygon([(cx + R + 1 * scale, cy - 2 * scale), (cx + R - 4 * scale, cy - 8 * scale), (cx + R - 4 * scale, cy + 3 * scale)], fill=color)
    idraw.polygon([(cx - R - 1 * scale, cy + 2 * scale), (cx - R + 4 * scale, cy + 8 * scale), (cx - R + 4 * scale, cy - 3 * scale)], fill=color)
    icon_small = icon_im.resize((width, height), Image.Resampling.LANCZOS)
    im = Image.alpha_composite(im, icon_small)
    return im

def create_dropdown_bar_image(width, height, text, is_hover=False):
    im = Image.new('RGBA', (width, height), (0, 0, 0, 0))
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

class NativeVpnApp:

    def __init__(self, root: tk.Tk, start_hidden: bool=False):
        self.root = root
        self.root.title('')
        self.root.geometry(f'{APP_WIDTH}x{APP_HEIGHT}')
        self.root.minsize(APP_WIDTH, APP_HEIGHT)
        self.root.maxsize(APP_WIDTH, APP_HEIGHT)
        self.root.resizable(False, False)
        self._setup_window_styling()
        self.service = VpnServerService()
        self.engine = VpnEngine(on_status_change=self._on_status_change)
        self.current_mode = 'full'
        self.countries = []
        self.selected_country_code = ''
        self.selected_server = None
        self.expanded_countries = set()
        self.selected_country_label = 'Loading servers...'
        self.controls_hidden = False
        self.public_ip = 'Checking...'
        self.popup_menu = None
        if self.service.servers:
            self.countries = self.service.get_countries()
            if self.countries:
                c0 = self.countries[0]
                ping_str = f"{c0['best_ping']}ms" if c0['best_ping'] < 9000 else 'N/A'
                self.selected_country_code = c0['code']
                self.selected_country_label = f"{c0['name']}   ({c0['server_count']} serv. • {ping_str})"
        self.imgs = {}
        self.wallpaper_path = get_asset_path('wallpaper.png')
        self._load_wallpaper()
        self.canvas = tk.Canvas(self.root, width=APP_WIDTH, height=APP_HEIGHT, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self._render_background()
        self._create_canvas_items()
        threading.Thread(target=self._fast_fetch_ip, daemon=True).start()
        threading.Thread(target=self._load_servers_thread, daemon=True).start()
        self.root.bind('<Key-h>', lambda e: self.toggle_controls())
        self.root.bind('<Key-H>', lambda e: self.toggle_controls())
        self.root.bind('<Button-1>', self._on_root_click)
        self.root.protocol('WM_DELETE_WINDOW', self.minimize_to_tray)
        try:
            from tray_manager import TrayManager
            self.tray = TrayManager(self)
            self.tray.start()
        except Exception as e:
            logger.warning(f'Não foi possível iniciar o tray icon: {e}')
            self.tray = None
        if start_hidden:
            self.root.withdraw()

    def _setup_window_styling(self):
        ico_path = get_asset_path('transparent.ico')
        if not os.path.isfile(ico_path):
            try:
                from PIL import Image
                sizes = [(16, 16), (32, 32), (48, 48)]
                imgs = [Image.new('RGBA', s, (0, 0, 0, 0)) for s in sizes]
                imgs[-1].save(ico_path, format='ICO', sizes=[(i.width, i.height) for i in imgs], append_images=imgs[:-1])
            except Exception:
                pass
        if os.path.isfile(ico_path):
            try:
                self.root.iconbitmap(ico_path)
            except Exception:
                pass
        if sys.platform == 'win32':
            try:
                self.root.update_idletasks()
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                if not hwnd:
                    hwnd = self.root.winfo_id()
                dark = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(dark), ctypes.sizeof(dark))
                caption_color = ctypes.c_int(985610)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption_color), ctypes.sizeof(caption_color))
                text_color = ctypes.c_int(16777215)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(text_color), ctypes.sizeof(text_color))
            except Exception as e:
                logger.debug(f'Could not apply DWM dark titlebar: {e}')

    def _load_wallpaper(self):
        if os.path.isfile(self.wallpaper_path):
            img = Image.open(self.wallpaper_path).convert('RGBA')
        else:
            img = Image.new('RGBA', (APP_WIDTH, APP_HEIGHT), (20, 25, 35, 255))
        if img.size != (APP_WIDTH, APP_HEIGHT):
            img = img.resize((APP_WIDTH, APP_HEIGHT), Image.Resampling.LANCZOS)
        self.base_wallpaper = img

    def _render_background(self):
        bg = self.base_wallpaper.copy()
        overlay = Image.new('RGBA', (APP_WIDTH, APP_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        p1 = [20, 16, 260, 52]
        crop1 = bg.crop(p1).filter(ImageFilter.GaussianBlur(10))
        bg.paste(crop1, p1)
        draw.rounded_rectangle(p1, radius=18, fill=(15, 20, 30, 140), outline=(255, 255, 255, 170), width=1)
        draw.line([p1[0] + 18, p1[1] + 1, p1[2] - 18, p1[1] + 1], fill=(255, 255, 255, 230), width=1)
        p2 = [272, 16, 480, 52]
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
            draw.text((50, 477), 'CONNECTION MODE', fill=(255, 255, 255, 220), font=font_label)
            draw.text((305, 477), 'SERVER LOCATION', fill=(255, 255, 255, 220), font=font_label)
            draw.text((645, 477), 'DISCORD', fill=(255, 255, 255, 220), font=font_label)
        composite = Image.alpha_composite(bg, overlay)
        self.bg_tk = ImageTk.PhotoImage(composite)
        self.canvas.delete('bg_tag')
        self.canvas.create_image(0, 0, anchor='nw', image=self.bg_tk, tags='bg_tag')
        self.canvas.tag_lower('bg_tag')

    def _create_canvas_items(self):
        self.status_dot = self.canvas.create_oval(34, 29, 44, 39, fill='#94a3b8', outline='#ffffff', width=1)
        self.status_text = self.canvas.create_text(52, 34, text='Disconnected', anchor='w', fill='#ffffff', font=('Segoe UI', 10, 'bold'))
        self.ip_text = self.canvas.create_text(288, 34, text=f'IP: {self.public_ip}', anchor='w', fill='#ffffff', font=('Segoe UI', 10, 'bold'))
        self._update_eye_button(slashed=not self.controls_hidden)
        self._bind_button('btn_hide', self.toggle_controls)
        self._update_button_image('btn_pc', 115, 38, 'Entire PC', is_active=self.current_mode == 'full', x=107, y=517, tag_group='dock')
        self._bind_button('btn_pc', lambda: self.set_mode('full'))
        self._update_button_image('btn_disc', 115, 38, 'Discord', is_active=self.current_mode == 'discord', x=228, y=517, tag_group='dock')
        self._bind_button('btn_disc', lambda: self.set_mode('discord'))
        self._update_dropdown_image()
        self.canvas.tag_bind('btn_dropdown', '<Button-1>', self._on_dropdown_click)
        self.canvas.tag_bind('btn_dropdown', '<Enter>', lambda e: self.canvas.config(cursor='hand2'))
        self.canvas.tag_bind('btn_dropdown', '<Leave>', lambda e: self.canvas.config(cursor=''))
        self._update_reload_button()
        self._bind_button('btn_refresh', self._on_refresh_click)
        self._update_button_image('btn_restart_disc', 140, 38, 'Restart Discord', x=715, y=517, tag_group='dock')
        self._bind_button('btn_restart_disc', self._on_restart_discord)
        self._update_connect_button()
        self._bind_button('btn_connect', self._on_toggle_connect)

    def _update_button_image(self, name, width, height, text, is_active=False, is_main=False, is_connected=False, is_connecting=False, x=0, y=0, tag_group=''):
        img = ImageTk.PhotoImage(create_glossy_button_image(width, height, text, is_active, is_main, is_connected, is_connecting, is_hover=False))
        self.imgs[name] = img
        tags = (name, tag_group) if tag_group else (name,)
        item_id = self.canvas.find_withtag(name)
        if item_id:
            self.canvas.itemconfigure(item_id[0], image=img)
        else:
            self.canvas.create_image(x, y, image=img, tags=tags)

    def _bind_button(self, name, command):
        self.canvas.tag_bind(name, '<Button-1>', lambda e: command())
        self.canvas.tag_bind(name, '<Enter>', lambda e: self.canvas.config(cursor='hand2'))
        self.canvas.tag_bind(name, '<Leave>', lambda e: self.canvas.config(cursor=''))

    def _update_eye_button(self, slashed=True, is_hover=False):
        img = ImageTk.PhotoImage(create_eye_button_image(56, 36, slashed=slashed, is_hover=is_hover))
        self.imgs['eye_btn'] = img
        item = self.canvas.find_withtag('btn_hide')
        if item:
            self.canvas.itemconfigure(item[0], image=img)
        else:
            self.canvas.create_image(974, 34, image=img, tags='btn_hide')

    def _update_reload_button(self, is_hover=False):
        img = ImageTk.PhotoImage(create_reload_button_image(42, 38, is_hover=is_hover))
        self.imgs['reload_btn'] = img
        item = self.canvas.find_withtag('btn_refresh')
        if item:
            self.canvas.itemconfigure(item[0], image=img)
        else:
            self.canvas.create_image(595, 517, image=img, tags=('btn_refresh', 'dock'))

    def _update_dropdown_image(self, is_hover=False):
        img = ImageTk.PhotoImage(create_dropdown_bar_image(250, 38, self.selected_country_label, is_hover=is_hover))
        self.imgs['dropdown'] = img
        item = self.canvas.find_withtag('btn_dropdown')
        if item:
            self.canvas.itemconfigure(item[0], image=img)
        else:
            self.canvas.create_image(440, 517, image=img, tags=('btn_dropdown', 'dock'))

    def _update_connect_button(self, is_hover=False):
        status = self.engine.status
        is_conn = status == STATUS_CONNECTED
        is_connecting = status == STATUS_CONNECTING
        text = 'DISCONNECT' if is_conn else 'CANCEL' if is_connecting else 'CONNECT'
        img = ImageTk.PhotoImage(create_glossy_button_image(160, 44, text, is_main=True, is_connected=is_conn, is_connecting=is_connecting, is_hover=is_hover))
        self.imgs['connect_btn'] = img
        item = self.canvas.find_withtag('btn_connect')
        if item:
            self.canvas.itemconfigure(item[0], image=img)
        else:
            self.canvas.create_image(905, 517, image=img, tags=('btn_connect', 'dock'))

    def _on_dropdown_click(self, event=None):
        if self.popup_menu:
            self.popup_menu.destroy()
            self.popup_menu = None
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
        self.popup_menu.geometry(f'{menu_w}x{menu_h}+{popup_x}+{popup_y}')
        self.popup_menu.configure(bg='#0a0a0f')
        outer = tk.Frame(self.popup_menu, bg='#0a0a0f', bd=1, highlightbackground='#3b82f6', highlightthickness=1)
        outer.pack(fill='both', expand=True)
        from tkinter import ttk
        try:
            s = ttk.Style()
            s.theme_use('clam')
            s.configure('Dark.Vertical.TScrollbar', gripcount=0, background='#2d3247', troughcolor='#0e1017', bordercolor='#0e1017', arrowcolor='#ffffff', arrowsize=11, width=12)
            scroll = ttk.Scrollbar(outer, orient='vertical', style='Dark.Vertical.TScrollbar')
        except Exception:
            scroll = tk.Scrollbar(outer, orient='vertical')
        scroll.pack(side='right', fill='y')
        cv = tk.Canvas(outer, bg='#0e1017', highlightthickness=0)
        cv.pack(side='left', fill='both', expand=True)
        cv.configure(yscrollcommand=scroll.set)
        scroll.configure(command=cv.yview)
        scroll_frame = tk.Frame(cv, bg='#0e1017')
        cv.create_window((0, 0), window=scroll_frame, anchor='nw', width=menu_w - 22)

        def update_scroll_region(event=None):
            cv.configure(scrollregion=cv.bbox('all'))
        scroll_frame.bind('<Configure>', update_scroll_region)

        def on_mousewheel(event):
            cv.yview_scroll(int(-1 * (event.delta / 120)), 'units')

        def bind_mousewheel_recursive(widget):
            widget.bind('<MouseWheel>', on_mousewheel)
            for child in widget.winfo_children():
                bind_mousewheel_recursive(child)
        self.popup_menu.bind('<MouseWheel>', on_mousewheel)
        outer.bind('<MouseWheel>', on_mousewheel)
        cv.bind('<MouseWheel>', on_mousewheel)
        scroll_frame.bind('<MouseWheel>', on_mousewheel)

        def render_items():
            for w in scroll_frame.winfo_children():
                w.destroy()
            for c in self.countries:
                code = c['code']
                count = c['server_count']
                ping_str = f"{c['best_ping']}ms" if c['best_ping'] < 9000 else 'N/A'
                is_expanded = code in self.expanded_countries
                row = tk.Frame(scroll_frame, bg='#131722' if is_expanded else '#0e1017', height=34)
                row.pack(fill='x', padx=2, pady=1)
                if count > 1:
                    arrow_icon = '▼' if is_expanded else '▶'
                    lbl_arrow = tk.Label(row, text=arrow_icon, bg=row['bg'], fg='#60a5fa', font=('Segoe UI', 9, 'bold'), width=3)
                    lbl_arrow.pack(side='left', padx=(2, 0))
                else:
                    lbl_arrow = tk.Label(row, text='•', bg=row['bg'], fg='#64748b', font=('Segoe UI', 10), width=3)
                    lbl_arrow.pack(side='left', padx=(2, 0))
                c_text = f"{c['name']}   ({count} serv. • {ping_str})"
                lbl_text = tk.Label(row, text=c_text, bg=row['bg'], fg='#ffffff', font=('Segoe UI', 10, 'bold'), anchor='w')
                lbl_text.pack(side='left', fill='both', expand=True, padx=2)

                def make_toggle(target_code):

                    def toggle(e=None):
                        if target_code in self.expanded_countries:
                            self.expanded_countries.remove(target_code)
                        else:
                            self.expanded_countries.add(target_code)
                        render_items()
                        bind_mousewheel_recursive(scroll_frame)
                    return toggle

                def make_select_single(target_c):

                    def select(e=None):
                        self.selected_country_code = target_c['code']
                        self.selected_server = None
                        p_str = f"{target_c['best_ping']}ms" if target_c['best_ping'] < 9000 else 'N/A'
                        self.selected_country_label = f"{target_c['name']}   ({target_c['server_count']} serv. • {p_str})"
                        self._update_dropdown_image()
                        self._close_popup()
                    return select
                click_handler = make_toggle(code) if count > 1 else make_select_single(c)

                def make_hover(r, la, lt, c_code):

                    def on_enter(e):
                        r.configure(bg='#222738')
                        la.configure(bg='#222738')
                        lt.configure(bg='#222738')

                    def on_leave(e):
                        base_bg = '#131722' if c_code in self.expanded_countries else '#0e1017'
                        r.configure(bg=base_bg)
                        la.configure(bg=base_bg)
                        lt.configure(bg=base_bg)
                    return (on_enter, on_leave)
                he, hl = make_hover(row, lbl_arrow, lbl_text, code)
                for w in (row, lbl_arrow, lbl_text):
                    w.bind('<Enter>', he)
                    w.bind('<Leave>', hl)
                    w.bind('<Button-1>', click_handler)
                if is_expanded and count > 1:
                    srv_list = [s for s in self.service.servers if s['country_short'] == code]
                    srv_list.sort(key=lambda s: (s['ping'] if s['ping'] > 0 else 9999, -s['speed_mbps']))
                    auto_row = tk.Frame(scroll_frame, bg='#161b28', height=28)
                    auto_row.pack(fill='x', padx=(20, 4), pady=1)
                    auto_lbl = tk.Label(auto_row, text='⚡ Auto (Best Server)', bg='#161b28', fg='#38bdf8', font=('Segoe UI', 9, 'bold'), anchor='w')
                    auto_lbl.pack(side='left', padx=8, pady=3)
                    auto_sub = tk.Label(auto_row, text=f'• {ping_str}', bg='#161b28', fg='#94a3b8', font=('Segoe UI', 9))
                    auto_sub.pack(side='right', padx=8)

                    def make_select_auto(target_c):

                        def on_auto(e=None):
                            self.selected_country_code = target_c['code']
                            self.selected_server = None
                            p_str = f"{target_c['best_ping']}ms" if target_c['best_ping'] < 9000 else 'N/A'
                            self.selected_country_label = f"{target_c['name']}   ({target_c['server_count']} serv. • {p_str})"
                            self._update_dropdown_image()
                            self._close_popup()
                        return on_auto

                    def make_row_hover(r, l1, l2, default_bg, hover_bg):

                        def se(e):
                            r.configure(bg=hover_bg)
                            l1.configure(bg=hover_bg)
                            l2.configure(bg=hover_bg)

                        def sl(e):
                            r.configure(bg=default_bg)
                            l1.configure(bg=default_bg)
                            l2.configure(bg=default_bg)
                        return (se, sl)
                    ae, al = make_row_hover(auto_row, auto_lbl, auto_sub, '#161b28', '#253047')
                    sel_auto_fn = make_select_auto(c)
                    for aw in (auto_row, auto_lbl, auto_sub):
                        aw.bind('<Enter>', ae)
                        aw.bind('<Leave>', al)
                        aw.bind('<Button-1>', sel_auto_fn)
                    for s_idx, srv in enumerate(srv_list, 1):
                        s_row = tk.Frame(scroll_frame, bg='#11141f', height=26)
                        s_row.pack(fill='x', padx=(20, 4), pady=1)
                        s_ping = f"{srv['ping']}ms" if srv['ping'] > 0 else 'N/A'
                        s_speed = f"{srv['speed_mbps']}M" if srv['speed_mbps'] > 0 else ''
                        s_name = f"Node {s_idx:02d} ({srv['ip']})"
                        s_lbl = tk.Label(s_row, text=f'• {s_name}', bg='#11141f', fg='#e2e8f0', font=('Segoe UI', 9), anchor='w')
                        s_lbl.pack(side='left', padx=6, pady=2)
                        stat_txt = f'{s_speed} • {s_ping}' if s_speed else s_ping
                        s_sub = tk.Label(s_row, text=stat_txt, bg='#11141f', fg='#38bdf8', font=('Segoe UI', 8, 'bold'))
                        s_sub.pack(side='right', padx=6)

                        def make_select_server(target_srv, c_name, node_title, s_stat):

                            def on_srv(e=None):
                                self.selected_country_code = target_srv.get('country_short', '')
                                self.selected_server = target_srv
                                self.selected_country_label = f'{c_name} • {node_title} ({s_stat})'
                                self._update_dropdown_image()
                                self._close_popup()
                            return on_srv
                        se_h, sl_h = make_row_hover(s_row, s_lbl, s_sub, '#11141f', '#262d42')
                        sel_srv_fn = make_select_server(srv, c['name'], f'Node {s_idx:02d}', stat_txt)
                        for sw in (s_row, s_lbl, s_sub):
                            sw.bind('<Enter>', se_h)
                            sw.bind('<Leave>', sl_h)
                            sw.bind('<Button-1>', sel_srv_fn)
        render_items()
        scroll_frame.update_idletasks()
        cv.configure(scrollregion=cv.bbox('all'))
        bind_mousewheel_recursive(self.popup_menu)
        self.popup_menu.bind('<FocusOut>', lambda e: self._close_popup())
        self.popup_menu.focus_set()

    def _close_popup(self):
        if self.popup_menu:
            self.popup_menu.destroy()
            self.popup_menu = None

    def _on_root_click(self, event):
        if self.popup_menu:
            if hasattr(self, '_popup_open_time') and time.time() - self._popup_open_time < 0.2:
                return
            self._close_popup()

    def toggle_controls(self):
        self._close_popup()
        self.controls_hidden = not self.controls_hidden
        self._render_background()
        dock_items = self.canvas.find_withtag('dock')
        state = 'hidden' if self.controls_hidden else 'normal'
        for it in dock_items:
            self.canvas.itemconfigure(it, state=state)
        self._update_eye_button(slashed=not self.controls_hidden)

    def set_mode(self, mode):
        self.current_mode = mode
        self._update_button_image('btn_pc', 115, 38, 'Entire PC', is_active=mode == 'full', x=107, y=517, tag_group='dock')
        self._update_button_image('btn_disc', 115, 38, 'Discord', is_active=mode == 'discord', x=228, y=517, tag_group='dock')

    def _fast_fetch_ip(self):
        endpoints = ['http://api.ipify.org', 'http://icanhazip.com', 'http://checkip.amazonaws.com']
        new_ip = None
        for url in endpoints:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'curl/7.68.0'})
                with urllib.request.urlopen(req, timeout=1.8) as resp:
                    ip = resp.read().decode('utf-8').strip()
                    if ip and len(ip) <= 45:
                        new_ip = ip
                        break
            except Exception:
                pass
        if new_ip:
            self.public_ip = new_ip
            try:
                self.root.after(0, lambda: self.canvas.itemconfigure(self.ip_text, text=f'IP: {self.public_ip}'))
            except Exception:
                pass

    def _load_servers_thread(self, force_refresh=False):
        self.service.fetch_servers(force_refresh=force_refresh)
        self.countries = self.service.get_countries()
        try:
            self.root.after(0, self._populate_countries)
        except Exception:
            pass

    def _populate_countries(self):
        if not self.countries:
            self.selected_country_label = 'No servers found'
            self._update_dropdown_image()
            return
        if self.selected_server:
            srv_exists = any((s.get('id') == self.selected_server.get('id') for s in self.service.servers))
            if srv_exists:
                self._update_dropdown_image()
                return
            else:
                self.selected_server = None
        if not self.selected_country_code:
            c0 = self.countries[0]
            self.selected_country_code = c0['code']
        for c in self.countries:
            if c['code'] == self.selected_country_code:
                ping_str = f"{c['best_ping']}ms" if c['best_ping'] < 9000 else 'N/A'
                self.selected_country_label = f"{c['name']}   ({c['server_count']} serv. • {ping_str})"
                break
        else:
            c0 = self.countries[0]
            self.selected_country_code = c0['code']
            ping_str = f"{c0['best_ping']}ms" if c0['best_ping'] < 9000 else 'N/A'
            self.selected_country_label = f"{c0['name']}   ({c0['server_count']} serv. • {ping_str})"
        self._update_dropdown_image()

    def _on_refresh_click(self):
        self.selected_country_label = 'Updating server list...'
        self._update_dropdown_image()
        threading.Thread(target=self._load_servers_thread, args=(True,), daemon=True).start()

    def _on_restart_discord(self):
        self._update_button_image('btn_restart_disc', 140, 38, 'Restarting...', x=715, y=517, tag_group='dock')

        def run():
            success = restart_discord()
            time.sleep(1.0)
            msg = '✓ Restarted!' if success else 'Not Found'
            self.root.after(0, lambda: self._update_button_image('btn_restart_disc', 140, 38, msg, x=715, y=517, tag_group='dock'))
            time.sleep(1.8)
            self.root.after(0, lambda: self._update_button_image('btn_restart_disc', 140, 38, 'Restart Discord', x=715, y=517, tag_group='dock'))
        threading.Thread(target=run, daemon=True).start()

    def _on_toggle_connect(self):
        if self.engine.status in (STATUS_DISCONNECTED, STATUS_ERROR):
            self.canvas.itemconfigure(self.status_dot, fill='#f59e0b')
            self.canvas.itemconfigure(self.status_text, text='Connecting...')
            self.canvas.itemconfigure(self.ip_text, text='IP: Connecting...')
            self.engine.status = STATUS_CONNECTING
            self._update_connect_button()

            def async_connect():
                if self.selected_server:
                    target_srv = self.selected_server
                    country_code = target_srv.get('country_short', '')
                    country_servers = [s for s in self.service.servers if s.get('country_short') == country_code]
                    global_ranked = self.service.get_servers_ranked(probe_alive=False)
                    fallbacks = [s for s in country_servers if s.get('id') != target_srv.get('id')]
                    for gs in global_ranked:
                        if len(fallbacks) >= 2:
                            break
                        if gs.get('id') != target_srv.get('id') and gs.get('id') not in [f.get('id') for f in fallbacks]:
                            fallbacks.append(gs)
                    self.engine.connect(target_srv, mode=self.current_mode, fallback_servers=fallbacks)
                    return
                ranked = self.service.get_servers_ranked(self.selected_country_code, probe_alive=True)
                global_ranked = self.service.get_servers_ranked(probe_alive=False)
                if not ranked:
                    ranked = global_ranked
                if not ranked:
                    self.root.after(0, lambda: self._apply_status(STATUS_ERROR, 'No servers found.'))
                    return
                fallbacks = list(ranked[1:])
                for gs in global_ranked:
                    if len(fallbacks) >= 2:
                        break
                    if gs['id'] != ranked[0]['id'] and gs['id'] not in [f['id'] for f in fallbacks]:
                        fallbacks.append(gs)
                self.engine.connect(ranked[0], mode=self.current_mode, fallback_servers=fallbacks)
            threading.Thread(target=async_connect, daemon=True).start()
        else:
            self.canvas.itemconfigure(self.ip_text, text='IP: Updating...')
            self.engine.disconnect()

    def _on_status_change(self, status, msg):
        self.root.after(0, lambda: self._apply_status(status, msg))

    def _apply_status(self, status, msg):
        self._update_connect_button()
        if status == STATUS_CONNECTED:
            self.canvas.itemconfigure(self.status_dot, fill='#22c55e')
            mode_lbl = 'Entire PC' if self.engine.active_mode == 'full' else 'Discord'
            self.canvas.itemconfigure(self.status_text, text=f'Connected ({mode_lbl})')
            if self.engine.active_server:
                srv_code = self.engine.active_server.get('country_short')
                if srv_code and srv_code != self.selected_country_code:
                    self.selected_country_code = srv_code
                    for c in self.countries:
                        if c['code'] == srv_code:
                            ping_str = f"{c['best_ping']}ms" if c['best_ping'] < 9000 else 'N/A'
                            self.selected_country_label = f"{c['name']}   ({c['server_count']} serv. • {ping_str})"
                            break
                    self._update_dropdown_image()
            if self.engine.active_mode == 'discord':
                srv = self.engine.active_server
                srv_ip = srv.get('ip', '') if srv else ''
                if srv_ip:
                    self.canvas.itemconfigure(self.ip_text, text=f'IP: {srv_ip} (Discord)')
                else:
                    self.canvas.itemconfigure(self.ip_text, text='IP: Discord Active')
            else:
                self.canvas.itemconfigure(self.ip_text, text='IP: Updating...')
                threading.Thread(target=self._fast_fetch_ip, daemon=True).start()
        elif status == STATUS_CONNECTING:
            self.canvas.itemconfigure(self.status_dot, fill='#f59e0b')
            self.canvas.itemconfigure(self.status_text, text='Connecting...')
            if self.engine.active_server and self.engine.active_server.get('ip'):
                self.canvas.itemconfigure(self.ip_text, text=f"Node: {self.engine.active_server['ip']}")
            else:
                self.canvas.itemconfigure(self.ip_text, text='IP: Connecting...')
        elif status == STATUS_ERROR:
            self.canvas.itemconfigure(self.status_dot, fill='#ef4444')
            self.canvas.itemconfigure(self.status_text, text='Connection Error')
            threading.Thread(target=self._fast_fetch_ip, daemon=True).start()
        else:
            self.canvas.itemconfigure(self.status_dot, fill='#94a3b8')
            self.canvas.itemconfigure(self.status_text, text='Disconnected')
            threading.Thread(target=self._fast_fetch_ip, daemon=True).start()
        if hasattr(self, 'tray') and self.tray:
            self.tray.update_status(status, msg)

    def minimize_to_tray(self):
        self._close_popup()
        self.root.withdraw()

    def restore_from_tray(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def quit_app(self):
        self._close_popup()
        if hasattr(self, 'tray') and self.tray:
            self.tray.stop()
        if self.engine.status in (STATUS_CONNECTING, STATUS_CONNECTED):
            self.engine.disconnect()
        try:
            self.root.destroy()
        except Exception:
            pass
        sys.exit(0)
    on_close = minimize_to_tray
