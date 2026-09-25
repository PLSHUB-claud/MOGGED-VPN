import json
import logging
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Dict, Optional

from mogged.exceptions import SecureStoreError

logger = logging.getLogger("Mogged.Storage.SecureStore")

def dpapi_protect(data_bytes: bytes) -> bytes:
    if sys.platform != "win32":
        return data_bytes

    try:
        import win32crypt

        return win32crypt.CryptProtectData(data_bytes, "MoggedVPN_SecureStore", None, None, None, 0)
    except Exception as e:
        logger.error(f"Erro ao criptografar via DPAPI: {e}")
        raise SecureStoreError(f"Falha na proteção DPAPI: {e}")

def dpapi_unprotect(encrypted_bytes: bytes) -> bytes:
    if sys.platform != "win32":
        return encrypted_bytes

    try:
        import win32crypt

        _, data = win32crypt.CryptUnprotectData(encrypted_bytes, None, None, None, 0)
        return data
    except Exception as e:
        logger.error(f"Erro ao descriptografar via DPAPI: {e}")
        raise SecureStoreError(f"Falha na descriptografia DPAPI: {e}")

class SecureStore:

    def __init__(self, filename: str = "preferences.dat") -> None:
        local_appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        self.store_dir = Path(local_appdata) / "MoggedVPN" / "secure"
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.store_path = self.store_dir / filename
        self.backup_path = self.store_dir / f"{filename}.bak"

    def save(self, data: Dict[str, Any]) -> None:
        try:
            raw_json = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            encrypted = dpapi_protect(raw_json)

            if self.store_path.is_file():
                shutil.copy2(self.store_path, self.backup_path)

            temp_file = self.store_path.with_suffix(".tmp")
            with open(temp_file, "wb") as f:
                f.write(encrypted)
            temp_file.replace(self.store_path)
            logger.debug("Armazenamento seguro atualizado com sucesso.")
        except Exception as e:
            logger.error(f"Falha ao salvar dados seguros: {e}")
            raise SecureStoreError(f"Erro ao salvar armazenamento seguro: {e}")

    def load(self) -> Dict[str, Any]:
        if not self.store_path.is_file():
            if self.backup_path.is_file():
                logger.warning("Arquivo principal ausente. Tentando recuperar de backup.")
                shutil.copy2(self.backup_path, self.store_path)
            else:
                return {}

        try:
            with open(self.store_path, "rb") as f:
                encrypted = f.read()
            raw_json = dpapi_unprotect(encrypted)
            return json.loads(raw_json.decode("utf-8"))
        except Exception as e:
            logger.warning(f"Erro ao ler arquivo seguro ({e}). Tentando restaurar backup.")
            if self.backup_path.is_file():
                try:
                    with open(self.backup_path, "rb") as f:
                        raw_json = dpapi_unprotect(f.read())
                    recovered = json.loads(raw_json.decode("utf-8"))
                    shutil.copy2(self.backup_path, self.store_path)
                    return recovered
                except Exception as ex_bak:
                    logger.error(f"Falha ao restaurar backup: {ex_bak}")
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        try:
            data = self.load()
            return data.get(key, default)
        except Exception:
            return default

    def set(self, key: str, value: Any) -> None:
        try:
            data = self.load()
            data[key] = value
            self.save(data)
        except Exception as e:
            logger.warning(f"Erro ao salvar chave {key} no SecureStore: {e}")
