import os
import sys

def get_base_dir() -> str:
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_asset_path(filename: str) -> str:
    base = get_base_dir()
    p = os.path.join(base, filename)
    if os.path.exists(p):
        return p
    if getattr(sys, 'frozen', False):
        p2 = os.path.join(os.path.dirname(sys.executable), filename)
        if os.path.exists(p2):
            return p2
    if os.path.exists(filename):
        return os.path.abspath(filename)
    return p

def get_writable_data_path(filename: str) -> str:
    if getattr(sys, 'frozen', False):
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        data_dir = os.path.join(appdata, 'MoggedVPN')
        try:
            os.makedirs(data_dir, exist_ok=True)
            return os.path.join(data_dir, filename)
        except Exception:
            pass
    return os.path.join(get_base_dir(), filename)
