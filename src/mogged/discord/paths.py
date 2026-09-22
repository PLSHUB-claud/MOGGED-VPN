import glob
import os
from pathlib import Path
from typing import Optional

def find_discord_executable() -> Optional[Path]:
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if not local_appdata:
        return None

    update_exe = Path(local_appdata) / "Discord" / "Update.exe"
    if update_exe.is_file():
        return update_exe

    pattern = str(Path(local_appdata) / "Discord" / "app-*" / "Discord.exe")
    matches = glob.glob(pattern)
    if matches:
        matches.sort(reverse=True)
        return Path(matches[0])

    return None
