"""Testes unitários para DiscordProcessManager e find_discord_executable.

Todos os testes de processo são executados com mocks; nenhum processo real
do Discord é iniciado, encerrado ou consultado.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mogged.discord.paths import find_discord_executable
from mogged.discord.process_manager import DiscordProcessManager
from mogged.exceptions import DiscordNotFoundError, DiscordRestartError


# ---------------------------------------------------------------------------
# find_discord_executable — Descoberta do executável
# ---------------------------------------------------------------------------


def test_find_discord_executable_returns_none_without_localappdata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem LOCALAPPDATA definido, a função deve retornar None."""
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    result = find_discord_executable()
    assert result is None


def test_find_discord_executable_prefers_update_exe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Quando Update.exe existe, deve ser retornado com prioridade."""
    discord_dir = tmp_path / "Discord"
    discord_dir.mkdir()
    update_exe = discord_dir / "Update.exe"
    update_exe.write_bytes(b"MZ")

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    result = find_discord_executable()
    assert result == update_exe


def test_find_discord_executable_fallback_to_versioned_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem Update.exe, deve localizar Discord.exe no subdiretório app-*."""
    discord_dir = tmp_path / "Discord" / "app-1.0.9999"
    discord_dir.mkdir(parents=True)
    discord_exe = discord_dir / "Discord.exe"
    discord_exe.write_bytes(b"MZ")

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    result = find_discord_executable()
    assert result == discord_exe


def test_find_discord_executable_returns_none_when_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    result = find_discord_executable()
    assert result is None


# ---------------------------------------------------------------------------
# DiscordProcessManager.is_running — Detecção de processo
# ---------------------------------------------------------------------------


def test_is_running_returns_false_on_non_windows() -> None:
    with patch("sys.platform", "linux"):
        result = DiscordProcessManager.is_running()
    assert result is False


@pytest.mark.skipif(sys.platform != "win32", reason="tasklist é específico do Windows")
def test_is_running_returns_true_when_discord_in_output() -> None:
    with patch("subprocess.check_output", return_value="Discord.exe  1234  Console"):
        result = DiscordProcessManager.is_running()
    assert result is True


@pytest.mark.skipif(sys.platform != "win32", reason="tasklist é específico do Windows")
def test_is_running_returns_false_when_discord_not_in_output() -> None:
    with patch("subprocess.check_output", return_value="No tasks are running with the specified criteria."):
        result = DiscordProcessManager.is_running()
    assert result is False


@pytest.mark.skipif(sys.platform != "win32", reason="tasklist é específico do Windows")
def test_is_running_returns_false_on_subprocess_exception() -> None:
    with patch("subprocess.check_output", side_effect=OSError("acesso negado")):
        result = DiscordProcessManager.is_running()
    assert result is False


@pytest.mark.skipif(sys.platform != "win32", reason="tasklist é específico do Windows")
def test_is_running_uses_no_shell_true() -> None:
    """check_output não deve usar shell=True."""
    with patch("subprocess.check_output", return_value="") as mock_co:
        DiscordProcessManager.is_running()

    for call in mock_co.call_args_list:
        assert call.kwargs.get("shell") is not True


# ---------------------------------------------------------------------------
# DiscordProcessManager.restart — Reinicialização
# ---------------------------------------------------------------------------


def test_restart_raises_discord_not_found_when_no_executable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """restart() deve lançar DiscordNotFoundError quando o executável não existe."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    with patch.object(DiscordProcessManager, "close_gracefully", return_value=True):
        with pytest.raises(DiscordNotFoundError):
            DiscordProcessManager.restart()


@pytest.mark.skipif(sys.platform != "win32", reason="Popen com CREATE_NO_WINDOW é Windows-only")
def test_restart_raises_discord_restart_error_on_popen_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Se Popen falhar, restart() deve lançar DiscordRestartError."""
    discord_dir = tmp_path / "Discord"
    discord_dir.mkdir()
    update_exe = discord_dir / "Update.exe"
    update_exe.write_bytes(b"MZ")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    with patch.object(DiscordProcessManager, "close_gracefully", return_value=True):
        with patch("subprocess.Popen", side_effect=OSError("permissão negada")):
            with pytest.raises(DiscordRestartError):
                DiscordProcessManager.restart()


@pytest.mark.skipif(sys.platform != "win32", reason="Popen com CREATE_NO_WINDOW é Windows-only")
def test_restart_uses_update_exe_with_processstart_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quando Update.exe é encontrado, deve chamar com --processStart Discord.exe."""
    discord_dir = tmp_path / "Discord"
    discord_dir.mkdir()
    update_exe = discord_dir / "Update.exe"
    update_exe.write_bytes(b"MZ")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    with patch.object(DiscordProcessManager, "close_gracefully", return_value=True):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            result = DiscordProcessManager.restart()

    assert result is True
    cmd = mock_popen.call_args.args[0]
    assert "--processStart" in cmd
    assert "Discord.exe" in cmd
    # Garantir que não usou shell=True
    assert mock_popen.call_args.kwargs.get("shell") is not True
