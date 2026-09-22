"""Testes unitários para o armazenamento seguro com DPAPI e backup."""

from pathlib import Path
from mogged.storage.secure_store import SecureStore


def test_secure_store_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    store = SecureStore("test_pref.dat")

    data = {"mode": "discord", "last_server": "US-Node", "favorite": True}
    store.save(data)

    loaded = store.load()
    assert loaded == data


def test_secure_store_backup_recovery(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    store = SecureStore("recover_test.dat")

    initial_data = {"v": 1}
    store.save(initial_data)

    second_data = {"v": 2}
    store.save(second_data)

    # Simular corrupção ou remoção do arquivo principal
    assert store.store_path.is_file()
    assert store.backup_path.is_file()

    store.store_path.unlink()

    # O carregamento deve restaurar do backup
    recovered = store.load()
    assert recovered == initial_data
    assert store.store_path.is_file()
