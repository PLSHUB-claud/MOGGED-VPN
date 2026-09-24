import os
import sys
import shutil
import subprocess
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_SCRIPT = os.path.join(BASE_DIR, 'main.py')
ICON_FILE = os.path.join(BASE_DIR, 'app_icon.ico')
APP_NAME = 'MoggedVPN'
DATA_FILES = [('wallpaper.png', '.'), ('transparent.ico', '.'), ('app_icon.ico', '.'), ('servers_cache.json', '.'), ('bin', 'bin')]
HIDDEN_IMPORTS = [
    'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL.ImageDraw', 'PIL.ImageFilter', 'PIL.ImageFont',
    'pystray', 'pystray._win32', 'win32gui', 'win32ui', 'win32con', 'winreg', 'ctypes',
    'urllib.request', 'json', 'logging', 'csv', 'base64', 'ipaddress', 'subprocess',
    'threading', 'queue', 're', 'tempfile', 'psutil', 'cryptography',
    'mogged', 'mogged.app', 'mogged.constants', 'mogged.exceptions', 'mogged.logging_config',
    'mogged.resource_helper', 'mogged.discord', 'mogged.discord.paths', 'mogged.discord.process_manager',
    'mogged.network', 'mogged.network.dns_manager', 'mogged.network.kill_switch',
    'mogged.network.openvpn_backend', 'mogged.network.server_fetcher', 'mogged.network.server_validator',
    'mogged.network.split_tunnel', 'mogged.network.vpn_backend', 'mogged.network.vpn_manager',
    'mogged.network.wireguard_backend', 'mogged.security', 'mogged.security.binary_verify',
    'mogged.storage', 'mogged.storage.secure_store', 'mogged.ui', 'mogged.ui.main_window',
    'mogged.ui.tray', 'mogged.updates', 'mogged.updates.updater',
]

def clean_previous_builds():
    for folder in ['build', 'dist']:
        path = os.path.join(BASE_DIR, folder)
        if os.path.isdir(path):
            print(f'Limpando pasta anterior: {folder}/')
            shutil.rmtree(path, ignore_errors=True)
    spec = os.path.join(BASE_DIR, f'{APP_NAME}.spec')
    if os.path.isfile(spec):
        os.remove(spec)

def build_executable(onefile=False):
    clean_previous_builds()
    cmd = [sys.executable, '-m', 'PyInstaller', '--name', APP_NAME, '--noconsole', '--uac-admin', '--clean']
    cmd.extend(['--paths', os.path.join(BASE_DIR, 'src')])
    if onefile:
        cmd.append('--onefile')
    else:
        cmd.append('--onedir')
    if os.path.isfile(ICON_FILE):
        cmd.extend(['--icon', ICON_FILE])
    for src, dst in DATA_FILES:
        src_path = os.path.join(BASE_DIR, src)
        if os.path.exists(src_path):
            cmd.extend(['--add-data', f'{src_path};{dst}'])
    for imp in HIDDEN_IMPORTS:
        cmd.extend(['--hidden-import', imp])
    cmd.append(MAIN_SCRIPT)
    print('=' * 60)
    print(f'Iniciando compilação do {APP_NAME}...')
    print(f"Modo: {('Arquivo único (.exe)' if onefile else 'Pasta portátil otimizada')}")
    print('=' * 60)
    res = subprocess.run(cmd, cwd=BASE_DIR)
    if res.returncode == 0:
        print('\n' + '=' * 60)
        print('[OK] COMPILACAO CONCLUIDA COM SUCESSO!')
        if onefile:
            target = os.path.join(BASE_DIR, 'dist', f'{APP_NAME}.exe')
            print(f'Executável gerado em: {target}')
        else:
            target = os.path.join(BASE_DIR, 'dist', APP_NAME)
            print(f'Pasta do aplicativo gerada em: {target}')
            print(f"Executável principal: {os.path.join(target, f'{APP_NAME}.exe')}")
        print('Código-fonte protegido e empacotado para distribuição.')
        print('=' * 60)
        return True
    else:
        print('\nErro durante a compilação.')
        return False
if __name__ == '__main__':
    is_onefile = '--onefile' in sys.argv
    build_executable(onefile=is_onefile)
