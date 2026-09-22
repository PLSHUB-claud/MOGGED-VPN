import hashlib
import hmac
import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import Dict, Optional

from mogged.exceptions import IntegrityCheckError, SignatureVerificationError

logger = logging.getLogger("Mogged.Security.BinaryVerify")

KNOWN_BINARY_HASHES: Dict[str, str] = {
    "openvpn.exe": "048c3504f9d139bbc08e30f8d81e034d208cae3212a5ecbd9b5e77f2494de525",
    "wintun.dll": "e5da8447dc2c320edc0fc52fa01885c103de8c118481f683643cacc3220dafce",
    "libcrypto-3-x64.dll": "8034c4e604205db3591e4c7bb377476479158b1971863602c73d3b2368f27688",
    "libssl-3-x64.dll": "ddd8c342bc45eb641b64f3ef72b85426333755c6c7c26c3077d6d33004552b14",
    "libopenvpn_plap.dll": "33acb131e751a7e817c6a9396092e4e7437372bb720430276f5fe81c65080962",
    "libpkcs11-helper-1.dll": "9a7938fe6d86bad653db6d1db8aa4f6b984ea9cfee998c686a82578d4f0d81fc",
    "tapctl.exe": "f1eae4b5306be504b3ffca66426ce0f2fadb6d95a0f1ee9b1327873491c2837d",
    "vcruntime140.dll": "c51c64dfb7c445ecf0001f69c27e13299ddcfba0780efa72b866a7487b7491c7",
}

def calculate_sha256(file_path: Path) -> str:
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()

def verify_sha256(file_path: Path, expected_hash: str) -> bool:
    if not file_path.is_file():
        raise IntegrityCheckError(f"Arquivo não encontrado para verificação: {file_path}")

    actual_hash = calculate_sha256(file_path)
    if not hmac.compare_digest(actual_hash.lower(), expected_hash.lower()):
        raise IntegrityCheckError(
            f"Hash SHA-256 divergente para {file_path.name}. "
            f"Esperado: {expected_hash}, Obtido: {actual_hash}",
            context={"file": file_path.name, "expected": expected_hash, "actual": actual_hash},
        )
    return True

def verify_authenticode_signature(
    file_path: Path, expected_publisher: Optional[str] = None
) -> bool:
    if sys.platform != "win32":
        return True

    if not file_path.is_file():
        raise SignatureVerificationError(f"Arquivo ausente: {file_path}")

    script = (
        f"$sig = Get-AuthenticodeSignature -FilePath '{file_path.resolve()}'; "
        f"$signer = if ($sig.SignerCertificate) {{ $sig.SignerCertificate.Subject }} else {{ '' }}; "
        f"$sig.Status.ToString() + '|' + $signer"
    )

    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        script,
    ]

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        out = res.stdout.strip()
        parts = out.split("|", 1)
        status = parts[0].strip() if parts else ""
        signer = parts[1].strip() if len(parts) > 1 else ""

        if status != "Valid":
            logger.warning(f"Assinatura de {file_path.name} retornou status: {status}")
            return False

        if expected_publisher:
            if expected_publisher.lower() not in signer.lower():
                logger.warning(
                    f"Publisher de {file_path.name} ('{signer}') não corresponde ao esperado ('{expected_publisher}')"
                )
                return False

        return True
    except Exception as e:
        logger.warning(f"Erro ao validar Authenticode em {file_path.name}: {e}")
        return False

class BinaryVerifier:

    def __init__(self, manifest: Optional[Dict[str, str]] = None) -> None:
        self.manifest = manifest or KNOWN_BINARY_HASHES
        self._verified_cache: Dict[str, bool] = {}

    def verify_file(self, file_path: Path) -> bool:
        resolved = str(file_path.resolve())
        if self._verified_cache.get(resolved):
            return True

        filename = file_path.name.lower()
        if filename not in self.manifest:
            logger.warning(f"Arquivo {filename} não listado no manifesto oficial.")
            return False

        expected_hash = self.manifest[filename]
        verify_sha256(file_path, expected_hash)
        self._verified_cache[resolved] = True
        return True

    def verify_directory(self, bin_dir: Path) -> bool:
        for filename in self.manifest:
            target = bin_dir / filename
            if target.is_file():
                self.verify_file(target)
        return True
