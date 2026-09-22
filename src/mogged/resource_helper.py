import os
from pathlib import Path
import sys

def get_base_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent

def get_asset_path(filename: str) -> Path:
    candidates = [
        Path(filename),
        get_base_dir() / filename,
        Path(__file__).resolve().parent.parent.parent / filename,
        Path(sys.executable).parent / filename,
    ]
    if hasattr(sys, "_MEIPASS"):
        candidates.insert(0, Path(sys._MEIPASS) / filename)

    for cand in candidates:
        if cand.is_file():
            return cand.resolve()

    return (get_base_dir() / filename).resolve()

def get_writable_data_path(filename: str) -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
    data_dir = Path(local_appdata) / "MoggedVPN"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / filename
