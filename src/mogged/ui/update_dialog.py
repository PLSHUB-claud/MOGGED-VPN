import logging
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, Optional
import webbrowser

from mogged.constants import APP_VERSION
from mogged.updates.updater import Updater

logger = logging.getLogger("Mogged.UI.UpdateDialog")

class UpdateDialog:

    def __init__(self, parent: tk.Tk, update_info: Dict[str, Any], app_controller: Any = None) -> None:
        self.parent = parent
        self.update_info = update_info
        self.app = app_controller
        self.top = tk.Toplevel(parent)
        self.top.title("Atualização Disponível")
        self.top.geometry("520x360")
        self.top.minsize(520, 360)
        self.top.maxsize(520, 360)
        self.top.resizable(False, False)
        self.top.configure(bg="#0c0e14")
        self.top.transient(parent)
        self.top.grab_set()

        self._is_downloading = False
        self._updater = Updater()

        self._setup_window()
        self._build_ui()
        self._center_window()

    def _setup_window(self) -> None:
        from mogged.resource_helper import get_asset_path
        ico = get_asset_path("app_icon.ico")
        if ico.is_file():
            try:
                self.top.iconbitmap(str(ico))
            except Exception:
                pass

        if sys.platform == "win32":
            try:
                self.top.update_idletasks()
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(self.top.winfo_id()) or self.top.winfo_id()
                dark = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(dark), ctypes.sizeof(dark))
            except Exception:
                pass

    def _center_window(self) -> None:
        self.top.update_idletasks()
        pw = self.parent.winfo_width()
        ph = self.parent.winfo_height()
        px = self.parent.winfo_x()
        py = self.parent.winfo_y()
        w = 520
        h = 360
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.top.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    def _build_ui(self) -> None:
        header = tk.Frame(self.top, bg="#131722", height=65, highlightbackground="#1e2438", highlightthickness=1)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        title_lbl = tk.Label(
            header,
            text="Nova Versão do Mogged VPN Disponível!",
            bg="#131722",
            fg="#38bdf8",
            font=("Segoe UI", 12, "bold"),
        )
        title_lbl.pack(anchor="w", padx=20, pady=(12, 2))

        new_ver = self.update_info.get("version", "")
        sub_lbl = tk.Label(
            header,
            text=f"Versão atual: v{APP_VERSION}  ->  Nova versão: {new_ver}",
            bg="#131722",
            fg="#94a3b8",
            font=("Segoe UI", 9),
        )
        sub_lbl.pack(anchor="w", padx=20)

        body = tk.Frame(self.top, bg="#0c0e14")
        body.pack(fill="both", expand=True, padx=20, pady=12)

        notes_title = tk.Label(
            body,
            text="Notas de Lançamento:",
            bg="#0c0e14",
            fg="#cbd5e1",
            font=("Segoe UI", 9, "bold"),
        )
        notes_title.pack(anchor="w", pady=(0, 4))

        notes_box = tk.Text(
            body,
            bg="#131722",
            fg="#e2e8f0",
            font=("Segoe UI", 9),
            height=6,
            bd=0,
            highlightbackground="#1e2438",
            highlightthickness=1,
            wrap="word",
        )
        notes = self.update_info.get("release_notes", "") or "Melhorias gerais e correções de estabilidade."
        notes_box.insert("1.0", notes)
        notes_box.configure(state="disabled")
        notes_box.pack(fill="x", pady=(0, 10))

        self.status_lbl = tk.Label(
            body,
            text="Clique em 'Atualizar Agora' para baixar e instalar automaticamente.",
            bg="#0c0e14",
            fg="#94a3b8",
            font=("Segoe UI", 8),
        )
        self.status_lbl.pack(anchor="w", pady=(0, 4))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Update.Horizontal.TProgressbar",
            background="#2563eb",
            troughcolor="#131722",
            bordercolor="#1e2438",
            lightcolor="#2563eb",
            darkcolor="#2563eb",
        )
        self.progress = ttk.Progressbar(
            body,
            orient="horizontal",
            mode="determinate",
            style="Update.Horizontal.TProgressbar",
            length=480,
        )
        self.progress.pack(fill="x", pady=(0, 10))

        bottom = tk.Frame(self.top, bg="#0c0e14")
        bottom.pack(side="bottom", fill="x", padx=20, pady=(0, 14))

        self.btn_later = tk.Button(
            bottom,
            text="Mais Tarde",
            command=self.top.destroy,
            bg="#1e2438",
            fg="#94a3b8",
            activebackground="#2a324b",
            activeforeground="#ffffff",
            bd=0,
            padx=16,
            pady=6,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )
        self.btn_later.pack(side="right", padx=(8, 0))

        self.btn_update = tk.Button(
            bottom,
            text="Atualizar Agora",
            command=self._start_download,
            bg="#2563eb",
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            bd=0,
            padx=20,
            pady=6,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )
        self.btn_update.pack(side="right")

    def _start_download(self) -> None:
        if self._is_downloading:
            return
        self._is_downloading = True
        self.btn_update.configure(state="disabled", text="Baixando...")
        self.btn_later.configure(state="disabled")
        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self) -> None:
        download_url = self.update_info.get("download_url", "")
        sha256 = self.update_info.get("sha256", "")
        html_url = self.update_info.get("html_url", "")

        def _update_ui(pct: int, text: str) -> None:
            self.progress["value"] = pct
            self.status_lbl.configure(text=text)

        try:
            self.top.after(0, lambda: _update_ui(5, "Iniciando download da nova versão..."))

            def _on_progress(pct: int, downloaded: int) -> None:
                mb = downloaded / (1024 * 1024)
                self.top.after(0, lambda: _update_ui(pct, f"Baixando atualização: {pct}% ({mb:.1f} MB)..."))

            setup_path = self._updater.download_and_verify(
                asset_url=download_url,
                expected_sha256=sha256 if sha256 else None,
                progress_callback=_on_progress,
            )

            self.top.after(0, lambda: _update_ui(100, "Download concluído! Iniciando instalador..."))
            time.sleep(0.6)

            if sys.platform == "win32":
                subprocess.Popen([str(setup_path)], shell=False)  # nosec B603
            else:
                subprocess.Popen([str(setup_path)])

            if self.app and hasattr(self.app, "quit_app"):
                self.top.after(300, self.app.quit_app)
            else:
                self.top.after(300, self.top.destroy)

        except Exception as e:
            logger.error(f"Erro ao baixar atualização: {e}")
            msg = f"Falha ao baixar atualização automaticamente ({e}). Abrindo navegador para download manual..."
            self.top.after(0, lambda: _update_ui(0, msg))
            if html_url:
                webbrowser.open(html_url)
            self.top.after(0, lambda: self.btn_update.configure(state="normal", text="Tentar Novamente"))
            self.top.after(0, lambda: self.btn_later.configure(state="normal"))
            self._is_downloading = False
