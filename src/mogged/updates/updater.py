import hashlib
import json
import logging
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Dict, Optional, Tuple
import urllib.request

from mogged.constants import APP_VERSION
from mogged.exceptions import UpdateDownloadError, UpdateVerificationError
from mogged.security.binary_verify import calculate_sha256, verify_authenticode_signature

logger = logging.getLogger("Mogged.Updates.Updater")

MAX_UPDATE_SIZE_BYTES = 100 * 1024 * 1024

def parse_semver(version_str: str) -> Tuple[int, int, int]:
    clean = version_str.lstrip("vV").strip()
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", clean)
    if not match:
        raise ValueError(f"Formato semver inválido: {version_str}")
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))

def is_newer_version(current_ver: str, candidate_ver: str) -> bool:
    try:
        return parse_semver(candidate_ver) > parse_semver(current_ver)
    except ValueError:
        return False

class Updater:

    def __init__(
        self,
        repo_owner: str = "mogged-vpn",
        repo_name: str = "mogged-vpn",
        expected_publisher: Optional[str] = "Mogged Security",
    ) -> None:
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.expected_publisher = expected_publisher
        self.api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"

    def check_for_updates(self) -> Optional[Dict[str, Any]]:
        try:
            req = urllib.request.Request(
                self.api_url,
                headers={
                    "User-Agent": f"MoggedVPN-Updater/{APP_VERSION}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
                data = json.loads(resp.read().decode("utf-8"))

            tag_name = data.get("tag_name", "")
            if is_newer_version(APP_VERSION, tag_name):
                logger.info(f"Nova versão identificada: {tag_name} (atual: {APP_VERSION})")
                return {
                    "version": tag_name,
                    "release_notes": data.get("body", ""),
                    "assets": data.get("assets", []),
                    "html_url": data.get("html_url", ""),
                }
            return None
        except Exception as e:
            logger.debug(f"Erro ao verificar atualizações: {e}")
            return None

    def download_and_verify(
        self,
        asset_url: str,
        expected_sha256: str,
        target_dir: Optional[Path] = None,
    ) -> Path:
        if not asset_url.startswith("https://"):
            raise UpdateDownloadError("Downloads de atualização devem utilizar estritamente HTTPS.")

        fd, temp_path_str = tempfile.mkstemp(suffix=".exe", prefix="mogged_upd_")
        temp_path = Path(temp_path_str)

        try:
            req = urllib.request.Request(
                asset_url,
                headers={"User-Agent": f"MoggedVPN-Updater/{APP_VERSION}"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310
                total_downloaded = 0
                sha = hashlib.sha256()

                with os.fdopen(fd, "wb") as f:
                    while chunk := resp.read(65536):
                        total_downloaded += len(chunk)
                        if total_downloaded > MAX_UPDATE_SIZE_BYTES:
                            raise UpdateDownloadError("Tamanho do instalador excedeu o limite de 100MB.")
                        sha.update(chunk)
                        f.write(chunk)

            computed_hash = sha.hexdigest().lower()
            if computed_hash != expected_sha256.lower().strip():
                raise UpdateVerificationError(
                    f"Hash SHA-256 do instalador diverge do publicado. Esperado: {expected_sha256}, Obtido: {computed_hash}"
                )

            if self.expected_publisher and sys.platform == "win32":
                is_valid_sig = verify_authenticode_signature(
                    temp_path, expected_publisher=self.expected_publisher
                )
                if not is_valid_sig:
                    raise UpdateVerificationError("Assinatura digital do instalador é inválida ou não confiável.")

            logger.info(f"Instalador baixado e verificado com sucesso: {temp_path}")
            return temp_path

        except Exception as e:
            if temp_path.is_file():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            if isinstance(e, (UpdateDownloadError, UpdateVerificationError)):
                raise
            raise UpdateDownloadError(f"Falha ao transferir atualização: {e}")
