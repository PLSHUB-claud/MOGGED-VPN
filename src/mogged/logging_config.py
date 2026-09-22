import logging
from logging.handlers import RotatingFileHandler
import os
import re
import sys
from typing import Optional

_IP_PATTERN = re.compile(r"\b(?!(?:127\.0\.0\.1|0\.0\.0\.0)\b)(?:\d{1,3}\.){3}\d{1,3}\b")
_CERT_PATTERN = re.compile(
    r"-----BEGIN [A-Z ]+-----[^-]+-----END [A-Z ]+-----", re.DOTALL | re.MULTILINE
)
_TOKEN_PATTERN = re.compile(
    r"(?:token|secret|password|key|auth|bearer)[\s:=]+['\"]?([A-Za-z0-9_\-\.]{8,})['\"]?",
    re.IGNORECASE,
)

def redact_sensitive(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)

    text = _CERT_PATTERN.sub("[REDACTED_CERTIFICATE]", text)

    text = _TOKEN_PATTERN.sub(lambda m: m.group(0).replace(m.group(1), "[REDACTED]"), text)

    text = _IP_PATTERN.sub("[REDACTED_IP]", text)

    user = os.environ.get("USERNAME") or os.environ.get("USER")
    if user and len(user) > 1:
        text = re.sub(re.escape(user), "[USER]", text, flags=re.IGNORECASE)

    return text

class SensitiveDataFilter(logging.Filter):

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact_sensitive(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(redact_sensitive(str(arg)) for arg in record.args)
        return True

def get_log_directory() -> str:
    local_appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    log_dir = os.path.join(local_appdata, "MoggedVPN", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir

def setup_logging(level: str = "INFO", dev_mode: bool = False) -> None:
    log_dir = get_log_directory()
    log_file = os.path.join(log_dir, "mogged_vpn.log")

    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sensitive_filter = SensitiveDataFilter()

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(sensitive_filter)
    root_logger.addHandler(file_handler)

    if dev_mode or not getattr(sys, "frozen", False):
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        stream_handler.addFilter(sensitive_filter)
        root_logger.addHandler(stream_handler)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"Mogged.{name}")
