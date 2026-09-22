"""Testes headless e de renderização de componentes de interface do usuário."""

from unittest.mock import MagicMock, patch
from PIL import Image
import pytest

from mogged.ui.main_window import (
    create_dropdown_bar_image,
    create_eye_button_image,
    create_glossy_button_image,
    create_reload_button_image,
)
from mogged.ui.tray import TrayManager


def test_create_glossy_button_images():
    btn_normal = create_glossy_button_image(120, 40, "Conectar", is_active=False)
    assert isinstance(btn_normal, Image.Image)
    assert btn_normal.size == (120, 40)

    btn_connected = create_glossy_button_image(120, 40, "Desconectar", is_connected=True)
    assert isinstance(btn_connected, Image.Image)

    btn_connecting = create_glossy_button_image(120, 40, "Conectando...", is_connecting=True)
    assert isinstance(btn_connecting, Image.Image)


def test_create_eye_and_reload_icons():
    eye_img = create_eye_button_image(width=56, height=36, slashed=True)
    assert isinstance(eye_img, Image.Image)
    assert eye_img.size == (56, 36)

    reload_img = create_reload_button_image(width=42, height=38)
    assert isinstance(reload_img, Image.Image)
    assert reload_img.size == (42, 38)


def test_create_dropdown_image():
    dd_img = create_dropdown_bar_image(200, 38, "Brasil (1 serv.)")
    assert isinstance(dd_img, Image.Image)
    assert dd_img.size == (200, 38)


def test_tray_manager_lifecycle():
    mock_app = MagicMock()
    mock_app.root = MagicMock()

    with patch("pystray.Icon") as mock_icon_cls:
        fake_icon = MagicMock()
        mock_icon_cls.return_value = fake_icon

        tray = TrayManager(mock_app)
        tray.start()
        fake_icon.run_detached.assert_called_once()

        tray.update_status("connected", "OK")
        assert "Connected" in fake_icon.title

        tray.stop()
        fake_icon.stop.assert_called_once()
