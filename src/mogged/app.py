import ctypes
from ctypes import byref, c_bool, c_long, c_size_t, c_void_p, c_wchar, sizeof, Structure, WINFUNCTYPE, wintypes
import logging
import os
import sys
import tkinter as tk
from typing import Optional

from mogged.constants import APP_MUTEX_NAME
from mogged.logging_config import get_logger, setup_logging
from mogged.ui.main_window import MainWindow

logger = get_logger("App")

_mutex_handle = None

def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def elevate_admin() -> bool:
    if is_admin():
        return False
    try:
        if getattr(sys, "frozen", False):
            params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        else:
            script = os.path.abspath(sys.argv[0])
            params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{script}" {params}', None, 1
            )
        if ret > 32:
            sys.exit(0)
    except Exception as e:
        logger.error(f"Erro ao solicitar elevação de privilégios: {e}")
    return False

def ensure_single_instance() -> bool:
    global _mutex_handle
    if sys.platform != "win32":
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        _mutex_handle = kernel32.CreateMutexW(None, c_bool(True), APP_MUTEX_NAME)
        ERROR_ALREADY_EXISTS = 183
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(_mutex_handle)
            _mutex_handle = None
            return False
        return True
    except Exception:
        return True

def release_single_instance() -> None:
    global _mutex_handle
    if _mutex_handle:
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.ReleaseMutex(_mutex_handle)
            kernel32.CloseHandle(_mutex_handle)
        except Exception:
            pass
        _mutex_handle = None

def bring_existing_to_front() -> None:
    if sys.platform != "win32":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        TH32CS_SNAPPROCESS = 0x00000002

        class PROCESSENTRY32W(Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", c_wchar * 260),
            ]

        current_pid = os.getpid()
        target_pid = None

        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == c_void_p(-1).value:
            return
        try:
            pe = PROCESSENTRY32W()
            pe.dwSize = sizeof(PROCESSENTRY32W)
            if kernel32.Process32FirstW(snap, byref(pe)):
                while True:
                    if pe.szExeFile.lower() == "moggedvpn.exe" and pe.th32ProcessID != current_pid:
                        target_pid = pe.th32ProcessID
                        break
                    if not kernel32.Process32NextW(snap, byref(pe)):
                        break
        finally:
            kernel32.CloseHandle(snap)

        if target_pid is None:
            return

        SW_RESTORE = 9
        SW_SHOW = 5
        GW_OWNER = 4
        found_hwnd = None
        process_id = wintypes.DWORD()

        WNDENUMPROC = WINFUNCTYPE(c_bool, wintypes.HWND, wintypes.LPARAM)

        def _enum_cb(hwnd, _lparam):
            nonlocal found_hwnd
            user32.GetWindowThreadProcessId(hwnd, byref(process_id))
            if process_id.value == target_pid:
                if user32.GetWindow(hwnd, GW_OWNER) == 0:
                    found_hwnd = hwnd
                    return False
            return True

        user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)

        if found_hwnd:
            if user32.IsIconic(found_hwnd):
                user32.ShowWindow(found_hwnd, SW_RESTORE)
            else:
                user32.ShowWindow(found_hwnd, SW_SHOW)
            user32.SetForegroundWindow(found_hwnd)
    except Exception as e:
        logger.debug(f"Não foi possível trazer janela para a frente: {e}")

def run() -> None:
    setup_logging(level="INFO")

    try:
        from mogged.network.kill_switch import KillSwitch
        KillSwitch.cleanup()
    except Exception as e:
        logger.debug(f"Aviso ao limpar regras do KillSwitch no startup: {e}")

    if not ensure_single_instance():
        logger.info("Mogged VPN já em execução. Trazendo janela ativa para o foco...")
        bring_existing_to_front()
        sys.exit(0)

    start_hidden = "--tray" in sys.argv or "--minimized" in sys.argv
    if not start_hidden and not is_admin():
        logger.info("Solicitando permissão de Administrador...")
        release_single_instance()
        elevated = elevate_admin()
        if elevated:
            return
        if not ensure_single_instance():
            bring_existing_to_front()
            return

    root = tk.Tk()
    if start_hidden:
        root.withdraw()
    app = MainWindow(root, start_hidden=start_hidden)
    root.protocol("WM_DELETE_WINDOW", app.minimize_to_tray)
    root.mainloop()
