"""Testes unitários para KillSwitch — ativação/desativação no Windows Firewall.

Testes que invocam netsh são executados com mocks para evitar modificações
reais nas regras de firewall. Testes que exigem Windows são marcados com skipif.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from mogged.network.kill_switch import KillSwitch, RULE_NAME


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_run(returncode: int = 0) -> MagicMock:
    mock = MagicMock()
    mock.returncode = returncode
    mock.stderr = ""
    return mock


# ---------------------------------------------------------------------------
# Comportamento em plataformas não-Windows
# ---------------------------------------------------------------------------


def test_enable_returns_true_on_non_windows() -> None:
    """enable() deve retornar True em plataformas não-Windows sem chamar subprocess."""
    with patch("sys.platform", "linux"):
        ks = KillSwitch("/fake/Discord.exe")
        with patch("subprocess.run") as mock_run:
            result = ks.enable()
    assert result is True
    mock_run.assert_not_called()


def test_disable_returns_true_on_non_windows() -> None:
    with patch("sys.platform", "linux"):
        ks = KillSwitch()
        result = ks.disable()
    assert result is True


def test_cleanup_returns_true_on_non_windows() -> None:
    with patch("sys.platform", "linux"):
        result = KillSwitch.cleanup()
    assert result is True


# ---------------------------------------------------------------------------
# enable() — validação de caminho do executável
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="Só relevante no Windows")
def test_enable_returns_false_when_no_discord_path() -> None:
    """enable() sem caminho do Discord deve retornar False imediatamente."""
    ks = KillSwitch()
    result = ks.enable()
    assert result is False


@pytest.mark.skipif(sys.platform != "win32", reason="Só relevante no Windows")
def test_enable_returns_false_when_path_does_not_exist(tmp_path: "Path") -> None:
    """enable() com caminho inexistente deve retornar False."""
    nonexistent = str(tmp_path / "Discord.exe")
    ks = KillSwitch(nonexistent)
    result = ks.enable()
    assert result is False


# ---------------------------------------------------------------------------
# enable() — simulação de netsh com mock
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="netsh é específico do Windows")
def test_enable_calls_netsh_with_correct_args(tmp_path: "Path") -> None:
    """Verificar que netsh é chamado com os parâmetros corretos."""
    # Criar exe fictício para passar a verificação os.path.isfile
    fake_exe = tmp_path / "Discord.exe"
    fake_exe.write_bytes(b"MZ")  # magic bytes de PE

    with patch("subprocess.run", return_value=_make_mock_run(0)) as mock_run:
        ks = KillSwitch(str(fake_exe))
        result = ks.enable()

    assert result is True

    # Verificar parâmetros chamados (pode ter sido chamado 2x: cleanup + add)
    all_calls = mock_run.call_args_list
    add_call = next(
        (c for c in all_calls if "add" in c.args[0]),
        None,
    )
    assert add_call is not None
    cmd = add_call.args[0]
    assert "netsh" in cmd
    assert f"name={RULE_NAME}" in cmd
    assert "action=block" in cmd
    assert "dir=out" in cmd
    # Nunca deve usar shell=True
    assert add_call.kwargs.get("shell") is not True


@pytest.mark.skipif(sys.platform != "win32", reason="netsh é específico do Windows")
def test_enable_returns_false_on_netsh_failure(tmp_path: "Path") -> None:
    """Se netsh retornar código != 0, enable() deve retornar False."""
    fake_exe = tmp_path / "Discord.exe"
    fake_exe.write_bytes(b"MZ")

    with patch("subprocess.run", return_value=_make_mock_run(1)):
        ks = KillSwitch(str(fake_exe))
        result = ks.enable()

    assert result is False


@pytest.mark.skipif(sys.platform != "win32", reason="netsh é específico do Windows")
def test_enable_sets_is_active_flag_on_success(tmp_path: "Path") -> None:
    fake_exe = tmp_path / "Discord.exe"
    fake_exe.write_bytes(b"MZ")

    with patch("subprocess.run", return_value=_make_mock_run(0)):
        ks = KillSwitch(str(fake_exe))
        ks.enable()

    assert ks._is_active is True


# ---------------------------------------------------------------------------
# disable() / cleanup()
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="netsh é específico do Windows")
def test_disable_clears_is_active_flag() -> None:
    with patch("subprocess.run", return_value=_make_mock_run(0)):
        ks = KillSwitch()
        ks._is_active = True
        ks.disable()
    assert ks._is_active is False


@pytest.mark.skipif(sys.platform != "win32", reason="netsh é específico do Windows")
def test_cleanup_calls_netsh_delete() -> None:
    with patch("subprocess.run", return_value=_make_mock_run(0)) as mock_run:
        KillSwitch.cleanup()

    any_delete = any(
        "delete" in c.args[0] for c in mock_run.call_args_list
    )
    assert any_delete


@pytest.mark.skipif(sys.platform != "win32", reason="netsh é específico do Windows")
def test_cleanup_returns_true_on_exception() -> None:
    """cleanup() deve retornar False (não propagar) quando subprocess lança exceção."""
    with patch("subprocess.run", side_effect=OSError("permissão negada")):
        result = KillSwitch.cleanup()
    assert result is False


# ---------------------------------------------------------------------------
# Segurança: nenhum comando usa shell=True
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="Verificação de shell=True no Windows")
def test_no_shell_true_in_any_subprocess_call(tmp_path: "Path") -> None:
    fake_exe = tmp_path / "Discord.exe"
    fake_exe.write_bytes(b"MZ")

    with patch("subprocess.run", return_value=_make_mock_run(0)) as mock_run:
        ks = KillSwitch(str(fake_exe))
        ks.enable()
        ks.disable()

    for call in mock_run.call_args_list:
        assert call.kwargs.get("shell") is not True
