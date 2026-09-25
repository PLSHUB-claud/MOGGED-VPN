import os
import sys
import shutil
import zipfile
import subprocess
import threading
import time
import winreg
import ctypes
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
try:
    import win32com.client
except Exception:
    pass
APP_NAME = 'Mogged VPN'
EXE_NAME = 'MoggedVPN.exe'

def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def get_default_install_dir():
    local_appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
    return os.path.join(local_appdata, 'Programs', 'MoggedVPN')

def get_resource_path(filename: str) -> str:
    if hasattr(sys, '_MEIPASS'):
        p = os.path.join(sys._MEIPASS, filename)
        if os.path.exists(p):
            return p
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    if os.path.exists(local):
        return local
    return filename

def make_shortcut_admin(lnk_path):
    try:
        if not os.path.isfile(lnk_path):
            return
        with open(lnk_path, 'r+b') as f:
            f.seek(0x15)
            b = f.read(1)
            if b:
                flags = ord(b) | 0x20
                f.seek(0x15)
                f.write(bytes([flags]))
    except Exception:
        pass

class InstallerApp:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title('Instalação - Mogged VPN')
        self.root.geometry('620x460')
        self.root.minsize(620, 460)
        self.root.maxsize(620, 460)
        self.root.resizable(False, False)
        self.root.configure(bg='#0a0a0f')
        self.install_dir = get_default_install_dir()
        self.create_desktop_shortcut = tk.BooleanVar(value=True)
        self.create_startmenu_shortcut = tk.BooleanVar(value=True)
        self.launch_after = tk.BooleanVar(value=True)
        self._setup_window_styling()
        self._setup_ui()
        if '--silent' in sys.argv or '--update' in sys.argv:
            self.root.after(100, self.start_installation)

    def _setup_window_styling(self):
        ico_path = get_resource_path('app_icon.ico')
        if os.path.isfile(ico_path):
            try:
                self.root.iconbitmap(default=ico_path)
            except Exception:
                try:
                    self.root.iconbitmap(ico_path)
                except Exception:
                    pass
        if sys.platform == 'win32':
            try:
                self.root.update_idletasks()
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                if not hwnd:
                    hwnd = self.root.winfo_id()
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(value), ctypes.sizeof(value))
                DWMWA_CAPTION_COLOR = 35
                color = ctypes.c_int(985610)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(color), ctypes.sizeof(color))
                DWMWA_TEXT_COLOR = 36
                text_col = ctypes.c_int(16777215)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_TEXT_COLOR, ctypes.byref(text_col), ctypes.sizeof(text_col))
            except Exception as e:
                print(f'Erro DWM: {e}')

    def _setup_ui(self):
        bottom = tk.Frame(self.root, bg='#11141f', height=60, bd=1, highlightbackground='#1e2438', highlightthickness=1)
        bottom.pack(side='bottom', fill='x')
        bottom.pack_propagate(False)
        self.btn_cancel = tk.Button(bottom, text='Cancelar', command=self.root.destroy, bg='#1e2438', fg='#94a3b8', activebackground='#2a324b', activeforeground='#ffffff', bd=0, padx=18, pady=8, font=('Segoe UI', 9, 'bold'), cursor='hand2')
        self.btn_cancel.pack(side='right', padx=(5, 20), pady=12)
        self.btn_install = tk.Button(bottom, text='Instalar Agora', command=self.start_installation, bg='#2563eb', fg='#ffffff', activebackground='#1d4ed8', activeforeground='#ffffff', bd=0, padx=24, pady=8, font=('Segoe UI', 10, 'bold'), cursor='hand2')
        self.btn_install.pack(side='right', padx=5, pady=12)
        header = tk.Frame(self.root, bg='#131722', height=85, bd=1, highlightbackground='#1e2438', highlightthickness=1)
        header.pack(side='top', fill='x')
        header.pack_propagate(False)
        self.chad_img = None
        icon_path = get_resource_path('app_icon.ico')
        if os.path.isfile(icon_path):
            try:
                im = Image.open(icon_path).resize((60, 60), Image.Resampling.LANCZOS)
                self.chad_img = ImageTk.PhotoImage(im)
                lbl_img = tk.Label(header, image=self.chad_img, bg='#131722')
                lbl_img.pack(side='right', padx=20, pady=10)
            except Exception:
                pass
        header_text_frame = tk.Frame(header, bg='#131722')
        header_text_frame.pack(side='left', padx=20, pady=12, fill='y')
        title_lbl = tk.Label(header_text_frame, text='Mogged VPN Setup', bg='#131722', fg='#38bdf8', font=('Segoe UI', 15, 'bold'))
        title_lbl.pack(anchor='w')
        sub_lbl = tk.Label(header_text_frame, text='Instalação completa e configuração de rede virtual', bg='#131722', fg='#94a3b8', font=('Segoe UI', 9))
        sub_lbl.pack(anchor='w', pady=(2, 0))
        self.body = tk.Frame(self.root, bg='#0a0a0f')
        self.body.pack(fill='both', expand=True, padx=25, pady=12)
        msg = tk.Label(self.body, text='O instalador irá configurar o Mogged VPN no seu computador, registrar o driver de rede Wintun e criar atalhos de inicialização rápida.', bg='#0a0a0f', fg='#cbd5e1', font=('Segoe UI', 9), justify='left', wraplength=570)
        msg.pack(anchor='w', pady=(0, 10))
        dir_box = tk.LabelFrame(self.body, text='  Pasta de Instalação  ', bg='#0a0a0f', fg='#60a5fa', font=('Segoe UI', 9, 'bold'), bd=1, highlightbackground='#1e2438')
        dir_box.pack(fill='x', pady=(0, 10), ipady=4)
        self.dir_entry = tk.Entry(dir_box, bg='#131722', fg='#ffffff', font=('Segoe UI', 9), insertbackground='#ffffff', bd=0, highlightbackground='#2a324b', highlightthickness=1)
        self.dir_entry.insert(0, self.install_dir)
        self.dir_entry.pack(side='left', fill='x', expand=True, padx=(10, 8), pady=6, ipady=3)
        btn_browse = tk.Button(dir_box, text='Procurar...', command=self._browse_dir, bg='#1e2438', fg='#e2e8f0', activebackground='#2a324b', activeforeground='#ffffff', bd=0, padx=12, pady=3, font=('Segoe UI', 8, 'bold'), cursor='hand2')
        btn_browse.pack(side='right', padx=(0, 10), pady=6)
        opt_frame = tk.Frame(self.body, bg='#0a0a0f')
        opt_frame.pack(fill='x', pady=(0, 8))
        chk1 = tk.Checkbutton(opt_frame, text='Criar atalho na Área de Trabalho com o ícone do Chad', variable=self.create_desktop_shortcut, bg='#0a0a0f', fg='#e2e8f0', selectcolor='#131722', activebackground='#0a0a0f', activeforeground='#ffffff', font=('Segoe UI', 9), cursor='hand2')
        chk1.pack(anchor='w', pady=1)
        chk2 = tk.Checkbutton(opt_frame, text='Adicionar ao Menu Iniciar', variable=self.create_startmenu_shortcut, bg='#0a0a0f', fg='#e2e8f0', selectcolor='#131722', activebackground='#0a0a0f', activeforeground='#ffffff', font=('Segoe UI', 9), cursor='hand2')
        chk2.pack(anchor='w', pady=1)
        chk3 = tk.Checkbutton(opt_frame, text='Abrir o Mogged VPN automaticamente ao finalizar', variable=self.launch_after, bg='#0a0a0f', fg='#38bdf8', selectcolor='#131722', activebackground='#0a0a0f', activeforeground='#38bdf8', font=('Segoe UI', 9, 'bold'), cursor='hand2')
        chk3.pack(anchor='w', pady=1)
        self.status_lbl = tk.Label(self.body, text="Clique em 'Instalar Agora' para começar.", bg='#0a0a0f', fg='#94a3b8', font=('Segoe UI', 9))
        self.status_lbl.pack(anchor='w', pady=(8, 3))
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Dark.Horizontal.TProgressbar', background='#2563eb', troughcolor='#131722', bordercolor='#1e2438', lightcolor='#2563eb', darkcolor='#2563eb')
        self.progress = ttk.Progressbar(self.body, orient='horizontal', mode='determinate', style='Dark.Horizontal.TProgressbar', length=560)
        self.progress.pack(fill='x')

    def _browse_dir(self):
        chosen = filedialog.askdirectory(initialdir=self.install_dir, title='Selecione a Pasta de Instalação')
        if chosen:
            self.install_dir = chosen
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, self.install_dir)

    def start_installation(self):
        self.btn_install.configure(state='disabled', text='Instalando...')
        self.btn_cancel.configure(state='disabled')
        self.dir_entry.configure(state='disabled')
        self.install_dir = self.dir_entry.get().strip()
        threading.Thread(target=self._run_install, daemon=True).start()

    def _run_install(self):
        try:
            if sys.platform == 'win32':
                try:
                    subprocess.run(['taskkill', '/f', '/im', EXE_NAME], capture_output=True, timeout=3)
                except Exception:
                    pass
                try:
                    subprocess.run(['taskkill', '/f', '/im', 'openvpn.exe'], capture_output=True, timeout=3)
                except Exception:
                    pass
                try:
                    subprocess.run(['powershell', '-NoProfile', '-Command', "Get-CimInstance Win32_Process -Filter \"Name = 'openvpn.exe' or Name = 'MoggedVPN.exe'\" | Invoke-CimMethod -MethodName Terminate"], capture_output=True, timeout=5)
                except Exception:
                    pass
                time.sleep(0.5)
            self._update_progress(10, 'Criando diretório de instalação...')
            os.makedirs(self.install_dir, exist_ok=True)
            bin_dir = os.path.join(self.install_dir, 'bin')
            os.makedirs(bin_dir, exist_ok=True)
            self._update_progress(30, 'Extraindo binários e assets do Mogged VPN...')
            bundle_zip = get_resource_path('app_data.zip')
            if os.path.isfile(bundle_zip):
                with zipfile.ZipFile(bundle_zip, 'r') as z:
                    z.extractall(self.install_dir)
            else:
                src_dir = os.path.dirname(os.path.abspath(__file__))
                for item in os.listdir(src_dir):
                    if item in ['__pycache__', 'build', 'dist', 'build_dist.py', 'build_exe.bat', 'generate_chad_icon.py', 'installer.py', 'build_installer.py', 'download_jdk.py']:
                        continue
                    s = os.path.join(src_dir, item)
                    d = os.path.join(self.install_dir, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s, d)
            self._update_progress(65, 'Registrando adaptadores de rede e drivers...')
            wintun_src = os.path.join(bin_dir, 'wintun.dll')
            if os.path.isfile(wintun_src):
                try:
                    sys32 = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32')
                    if os.path.isdir(sys32):
                        shutil.copy2(wintun_src, os.path.join(sys32, 'wintun.dll'))
                except Exception:
                    pass
                try:
                    wintun_lib = ctypes.CDLL(wintun_src)
                    ad = wintun_lib.WintunCreateAdapter(ctypes.c_wchar_p('MoggedVPN'), ctypes.c_wchar_p('Wintun'), None)
                    if ad:
                        wintun_lib.WintunCloseAdapter(ad)
                except Exception:
                    pass
            drivers_dir = os.path.join(bin_dir, 'drivers')
            if os.path.isdir(drivers_dir):
                for root_d, _, files in os.walk(drivers_dir):
                    for f in files:
                        if f.lower().endswith('.inf'):
                            inf_path = os.path.join(root_d, f)
                            try:
                                subprocess.run(['pnputil', '/add-driver', inf_path, '/install'], capture_output=True, timeout=15)
                            except Exception:
                                pass
            tapctl = os.path.join(bin_dir, 'tapctl.exe')
            if os.path.isfile(tapctl):
                adapter_exists = False
                try:
                    chk_all = subprocess.run(['netsh', 'interface', 'show', 'interface'], capture_output=True, text=True, timeout=5)
                    if 'MoggedVPN' in (chk_all.stdout or ''):
                        adapter_exists = True
                except Exception:
                    pass
                if not adapter_exists:
                    try:
                        chk = subprocess.run(['netsh', 'interface', 'show', 'interface', 'name=MoggedVPN'], capture_output=True, timeout=5)
                        if chk.returncode == 0:
                            adapter_exists = True
                    except Exception:
                        pass
                if not adapter_exists:
                    try:
                        chk_tap = subprocess.run([tapctl, 'list'], capture_output=True, text=True, timeout=5)
                        if 'MoggedVPN' in (chk_tap.stdout or ''):
                            adapter_exists = True
                    except Exception:
                        pass
                if not adapter_exists:
                    for tap_cmd in [
                        [tapctl, 'create', '--hwid', 'root\\tap0901', '--name', 'MoggedVPN'],
                        [tapctl, 'create', '--hwid', 'tap0901', '--name', 'MoggedVPN'],
                        [tapctl, 'create', '--name', 'MoggedVPN'],
                    ]:
                        try:
                            res = subprocess.run(tap_cmd, capture_output=True, timeout=10)
                            if res.returncode == 0:
                                break
                        except Exception:
                            pass
            target_exe = os.path.join(self.install_dir, EXE_NAME)
            if not os.path.isfile(target_exe):
                target_exe = os.path.join(self.install_dir, 'dist', 'MoggedVPN', EXE_NAME)
            if not os.path.isfile(target_exe):
                target_exe = os.path.join(self.install_dir, 'main.py')
            openvpn_exe = os.path.join(bin_dir, 'openvpn.exe')
            if sys.platform == 'win32':
                try:
                    subprocess.run(['netsh', 'advfirewall', 'firewall', 'delete', 'rule', 'name=Mogged VPN OpenVPN'], capture_output=True, timeout=3)
                    subprocess.run(['netsh', 'advfirewall', 'firewall', 'add', 'rule', 'name=Mogged VPN OpenVPN', f'program={openvpn_exe}', 'dir=out', 'action=allow', 'enable=yes'], capture_output=True, timeout=5)
                    subprocess.run(['netsh', 'advfirewall', 'firewall', 'add', 'rule', 'name=Mogged VPN OpenVPN In', f'program={openvpn_exe}', 'dir=in', 'action=allow', 'enable=yes'], capture_output=True, timeout=5)
                    subprocess.run(['netsh', 'advfirewall', 'firewall', 'add', 'rule', 'name=Mogged VPN Client', f'program={target_exe}', 'dir=out', 'action=allow', 'enable=yes'], capture_output=True, timeout=5)
                except Exception:
                    pass
            self._update_progress(80, 'Criando atalhos na Área de Trabalho e Menu Iniciar...')
            icon_file = os.path.join(self.install_dir, 'app_icon.ico')
            if not os.path.isfile(icon_file):
                icon_file = target_exe
            try:
                shell = win32com.client.Dispatch('WScript.Shell')
                if self.create_desktop_shortcut.get():
                    desktop = shell.SpecialFolders('Desktop')
                    s_path = os.path.join(desktop, 'Mogged VPN.lnk')
                    s = shell.CreateShortcut(s_path)
                    s.TargetPath = target_exe
                    s.WorkingDirectory = os.path.dirname(target_exe)
                    s.IconLocation = icon_file
                    s.Description = 'Mogged VPN Client'
                    s.Save()
                    make_shortcut_admin(s_path)
                if self.create_startmenu_shortcut.get():
                    start_menu = shell.SpecialFolders('Programs')
                    sm_dir = os.path.join(start_menu, 'Mogged VPN')
                    os.makedirs(sm_dir, exist_ok=True)
                    s_path = os.path.join(sm_dir, 'Mogged VPN.lnk')
                    s = shell.CreateShortcut(s_path)
                    s.TargetPath = target_exe
                    s.WorkingDirectory = os.path.dirname(target_exe)
                    s.IconLocation = icon_file
                    s.Description = 'Mogged VPN Client'
                    s.Save()
                    make_shortcut_admin(s_path)
            except Exception as e:
                print(f'Aviso ao criar atalhos: {e}')
            self._update_progress(95, 'Registrando no Windows...')
            self._register_uninstall(target_exe, icon_file)
            self._update_progress(100, 'Instalação concluída com sucesso!')
            time.sleep(0.4)
            if self.launch_after.get() and os.path.isfile(target_exe):
                try:
                    subprocess.Popen([target_exe], cwd=os.path.dirname(target_exe))
                except Exception:
                    pass
            if '--silent' not in sys.argv:
                self.root.after(0, lambda: messagebox.showinfo('Mogged VPN', 'O Mogged VPN foi instalado com sucesso!\nO atalho com o ícone do Chad já está disponível na Área de Trabalho.'))
            self.root.after(0, self.root.destroy)
        except Exception as e:
            if '--silent' in sys.argv or '--update' in sys.argv:
                self.root.after(0, self.root.destroy)
            else:
                self.root.after(0, lambda: messagebox.showerror('Erro na Instalação', f'Ocorreu um erro durante a instalação:\n{e}'))
                self.root.after(0, lambda: self.btn_install.configure(state='normal', text='Instalar Agora'))
                self.root.after(0, lambda: self.btn_cancel.configure(state='normal'))

    def _register_uninstall(self, target_exe, icon_file):
        try:
            key_path = 'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\MoggedVPN'
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, 'DisplayName', 0, winreg.REG_SZ, 'Mogged VPN')
                winreg.SetValueEx(key, 'DisplayIcon', 0, winreg.REG_SZ, icon_file)
                winreg.SetValueEx(key, 'DisplayVersion', 0, winreg.REG_SZ, '1.1.0')
                winreg.SetValueEx(key, 'Publisher', 0, winreg.REG_SZ, 'Mogged Security')
                winreg.SetValueEx(key, 'InstallLocation', 0, winreg.REG_SZ, self.install_dir)
                uninst_cmd = f'powershell.exe -NoProfile -Command "Stop-Process -Name MoggedVPN -Force -ErrorAction SilentlyContinue; Remove-Item -Recurse -Force \'{self.install_dir}\' -ErrorAction SilentlyContinue; Remove-Item -Force (Join-Path ([Environment]::GetFolderPath(\'Desktop\')) \'Mogged VPN.lnk\') -ErrorAction SilentlyContinue; Remove-Item -Force (Join-Path ([Environment]::GetFolderPath(\'CommonDesktopDirectory\')) \'Mogged VPN.lnk\') -ErrorAction SilentlyContinue; Remove-Item -Recurse -Force (Join-Path ([Environment]::GetFolderPath(\'Programs\')) \'Mogged VPN\') -ErrorAction SilentlyContinue; Remove-Item -Force (Join-Path ([Environment]::GetFolderPath(\'Programs\')) \'Mogged VPN.lnk\') -ErrorAction SilentlyContinue; Remove-Item -Recurse -Force (Join-Path ([Environment]::GetFolderPath(\'CommonPrograms\')) \'Mogged VPN\') -ErrorAction SilentlyContinue; Remove-Item -Path \'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\MoggedVPN\' -Recurse -Force -ErrorAction SilentlyContinue"'
                winreg.SetValueEx(key, 'UninstallString', 0, winreg.REG_SZ, uninst_cmd)
        except Exception:
            pass

    def _update_progress(self, val, msg):

        def ui():
            self.progress['value'] = val
            self.status_lbl.configure(text=msg)
        self.root.after(0, ui)

def main():
    root = tk.Tk()
    app = InstallerApp(root)
    root.mainloop()
if __name__ == '__main__':
    main()
