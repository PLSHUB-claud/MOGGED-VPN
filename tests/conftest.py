"""Configurações globais de fixtures e ambiente de testes do MOGGED-VPN."""

import os
from pathlib import Path
import sys
import pytest

# Assegurar que 'src' está no sys.path durante a execução do pytest
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
