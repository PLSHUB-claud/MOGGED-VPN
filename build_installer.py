import os
import sys
import shutil
import zipfile
import subprocess
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, 'dist')
ZIP_BUNDLE = os.path.join(BASE_DIR, 'app_data.zip')
ICON_FILE = os.path.join(BASE_DIR, 'app_icon.ico')

def create_app_bundle():
    print('Criando pacote app_data.zip...')
    if os.path.isfile(ZIP_BUNDLE):
        os.remove(ZIP_BUNDLE)
    with zipfile.ZipFile(ZIP_BUNDLE, 'w', zipfile.ZIP_DEFLATED) as z:
        exe_src = os.path.join(DIST_DIR, 'MoggedVPN.exe')
        if os.path.isfile(exe_src):
            z.write(exe_src, 'MoggedVPN.exe')
            print('Adicionado: MoggedVPN.exe')
        for asset in ['wallpaper.png', 'app_icon.ico', 'transparent.ico', 'servers_cache.json']:
            p = os.path.join(BASE_DIR, asset)
            if os.path.isfile(p):
                z.write(p, asset)
                print(f'Adicionado: {asset}')
        bin_dir = os.path.join(BASE_DIR, 'bin')
        if os.path.isdir(bin_dir):
            for root_d, _, files in os.walk(bin_dir):
                for f in files:
                    fp = os.path.join(root_d, f)
                    rel = os.path.relpath(fp, BASE_DIR)
                    z.write(fp, rel)
                    print(f'Adicionado bin: {rel}')
    print(f'Bundle app_data.zip criado ({os.path.getsize(ZIP_BUNDLE) // 1024} KB)')

def build_setup_exe():
    create_app_bundle()
    print('Compilando MoggedVPN_Setup.exe...')
    cmd = [sys.executable, '-m', 'PyInstaller', '--name', 'MoggedVPN_Setup', '--onefile', '--noconsole', '--uac-admin', '--clean', '--icon', ICON_FILE, '--add-data', f'{ZIP_BUNDLE};.', '--add-data', f'{ICON_FILE};.', '--hidden-import', 'PIL', '--hidden-import', 'PIL.Image', '--hidden-import', 'PIL.ImageTk', '--hidden-import', 'win32com.client', '--hidden-import', 'win32com', '--hidden-import', 'pythoncom', os.path.join(BASE_DIR, 'installer.py')]
    res = subprocess.run(cmd, cwd=BASE_DIR)
    if res.returncode == 0:
        setup_exe = os.path.join(DIST_DIR, 'MoggedVPN_Setup.exe')
        print('\n' + '=' * 60)
        print('[OK] INSTALADOR GERADO COM SUCESSO!')
        print(f'Caminho do Instalador: {setup_exe}')
        print('Tamanho:', os.path.getsize(setup_exe) // (1024 * 1024), 'MB')
        print('=' * 60)
        return True
    else:
        print('Erro ao gerar o instalador.')
        return False
if __name__ == '__main__':
    build_setup_exe()
