from typing import Any, Dict, Optional

class MoggedError(Exception):

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.context: Dict[str, Any] = context or {}

    def to_dict(self) -> Dict[str, Any]:
        sanitized_ctx = {}
        for k, v in self.context.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ("token", "secret", "password", "key", "cert", "b64")):
                sanitized_ctx[k] = "[REDACTED]"
            else:
                sanitized_ctx[k] = str(v)
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "context": sanitized_ctx,
        }

    def __str__(self) -> str:
        return self.message

class ConfigurationError(MoggedError):
    pass

class NetworkError(MoggedError):
    pass

class VPNConnectionError(NetworkError):
    pass

class VPNDisconnectError(NetworkError):
    pass

class ServerFetchError(NetworkError):
    pass

class ServerValidationError(NetworkError):
    pass

class DNSLeakError(NetworkError):
    pass

class SecurityError(MoggedError):
    pass

class SignatureVerificationError(SecurityError):
    pass

class IntegrityCheckError(SecurityError):
    pass

class CertificateError(SecurityError):
    pass

class PrivilegeEscalationError(SecurityError):
    pass

class DiscordError(MoggedError):
    pass

class DiscordNotFoundError(DiscordError):
    pass

class DiscordRestartError(DiscordError):
    pass

class StorageError(MoggedError):
    pass

class SecureStoreError(StorageError):
    pass

class CacheCorruptionError(StorageError):
    pass

class UpdateError(MoggedError):
    pass

class UpdateDownloadError(UpdateError):
    pass

class UpdateVerificationError(UpdateError):
    pass
